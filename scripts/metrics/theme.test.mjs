import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FACES,HEADINGS,ISO,LEVEL_SENTINELS,cardCss,fontFaces,once,recolorIso,retitle,stamp} from './theme.mjs';

const fonts=path.join(path.dirname(fileURLToPath(import.meta.url)),'fonts');
// One day group exactly as the pinned isocalendar plugin prints it.
const day=(color,height=1)=>`<g transform="translate(0, 0)">
  <path fill="${color}" d="M1.7,2 0,1 1.7,0 3.4,1 z" />
  <path fill="${color}" filter="url(#brightness1)" d="M0,1 1.7,2 1.7,${2+6*height} 0,${1+6*height} z" />
  <path fill="${color}" filter="url(#brightness2)" d="M1.7,2 3.4,1 3.4,${1+6*height} 1.7,${2+6*height} z" />
</g>`;
const filters='<filter id="brightness1"><feComponentTransfer></feComponentTransfer></filter><filter id="brightness2"><feComponentTransfer></feComponentTransfer></filter>';

test('isocalendar days take the Rhine Lab ramp and the best day turns orange',()=>{
  const svg=`<svg>${filters}${day(LEVEL_SENTINELS[0],0)}${day(LEVEL_SENTINELS[2],0.5)}${day(LEVEL_SENTINELS[4],1)}</svg>`;
  for(const mode of ['light','dark']) {
    const out=recolorIso(svg,mode);
    assert.doesNotMatch(out,/brightness|filter/);
    assert.ok(out.includes(`fill="${ISO[mode][0][0]}"`));
    assert.ok(out.includes(`fill="${ISO[mode][2][1]}"`));
    // Full height (count === max) is the best day, whatever its level.
    assert.ok(out.includes(`fill="${ISO[mode][5][0]}"`));
    assert.ok(!out.includes(`fill="${ISO[mode][4][0]}"`));
  }
});

test('isocalendar rewrite fails closed on upstream drift',()=>{
  assert.throws(()=>recolorIso(`<svg>${day('#123456')}</svg>`,'light'),/Unexpected isocalendar colour/);
  assert.throws(()=>recolorIso('<svg></svg>','light'),/changed/);
});

test('card headings become tag, Chinese gloss and a readout from the data',()=>{
  const markup='<section><h2 class="field"><svg viewBox="0 0 16 16"><path d="M0 0"/></svg>\n  9 Languages\n</h2></section>';
  const heading=HEADINGS.languages({unique:9});
  const out=retitle(markup,heading);
  assert.equal(out,'<section><h2 class="field rl-head"><span class="tag">Most used languages</span><small class="zh">代码构成</small><span class="readout">9 LANGUAGES · BYTES</span></h2></section>');
  assert.equal(HEADINGS.isocalendar({duration:'half-year'}).readout,'HALF YEAR');
  assert.equal(HEADINGS.activity({events:[1,2,3]}).readout,'3 EVENTS · TORONTO');
  assert.match(retitle(markup,HEADINGS.activity({events:[]})),/rl-bar/);
  assert.throws(()=>retitle('<p></p>',heading),/one card heading/);
  assert.throws(()=>retitle(markup+markup,heading),/found 2/);
});

test('guarded replacements need exactly one match',()=>{
  assert.equal(once('a b','b','c'),'a c');
  assert.throws(()=>once('a b','x','c'),/found 0/);
  assert.throws(()=>once('b b',/b/g,'c'),/found 2/);
});

test('event timestamps use the website log format in Toronto time',()=>{
  assert.equal(stamp('2026-10-14T04:06:00Z'),'2026-10-14 00:06');
  assert.equal(stamp('2026-01-15T05:00:00Z'),'2026-01-15 00:00');
  assert.equal(stamp('2026-10-14T04:06:00Z','UTC'),'2026-10-14 04:06');
});

test('every card stylesheet is self-contained and theme-specific',()=>{
  for(const name of ['isocalendar','languages','activity','traffic']) {
    const light=cardCss(name,'light'), dark=cardCss(name,'dark');
    assert.notEqual(light,dark);
    assert.doesNotMatch(light,/url\((?!data:)|@import|color-mix/);
  }
});

test('embedded fonts are verified against their recorded hashes',async t=>{
  const css=await fontFaces(fonts);
  assert.equal((css.match(/@font-face/g)||[]).length,FACES.length);
  const copy=await fs.mkdtemp(path.join(os.tmpdir(),'profile-card-fonts-'));
  t.after(()=>fs.rm(copy,{recursive:true,force:true}));
  for(const file of await fs.readdir(fonts)) await fs.copyFile(path.join(fonts,file),path.join(copy,file));
  await fs.appendFile(path.join(copy,'zh-500.woff2'),Buffer.from([0]));
  await assert.rejects(fontFaces(copy),/hash mismatch: zh-500/);
});
