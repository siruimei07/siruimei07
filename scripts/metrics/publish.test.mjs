import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {publishMetrics} from './publish.mjs';

const names=['isocalendar','languages-card','activity','traffic'].flatMap(name=>['light','dark'].map(mode=>`${name}-${mode}`));
const svg=(name,version=1)=>`<svg xmlns="http://www.w3.org/2000/svg" width="480" height="200"><text>${name}: ${version}</text></svg>\n`;
const digest=bytes=>createHash('sha256').update(bytes).digest('hex').slice(0,16);

async function fixture(t) {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'profile-metrics-publish-'));
  t.after(async()=>{
    const resolved=await fs.realpath(root);
    const parent=await fs.realpath(os.tmpdir());
    assert.equal(path.dirname(resolved),parent);
    assert(path.basename(resolved).startsWith('profile-metrics-publish-'));
    await fs.rm(resolved,{recursive:true,force:true});
  });
  await fs.mkdir(path.join(root,'assets'));
  for(const name of names) await fs.writeFile(path.join(root,'assets',`${name}.svg`),svg(name));
  const references=names.map(name=>name.endsWith('-dark')
    ?`  <source media="(prefers-color-scheme: dark)" srcset='./assets/${name}.svg' />`
    :`  <img src="./assets/${name}.svg" width="49%" align="top" alt="Keep ${name} unchanged." />`).join('\r\n');
  const readme=`<img src="./assets/banner.png" width="100%" alt="Banner" />\r\n\r\n<p>\r\n${references}\r\n</p>\r\n`;
  await fs.writeFile(path.join(root,'README.md'),readme);
  return {root,readme,metrics:path.join(root,'assets','metrics')};
}

test('publishes all src/srcset URLs, preserves layout, and is content-idempotent',async t=>{
  const {root,readme,metrics}=await fixture(t);
  const first=await publishMetrics({repoRoot:root});
  assert.equal(first.created.length,8);
  let expected=readme;
  for(const name of names) {
    const bytes=await fs.readFile(path.join(root,'assets',`${name}.svg`));
    const filename=`${name}.${digest(bytes)}.svg`;
    assert.equal(first.assets[`${name}.svg`].current,filename);
    assert.equal(first.assets[`${name}.svg`].previous,null);
    assert.deepEqual(await fs.readFile(path.join(metrics,filename)),bytes);
    expected=expected.replace(`./assets/${name}.svg`,`./assets/metrics/${filename}`);
  }
  assert.equal(await fs.readFile(path.join(root,'README.md'),'utf8'),expected);
  const beforeManifest=await fs.readFile(path.join(metrics,'manifest.json'));
  const beforeStat=await fs.stat(path.join(root,'README.md'));
  const second=await publishMetrics({repoRoot:root});
  assert.equal(second.readmeChanged,false);
  assert.equal(second.manifestChanged,false);
  assert.deepEqual(second.created,[]);
  assert.deepEqual(second.pruned,[]);
  assert.equal((await fs.stat(path.join(root,'README.md'))).mtimeMs,beforeStat.mtimeMs);
  assert.deepEqual(await fs.readFile(path.join(metrics,'manifest.json')),beforeManifest);
});

test('only changed card gets a new URL and retains exactly its previous generation',async t=>{
  const {root,metrics}=await fixture(t);
  const first=await publishMetrics({repoRoot:root});
  const firstReadme=await fs.readFile(path.join(root,'README.md'),'utf8');
  const unrelated='activity-light.0000000000000000.svg';
  await fs.writeFile(path.join(metrics,unrelated),'unrelated file');
  await fs.writeFile(path.join(metrics,'notes.txt'),'keep notes');
  await fs.writeFile(path.join(root,'assets','activity-light.svg'),svg('activity-light',2));
  const second=await publishMetrics({repoRoot:root});
  const old=first.assets['activity-light.svg'].current;
  const newer=second.assets['activity-light.svg'].current;
  assert.equal(second.assets['activity-light.svg'].previous,old);
  assert.notEqual(newer,old);
  assert.deepEqual(second.created,[newer]);
  assert.deepEqual(second.pruned,[]);
  assert.equal(await fs.readFile(path.join(root,'README.md'),'utf8'),firstReadme.replace(old,newer));
  assert.equal(await fs.readFile(path.join(metrics,old),'utf8'),svg('activity-light'));
  for(const name of names.filter(name=>name!=='activity-light')) assert.deepEqual(second.assets[`${name}.svg`],first.assets[`${name}.svg`]);
  await fs.writeFile(path.join(root,'assets','activity-light.svg'),svg('activity-light',3));
  const third=await publishMetrics({repoRoot:root});
  assert.equal(third.assets['activity-light.svg'].previous,newer);
  assert.deepEqual(third.pruned,[old]);
  await assert.rejects(fs.access(path.join(metrics,old)),{code:'ENOENT'});
  assert.equal(await fs.readFile(path.join(metrics,newer),'utf8'),svg('activity-light',2));
  assert.equal(await fs.readFile(path.join(metrics,unrelated),'utf8'),'unrelated file');
  assert.equal(await fs.readFile(path.join(metrics,'notes.txt'),'utf8'),'keep notes');
});

test('missing or invalid sources and ambiguous README links fail before mutations',async t=>{
  const {root,readme,metrics}=await fixture(t);
  const last=path.join(root,'assets','traffic-dark.svg');
  await fs.unlink(last);
  await assert.rejects(publishMetrics({repoRoot:root}),/Expected a regular file/);
  assert.equal(await fs.readFile(path.join(root,'README.md'),'utf8'),readme);
  await assert.rejects(fs.access(metrics),{code:'ENOENT'});
  await fs.writeFile(last,'<svg xmlns="http://www.w3.org/2000/svg"><broken></svg>');
  await assert.rejects(publishMetrics({repoRoot:root}),/Invalid metric SVG/);
  assert.equal(await fs.readFile(path.join(root,'README.md'),'utf8'),readme);
  await assert.rejects(fs.access(metrics),{code:'ENOENT'});
  await fs.writeFile(last,svg('traffic-dark'));
  const duplicate=readme+'<img src="./assets/traffic-dark.svg" />\n';
  await fs.writeFile(path.join(root,'README.md'),duplicate);
  await assert.rejects(publishMetrics({repoRoot:root}),/exactly one README/);
  assert.equal(await fs.readFile(path.join(root,'README.md'),'utf8'),duplicate);
  await assert.rejects(fs.access(metrics),{code:'ENOENT'});
});

test('rejects unsafe manifest paths and corrupted immutable output before editing README',async t=>{
  const {root,metrics}=await fixture(t);
  const first=await publishMetrics({repoRoot:root});
  const readme=await fs.readFile(path.join(root,'README.md'));
  const manifestPath=path.join(metrics,'manifest.json');
  const manifest=JSON.parse(await fs.readFile(manifestPath,'utf8'));
  manifest.assets['activity-light.svg'].previous='../unrelated.svg';
  await fs.writeFile(manifestPath,JSON.stringify(manifest));
  await assert.rejects(publishMetrics({repoRoot:root}),/Invalid metric manifest entry/);
  assert.deepEqual(await fs.readFile(path.join(root,'README.md')),readme);
  manifest.assets['activity-light.svg'].previous=null;
  await fs.writeFile(manifestPath,JSON.stringify(manifest));
  await fs.writeFile(path.join(metrics,first.assets['activity-light.svg'].current),'corrupt');
  await assert.rejects(publishMetrics({repoRoot:root}),/Immutable metric filename/);
  assert.deepEqual(await fs.readFile(path.join(root,'README.md')),readme);
});
