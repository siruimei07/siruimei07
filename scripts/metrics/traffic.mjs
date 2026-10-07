import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

const execFileAsync = promisify(execFile);
const sourceRevision = '366f8b9dfe3a59656c67d5dcad9950f59c9bc96d';
const validCount = value => Number.isSafeInteger(value) && value >= 0;
const formatDate = date => new Intl.DateTimeFormat('en-US', {
  month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
}).format(new Date(date));

function normalizeViews(response) {
  if (!response || !validCount(response.count) || !validCount(response.uniques) || !Array.isArray(response.views)) {
    throw new Error('Invalid traffic response');
  }
  const dates = new Set();
  const views = response.views.map(point => {
    if (!/^\d{4}-\d{2}-\d{2}T00:00:00Z$/.test(point.timestamp) || !Number.isFinite(Date.parse(point.timestamp)) || !validCount(point.count) || !validCount(point.uniques)) {
      throw new Error('Invalid daily traffic response');
    }
    if (dates.has(point.timestamp)) throw new Error('Duplicate daily traffic response');
    dates.add(point.timestamp);
    return {timestamp: point.timestamp, count: point.count, uniques: point.uniques};
  }).sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  if (views.reduce((total, point) => total + point.count, 0) !== response.count) {
    throw new Error('Traffic total does not match its daily breakdown');
  }
  return {count: response.count, uniques: response.uniques, views};
}

async function readSnapshot(snapshotPath, login) {
  try {
    const snapshot = JSON.parse(await fs.readFile(snapshotPath, 'utf8'));
    if (snapshot.version !== 1 || snapshot.login.toLowerCase() !== login.toLowerCase() || !Number.isFinite(Date.parse(snapshot.capturedAt)) || !Array.isArray(snapshot.repositories)) {
      throw new Error('Invalid traffic snapshot');
    }
    const names = new Set();
    for (const repo of snapshot.repositories) {
      if (repo.public !== true || !/^[a-z\d_.-]+$/i.test(repo.name) || repo.fullName.toLowerCase() !== `${login}/${repo.name}`.toLowerCase() || names.has(repo.fullName.toLowerCase())) {
        throw new Error('Invalid repository in traffic snapshot');
      }
      names.add(repo.fullName.toLowerCase());
      repo.traffic = normalizeViews(repo.traffic);
    }
    return snapshot;
  } catch (error) {
    if (error.code !== 'ENOENT') console.warn('Traffic: previous snapshot could not be validated.');
    return null;
  }
}

/**
 * Return presentation data for templates/traffic.ejs as plugins.traffic.
 * Only explicitly public repositories currently owned by login are eligible; forks
 * are included and the profile repository is excluded. Snapshot counts are from
 * the authenticated traffic API, never inferred from public stars or activity.
 * TRAFFIC_TOKEN enables refresh. METRICS_TRAFFIC_USE_GH=1 explicitly enables a
 * local refresh via gh without exporting its credential. Otherwise use the cache.
 */
export async function loadTraffic({login, publicRepos, upstream, now = new Date(), snapshotPath}) {
  if (!/^[a-z\d][a-z\d-]{0,38}$/i.test(login) || !Array.isArray(publicRepos)) throw new Error('Invalid traffic account inputs');
  const capturedAt = new Date(now).toISOString();
  const eligible = publicRepos.filter(repo =>
    repo.private === false && repo.owner?.login?.toLowerCase() === login.toLowerCase() &&
    /^[a-z\d_.-]+$/i.test(repo.name) && repo.name.toLowerCase() !== login.toLowerCase()
  ).map(repo => ({name: repo.name, fullName: `${login}/${repo.name}`}));
  const allowed = new Set(eligible.map(repo => repo.fullName.toLowerCase()));
  if (allowed.size !== eligible.length) throw new Error('Duplicate public repositories');

  let snapshot = await readSnapshot(snapshotPath, login);
  let refreshed = false;
  const token = process.env.TRAFFIC_TOKEN?.trim();
  const useGh = !token && process.env.METRICS_TRAFFIC_USE_GH === '1';
  if ((token || useGh) && eligible.length) {
    try {
      const repositories = [];
      for (const repo of eligible) {
        // The authenticated endpoint is constructed only from the public allowlist.
        const endpoint = `repos/${encodeURIComponent(login)}/${encodeURIComponent(repo.name)}/traffic/views?per=day`;
        let data;
        if (token) {
          const response = await fetch(`https://api.github.com/${endpoint}`, {
            headers: {
              Authorization: `Bearer ${token}`,
              Accept: 'application/vnd.github+json',
              'X-GitHub-Api-Version': '2022-11-28',
              'User-Agent': 'public-github-profile-metrics',
            },
            redirect: 'error',
            signal: AbortSignal.timeout(30000),
          });
          if (!response.ok) {
            const error = new Error('Traffic request failed');
            error.publicReason = `HTTP ${response.status}`;
            throw error;
          }
          data = await response.json();
        } else {
          const {stdout} = await execFileAsync('gh', [
            'api', '--hostname', 'github.com', '-H', 'Accept: application/vnd.github+json',
            '-H', 'X-GitHub-Api-Version: 2022-11-28', endpoint,
          ], {encoding: 'utf8', windowsHide: true, timeout: 30000, maxBuffer: 1024 * 1024});
          data = JSON.parse(stdout);
        }
        repositories.push({...repo, public: true, traffic: normalizeViews(data)});
      }
      // No partially successful refresh may replace the previous complete snapshot.
      snapshot = {version: 1, login, sourceRevision, capturedAt, repositories};
      refreshed = true;
    } catch (error) {
      console.warn(`Traffic: refresh failed (${error.publicReason || 'request or data validation failed'}); ${snapshot ? `keeping snapshot captured ${snapshot.capturedAt}` : 'no previous snapshot is available'}.`);
    }
  }
  if (!snapshot) {
    return {available: false, refreshed: false, message: 'Traffic has not been captured yet.'};
  }

  // Never display a cached repository that is no longer in the current public list.
  const entries = snapshot.repositories.filter(repo => allowed.has(repo.fullName.toLowerCase()));
  if (!entries.length) return {available: false, refreshed: false, message: 'No captured traffic for the current public repositories.'};
  const records = new Map(entries.map(repo => [repo.fullName.toLowerCase(), repo.traffic]));
  const officialTraffic = (await import(pathToFileURL(path.join(upstream, 'source/plugins/traffic/index.mjs')).href)).default;
  const result = await officialTraffic({
    login, account: 'user', q: {traffic: true},
    data: {shared: {'repositories.skipped': []}, user: {repositories: {nodes: entries.map(repo => ({name: repo.name, owner: {login}}))}}},
    rest: {repos: {getViews: async ({owner, repo}) => {
      const data = records.get(`${owner}/${repo}`.toLowerCase());
      if (!data) throw new Error('Traffic endpoint is outside the public snapshot');
      return {data};
    }}},
    imports: {
      metadata: {plugins: {traffic: {enabled: () => true, inputs: () => ({skipped: []})}}},
      filters: {repo: fullName => records.has(fullName.toLowerCase())},
      format: {error: error => error},
    },
  }, {enabled: true});
  if (!validCount(result?.views?.count)) throw new Error('Official traffic aggregation failed');
  // The upstream plugin also sums repository-level uniques. Deliberately discard
  // that field: visitors cannot be deduplicated across different repositories.
  const daily = new Map();
  for (const repo of entries) {
    for (const point of repo.traffic.views) {
      const day = point.timestamp.slice(0, 10);
      daily.set(day, (daily.get(day) || 0) + point.count);
    }
  }
  const dates = [...daily.keys()].sort();
  const end = dates.at(-1) || snapshot.capturedAt.slice(0, 10);
  const emptyStart = new Date(`${end}T00:00:00Z`);
  emptyStart.setUTCDate(emptyStart.getUTCDate() - 13);
  const start = dates[0] || emptyStart.toISOString().slice(0, 10);
  const days = [];
  for (let day = new Date(`${start}T00:00:00Z`); day.toISOString().slice(0, 10) <= end; day.setUTCDate(day.getUTCDate() + 1)) {
    if (days.length >= 31) throw new Error('Traffic period is unexpectedly long');
    const date = day.toISOString().slice(0, 10);
    days.push({date, count: daily.get(date) || 0});
  }
  if (days.reduce((total, day) => total + day.count, 0) !== result.views.count) throw new Error('Traffic chart and aggregate differ');
  const card = {
    available: true, refreshed, totalViews: result.views.count,
    capturedAt: snapshot.capturedAt, capturedLabel: formatDate(snapshot.capturedAt),
    period: {start, end}, periodLabel: `${formatDate(`${start}T00:00:00Z`)} – ${formatDate(`${end}T00:00:00Z`)}`,
    days, maxDayCount: Math.max(1, ...days.map(day => day.count)),
    repositories: entries.map(repo => {
      const start = repo.traffic.views[0]?.timestamp;
      const end = repo.traffic.views.at(-1)?.timestamp;
      return {
        name: repo.name, fullName: repo.fullName, count: repo.traffic.count,
        period: start && end ? {start: start.slice(0, 10), end: end.slice(0, 10)} : null,
        periodLabel: start && end ? `${formatDate(start)} – ${formatDate(end)}` : 'No daily views reported',
      };
    }).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name)),
    repositoryCount: entries.length, complete: entries.length === eligible.length,
  };
  if (refreshed) {
    await fs.mkdir(path.dirname(snapshotPath), {recursive: true});
    await fs.writeFile(snapshotPath, `${JSON.stringify(snapshot, null, 2)}\n`, 'utf8');
    console.info(`Traffic: refreshed ${entries.length} public repositories, captured ${snapshot.capturedAt}.`);
  } else {
    console.info(`Traffic: using snapshot captured ${snapshot.capturedAt} for ${entries.length} public repositories.`);
  }
  return card;
}
