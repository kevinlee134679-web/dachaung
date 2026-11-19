// Deterministic UI writes and local-API readiness, without collecting credentials.
const assert=require('node:assert/strict');

function requestMeta(request){
 return {method:request.method(),path:new URL(request.url()).pathname};
}

async function click(page,name){
 await page.getByRole('button',{name,exact:true}).click({timeout:15000});
}

async function write(page,name,fragment,method='POST'){
 // Attach both handlers immediately. Awaiting click/networkidle first left the
 // response rejection unhandled and killed Node before diagnostics could save.
 const [response]=await Promise.all([
  page.waitForResponse(r=>r.request().method()===method&&new URL(r.url()).pathname.includes(fragment),{timeout:45000}),
  click(page,name)
 ]);
 const body=await response.json();
 assert(response.status()<300,`${name}: HTTP ${response.status()} ${body.error?.code||''}`);
 return body.data;
}

async function waitForApiIdle(state,{timeout=20000,quiet=150,poll=25}={}){
 const deadline=Date.now()+timeout;
 while(state.pending.size || Date.now()-state.lastEvent<quiet){
  if(Date.now()>=deadline)throw new Error('Local application API requests did not settle');
  await new Promise(resolve=>setTimeout(resolve,poll));
 }
}

module.exports={click,write,requestMeta,waitForApiIdle};
