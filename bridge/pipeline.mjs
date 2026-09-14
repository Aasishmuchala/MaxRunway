import path from 'node:path';

function guidedPrompt(job) {
  const count = job.frames.length;
  const timings = job.frames.map((frame, index) => {
    const seconds = (frame.sceneFrame - job.firstFrame) / job.fps;
    return `Image ${index + 1} is native appearance evidence for ${seconds.toFixed(3)} seconds.`;
  }).join(' ');
  return `${job.prompt}\n\nVideo 1 is authoritative for every camera pose, timing, framing, lens, and occlusion order. ` +
    `The ${count} images are native V-Ray appearance evidence for the same unchanged scene, not new shots. ${timings} ` +
    `Use them only to restore existing geometry, material boundaries, texture scale, reflections, markings, lighting, and colour. ` +
    `Do not add, remove, redesign, relight, restyle, or rename anything. The camera alone follows Video 1.` +
    (job.loop ? ' Finish on the same camera pose where the shot began.' : '');
}

export function requestFor(job, sourceUrl, anchorUrls = []) {
  if (job.mode === 'native') throw new Error('Native master jobs must never be sent to a generative model.');
  if (!['image', 'video', 'guided'].includes(job.mode)) throw new Error('Unknown job mode.');
  if (job.width !== 3840 || job.height !== 2160) throw new Error('This prototype supports UHD 3840×2160 exports.');
  if (!job.prompt?.trim() || job.prompt.length > 3500) throw new Error('Enter a motion prompt of 1–3500 characters.');
  const promptText = job.mode === 'guided' ? guidedPrompt(job) : job.prompt;
  if (promptText.length > 3500) throw new Error('The guided prompt plus anchor instructions exceeds 3500 characters. Shorten the motion prompt.');
  const args = {model: 'seedance-2', promptText,
    resolution: '4k', generateAudio: false,
    rationale: 'Create a separate 4K cinematic version of the selected V-Ray render.'};
  if (job.mode === 'image') {
    if (!Number.isInteger(job.duration) || job.duration < 4 || job.duration > 15)
      throw new Error('AI duration must be 4–15 whole seconds.');
    Object.assign(args, {startFrame: {url: sourceUrl}, duration: job.duration, ratio: '16:9'});
  } else if (job.mode === 'video') {
    const seconds = job.frames.length / job.fps;
    if (seconds < 4 || seconds > 15 || Math.abs(seconds - Math.round(seconds)) > 0.001)
      throw new Error('Sequence duration must be 4–15 whole seconds.');
    if (job.frames.length !== job.lastFrame - job.firstFrame + 1)
      throw new Error('The rendered sequence is incomplete.');
    // Keep source timing: never silently set a shorter explicit duration.
    args.referenceVideo = {url: sourceUrl, durationSeconds: seconds};
  } else {
    if (job.guideFrames?.length !== job.lastFrame - job.firstFrame + 1)
      throw new Error('The full-rate guide is incomplete.');
    if (anchorUrls.length !== job.frames.length || anchorUrls.length < 2 || anchorUrls.length > 9)
      throw new Error('Guided generation requires every native 4K anchor (2–9 images).');
    if (!Number.isInteger(job.duration) || job.duration < 4 || job.duration > 15)
      throw new Error('Guided output duration must be 4–15 whole seconds.');
    Object.assign(args, {
      duration: job.duration, ratio: '16:9',
      referenceImages: anchorUrls.map(url => ({url})),
      referenceVideos: [{url: sourceUrl, durationSeconds: job.guideFrames.length / job.fps}],
    });
  }
  return args;
}

export function assertGuidedSchema(job, schema) {
  if (job.mode !== 'guided') return;
  const properties = schema?.properties ?? {};
  for (const name of ['referenceImages', 'referenceVideos']) {
    if (!Object.hasOwn(properties, name))
      throw new Error(`The live Runway MCP schema does not expose ${name}; guided submission is disabled before credits are spent.`);
  }
}

export function validateDelivery(meta, expectedDuration) {
  const problems = [];
  if (meta.width !== 3840 || meta.height !== 2160) problems.push('Output is not UHD 3840×2160.');
  if (!Number.isFinite(meta.duration) || Math.abs(meta.duration - expectedDuration) > 0.15)
    problems.push('Output duration differs from the requested shot.');
  return problems;
}

export async function runJob(job, deps) {
  const {mcp, save, log, folder, download, probe, verifySources, exists, sleep} = deps;
  requestFor(job, 'https://validation.invalid/source',
    job.mode === 'guided' ? job.frames.map((_, index) => `https://validation.invalid/anchor-${index}`) : []);
  if (job.status === 'submitting' && !job.taskId)
    throw new Error('Submission outcome is unknown. Check Runway history and recover the task ID; automatic resubmission is disabled.');
  if (job.status === 'remote_failed') throw new Error('This Runway task failed. Create a new export job to try again.');
  await verifySources(job);
  if (job.status === 'complete' || job.status === 'needs_review') return job;
  if (!job.taskId) {
    if (job.status !== 'ready') throw new Error('Prepare the source preview before submitting.');
    if (!mcp.identity?.availableVideoModels?.includes('seedance-2'))
      throw new Error('The required 4K video option is unavailable in this Runway workspace.');
    assertGuidedSchema(job, mcp.inputSchema?.('generate_video'));
    if (!job.uploadedSource) {
      log('Uploading the reviewed reference to Runway.');
      job.uploadedSource = await mcp.upload(job.source, job.mode === 'image' ? 'image/png' : 'video/mp4');
      await save(job);
    }
    if (job.mode === 'guided' && !job.uploadedAnchors) {
      job.uploadedAnchors = [];
      for (const frame of job.frames) {
        log(`Uploading native 4K anchor ${job.uploadedAnchors.length + 1}/${job.frames.length}.`);
        job.uploadedAnchors.push(await mcp.upload(frame.preview, 'image/png'));
        await save(job);
      }
    }
    const args = requestFor(job, job.uploadedSource, job.uploadedAnchors ?? []);
    job.status = 'submitting';
    await save(job); // Persist uncertainty BEFORE spending credits. Do not auto retry.
    const result = await mcp.call('generate_video', args);
    if (result.kind === 'account_limitation' || result.reason === 'paid_plan_required') {
      job.status = 'account_blocked';
      job.error = result.reason || 'Runway account limitation';
      await save(job);
      throw new Error(job.error);
    }
    if (!result.taskId) throw new Error('Submission returned no task ID. Check Runway before retrying.');
    job.taskId = result.taskId;
    job.status = 'submitted';
    await save(job);
  }
  log('Tracking Runway task ' + job.taskId + '. The task ID is saved for resume.');
  for (let attempts = 0; attempts < 90; attempts++) {
    const result = await mcp.call('get_task', {id: job.taskId});
    if (result.kind === 'task_failed' || ['FAILED', 'CANCELLED', 'CANCELED'].includes(result.status)) {
      job.status = 'remote_failed';
      job.error = result.error ?? result.errorInfo?.hint ?? 'Runway task failed.';
      await save(job);
      throw new Error(job.error);
    }
    if (result.kind === 'video' && result.url) {
      job.status = 'downloading';
      await save(job);
      const output = path.join(folder, 'runway', 'cinematic_4k.mp4');
      if (!await exists(output)) await download(result.url, output);
      const meta = await probe(output);
      await verifySources(job);
      job.output = output;
      job.outputMetadata = meta;
      const expectedDuration = job.mode === 'image' || job.mode === 'guided' ? job.duration : job.frames.length / job.fps;
      job.reviewFindings = validateDelivery(meta, expectedDuration);
      job.materialFidelityGuaranteed = false;
      job.status = job.reviewFindings.length ? 'needs_review' : 'complete';
      await save(job);
      log(job.reviewFindings.length ? job.reviewFindings.join(' ') : 'Downloaded and verified the 4K video dimensions and duration.');
      return job;
    }
    if (result.status === 'SUCCEEDED') throw new Error('Runway finished without a video URL. Resume after checking the task.');
    log('Runway: ' + (result.status ?? 'processing'));
    await sleep(60000);
  }
  throw new Error('Stopped tracking after 90 minutes. Use Resume to continue tracking this saved task.');
}
