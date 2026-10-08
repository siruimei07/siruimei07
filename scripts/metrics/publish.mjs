import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash, randomUUID} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {JSDOM} from 'jsdom';

const scriptPath=fileURLToPath(import.meta.url);
const names=['isocalendar','languages-card','activity','traffic'].flatMap(name=>['light','dark'].map(mode=>`${name}-${mode}`));
const hash=bytes=>createHash('sha256').update(bytes).digest('hex').slice(0,16);
const quoteRegex=value=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');

async function statOrNull(file) {
  try {return await fs.lstat(file);}
  catch(error) {if(error.code==='ENOENT') return null;throw error;}
}

function within(directory,file) {
  const relative=path.relative(directory,file);
  if(!relative||relative==='..'||relative.startsWith(`..${path.sep}`)||path.isAbsolute(relative)) throw new Error('Metric output path escaped its directory');
  return file;
}

async function regularFile(file,{optional=false}={}) {
  const stat=await statOrNull(file);
  if(!stat&&optional) return null;
  if(!stat?.isFile()||stat.isSymbolicLink()) throw new Error(`Expected a regular file: ${file}`);
  return fs.readFile(file);
}

function validateSvg(bytes,name) {
  try {
    const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);
    const dom=new JSDOM(text,{contentType:'image/svg+xml'});
    const document=dom.window.document;
    const valid=document.documentElement.localName==='svg'
      &&document.documentElement.namespaceURI==='http://www.w3.org/2000/svg'
      &&!document.doctype;
    dom.window.close();
    if(!valid) throw new Error('Expected an SVG root without a document type');
  } catch(error) {throw new Error(`Invalid metric SVG ${name}: ${error.message}`);}
}

function validateManifest(manifest) {
  if(manifest.version!==1||!manifest.assets||Array.isArray(manifest.assets)
    ||Object.keys(manifest.assets).length!==names.length) throw new Error('Invalid metric publication manifest');
  for(const name of names) {
    const entry=manifest.assets[`${name}.svg`];
    const pattern=new RegExp(`^${quoteRegex(name)}\\.[a-f0-9]{16}\\.svg$`);
    if(!entry||!pattern.test(entry.current)||!(entry.previous===null||pattern.test(entry.previous))
      ||entry.current===entry.previous) throw new Error(`Invalid metric manifest entry: ${name}`);
  }
}

// Only call after the complete preflight. Temporary files stay next to their
// destination, and replacing a file does not truncate a concurrent reader.
async function writeAtomically(directory,destination,bytes) {
  within(directory,destination);
  const temporary=within(directory,path.join(path.dirname(destination),`.${path.basename(destination)}.${randomUUID()}.tmp`));
  try {
    await fs.writeFile(temporary,bytes,{flag:'wx'});
    await fs.rename(temporary,destination);
  } finally {
    await fs.unlink(within(directory,temporary)).catch(error=>{if(error.code!=='ENOENT') throw error;});
  }
}

/**
 * Publish all eight canonical metric SVGs under content-addressed URLs.
 * Validates every input/reference before any write. Only the current and
 * previous manifest generation are retained for each individual metric.
 */
export async function publishMetrics({repoRoot=path.resolve(path.dirname(scriptPath),'../..')}={}) {
  const root=await fs.realpath(path.resolve(repoRoot));
  const assetsDirectory=path.join(root,'assets');
  const metricsDirectory=path.join(assetsDirectory,'metrics');
  const readmePath=path.join(root,'README.md');
  const manifestPath=path.join(metricsDirectory,'manifest.json');
  for(const directory of [assetsDirectory,metricsDirectory]) {
    const stat=await statOrNull(directory);
    if(stat&&(!stat.isDirectory()||stat.isSymbolicLink())) throw new Error(`Expected a regular directory: ${directory}`);
  }
  const readmeBytes=await regularFile(readmePath);
  const originalReadme=new TextDecoder('utf-8',{fatal:true}).decode(readmeBytes);
  const oldManifestBytes=await regularFile(manifestPath,{optional:true});
  const oldManifest=oldManifestBytes?JSON.parse(oldManifestBytes.toString('utf8')):null;
  if(oldManifest) validateManifest(oldManifest);

  const planned=[];
  const manifest={version:1,assets:{}};
  let readme=originalReadme;
  for(const name of names) {
    const sourceBytes=await regularFile(path.join(assetsDirectory,`${name}.svg`));
    validateSvg(sourceBytes,`${name}.svg`);
    const current=`${name}.${hash(sourceBytes)}.svg`;
    // The surrounding quote must close directly after the exact known URL.
    // This cannot match data-src, query strings, banner URLs, or another card.
    const reference=new RegExp(`(?<=\\s)(src|srcset)(\\s*=\\s*)(["'])(\\./assets/${quoteRegex(name)}\\.svg|\\./assets/metrics/${quoteRegex(name)}\\.[a-f0-9]{16}\\.svg)\\3`,'g');
    const matches=[...originalReadme.matchAll(reference)];
    if(matches.length!==1) throw new Error(`Expected exactly one README src/srcset reference for ${name}.svg; found ${matches.length}`);
    const oldReference=matches[0][4];
    const oldEntry=oldManifest?.assets[`${name}.svg`];
    let previous=oldEntry?(oldEntry.current===current?oldEntry.previous:oldEntry.current):null;
    // Permit adopting an already content-addressed README without a manifest.
    // Only retain an existing file; do not fabricate old image contents.
    if(!oldEntry&&oldReference.startsWith('./assets/metrics/')) {
      const referenced=path.posix.basename(oldReference);
      if(referenced!==current&&await regularFile(within(metricsDirectory,path.join(metricsDirectory,referenced)),{optional:true})) previous=referenced;
    }
    manifest.assets[`${name}.svg`]={current,previous};
    const destination=within(metricsDirectory,path.join(metricsDirectory,current));
    const existing=await regularFile(destination,{optional:true});
    if(existing&&!existing.equals(sourceBytes)) throw new Error(`Immutable metric filename already contains different bytes: ${current}`);
    const prune=[oldEntry?.current,oldEntry?.previous].filter(file=>file&&file!==current&&file!==previous);
    for(const file of prune) await regularFile(within(metricsDirectory,path.join(metricsDirectory,file)),{optional:true});
    planned.push({name,current,sourceBytes,destination,create:!existing,prune});
    readme=readme.replace(reference,(_,attribute,equal,quote)=>`${attribute}${equal}${quote}./assets/metrics/${current}${quote}`);
  }
  const manifestBytes=Buffer.from(`${JSON.stringify(manifest,null,2)}\n`);
  const readmeChanged=readme!==originalReadme;
  const manifestChanged=!oldManifestBytes?.equals(manifestBytes);

  // All sources, all eight references, destinations, and prune candidates are
  // now validated. Publish images before changing the document that uses them.
  await fs.mkdir(metricsDirectory,{recursive:true});
  for(const item of planned) if(item.create) await fs.writeFile(item.destination,item.sourceBytes,{flag:'wx'});
  if(readmeChanged) await writeAtomically(root,readmePath,Buffer.from(readme));
  if(manifestChanged) await writeAtomically(metricsDirectory,manifestPath,manifestBytes);
  const pruned=[];
  for(const item of planned) for(const filename of item.prune) {
    const target=within(metricsDirectory,path.join(metricsDirectory,filename));
    try {await fs.unlink(target);pruned.push(filename);}
    catch(error) {if(error.code!=='ENOENT') throw error;}
  }
  return {readmeChanged,manifestChanged,created:planned.filter(item=>item.create).map(item=>item.current),pruned,assets:manifest.assets};
}

if(process.argv[1]&&path.resolve(process.argv[1])===scriptPath) {
  try {
    if(process.argv.length>3) throw new Error('Usage: node scripts/metrics/publish.mjs [repoRoot]');
    console.log(JSON.stringify(await publishMetrics({repoRoot:process.argv[2]}),null,2));
  } catch(error) {console.error(error.message);process.exitCode=1;}
}
