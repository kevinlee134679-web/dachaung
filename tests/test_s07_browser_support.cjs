const assert=require('node:assert/strict');
const {test}=require('node:test');
const {write,requestMeta,waitForApiIdle}=require('../scripts/acceptance_browser_support.cjs');
const response=(status=201)=>({status:()=>status,json:async()=>({data:{session_id:'fictional'},error:{code:'FORBIDDEN'}})});
const page=(wait,action)=>({waitForResponse:wait,getByRole:()=>({click:action})});

test('response rejection is handled while click is still pending',async()=>{
 let unhandled=false;const listener=()=>{unhandled=true;};process.on('unhandledRejection',listener);
 try{
  await assert.rejects(write(page(()=>new Promise((_,reject)=>setTimeout(()=>reject(new Error('response timeout')),5)),
   ()=>new Promise(resolve=>setTimeout(resolve,25))),'start','/sessions'),/response timeout/);
  await new Promise(resolve=>setTimeout(resolve,35));assert.equal(unhandled,false);
 }finally{process.removeListener('unhandledRejection',listener);}
});
test('a click failure is retained instead of waiting for a response that was never sent',async()=>{
 await assert.rejects(write(page(()=>new Promise(()=>{}),async()=>{throw new Error('button covered');}),'start','/sessions'),/button covered/);
});
test('a backend rejection cannot become a successful UI write',async()=>{
 await assert.rejects(write(page(async()=>response(403),async()=>{}),'start','/sessions'),/HTTP 403 FORBIDDEN/);
});
test('request diagnostics exclude queries, bodies and headers',()=>{
 const req={method:()=> 'POST',url:()=> 'http://127.0.0.1:9000/api/v1/sessions?token=never-log',
  headers:()=>{throw new Error('must not read credentials');},postData:()=>{throw new Error('must not read body');}};
 assert.deepEqual(requestMeta(req),{method:'POST',path:'/api/v1/sessions'});
});
test('local API readiness waits for the next chained request to finish',async(t)=>{
 t.mock.timers.enable({apis:['Date','setTimeout'],now:1000});
 const state={pending:new Set([1]),lastEvent:Date.now()};let settled=false;
 setTimeout(()=>{state.pending.delete(1);state.lastEvent=Date.now();},5);
 setTimeout(()=>{state.pending.add(2);state.lastEvent=Date.now();},10);
 setTimeout(()=>{state.pending.delete(2);state.lastEvent=Date.now();},25);
 const waiting=waitForApiIdle(state,{quiet:15,poll:2,timeout:500}).then(()=>{settled=true;});
 for(let elapsed=1;elapsed<=45;elapsed++){
  t.mock.timers.tick(1);await Promise.resolve();await Promise.resolve();
  if(elapsed<40)assert.equal(settled,false,'must await chained request and its quiet period');
 }
 assert.equal(settled,true);await waiting;
});
