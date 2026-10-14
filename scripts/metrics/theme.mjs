// Rhine Lab presentation layer for the metric cards, after the website's ACTIVITY LOG
// screen (siruimei07.github.io: src/styles/tokens.css, components.css, screens/activity.css).
// Pure functions: CSS strings, colour tables and guarded markup rewrites, so the vendored
// lowlighter/metrics files stay byte-for-byte upstream.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';

export const THEMES = {
  light: {page: '#ffffff', ink: '#0b0c0b', ink2: '#2f302d', sub: '#5f5d56', line: '#aaa59a',
    hair: 'rgba(11,12,11,0.14)', rule: 'rgba(11,12,11,0.45)', tagBg: '#0b0c0b', tagInk: '#f6f5f2',
    orange: '#ee7d1f', lime: '#c4e84c', limeInk: '#11140b', meter: '#8b8a86', barFill: 'rgba(11,12,11,0.06)', barStroke: 'rgba(11,12,11,0.34)'},
  dark: {page: '#0d1117', ink: '#e0e3dc', ink2: '#c4c9c2', sub: '#a6b0b1', line: '#536166',
    hair: 'rgba(224,227,220,0.14)', rule: 'rgba(224,227,220,0.45)', tagBg: '#e0e3dc', tagInk: '#0d1214',
    orange: '#e88a3a', lime: '#b6dc45', limeInk: '#11140b', meter: '#8b8a86', barFill: 'rgba(224,227,220,0.06)', barStroke: 'rgba(224,227,220,0.34)'},
};

// Isometric calendar: [top, left side, right side] per level, then the best day.
// Sides = the plugin's own feComponentTransfer (linearRGB slope 0.6 / 0.2) applied to the top colour.
export const ISO = {
  light: [['#e8e5e1', '#b9b6b3', '#706e6c'], ['#c0c0c0', '#999999', '#5b5b5b'], ['#8a8a8a', '#6d6d6d', '#404040'],
    ['#4f504f', '#3d3e3d', '#222222'], ['#2f302d', '#232422', '#111210'], ['#ee7d1f', '#be6216', '#733909']],
  dark: [['#1b2428', '#131a1e', '#070c0e'], ['#44484a', '#343839', '#1c1e1f'], ['#727676', '#595d5d', '#333535'],
    ['#a5a8a5', '#838583', '#4e4f4e'], ['#e0e3dc', '#b2b5af', '#6c6d6a'], ['#e88a3a', '#b96d2c', '#704017']],
};
// GitHub's own level colours stay the input to the plugin (levelColors); they are only sentinels now.
export const LEVEL_SENTINELS = ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39'];

const DAY = /<g transform="translate\(([^)]*)\)">\s*<path fill="(#[0-9a-f]{6})" d="M1\.7,2 0,1 1\.7,0 3\.4,1 z" \/>\s*<path fill="\2" filter="url\(#brightness1\)" d="([^"]+)" \/>\s*<path fill="\2" filter="url\(#brightness2\)" d="([^"]+)" \/>\s*<\/g>/g;
export function recolorIso(svg, mode) {
  let days = 0, best = 0;
  const out = svg.replace(DAY, (_, t, color, left, right) => {
    const level = LEVEL_SENTINELS.indexOf(color);
    if (level < 0) throw new Error(`Unexpected isocalendar colour ${color}`);
    days++;
    // ratio === 1 (count === max) is the only case where the left face ends at y 8 / 7
    const isBest = left === 'M0,1 1.7,2 1.7,8 0,7 z';
    if (isBest) best++;
    const [top, l, r] = ISO[mode][isBest ? 5 : level];
    return `<g transform="translate(${t})"><path fill="${top}" d="M1.7,2 0,1 1.7,0 3.4,1 z"/><path fill="${l}" d="${left}"/><path fill="${r}" d="${right}"/></g>`;
  }).replace(/<filter id="brightness[12]">[\s\S]*?<\/filter>/g, '');
  if (!days || /brightness|fill="#(?:ebedf0|9be9a8|40c463|30a14e|216e39)"/.test(out)) throw new Error('Upstream isocalendar SVG changed');
  return out;
}

// Languages by rank: lime (the website's VISUALIZED/TOTAL accent), then an ink ramp.
export const LANGUAGE_RAMP = {
  light: ['#c4e84c', 'rgba(11,12,11,0.92)', 'rgba(11,12,11,0.66)', 'rgba(11,12,11,0.44)', 'rgba(11,12,11,0.26)', 'rgba(11,12,11,0.12)'],
  dark: ['#b6dc45', 'rgba(224,227,220,0.92)', 'rgba(224,227,220,0.66)', 'rgba(224,227,220,0.44)', 'rgba(224,227,220,0.26)', 'rgba(224,227,220,0.12)'],
};

export const FACES = [['RLSans', 500, 'mont-500'], ['RLSans', 600, 'mont-600'], ['RLSans', 700, 'mont-700'],
  ['RLMono', 400, 'jbm-400'], ['RLMono', 500, 'jbm-500'], ['RLZh', 500, 'zh-500']];

/** @font-face rules with the subsets as data URIs (an SVG shown as an image loads nothing else).
 *  Each file must match the SHA-256 recorded by scripts/build_card_fonts.py. */
export async function fontFaces(dir) {
  const provenance = JSON.parse(await fs.readFile(path.join(dir, 'provenance.json'), 'utf8'));
  let css = '';
  for (const [family, weight, file] of FACES) {
    const bytes = await fs.readFile(path.join(dir, `${file}.woff2`));
    if (createHash('sha256').update(bytes).digest('hex') !== provenance.sha256[`${file}.woff2`]) throw new Error(`Card font hash mismatch: ${file}.woff2`);
    css += `@font-face{font-family:${family};font-style:normal;font-weight:${weight};font-display:block;src:url(data:font/woff2;base64,${bytes.toString('base64')})}`;
  }
  return css;
}

/** YYYY-MM-DD HH:mm in the given zone (the website's event log format). */
export function stamp(timestamp, timeZone = 'America/Toronto') {
  const p = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone})
    .formatToParts(new Date(timestamp)).map(x => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`;
}

/** Card headings: the website's black tag, a Chinese gloss and a mono readout built from the data. */
export const HEADINGS = {
  isocalendar: data => ({tag: 'Contribution calendar', zh: '近半年的提交', readout: String(data.duration || 'half-year').replace('-', ' ').toUpperCase()}),
  languages: data => ({tag: 'Most used languages', zh: '代码构成', readout: `${data.unique} LANGUAGES · BYTES`}),
  activity: data => ({tag: 'Recent public events', zh: '最近的公开动态', readout: `${data.events.length} EVENTS · TORONTO`, bar: true}),
};

const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const H2 = /<h2 class="field">\s*<svg[^>]*>[\s\S]*?<\/svg>\s*([^<]*?)\s*<\/h2>/g;
/** Replace the card's single octicon heading with tag + zh + optional mono readout. */
export function retitle(markup, {tag, zh, readout, bar = false}) {
  const hits = [...markup.matchAll(H2)].length;
  if (hits !== 1) throw new Error(`Expected one card heading, found ${hits}`);
  return markup.replace(H2, () => `<h2 class="field rl-head${bar ? ' rl-bar' : ''}"><span class="tag">${esc(tag)}</span>${zh ? `<small class="zh">${esc(zh)}</small>` : ''}${readout ? `<span class="readout">${esc(readout)}</span>` : ''}</h2>`);
}

/** Exact-once string replacement (same guard style as activityTemplate). */
export function once(markup, from, to) {
  const n = typeof from === 'string' ? markup.split(from).length - 1 : [...markup.matchAll(from)].length;
  if (n !== 1) throw new Error(`Expected exactly one match for ${from}, found ${n}`);
  return markup.replace(from, to);
}

export function cardCss(name, mode) {
  const T = THEMES[mode];
  const corner = `linear-gradient(${T.ink},${T.ink})`;
  const base = `
svg{color:${T.ink2}}
.items-wrapper{box-sizing:border-box;padding:14px 10px 12px;font-family:RLSans,Segoe UI,Arial,sans-serif;font-size:13px;line-height:20px;font-weight:500;color:${T.ink2};
 box-shadow:inset 0 0 0 1px ${T.hair};
 background:${corner} left top/8px 8px no-repeat,${corner} right top/8px 8px no-repeat,${corner} left bottom/8px 8px no-repeat,${corner} right bottom/8px 8px no-repeat}
h2.rl-head{display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;margin:0 0 12px;padding:0;font-size:12px;line-height:18px;font-weight:600;color:${T.sub};white-space:nowrap}
h2.rl-head .tag{display:inline-block;padding:1px 8px 0;background:${T.tagBg};color:${T.tagInk};font-family:RLSans,Segoe UI,Arial,sans-serif;font-weight:600;font-size:12px;line-height:18px;letter-spacing:.06em;text-transform:uppercase}
h2.rl-head .zh{font-family:RLZh,RLSans,sans-serif;font-weight:500;font-size:12px;line-height:18px;letter-spacing:.1em;color:${T.sub}}
h2.rl-head .readout{margin-left:auto;font-family:RLMono,monospace;font-weight:400;font-size:11px;line-height:18px;letter-spacing:.08em;color:${T.sub}}
h2.rl-bar .tag{position:relative;margin-left:6px}
h2.rl-bar .tag::before{content:"";position:absolute;left:-7px;top:0;bottom:0;width:2.5px;background:${T.ink}}
h3.field{margin:10px 0 4px;font-size:11px;line-height:16px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:${T.sub}}
h3.field>svg{display:none}
h3.field::before{content:"";flex:none;width:6px;height:6px;margin-right:8px;background:${T.ink}}
.field svg{fill:${T.sub}}`;
  const cards = {
    isocalendar: `
.items-wrapper>section>.row>section>div.field{padding-left:14px;font-size:12px;line-height:22px;letter-spacing:.04em;text-transform:uppercase;color:${T.ink2}}
.items-wrapper>section>.row>section>div.field>svg{display:none}
.items-wrapper>section>.row>section>div.field b{margin:0 5px 0 8px;font-weight:700;font-size:16px;color:${T.ink};font-variant-numeric:tabular-nums;letter-spacing:0}
.items-wrapper>section>.row>section>div.field small{font-family:RLMono,monospace;font-size:11px;font-weight:400;letter-spacing:.08em;color:${T.sub}}
.items-wrapper>section>.row>section>h3:first-child{margin-top:0}
.items-wrapper>section{display:grid;grid-template-columns:minmax(0,1fr)}
.items-wrapper>section>h2{grid-row:1;grid-column:1}
.items-wrapper>section>.row{grid-row:2;grid-column:1}
.items-wrapper>section>svg{grid-row:2;grid-column:1;align-self:start;display:block;width:100%;height:auto;margin-top:-18px !important}`,
    languages: `
section.column{align-items:stretch}
section.column>h3.field{display:none}
svg.bar{margin:2px 0 10px;outline:1px solid ${T.rule}}
.field.language.details{margin:0 14px 0 0}
.field.language.details>.field{font-size:12px;line-height:22px;font-weight:600;color:${T.ink2}}
.field.language.details>.field>svg{margin:0 8px 0 0}
.field.language.details>.field>svg path{stroke:${T.rule};stroke-width:1}
.field.language.details small{font-family:RLMono,monospace;font-size:11px;line-height:22px;font-weight:400;color:${T.sub};font-variant-numeric:tabular-nums}`,
    activity: `
.items-wrapper>section>.row>section{margin:0 0 0 6px;padding:2px 0 0 14px;border-left:1px dotted ${T.sub};font-family:RLMono,monospace;font-size:12px;letter-spacing:.02em}
.items-wrapper>section>.row>section::after{content:"> ";display:block;height:20px;line-height:20px;color:${T.sub};background:linear-gradient(${T.ink},${T.ink}) 16px 4px/7px 13px no-repeat}
section.activity{display:grid;grid-template-columns:116px minmax(0,1fr);column-gap:12px;margin:0 0 6px}
.activity>.timestamp{grid-column:1;grid-row:1;margin:0;padding:0;font-size:12px;line-height:20px;color:${T.sub};font-variant-numeric:tabular-nums;letter-spacing:.02em;display:block;white-space:nowrap}
.activity>.field{grid-column:2;grid-row:1;max-width:none;width:auto;line-height:20px;white-space:normal;overflow:visible}
.activity>.details{grid-column:2;grid-row:2;padding-left:0;font-size:11px;line-height:18px;color:${T.sub};overflow-wrap:anywhere}
.activity .field>svg,.items-wrapper>section>.row>section>.field>svg{display:none}
.items-wrapper>section>.row>section>.field::before{content:"> "}
.activity .content{font-weight:500;text-transform:uppercase;color:${T.ink2};overflow:visible;overflow-wrap:anywhere}
.activity .content::before{content:"> "}
.activity .content .repo,.activity .content .issue{text-transform:none;font-weight:400;color:${T.ink}}
.activity .details .repo{color:${T.ink2}}
.activity .code{margin:0 2px;padding:0 4px;border-radius:0;background:none;box-shadow:inset 0 0 0 1px ${T.rule};font-family:RLMono,monospace;font-size:10.5px;color:${T.ink};text-transform:none}
.items-wrapper>section>.row>section>.row:first-child .content{color:${T.ink}}`,
    traffic: `
.traffic-card{width:auto;margin:0}
.t-total{display:flex;align-items:baseline;gap:10px;margin:0 0 2px}
.t-total b{font-weight:700;font-size:32px;line-height:34px;letter-spacing:-.02em;color:${T.ink};font-variant-numeric:tabular-nums}
.t-total small{display:flex;align-items:center;flex:1;gap:8px;font-family:RLMono,monospace;font-size:11px;font-weight:400;letter-spacing:.08em;color:${T.sub}}
.t-total small::after{content:"";flex:1;height:5px;background:${T.lime}}
.t-sub{display:flex;justify-content:space-between;gap:12px;font-family:RLMono,monospace;font-size:11px;line-height:16px;letter-spacing:.06em;color:${T.sub};text-transform:uppercase}
.t-chart{display:block;margin:6px 0 10px}
.t-chart .base{stroke:${T.ink};stroke-width:1}
.t-chart .grid{stroke:${T.hair};stroke-width:1}
.t-chart .bar{fill:${T.barFill};stroke:${T.rule};stroke-width:1}
.t-chart .bar.is-best{fill:${T.orange};stroke:none}
.t-chart text{font-family:RLMono,monospace;font-size:11px;fill:${T.sub};letter-spacing:.04em}
.t-chart text.peak{fill:${T.ink};font-weight:500}
.t-repos{display:grid;grid-template-columns:1fr 1fr;gap:6px 22px;margin:0;padding:10px 0 0;border-top:1px solid ${T.hair};list-style:none}
.t-repos li{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:end;gap:3px 10px}
.t-repos li>span{font-size:12px;line-height:18px;font-weight:600;color:${T.ink2};overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.t-repos li>span::before{content:"";display:inline-block;width:6px;height:6px;margin-right:7px;background:currentColor;vertical-align:1px}
.t-repos li>b{font-size:13px;line-height:18px;font-weight:700;color:${T.ink};font-variant-numeric:tabular-nums}
.t-repos li>i{grid-column:1/-1;height:5px;box-shadow:inset 0 0 0 1px ${T.rule};background:linear-gradient(90deg,${T.meter} calc(var(--v,0)*100%),transparent 0)}
.t-repos li.is-hi>i{background:linear-gradient(90deg,${T.lime} calc(var(--v,0)*100%),transparent 0)}
.t-repos li>small{grid-column:1/-1;font-family:RLMono,monospace;font-size:11px;line-height:14px;color:${T.sub}}
.t-foot{margin:10px 0 0;font-family:RLMono,monospace;font-size:11px;line-height:16px;letter-spacing:.06em;color:${T.sub};text-transform:uppercase}
.t-empty{margin:0;font-family:RLMono,monospace;font-size:12px;color:${T.sub}}`,
  };
  return base + cards[name];
}
