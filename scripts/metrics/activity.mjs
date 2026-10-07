import fs from 'node:fs/promises';
import path from 'node:path';

const repoName = /^[a-z\d](?:[a-z\d-]{0,38})\/[a-z\d_.-]+$/i;
const supported = new Set(['CommitCommentEvent','CreateEvent','DeleteEvent','ForkEvent','GollumEvent','IssueCommentEvent','IssuesEvent','MemberEvent','PublicEvent','PullRequestEvent','PullRequestReviewEvent','PullRequestReviewCommentEvent','PushEvent','ReleaseEvent','WatchEvent']);
const clean = (value, limit=240) => typeof value==='string' ? value.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g,'').slice(0,limit) : '';
const integer = value => Number.isSafeInteger(value)&&value>=0;
const issueShape = value => value&&typeof value.user?.login==='string'&&integer(value.number)&&typeof value.title==='string';
const escapeHtml = value => clean(value,450).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

// GitHub removed commits/size from public PushEvent payloads in October 2025.
// Retain the upstream source bytes on disk; adapt only this known outdated branch.
async function activityPlugin(upstream) {
  const source=await fs.readFile(path.join(upstream,'source/plugins/activity/index.mjs'),'utf8');
  const marker='let {size, commits, ref} = payload';
  if(source.split(marker).length!==2) throw new Error('Upstream activity push parser changed');
  const patched=source.replace(marker,`${marker}
              if (!Array.isArray(commits) || !commits.length)
                return {type: "push", actor, timestamp, repo, size: null, branch: typeof ref === "string" ? ref.match(/^refs\\/heads\\/(?<branch>.*)/)?.groups?.branch ?? null : null, commits: []}`);
  return (await import(`data:text/javascript;base64,${Buffer.from(patched).toString('base64')}`)).default;
}

/**
 * Adapt public REST activity to lowlighter/metrics' official activity plugin.
 * Neither an event URL nor an enrichment URL from a payload is ever followed.
 * publicFetch must enforce its own public GitHub API allowlist.
 */
export async function loadActivity({login, upstream, now=new Date(), publicFetch}) {
  const cutoff=now.getTime()-30*24*60*60*1000;
  const batches=[];
  // GitHub serves at most 300 events. Inspect all available pages because the
  // public feed can contain events that are not in strict timestamp order.
  for(let page=1;page<=3;page++) {
    const batch=await publicFetch(`https://api.github.com/users/${encodeURIComponent(login)}/events/public?per_page=100&page=${page}`);
    if(!Array.isArray(batch)) throw new Error('Invalid public activity response');
    batches.push(...batch);
    if(batch.length<100) break;
  }
  const candidates=batches.filter(event=>event?.public===true
    &&event.actor?.login?.toLowerCase()===login.toLowerCase()
    &&repoName.test(event.repo?.name||'')
    &&supported.has(event.type)
    &&event.payload&&typeof event.payload==='object'
    &&new Date(event.created_at).getTime()>cutoff
    &&new Date(event.created_at).getTime()<=now.getTime())
    .sort((a,b)=>new Date(b.created_at)-new Date(a.created_at));

  const repoCache=new Map(), pullCache=new Map();
  async function availablePublicResource(url) {
    try {return await publicFetch(url);}
    catch(error) {
      // Public history can outlive a deleted or newly private repository/PR.
      // Skip only unavailable resources; rate/auth/server failures must keep
      // the previous card instead of silently publishing incomplete activity.
      if([404,410].includes(error.status)||/\bHTTP (404|410)\b/.test(error.message)) return null;
      throw error;
    }
  }
  async function publicRepo(fullName) {
    if(!repoName.test(fullName)) return false;
    if(!repoCache.has(fullName)) {
      const metadata=await availablePublicResource(`https://api.github.com/repos/${fullName}`);
      repoCache.set(fullName,metadata?.private===false&&metadata?.full_name?.toLowerCase()===fullName.toLowerCase());
    }
    return repoCache.get(fullName);
  }
  async function pull(fullName,number) {
    if(!integer(number)||number===0) return null;
    const key=`${fullName}#${number}`;
    if(!pullCache.has(key)) pullCache.set(key,await availablePublicResource(`https://api.github.com/repos/${fullName}/pulls/${number}`));
    const result=pullCache.get(key);
    // Enriched responses expose no head/base repository objects to the plugin.
    return issueShape(result)&&result.number===number ? result : null;
  }
  const events=[];
  for(const original of candidates) {
    if(events.length===5) break;
    const fullName=original.repo.name;
    if(!await publicRepo(fullName)) continue;
    const payload=structuredClone(original.payload);
    switch(original.type) {
      case 'PullRequestEvent':
      case 'PullRequestReviewEvent':
      case 'PullRequestReviewCommentEvent': {
        if(original.type==='PullRequestEvent'&&!['opened','closed'].includes(payload.action)) continue;
        if(original.type==='PullRequestReviewCommentEvent'&&payload.action!=='created') continue;
        if(original.type==='PullRequestReviewEvent'&&typeof payload.review?.state!=='string') continue;
        const pr=await pull(fullName,payload.number??payload.pull_request?.number);
        if(!pr) continue;
        if(original.type==='PullRequestEvent'&&![pr.additions,pr.deletions,pr.changed_files].every(integer)) continue;
        if(original.type==='PullRequestReviewCommentEvent'&&typeof payload.comment?.body!=='string') continue;
        payload.pull_request={user:{login:clean(pr.user.login)},number:pr.number,title:clean(pr.title),body:'',additions:pr.additions,deletions:pr.deletions,changed_files:pr.changed_files,
          merged:typeof pr.merged_at==='string'&&new Date(pr.merged_at)<=new Date(original.created_at)};
        break;
      }
      case 'PushEvent': {
        payload.ref=clean(payload.ref);
        payload.size=integer(payload.size)?payload.size:null;
        if(Array.isArray(payload.commits)) payload.commits=payload.commits
          .filter(commit=>typeof commit?.sha==='string'&&typeof commit?.message==='string')
          .map(commit=>({sha:clean(commit.sha,40),message:clean(commit.message,200),author:{email:clean(commit.author?.email)}}));
        break;
      }
      case 'CommitCommentEvent':
        if(payload.action!=='created'||typeof payload.comment?.user?.login!=='string'||typeof payload.comment?.commit_id!=='string'||typeof payload.comment?.body!=='string') continue;
        break;
      case 'IssueCommentEvent':
        if(payload.action!=='created'||!issueShape(payload.issue)||typeof payload.comment?.body!=='string') continue;
        break;
      case 'IssuesEvent':
        if(!['opened','closed','reopened'].includes(payload.action)||!issueShape(payload.issue)) continue;
        break;
      case 'CreateEvent':
      case 'DeleteEvent':
        if(!['repository','branch','tag'].includes(payload.ref_type)||payload.ref_type!=='repository'&&typeof payload.ref!=='string') continue;
        break;
      case 'ForkEvent':
        if(!repoName.test(payload.forkee?.full_name||'')||!await publicRepo(payload.forkee.full_name)) continue;
        break;
      case 'GollumEvent':
        if(!Array.isArray(payload.pages)||payload.pages.some(page=>typeof page?.title!=='string')) continue;
        break;
      case 'MemberEvent':
        if(payload.action!=='added'||typeof payload.member?.login!=='string') continue;
        break;
      case 'ReleaseEvent':
        if(payload.action!=='published'||!payload.release||typeof payload.release.tag_name!=='string'||payload.release.draft===true) continue;
        break;
      case 'WatchEvent':
        if(payload.action!=='started') continue;
        break;
    }
    events.push({type:original.type,payload,actor:{login},repo:{name:fullName},created_at:original.created_at,public:true});
  }

  const plugin=await activityPlugin(upstream);
  const result=await plugin({login,account:'user',q:{activity:true},data:{shared:{'repositories.skipped':[],'users.ignored':[]}},
    rest:{activity:{listEventsForAuthenticatedUser:async()=>({data:events})}},
    imports:{metadata:{plugins:{activity:{enabled:()=>true,inputs:()=>({limit:5,load:100,days:0,filter:['all'],visibility:'public',timestamps:true,skipped:[],ignored:[]})}}},
      filters:{repo:()=>true,text:()=>true},markdown:async content=>escapeHtml(content),format:{error:error=>error}}},
    {enabled:true});
  if(!result||result.error||!Array.isArray(result.events)) throw new Error('Official activity plugin did not return a valid activity card');
  return result;
}

// Optional guarded in-memory template compatibility. A missing push count is
// unknown, not zero; render "Pushed to …" instead of making up a commit total.
export function activityTemplate(source) {
  const marker='<%- _("P") %>ushed <%= event.size %> commit<%= s(event.size) %> in';
  if(source.split(marker).length!==2) throw new Error('Upstream activity push template changed');
  return source.replace(marker,'<%- _("P") %>ushed <% if (event.size === null) { %>to<% } else { %><%= event.size %> commit<%= s(event.size) %> in<% } %>');
}
