import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {loadTraffic} from './traffic.mjs';

const upstream = fileURLToPath(new URL('./vendor/metrics/', import.meta.url));
const capturedAt = '2026-10-07T06:01:52.473Z';

function fixtureSnapshot() {
  const repository = (name, counts, uniques) => ({
    name, fullName: `example/${name}`, public: true,
    traffic: {
      count: counts.reduce((sum, count) => sum + count, 0),
      uniques,
      views: counts.map((count, index) => ({
        timestamp: `2026-10-0${index + 5}T00:00:00Z`,
        count, uniques: 1,
      })),
    },
  });
  return {
    version: 1, login: 'example', capturedAt,
    sourceRevision: '366f8b9dfe3a59656c67d5dcad9950f59c9bc96d',
    repositories: [repository('alpha', [2, 3], 2), repository('public-fork', [3, 4], 3)],
  };
}

async function withFixture(run, {createSnapshot = true} = {}) {
  const tempRoot = path.resolve(os.tmpdir());
  const prefix = 'profile-traffic-test-';
  const directory = await fs.mkdtemp(path.join(tempRoot, prefix));
  const snapshotPath = path.join(directory, 'traffic-snapshot.json');
  const snapshot = fixtureSnapshot();
  const snapshotBytes = Buffer.from(`${JSON.stringify(snapshot, null, 2)}\n`);
  const originalFetch = globalThis.fetch;
  const savedEnvironment = Object.fromEntries(
    ['TRAFFIC_TOKEN', 'METRICS_TRAFFIC_USE_GH'].map(key => [key, process.env[key]]),
  );
  try {
    delete process.env.TRAFFIC_TOKEN;
    delete process.env.METRICS_TRAFFIC_USE_GH;
    globalThis.fetch = async () => { throw new Error('This test must not make a network request'); };
    if (createSnapshot) await fs.writeFile(snapshotPath, snapshotBytes);
    const publicRepos = snapshot.repositories.map(repo => ({
      name: repo.name, private: false, fork: repo.name === 'public-fork', owner: {login: 'example'},
    }));
    await run({
      snapshot, snapshotBytes, snapshotPath,
      args: {login: 'example', publicRepos, upstream, now: new Date('2026-10-10T12:00:00Z'), snapshotPath},
    });
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of Object.entries(savedEnvironment)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
    // Verify the exact generated directory before recursively removing test files.
    const resolved = path.resolve(directory);
    assert.equal(path.dirname(resolved), tempRoot);
    assert.ok(path.basename(resolved).startsWith(prefix));
    await fs.rm(resolved, {recursive: true, force: true});
  }
}

test('traffic snapshots and authenticated refresh failures', {concurrency: false}, async t => {
  await t.test('cached capture date stays unchanged and real view counts aggregate correctly', async () => {
    await withFixture(async ({args, snapshotPath, snapshotBytes}) => {
      const card = await loadTraffic(args);
      assert.equal(card.available, true);
      assert.equal(card.refreshed, false);
      assert.equal(card.capturedAt, capturedAt);
      assert.equal(card.totalViews, 12);
      assert.deepEqual(card.days, [{date: '2026-10-05', count: 5}, {date: '2026-10-06', count: 7}]);
      assert.deepEqual(card.period, {start: '2026-10-05', end: '2026-10-06'});
      assert.equal(card.repositoryCount, 2);
      assert.ok(card.repositories.some(repo => repo.name === 'public-fork'));
      assert.equal(Object.hasOwn(card, 'uniques'), false);
      assert.equal(Object.hasOwn(card, 'totalUniques'), false);
      assert.ok(card.repositories.every(repo => !Object.hasOwn(repo, 'uniques')));
      assert.deepEqual(await fs.readFile(snapshotPath), snapshotBytes);
    });
  });

  await t.test('cached repositories that are now private or removed do not appear', async () => {
    await withFixture(async ({args}) => {
      const publicRepos = args.publicRepos.map(repo => repo.name === 'public-fork' ? {...repo, private: true} : repo);
      const privateFiltered = await loadTraffic({...args, publicRepos});
      assert.equal(privateFiltered.totalViews, 5);
      assert.deepEqual(privateFiltered.repositories.map(repo => repo.name), ['alpha']);
      assert.deepEqual(privateFiltered.days.map(day => day.count), [2, 3]);

      const removed = await loadTraffic({...args, publicRepos: args.publicRepos.filter(repo => repo.name === 'alpha')});
      assert.equal(removed.totalViews, 5);
      assert.deepEqual(removed.repositories.map(repo => repo.name), ['alpha']);
    });
  });

  await t.test('missing token and snapshot produce unavailable data, never fabricated zero views', async () => {
    await withFixture(async ({args, snapshotPath}) => {
      const card = await loadTraffic(args);
      assert.equal(card.available, false);
      assert.equal(card.refreshed, false);
      assert.equal(Object.hasOwn(card, 'totalViews'), false);
      assert.equal(Object.hasOwn(card, 'days'), false);
      await assert.rejects(fs.access(snapshotPath), {code: 'ENOENT'});
    }, {createSnapshot: false});
  });

  await t.test('a 403 after one successful request retains the full original snapshot byte for byte', async () => {
    await withFixture(async ({args, snapshotPath, snapshotBytes}) => {
      process.env.TRAFFIC_TOKEN = 'test-placeholder-not-a-real-token';
      const requests = [];
      globalThis.fetch = async (url, options) => {
        requests.push(url);
        assert.equal(options.headers.Authorization, 'Bearer test-placeholder-not-a-real-token');
        assert.equal(options.redirect, 'error');
        if (requests.length === 1) {
          assert.equal(url, 'https://api.github.com/repos/example/alpha/traffic/views?per=day');
          return new Response(JSON.stringify({
            count: 99, uniques: 1,
            views: [{timestamp: '2026-10-10T00:00:00Z', count: 99, uniques: 1}],
          }), {status: 200, headers: {'Content-Type': 'application/json'}});
        }
        assert.equal(url, 'https://api.github.com/repos/example/public-fork/traffic/views?per=day');
        return new Response('', {status: 403});
      };
      const card = await loadTraffic(args);
      assert.equal(requests.length, 2);
      assert.equal(card.available, true);
      assert.equal(card.refreshed, false);
      assert.equal(card.totalViews, 12);
      assert.equal(card.capturedAt, capturedAt);
      assert.deepEqual(card.days.map(day => day.count), [5, 7]);
      assert.deepEqual(await fs.readFile(snapshotPath), snapshotBytes);
    });
  });
});
