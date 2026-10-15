
import fs from 'node:fs/promises';
const base='http://127.0.0.1:18992';
const target=await (await fetch(base+'/json/new?about:blank',{method:'PUT'})).json();
const ws=new WebSocket(target.webSocketDebuggerUrl);
await new Promise(resolve=>ws.addEventListener('open',resolve,{once:true}));
let counter=0;const pending=new Map();let errors=[];const requests=[];
ws.addEventListener('message',e=>{const p=JSON.parse(e.data);if(p.id){const waiter=pending.get(p.id);pending.delete(p.id);p.error?waiter.reject(p.error):waiter.resolve(p.result);}else if(p.method==='Network.requestWillBeSent'&&p.params.request.url.includes('/api/'))requests.push({method:p.params.request.method,url:p.params.request.url});else if(p.method==='Runtime.exceptionThrown')errors.push(p.params.exceptionDetails.text);});
const cdp=(method,params={})=>new Promise((resolve,reject)=>{const id=++counter;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
const evaluate=async expression=>(await cdp('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result.value;
await cdp('Page.enable');await cdp('Runtime.enable');await cdp('Network.enable');
const results=[];
for(const width of [1440,390]){
  await cdp('Emulation.setDeviceMetricsOverride',{width,height:width===390?844:1000,deviceScaleFactor:1,mobile:width===390});
  for(const scenario of ['inactive','stale','current','sandbox']){
    const mode=scenario==='sandbox'?'sandbox':'live';
    await cdp('Page.navigate',{url:`http://127.0.0.1:18991/?mode=${mode}&scenario=${scenario}`});
    await new Promise(r=>setTimeout(r,1800));
    for(const page of ['Dashboard','Strategy','Settings']){
      if(page!=='Dashboard'){
        await evaluate(`[...document.querySelectorAll('nav button')].find(el=>el.textContent.trim().endsWith('${page}')).click()`);
        await new Promise(r=>setTimeout(r,600));
      }
      const result=await evaluate(`({text:document.querySelector('.app-content').innerText,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,selected:document.querySelector('[aria-label="Execution view"]').value,buttons:[...document.querySelectorAll('button')].filter(el=>/Activate Live|Pause|Resume|Flatten|Save protection|Reset baseline/.test(el.textContent)).map(el=>({text:el.textContent,disabled:el.disabled})),overflow:[...document.querySelectorAll('body *')].filter(el=>el.getBoundingClientRect().right>innerWidth+2 && getComputedStyle(el).position!=='fixed').slice(0,10).map(el=>({tag:el.tagName,cls:el.className,right:el.getBoundingClientRect().right}))})`);
      result.scenario=scenario;result.page=page;result.viewport=width;result.exceptions=[...errors];
      if(result.scrollWidth>width+2)throw new Error('Horizontal overflow: '+JSON.stringify(result.overflow));
      if(result.selected!==mode)throw new Error('Wrong selected view');
      if((scenario==='inactive'||scenario==='stale')&&page==='Dashboard'&&!result.text.includes('Live is inactive or unavailable'))throw new Error('Missing Live inactive state');
      if(scenario==='inactive'&&page==='Dashboard'&&result.text.includes('10,000'))throw new Error('Sandbox cash leaked into Live');
      if(scenario==='inactive'&&page==='Strategy'&&(!result.text.includes('82 USDC')||!result.text.includes('V3+DP50')))throw new Error('Missing planned profile');
      if(scenario==='current'&&page==='Dashboard'&&!result.text.includes('82.3'))throw new Error('Native fixture cash not rendered');
      const metrics=await cdp('Page.getLayoutMetrics');
      const screenshot=await cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width,height:metrics.cssContentSize.height,scale:1}});
      await fs.writeFile(`reports/live82-gui/${scenario}-${page.toLowerCase()}-${width}.png`,Buffer.from(screenshot.data,'base64'));
      results.push(result);
    }
  }
}
await cdp('Page.navigate',{url:'http://127.0.0.1:18991/?mode=sandbox&scenario=inactive'});
await new Promise(r=>setTimeout(r,1000));
const before=requests.length;
await evaluate(`(()=>{const el=document.querySelector('[aria-label="Execution view"]');el.value='live';el.dispatchEvent(new Event('change',{bubbles:true}));})()`);
await new Promise(r=>setTimeout(r,1500));
const switched=await evaluate(`({mode:document.querySelector('[aria-label="Execution view"]').value,url:location.href,text:document.querySelector('.app-content').innerText})`);
if(switched.mode!=='live'||!switched.text.includes('Live is inactive'))throw new Error('View selection did not reload Live');
const switchedRequests=requests.slice(before);
if(requests.some(r=>r.method!=='GET'))throw new Error('View or navigation sent a mutation');
if(switchedRequests.some(r=>r.url.includes('/instances/hl-stageg-testnet')))throw new Error('Sandbox request after Live selection');
if(!switchedRequests.some(r=>r.url.endsWith('/instances/hl-stageg-live')))throw new Error('Missing selected Live request');
await fs.writeFile('reports/live82-gui/render-results.json',JSON.stringify({fixturePreview:true,results,selection:{switched,requests:switchedRequests},allRequests:requests},null,2));
console.log(JSON.stringify({states:results.length,exceptions:errors,screenshots:results.length}));
await cdp('Page.close');ws.close();
