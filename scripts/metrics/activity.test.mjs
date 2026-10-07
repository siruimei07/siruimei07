import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import ejs from 'ejs';
import {loadActivity,activityTemplate} from './activity.mjs';
const upstream=fileURLToPath(new URL('./vendor/metrics',import.meta.url));
const now=new Date('2026-10-07T12:00:00Z');
const event=(type,payload,extra={})=>({type,payload,actor:{login:'tester'},repo:{name:'tester/demo'},created_at:'2026-10-07T10:00:00Z',public:true,...extra});
const requested=[];
const fixtures=[
 event('PullRequestEvent',{action:'opened',number:42,pull_request:{number:42}}),
 event('PushEvent',{ref:'refs/heads/main'}),
 event('IssueCommentEvent',{action:'created',issue:{number:1,title:'Issue',user:{login:'friend'}},comment:{body:'<img src=x onerror=alert(1)> & content'}}),
 event('PublicEvent',{}, {public:false,repo:{name:'tester/secret'}}),
 event('PublicEvent',{}, {repo:{name:'tester/former-public'}}),
 event('PublicEvent',{}, {created_at:'2026-08-01T10:00:00Z'}),
 event('PullRequestEvent',{action:'opened',pull_request:{}}),
];
const publicFetch=async url=>{
 requested.push(url);
 if(url.includes('/events/public'))return fixtures;
 if(url.endsWith('/former-public'))return {private:true,full_name:'tester/former-public'};
 if(url.endsWith('/demo'))return {private:false,full_name:'tester/demo'};
 if(url.endsWith('/pulls/42'))return {number:42,title:'<svg onload=alert(1)> Test',user:{login:'tester'},additions:4,deletions:1,changed_files:2,merged_at:null};
 throw new Error(`Unexpected fetch: ${url}`);
};
const result=await loadActivity({login:'tester',upstream,now,publicFetch});
assert.equal(result.events.length,3);
assert.equal(result.events[0].number,42);
assert.equal(result.events[1].size,null);
assert.equal(result.events[1].branch,'main');
assert.deepEqual(result.events[1].commits,[]);
assert.equal(result.events[2].content,'&lt;img src=x onerror=alert(1)&gt; &amp; content');
assert(!requested.some(url=>url.includes('secret')));
const template=activityTemplate(await fs.readFile(path.join(upstream,'source/templates/classic/partials/activity.ejs'),'utf8'));
const f={date:date=>date.toISOString()};
const html=ejs.render(template,{plugins:{activity:result},account:'user',user:{login:'tester'},config:{timezone:{name:'America/Toronto'}},f,s:n=>n===1?'':'s'});
assert(!html.includes('<img src=x'));
assert(!html.includes('<svg onload='));
assert(html.includes('&lt;svg onload=alert(1)&gt; Test'));
assert(html.includes('Pushed to'));
assert(!html.includes('Pushed 0'));
console.log('Activity adapter regression checks passed: partial PR, count-less push, public filtering, and escaped untrusted markup.');
const retiredFixtures=[
 event('PublicEvent',{}, {repo:{name:'tester/deleted'}}),
 event('PullRequestEvent',{action:'opened',number:44,pull_request:{number:44}}),
 event('PushEvent',{ref:'refs/heads/main',size:1,commits:[{sha:'123456789abc',message:'Legacy author absent'}]}),
];
const retired=await loadActivity({login:'tester',upstream,now,publicFetch:async url=>{
 if(url.includes('/events/public'))return retiredFixtures;
 if(url.endsWith('/deleted'))throw Object.assign(new Error('HTTP 404'),{status:404});
 if(url.endsWith('/demo'))return {private:false,full_name:'tester/demo'};
 if(url.endsWith('/pulls/44'))throw Object.assign(new Error('HTTP 410'),{status:410});
 throw new Error(`Unexpected fetch ${url}`);
}});
assert.equal(retired.events.length,1);
assert.equal(retired.events[0].commits[0].sha,'1234567');
await assert.rejects(loadActivity({login:'tester',upstream,now,publicFetch:async url=>{
 if(url.includes('/events/public'))return [event('PublicEvent',{})];
 throw Object.assign(new Error('HTTP 500'),{status:500});
}}),/HTTP 500/);
console.log('Unavailable resource checks passed: skip404/410, fail500, legacy commits without author.');
