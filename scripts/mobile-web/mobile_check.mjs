import { chromium } from 'playwright';
import fs from 'node:fs/promises';
const browser=await chromium.launch({channel:'msedge',headless:true});
const results=[];
for(const width of [320,360,390,430,768,1280]){
  const page=await browser.newPage({viewport:{width,height:844},isMobile:width<768,hasTouch:width<768});
  for(const route of ['login','register']){
    await page.goto('http://127.0.0.1:3019/'+route);await page.locator('.auth-card').waitFor();
    const check=await page.evaluate(()=>({viewport:innerWidth,scroll:document.documentElement.scrollWidth,card:document.querySelector('.auth-card').getBoundingClientRect().toJSON(),inputSize:getComputedStyle(document.querySelector('input')).fontSize}));
    results.push({width,route,...check,pass:check.scroll<=width+1&&check.card.width<=width&&parseFloat(check.inputSize)>=16});
    if(width===390)await page.screenshot({path:`mobile-${route}.png`,fullPage:true});
  }
  await page.close();
}
await browser.close();await fs.writeFile('mobile-check.json',JSON.stringify(results,null,2));
console.log(JSON.stringify(results));if(results.some(r=>!r.pass))process.exitCode=1;
