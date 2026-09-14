import test from 'node:test';
import assert from 'node:assert/strict';
import {requestFor, runJob, validateDelivery} from '../pipeline.mjs';
import {unpack, toolName} from '../mcp.mjs';

function job(mode = 'image') {
  return {schemaVersion: 1, mode, status: 'ready', width: 3840, height: 2160,
    prompt: 'A slow camera move.', duration: 5, fps: 24, firstFrame: 0, lastFrame: 119,
    source: 'source.png', frames: Array.from({length: mode === 'image' ? 1 : 120}, (_, i) => ({index: i}))};
}

function guidedJob() {
  return {...job('guided'), lastFrame: 120, duration: 5, loop: false,
    guideFrames: Array.from({length: 121}, (_, index) => ({index})),
    frames: Array.from({length: 8}, (_, index) => ({index, sceneFrame: Math.round(index * 120 / 7), preview: `anchor-${index}.png`})),
    source: 'guide.mp4'};
}

function harness(options = {}) {
  const calls = [], snapshots = [];
  const deps = {
    folder: 'job', save: async j => snapshots.push(structuredClone(j)), log: () => {},
    sleep: async () => {}, exists: async () => false, download: async () => {},
    probe: async () => ({width: 3840, height: 2160, duration: 5}), verifySources: async () => {},
    mcp: {
      identity: {availableVideoModels: ['seedance-2']},
      inputSchema: () => ({properties: {referenceImages: {}, referenceVideos: {}}}),
      upload: async () => 'https://example.com/upload.png',
      call: async (name, args) => {
        calls.push({name, args});
        if (options.failSubmit && name === 'generate_video') throw new Error('connection lost');
        if (name === 'generate_video') return {kind: 'task_pending', taskId: 'task-12345'};
        return options.result ?? {kind: 'video', status: 'SUCCEEDED', url: 'https://example.com/video.mp4'};
      },
    },
  };
  return {deps, calls, snapshots};
}

test('native master is never submitted to a generative model', () => {
  assert.throws(() => requestFor(job('native'), 'https://example.com'), /never/);
});
test('explicit 4K request uses native 4K option and exact still duration', () => {
  const request = requestFor(job(), 'https://example.com/a.png');
  assert.equal(request.resolution, '4k');
  assert.equal(request.duration, 5);
  assert.equal(request.startFrame.url, 'https://example.com/a.png');
});
test('cinematic source duration is provided without a truncating duration override', () => {
  const request = requestFor(job('video'), 'https://example.com/a.mp4');
  assert.equal(request.referenceVideo.durationSeconds, 5);
  assert.equal(request.duration, undefined);
});
test('guided request uses every full-rate pose and every sparse 4K anchor', () => {
  const j = guidedJob();
  const anchors = j.frames.map((_, index) => `https://example.com/anchor-${index}.png`);
  const request = requestFor(j, 'https://example.com/guide.mp4', anchors);
  assert.equal(request.referenceVideos[0].durationSeconds, 121 / 24);
  assert.equal(request.referenceImages.length, 8);
  assert.equal(request.duration, 5);
  assert.match(request.promptText, /Video 1 is authoritative/);
  assert.match(request.promptText, /Do not add, remove, redesign/);
});
test('guided submission fails before upload when live MCP lacks reference arrays', async () => {
  const h = harness();
  let uploads = 0;
  h.deps.mcp.inputSchema = () => ({properties: {referenceVideo: {}}});
  h.deps.mcp.upload = async () => { uploads++; return 'https://example.com/upload'; };
  await assert.rejects(runJob(guidedJob(), h.deps), /referenceImages/);
  assert.equal(uploads, 0);
  assert.equal(h.calls.length, 0);
});
test('reject incomplete, fractional, or unsupported sequence duration', () => {
  const j = job('video');
  j.frames.pop();
  assert.throws(() => requestFor(j, 'url'), /whole seconds/);
  j.frames = Array.from({length: 96});
  assert.throws(() => requestFor(j, 'url'), /incomplete/);
});
test('job persists task ID and checks returned dimensions before completion', async () => {
  const h = harness();
  const j = await runJob(job(), h.deps);
  assert.equal(j.status, 'complete');
  assert.equal(j.materialFidelityGuaranteed, false);
  assert.ok(h.snapshots.some(s => s.status === 'submitting' && !s.taskId));
  assert.ok(h.snapshots.some(s => s.status === 'submitted' && s.taskId === 'task-12345'));
});
test('resuming an existing task never creates another generation', async () => {
  const h = harness();
  await runJob({...job(), status: 'submitted', taskId: 'existing-id'}, h.deps);
  assert.equal(h.calls.filter(x => x.name === 'generate_video').length, 0);
});
test('uncertain paid submission cannot be automatically retried', async () => {
  const h = harness({failSubmit: true});
  const j = job();
  await assert.rejects(runJob(j, h.deps), /connection lost/);
  assert.equal(j.status, 'submitting');
  await assert.rejects(runJob(j, h.deps), /unknown/);
  assert.equal(h.calls.filter(x => x.name === 'generate_video').length, 1);
});
test('changed source aborts before upload or credit spending', async () => {
  const h = harness();
  h.deps.verifySources = async () => { throw new Error('source changed'); };
  await assert.rejects(runJob(job(), h.deps), /changed/);
  assert.equal(h.calls.length, 0);
});
test('remote failure persists and is not treated as success', async () => {
  const h = harness({result: {kind: 'task_failed', error: 'invalid source'}});
  const j = job();
  await assert.rejects(runJob(j, h.deps), /invalid source/);
  assert.equal(j.status, 'remote_failed');
});
test('1080p delivered as 4K is flagged for review', async () => {
  const h = harness();
  h.deps.probe = async () => ({width: 1920, height: 1080, duration: 5});
  const j = await runJob(job(), h.deps);
  assert.equal(j.status, 'needs_review');
  assert.match(j.reviewFindings[0], /not UHD/);
});
test('duration mismatch is reported separately from spatial resolution', () => {
  assert.match(validateDelivery({width: 3840, height: 2160, duration: 4}, 5)[0], /duration/);
});
test('account availability prevents an unsupported paid submission', async () => {
  const h = harness();
  h.deps.mcp.identity.availableVideoModels = [];
  await assert.rejects(runJob(job(), h.deps), /unavailable/);
  assert.equal(h.calls.length, 0);
});
test('MCP result parsing supports structured and JSON-text results', () => {
  assert.deepEqual(unpack({structuredContent: {authenticated: true}}), {authenticated: true});
  assert.deepEqual(unpack({content: [{type: 'text', text: '{"taskId":"a"}'}]}), {taskId: 'a'});
  assert.throws(() => unpack({content: []}), /structured/);
});
test('exact tool matching rejects missing or ambiguous server schemas', () => {
  assert.equal(toolName([{name: 'runway_generate_video'}], 'generate_video'), 'runway_generate_video');
  assert.throws(() => toolName([{name: 'generate_video'}, {name: 'runway_generate_video'}], 'generate_video'), /ambiguous/);
});
