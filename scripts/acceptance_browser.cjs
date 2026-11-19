// Actual system-browser acceptance. Config and artifacts stay in the isolated run directory.
const assert=require('node:assert/strict'),fs=require('node:fs');
const {click,write,requestMeta,waitForApiIdle}=require('./acceptance_browser_support.cjs');
const config=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const evidence={steps:[],pageErrors:[],requests:[],platform:process.platform,current_step:'load browser tooling',success:false};
let browser,page,activePage;
const states=new WeakMap();
function save(){fs.writeFileSync(config.output,JSON.stringify(evidence,null,2)+'\n');}
function stage(name,p){if(p)activePage=p;evidence.current_step=name;save();console.log('[CHECK] '+name);}
function observe(p){
 const state={pending:new Set(),lastEvent:Date.now()};states.set(p,state);
 const local=req=>req.url().startsWith(config.url+'api/v1/');
 const keep=item=>{evidence.requests.push(item);if(evidence.requests.length>40)evidence.requests.shift();};
 p.on('pageerror',error=>evidence.pageErrors.push(error.message));
 p.on('request',req=>{if(local(req)){state.pending.add(req);state.lastEvent=Date.now();keep({...requestMeta(req),event:'sent'});}});
 p.on('response',response=>{if(local(response.request()))keep({...requestMeta(response.request()),event:'response',status:response.status()});});
 for(const name of ['requestfinished','requestfailed'])p.on(name,req=>{
  if(local(req)){state.pending.delete(req);state.lastEvent=Date.now();
   if(name==='requestfailed')keep({...requestMeta(req),event:'failed',error:req.failure()?.errorText});}
 });
 return p;
}
async function ready(p){await waitForApiIdle(states.get(p));}
async function login(p,account){
 stage('login '+account,p);
 await p.goto(config.url,{waitUntil:'domcontentloaded'});await ready(p);
 await p.getByLabel('选择虚构身份').selectOption(account);await write(p,'管理自己的用药','/auth/demo-session');
 await p.getByRole('button',{name:'退出',exact:true}).waitFor();await ready(p);
}
(async()=>{
 save();const {chromium}=require(require.resolve('playwright',{paths:[config.browser_package]}));
 stage('launch system browser');browser=await chromium.launch({executablePath:config.browser_executable,headless:true});
 const context=await browser.newContext({viewport:{width:1365,height:960},locale:'zh-CN'});
 page=observe(await context.newPage());await login(page,'demo-patient-a');
 for(const width of [1365,390]){
  await page.setViewportSize({width,height:960});
  for(const name of ['首页','用药管理','支持服务','积分权益','我的']){
   stage(`navigation ${width} ${name}`,page);
   await page.getByRole('navigation',{name:'主要导航',exact:true}).getByRole('button',{name,exact:true}).click({timeout:15000});await ready(page);
   assert.equal(await page.getByRole('navigation',{name:'主要导航',exact:true}).getByRole('button',{name,exact:true}).getAttribute('aria-current'),'page');
   assert(await page.locator('main').innerText());
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Page overflow: ${width} ${name}`);
   evidence.steps.push({page:name,width,status:'passed'});save();
  }
 }
 stage('open support view',page);await click(page,'支持服务');await ready(page);
 stage('create free dialogue session through visible UI',page);
 const session=await write(page,'开始自由对话','/sessions');await ready(page);
 await page.locator('textarea[data-support-session="'+session.session_id+'"]').waitFor();
 stage('single_pass actual generation',page);await page.getByLabel('你想说的话').fill('虚构验收：一步就好，给个办法。');
 const single=await write(page,'发送','/messages');await ready(page);
 assert.equal(single.generation.actual_pipeline,'single_pass');assert.equal(single.generation.calls.length,1);
 assert(await page.locator('.support-message.assistant').count());
 evidence.steps.push({name:'single_pass actual generation',status:'passed'});save();
 const adminContext=await browser.newContext({viewport:{width:1365,height:960},locale:'zh-CN'}),admin=observe(await adminContext.newPage());
 await login(admin,'demo-admin');stage('select STAR through admin UI',admin);await click(admin,'我的');await ready(admin);
 await write(admin,'选择 mock STAR','/config/model-profile','PUT');await ready(admin);
 const configStatus=(await (await admin.request.get(config.url+'api/v1/config/status')).json()).data;
 assert.equal(configStatus.capabilities.find(item=>item.code==='dialogue').reason,'本地 mock star');
 const probe=await write(admin,'显式检查模拟模型','/config/check-model');assert.equal(probe.network_attempt_count,0);
 stage('STAR actual generation',page);await page.getByLabel('你想说的话').fill('虚构STAR验收：我担心副作用，只想倾诉。');
 const star=await write(page,'发送','/messages');await ready(page);
 assert.equal(star.generation.actual_pipeline,'star');assert.equal(star.generation.calls.length,6);
 evidence.steps.push({name:'STAR generation, authoritative configuration and zero network probe',status:'passed'});
 assert.deepEqual(evidence.pageErrors,[]);evidence.success=true;evidence.browserVersion=browser.version();stage('complete');
})().catch(async error=>{
 evidence.success=false;evidence.error=error.message;evidence.error_stack=error.stack;process.exitCode=1;console.error(error);
 if(activePage){
  evidence.page_notice=await activePage.locator('#notice').innerText().catch(()=> '');
  evidence.main_text=await activePage.locator('main').innerText().catch(()=> '');
  evidence.buttons=await activePage.locator('button').evaluateAll(nodes=>nodes.map(n=>({text:n.textContent,disabled:n.disabled,connected:n.isConnected}))).catch(()=> []);
  await activePage.screenshot({path:config.output.replace(/\.json$/,'.png'),fullPage:true}).catch(()=>{});
 }
}).finally(async()=>{save();if(browser)await browser.close();});
