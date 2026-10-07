import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import ejs from 'ejs';
import {JSDOM} from 'jsdom';
import puppeteer from 'puppeteer-core';

const root = path.dirname(fileURLToPath(import.meta.url));
const upstream = path.join(root, 'vendor/metrics');
const output = path.resolve(process.env.METRICS_OUTPUT_DIR || root);
await fs.mkdir(output, {recursive:true});
const login = process.env.PROFILE_USERNAME || 'siruimei07';
if(!/^[a-z\d](?:[a-z\d-]{0,38})$/i.test(login)) throw new Error('Invalid GitHub username');
const revision = '366f8b9dfe3a59656c67d5dcad9950f59c9bc96d';
const provenance=JSON.parse(await fs.readFile(path.join(root,'vendor/provenance.json'),'utf8'));
if(provenance.metricsRevision!==revision) throw new Error('Unexpected upstream revision');
for(const [relative,expected] of Object.entries(provenance.sha256)) {
  const actual=createHash('sha256').update(await fs.readFile(path.join(root,'vendor',relative))).digest('hex');
  if(actual!==expected) throw new Error(`Vendored file hash mismatch: ${relative}`);
}

// Only public source endpoints are used. A repository-scoped Actions token is optional
// for API rate limits; calendar pages are always fetched anonymously. No PAT is needed.
async function publicFetch(url,kind='json') {
  const parsed=new URL(url);
  const headers={'User-Agent':'public-github-profile-metrics','Accept-Language':'en-US'};
  const publicApi=parsed.hostname==='api.github.com'&&(
    parsed.pathname===`/users/${login}/repos`||parsed.pathname.startsWith(`/repos/${login}/`)&&parsed.pathname.endsWith('/languages')
  );
  if(publicApi&&(process.env.GITHUB_TOKEN||process.env.GH_TOKEN)) headers.Authorization=`Bearer ${process.env.GITHUB_TOKEN||process.env.GH_TOKEN}`;
  for(let attempt=0;attempt<3;attempt++) {
    const response=await fetch(url,{headers,signal:AbortSignal.timeout(30000)});
    if(response.ok) return kind==='json'?response.json():response.text();
    if((response.status===429||response.status>=500)&&attempt<2) {
      await new Promise(resolve=>setTimeout(resolve,1000*2**attempt));
      continue;
    }
    throw new Error(`Public source ${new URL(url).pathname} returned HTTP ${response.status}; existing charts will be kept.`);
  }
}
const publicRepos=[];
for(let page=1;page<=20;page++) {
  const batch=await publicFetch(`https://api.github.com/users/${login}/repos?type=owner&sort=updated&per_page=100&page=${page}`);
  if(!Array.isArray(batch)) throw new Error('Invalid public repository response');
  publicRepos.push(...batch);
  if(batch.length<100) break;
  if(page===20) throw new Error('Public repository pagination limit exceeded');
}
if(publicRepos.some(r=>r.private)) throw new Error('Unexpected non-public repository');
const colors=JSON.parse(await fs.readFile(path.join(root,'vendor/language-colors.json'),'utf8'));
const repositories=[];
for(const repo of publicRepos.filter(r=>!r.fork&&r.name.toLowerCase()!==login.toLowerCase()&&r.owner.login.toLowerCase()===login.toLowerCase())) {
  const counts=await publicFetch(`https://api.github.com/repos/${login}/${encodeURIComponent(repo.name)}/languages`);
  if(Object.values(counts).some(n=>!Number.isSafeInteger(n)||n<0)) throw new Error('Invalid language byte count');
  const edges=Object.entries(counts).sort(([,a],[,b])=>b-a).slice(0,8).map(([name,size])=>({size,node:{name,color:colors[name]||'#959da5'}}));
  repositories.push({name:repo.name,owner:{login},languages:{edges}});
}

// Fetch public calendar pages anonymously. This cannot expose authenticated private activity.
// Counts can include anonymized private contributions deliberately shown on the public profile.
const now = new Date();
const allDays = new Map();
for (const year of [now.getUTCFullYear()-1, now.getUTCFullYear()]) {
  const url = `https://github.com/users/${login}/contributions?from=${year}-01-01&to=${year}-12-31`;
  const html = await publicFetch(url,'text');
  const document = new JSDOM(html).window.document;
  const tips = new Map([...document.querySelectorAll('tool-tip[for]')].map(t=>[t.getAttribute('for'),t.textContent.trim()]));
  for(const cell of document.querySelectorAll('td[data-date]')) {
    const label = tips.get(cell.id);
    if(!label) throw new Error(`Missing public contribution count for ${cell.dataset.date}`);
    const matched = label.match(/^(No|[\d,]+) contributions? on /);
    if(!matched) throw new Error(`Unexpected calendar tooltip format`);
    const level=Number(cell.dataset.level);
    if(!Number.isInteger(level)||level<0||level>4) throw new Error('Invalid contribution level');
    allDays.set(cell.dataset.date, {date:cell.dataset.date, contributionCount:matched[1]==='No'?0:Number(matched[1].replaceAll(',','')),level});
  }
}
const levelColors = ['#ebedf0','#9be9a8','#40c463','#30a14e','#216e39'];
const calendarGraphql = async ({from,to}) => {
  const start = from.slice(0,10), end = to.slice(0,10);
  const contributionDays=[];
  for(let d=new Date(`${start}T00:00:00Z`);d.toISOString().slice(0,10)<=end;d.setUTCDate(d.getUTCDate()+1)) {
    const date=d.toISOString().slice(0,10), entry=allDays.get(date);
    if(!entry) throw new Error(`Missing calendar day ${date}`);
    contributionDays.push({...entry,color:levelColors[entry.level]});
  }
  const weeks=[];
  for(let i=0;i<contributionDays.length;i+=7) weeks.push({contributionDays:contributionDays.slice(i,i+7)});
  return {user:{calendar:{contributionCalendar:{weeks}}}};
};
const isocalendar=(await import(pathToFileURL(path.join(upstream,'source/plugins/isocalendar/index.mjs')))).default;
const iso=await isocalendar({login,data:{},graphql:calendarGraphql,q:{isocalendar:true},queries:{isocalendar:{calendar:x=>x}},account:'user',imports:{metadata:{plugins:{isocalendar:{enabled:()=>true,inputs:()=>({duration:'full-year'})}}},format:{error:e=>e}}},{enabled:true});

// Keep the official most-used-language computation unchanged; remove only imports of
// unused indepth/recent analyzers, which otherwise load native image libraries on Windows.
const languageSource=await fs.readFile(path.join(upstream,'source/plugins/languages/index.mjs'),'utf8');
const importLine='import { indepth as indepth_analyzer, recent as recent_analyzer } from "./analyzers.mjs"';
if(!languageSource.includes(importLine)) throw new Error('Upstream language import changed');
const localLanguageSource=languageSource.replace(importLine,'const indepth_analyzer = () => { throw new Error("Indepth mode disabled") }; const recent_analyzer = () => { throw new Error("Recent mode disabled") };');
const languages=(await import(`data:text/javascript;base64,${Buffer.from(localLanguageSource).toString('base64')}`)).default;
const languageInputs={ignored:[],skipped:[],other:true,colors:'github',aliases:'',details:['percentage'],threshold:'0%',limit:6,indepth:false,sections:['most-used'],categories:['programming','markup']};
const lang=await languages({login,data:{shared:{'repositories.skipped':[]},user:{repositories:{nodes:repositories},repositoriesContributedTo:{nodes:[]}}},account:'user',q:{languages:true},imports:{metadata:{plugins:{languages:{enabled:()=>true,inputs:()=>({...languageInputs,skipped:[]}),extras:()=>false}}},fs,__module:()=>path.join(upstream,'source/plugins/languages'),filters:{repo:()=>true,text:()=>true},format:{error:e=>e}}},{enabled:true});

const css=await fs.readFile(path.join(upstream,'source/templates/classic/style.css'),'utf8');
const image=await fs.readFile(path.join(upstream,'source/templates/classic/image.svg'),'utf8');
const f=n=>new Intl.NumberFormat('en-US',{maximumFractionDigits:2}).format(n);
f.percentage=n=>`${(n*100).toFixed(1)}%`;
f.bytes=n=>`${f(n)} B`;
const browserCandidates=[process.env.PUPPETEER_EXECUTABLE_PATH,process.env.PUPPETEER_BROWSER_PATH,'C:/Program Files/Google/Chrome/Application/chrome.exe','C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','/usr/bin/google-chrome','/usr/bin/google-chrome-stable','/usr/bin/chromium','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].filter(Boolean);
let executablePath;
for(const candidate of browserCandidates) {
  if(await fs.access(candidate).then(()=>true,()=>false)) {executablePath=candidate;break;}
}
if(!executablePath) throw new Error('Chrome was not found. Set PUPPETEER_EXECUTABLE_PATH.');
const browser=await puppeteer.launch({executablePath,headless:true,args:['--no-sandbox','--disable-extensions']});
const generated=[];
try {
 for(const mode of ['light','dark']) {
  const color=mode==='dark'?'#b1bac4':'#59636e', accent=mode==='dark'?'#58a6ff':'#0969da';
  const extrasCss=`svg { color: ${color}; } h1, h2, h3 { color: ${accent}; } .field svg { fill: ${color}; } .field.language.details small { color: ${color}; }`;
  for(const [name,data] of [['isocalendar',iso],['languages',lang]]) {
    const themedData=name==='isocalendar'&&mode==='dark'?{...data,svg:data.svg.replaceAll('#ebedf0','#161b22').replaceAll('#9be9a8','#0e4429').replaceAll('#40c463','#006d32').replaceAll('#30a14e','#26a641').replaceAll('#216e39','#39d353')}:data;
    const context={large:false,columns:false,animated:false,fonts:'',style:css,extras:{css:extrasCss},warnings:[],partials:[name],base:{metadata:false},plugins:{[name]:themedData},s:n=>n===1?'':'s',f};
    const markup=(await ejs.render(image,context,{async:true,filename:path.join(upstream,'source/templates/classic/image.svg')})).replaceAll('Commits streaks','Contribution streaks').replaceAll('Commits per day','Contributions per day');
    const page=await browser.newPage();
    await page.setViewport({width:500,height:800,deviceScaleFactor:2});
    // Generated markup is local; stop all external resource requests while rendering.
    await page.setRequestInterception(true);
    page.on('request',request=>request.abort());
    await page.setContent(markup,{waitUntil:'load'});
    await page.addStyleTag({content:`body{margin:0;padding:0;background:${mode==='dark'?'#0d1117':'#ffffff'}}`});
    const svg=await page.evaluate(()=>{
      const node=document.querySelector('svg');
      const height=Math.ceil(document.querySelector('#metrics-end').getBoundingClientRect().y)+4;
      node.setAttribute('height',height);
      node.setAttribute('role','img');
      node.setAttribute('aria-label',document.querySelector('h2')?.textContent.trim()||'GitHub metrics');
      return node.outerHTML;
    });
    const notice=`<!-- Generated from lowlighter/metrics @ ${revision}, MIT license. Data: public GitHub pages/API only; calendar fetched anonymously. -->\n`;
    const out=path.join(output,`${name}-${mode}.svg`);
    generated.push({out,content:notice+svg});
    const h=await page.$eval('svg',node=>Number(node.getAttribute('height')));
    await page.setViewport({width:480,height:h,deviceScaleFactor:2});
    if(process.env.METRICS_SCREENSHOTS==='1') await page.screenshot({path:path.join(output,`${name}-${mode}.png`),omitBackground:false});
    await page.close();
    console.log(JSON.stringify({file:out,width:480,height:h}));
  }
 }
} finally {await browser.close();}
// Do not overwrite any existing SVG until all source data and all four renders succeed.
for(const {out,content} of generated) await fs.writeFile(out,content,'utf8');
await fs.writeFile(path.join(output,'public-data-summary.json'),JSON.stringify({sourceRevision:revision,generatedAt:now.toISOString(),repositories:repositories.map(r=>r.name),calendar:{source:'anonymous public GitHub contribution pages',daysFetched:allDays.size,bestStreak:iso.streak.max,maxPerDay:iso.max,averagePerDay:iso.average},languages:lang.favorites.map(({name,value,size})=>({name,percentage:value*100,bytes:size}))},null,2));
