import {readFile, writeFile, rename, open, unlink} from 'node:fs/promises';
import path from 'node:path';
import {RunwayMcp} from './mcp.mjs';
import {runJob} from './pipeline.mjs';
import {analyzeJob, testOmega} from './analysis.mjs';
import * as media from './media.mjs';

const log = message => process.stdout.write(JSON.stringify({message}) + '\n');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let mcp, lock, lockPath;
async function main() {
  const [action, filename, recoveryId] = process.argv.slice(2);
  if (action === 'connect') {
    mcp = new RunwayMcp(log);
    const identity = await mcp.connect();
    log('Connected to ' + (identity.team?.name ?? 'Runway') + '.');
    log(identity.availableVideoModels.includes('seedance-2') ? '4K generation is available.' : '4K generation is unavailable in this workspace.');
    return;
  }
  if (action === 'omega-test') {
    if (!filename) throw new Error('Omega settings JSON is required.');
    await testOmega(JSON.parse(filename));
    log('Omega Plus connection succeeded. This verifies chat/vision access, not image generation.');
    return;
  }
  if (!['prepare', 'submit', 'resume', 'analyze'].includes(action) || !filename)
    throw new Error('Usage: node cli.mjs connect | prepare/submit/resume/analyze path/to/job.json [provider-or-recovery-id]');
  const file = path.resolve(filename);
  const folder = path.dirname(file);
  lockPath = path.join(folder, '.bridge.lock');
  try { lock = await open(lockPath, 'wx'); }
  catch { throw new Error('This job is already open in another process. A stale .bridge.lock can be removed only after confirming that process has exited.'); }
  await lock.writeFile(String(process.pid));
  const job = JSON.parse(await readFile(file, 'utf8'));
  if (job.schemaVersion !== 1) throw new Error('Unsupported job format.');
  const save = async data => {
    await writeFile(file + '.tmp', JSON.stringify(data, null, 2));
    await rename(file + '.tmp', file);
  };
  if (action === 'analyze') {
    const settings = JSON.parse(process.env.MAXRUNWAY_ANALYSIS_SETTINGS || '{}');
    await analyzeJob(file, recoveryId || settings.analysisProvider || 'codex', settings, log);
    return;
  }
  if (action === 'prepare') {
    if (!['rendered', 'ready'].includes(job.status)) throw new Error('Only completed native exports can be prepared.');
    await media.verifySources(job);
    if (job.mode === 'video' && job.frames.length !== job.lastFrame - job.firstFrame + 1)
      throw new Error('The rendered frame sequence is incomplete.');
    if (job.mode === 'image') job.source = job.frames[0].preview;
    else if (job.mode === 'guided') {
      log('Encoding the full-rate native camera guide. Sparse 4K anchors remain separate.');
      job.source = await media.encodeGuide(job, folder);
      job.sourceMetadata = await media.probe(job.source);
      if (job.sourceMetadata.width !== job.guideWidth || job.sourceMetadata.height !== job.guideHeight)
        throw new Error('The camera guide has unexpected dimensions.');
    }
    else {
      log('Encoding the native review clip. EXR masters are retained.');
      job.source = await media.encodePreview(job, folder);
      job.sourceMetadata = await media.probe(job.source);
      if (job.sourceMetadata.width !== job.width || job.sourceMetadata.height !== job.height)
        throw new Error('The review clip has unexpected dimensions.');
    }
    job.sourceSha256 = await media.digest(job.source);
    job.status = job.mode === 'native' ? 'native_complete' : 'ready';
    await save(job);
    log('Ready for review: ' + job.source);
    return;
  }
  if (recoveryId) {
    if (job.status !== 'submitting' || job.taskId) throw new Error('A recovery ID is only valid for an uncertain submission.');
    if (!/^[\w-]{8,120}$/.test(recoveryId)) throw new Error('Invalid task ID.');
    job.taskId = recoveryId;
    job.status = 'submitted';
    await save(job);
  }
  if (job.mode === 'native') throw new Error('Native jobs do not use Runway.');
  if (await media.digest(job.source) !== job.sourceSha256) throw new Error('The reviewed source changed. Create a new job.');
  mcp = new RunwayMcp(log);
  await mcp.connect();
  await runJob(job, {...media, mcp, save, log, folder, sleep});
}

try { await main(); }
catch (error) {
  log('Error: ' + String(error.message).replace(/https?:\/\/\S+/g, '[link]'));
  process.exitCode = 1;
}
finally {
  await mcp?.close();
  if (lock) { await lock.close(); await unlink(lockPath); }
}
