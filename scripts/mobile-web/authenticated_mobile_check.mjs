import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const browser=await chromium.launch({channel:'msedge',headless:true});
const results=[]; const errors=[];
const paths=['dashboard','resume/upload','resume-polish','ability-diagnosis','knowledge-base','learning-tasks','training-review','profile','feedback','interview/1','interview/1/report'];
const profile={id:17,email:'mobile-test@example.test',first_name:'测试',last_name:'同学',privacy_agreed:true,base_privacy_consent:true,ai_provider:'deepseek',ai_model:'deepseek-v4-pro'};
for(const width of [320,360,390,430,768,1280]){
  const page=await browser.newPage({viewport:{width,height:844},isMobile:width<768,hasTouch:width<768});
  page.on('pageerror',e=>errors.push({width,url:page.url(),message:e.message}));
  await page.addInitScript(()=>{localStorage.setItem('token','isolated-layout-fixture');localStorage.setItem('userId','17')});
  let feedback=[];let failNext=false;
  await page.route('**/api/v1/**',async route=>{
    const url=new URL(route.request().url()); const p=url.pathname;
    let data={items:[],has_more:false};
    if(p.endsWith('/auth/me'))data=profile;
    else if(p==='/api/v1/interviews')data={items:[{interview_id:1,target_position:'人力资源专员与招聘培训方向测试岗位',difficulty:'easy',total_questions:5,status:'in_progress',created_at:'2026-10-19T09:00:00+08:00'}]};
    else if(p.endsWith('/messages'))data={items:[{role:'interviewer',content:'请结合课程实践说明如何筛选候选人简历。',question_index:0}],status:'in_progress',total_questions:5,current_question_index:0,difficulty:'easy',interview_mode:'single'};
    else if(p.endsWith('/report'))data={target_position:'人力资源专员',difficulty:'easy',overall_score:75,report:{overall_score:75,summary:'布局验证示例报告',strengths:['表达清晰'],weaknesses:['需要补充具体经历'],suggestions:['整理课程实践中的证据'],question_details:[]}};
    else if(p==='/api/v1/feedback'){
      if(route.request().method()==='POST'){
        if(failNext){failNext=false;return route.fulfill({status:500,json:{code:500,message:'测试网络错误'}})}
        data={...route.request().postDataJSON(),id:feedback.length+1,status:'pending',created_at:'2026-10-19T09:00:00+08:00'};feedback.unshift(data);
      }else data={items:feedback,has_more:false};
    }
    await route.fulfill({json:{code:200,data}});
  });
  for(const route of paths){
    await page.goto('http://127.0.0.1:3019/'+route);
    await page.locator('#page-content > *').waitFor();
    if(route==='interview/1')await page.locator('.input-area textarea').waitFor();
    await page.evaluate(()=>document.fonts.ready);
    const measure=await page.evaluate(()=>({viewport:innerWidth,scroll:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('#page-content *')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.right>innerWidth+1}).slice(0,6).map(e=>({tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width}))}));
    results.push({width,route,...measure,pass:measure.scroll<=width+1});
    if(width===390&&['dashboard','feedback','interview/1','interview/1/report'].includes(route))await page.screenshot({path:'actual-'+route.replaceAll('/','-')+'.png',fullPage:true});
    if(width===390&&route==='interview/1'){
      await page.setViewportSize({width:390,height:460});
      const box=await page.locator('.input-area textarea').boundingBox();assert(box&&box.y>=0&&box.y+box.height<=460,'Input remains reachable in reduced viewport');
      const send=await page.locator('.input-area button').last().boundingBox();assert(send&&send.y>=0&&send.y+send.height<=460,'Send remains reachable in reduced viewport');
      await page.setViewportSize({width:390,height:844});
      await page.getByRole('button',{name:'查看训练重点'}).click();
      assert(await page.locator('#interview-focus-details').isVisible());
    }
  }
  if(width===390){
    await page.goto('http://127.0.0.1:3019/feedback');
    await page.getByRole('button',{name:'更多功能',exact:true}).click();
    assert(await page.locator('#primary-links').isVisible());
    await page.locator('#primary-links a').first().focus();await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('button',{name:'更多功能',exact:true}).getAttribute('aria-expanded'),'false');
    await page.getByLabel('标题',{exact:true}).fill('手机反馈测试');await page.getByLabel('详细说明',{exact:true}).fill('浏览器布局测试内容');
    failNext=true;await page.getByRole('button',{name:'提交留言',exact:true}).click();
    await page.getByRole('alert').filter({hasText:'测试网络错误'}).waitFor();
    assert.equal(await page.getByLabel('详细说明',{exact:true}).inputValue(),'浏览器布局测试内容');
    await page.getByRole('button',{name:'提交留言',exact:true}).click();
    await page.getByRole('status').filter({hasText:'留言已提交'}).waitFor();
    assert.equal(await page.locator('.feedback-item').count(),1);
    await page.reload();await page.locator('.feedback-item').waitFor();
    assert.equal(await page.locator('.feedback-item').count(),1);
  }
  await page.close();
}
await browser.close();
await fs.writeFile('authenticated-mobile-results.json',JSON.stringify({mode:'isolated API fixtures; backend persistence is tested separately',results,errors},null,2));
console.log(JSON.stringify({checks:results.length,failures:results.filter(x=>!x.pass),errors}));
if(results.some(x=>!x.pass)||errors.length)process.exitCode=1;
