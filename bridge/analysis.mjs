import {spawn} from 'node:child_process';
import {mkdir, readFile, rename, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {digest, exists, probe} from './media.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const REVIEW_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['visualVerdict', 'scores', 'findings', 'summary'],
  properties: {
    visualVerdict: {type: 'string', enum: ['similar', 'changed', 'unusable']},
    scores: {
      type: 'object', additionalProperties: false,
      required: ['geometry', 'materials', 'lighting', 'colour', 'motionContinuity'],
      properties: {
        geometry: {type: 'integer', minimum: 0, maximum: 100},
        materials: {type: 'integer', minimum: 0, maximum: 100},
        lighting: {type: 'integer', minimum: 0, maximum: 100},
        colour: {type: 'integer', minimum: 0, maximum: 100},
        motionContinuity: {type: 'integer', minimum: 0, maximum: 100},
      },
    },
    findings: {type: 'array', maxItems: 12, items: {type: 'string', maxLength: 500}},
    summary: {type: 'string', maxLength: 1000},
  },
};

function safeMessage(value) {
  return String(value ?? '').replace(/https?:\/\/\S+/g, '[link]')
    .replace(/(?:(?:bearer|token|api[_ -]?key)\s*[:=]\s*)\S+/gi, '[credential redacted]')
    .slice(0, 1600);
}

function run(program, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(program, args, {
      cwd: options.cwd, env: options.env ?? process.env, windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '', stderr = '';
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(options.timeoutMessage ?? 'The analysis process timed out.'));
    }, options.timeout ?? 240000);
    child.stdout.on('data', data => { stdout = (stdout + data).slice(-4000); });
    child.stderr.on('data', data => { stderr = (stderr + data).slice(-4000); });
    child.on('error', error => { clearTimeout(timer); reject(error); });
    child.on('close', code => {
      clearTimeout(timer);
      if (code === 0) resolve(stdout);
      else reject(new Error(safeMessage(stderr || stdout || `${program} exited with code ${code}`)));
    });
  });
}

function parseJsonText(value) {
  if (Array.isArray(value)) value = value.map(item => item?.text ?? '').join('');
  const text = String(value ?? '').trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  const start = text.indexOf('{'), end = text.lastIndexOf('}');
  if (start < 0 || end <= start) throw new Error('The analysis provider returned no JSON object.');
  return JSON.parse(text.slice(start, end + 1));
}

export function validateReview(review) {
  if (!review || !['similar', 'changed', 'unusable'].includes(review.visualVerdict))
    throw new Error('The analysis provider returned an invalid visual verdict.');
  const names = ['geometry', 'materials', 'lighting', 'colour', 'motionContinuity'];
  for (const name of names) {
    const score = review.scores?.[name];
    if (!Number.isInteger(score) || score < 0 || score > 100)
      throw new Error('The analysis provider returned an invalid score.');
  }
  if (!Array.isArray(review.findings) || review.findings.some(item => typeof item !== 'string'))
    throw new Error('The analysis provider returned invalid findings.');
  if (typeof review.summary !== 'string') throw new Error('The analysis provider returned no summary.');
  return {
    visualVerdict: review.visualVerdict,
    scores: Object.fromEntries(names.map(name => [name, review.scores[name]])),
    findings: review.findings.slice(0, 12).map(item => item.slice(0, 500)),
    summary: review.summary.slice(0, 1000),
  };
}

async function saveJob(filename, job) {
  const temp = filename + '.analysis.tmp';
  await writeFile(temp, JSON.stringify(job, null, 2));
  await rename(temp, filename);
}

export function samplePlan(job, duration, count = 4) {
  const frames = job.frames ?? [];
  if (!frames.length) throw new Error('The job has no native preview frames.');
  const usableDuration = Math.max(0, duration - 1 / Math.max(1, job.fps || 24));
  return Array.from({length: count}, (_, index) => {
    const fraction = count === 1 ? 0 : index / (count - 1);
    const nativeIndex = job.mode === 'image' ? 0 : Math.round(fraction * (frames.length - 1));
    return {fraction, seconds: fraction * usableDuration, native: frames[nativeIndex].preview};
  });
}

async function buildEvidence(job, folder, log) {
  if (!job.output || !await exists(job.output)) throw new Error('A completed AI video is required for analysis.');
  const metadata = await probe(job.output);
  const analysisDir = path.join(folder, 'analysis');
  await mkdir(analysisDir, {recursive: true});
  const files = [];
  for (const [index, sample] of samplePlan(job, metadata.duration).entries()) {
    const output = path.join(analysisDir, `evidence_${String(index).padStart(2, '0')}.jpg`);
    const filter = '[0:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:black[n];' +
      '[1:v]scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:black[a];' +
      '[n][a]hstack=inputs=2[out]';
    await run('ffmpeg', ['-y', '-v', 'error', '-i', sample.native, '-ss', sample.seconds.toFixed(6),
      '-i', job.output, '-filter_complex', filter, '-map', '[out]', '-frames:v', '1', '-q:v', '3', output],
      {cwd: folder, timeout: 120000, timeoutMessage: 'FFmpeg evidence extraction timed out.'});
    if (!await exists(output)) throw new Error('FFmpeg did not create analysis evidence.');
    files.push(output);
  }
  log(`Prepared ${files.length} side-by-side comparisons (native V-Ray left, AI video right).`);
  return {files, metadata};
}

function reviewPrompt(job) {
  return `Act as a strict architectural-VFX quality-control reviewer. Each attached comparison has the native V-Ray render on the LEFT and the generated video at the matching time on the RIGHT.

Judge only visible evidence. Look for changed geometry, proportions, camera path, texture scale or identity, wood/stone/glass/metal response, reflections, foliage, lighting direction, exposure, white balance, temporal instability, invented objects, text changes, and seams. A 4K file is not proof of fidelity. Use 100 only for indistinguishable visible agreement. Mark visualVerdict "changed" for any material or geometry drift that would matter in a premium archviz film, and "unusable" for major drift. The camera is ${job.camera}; native frames ${job.firstFrame}-${job.lastFrame} at ${job.fps} fps. Return only the required JSON.`;
}

async function codexReview(job, folder, evidence) {
  const analysisDir = path.join(folder, 'analysis');
  const schema = path.join(analysisDir, 'review-schema.json');
  const response = path.join(analysisDir, 'codex-review.json');
  await writeFile(schema, JSON.stringify(REVIEW_SCHEMA, null, 2));
  const codex = process.env.CODEX_CLI_PATH || 'codex';
  const args = ['exec', '--skip-git-repo-check', '--ephemeral', '--sandbox', 'read-only',
    '--output-schema', schema, '--output-last-message', response, '-C', folder];
  for (const file of evidence) args.push('-i', file);
  // -- terminates the variadic -i option before the positional prompt.
  args.push('--', reviewPrompt(job));
  await run(codex, args, {cwd: folder, timeout: 600000, timeoutMessage: 'ChatGPT/Codex analysis timed out.'});
  return validateReview(parseJsonText(await readFile(response, 'utf8')));
}

async function omegaRequest(endpoint, key, body, timeout = 240000) {
  const url = new URL(endpoint);
  if (url.protocol !== 'https:' || url.username || url.password)
    throw new Error('Omega endpoint must use HTTPS without embedded credentials.');
  const response = await fetch(url, {
    method: 'POST', signal: AbortSignal.timeout(timeout),
    headers: {'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`Omega Plus rejected the request (HTTP ${response.status}).`);
  let payload;
  try { payload = JSON.parse(text); } catch { throw new Error('Omega Plus returned invalid JSON.'); }
  return payload;
}

async function omegaReview(job, evidence, settings) {
  const key = process.env.OMEGAPLUS_API_KEY;
  if (!key) throw new Error('No Omega Plus key is available in Windows Credential Manager.');
  const content = [{type: 'text', text: reviewPrompt(job)}];
  for (const file of evidence) {
    const image = (await readFile(file)).toString('base64');
    content.push({type: 'image_url', image_url: {url: `data:image/jpeg;base64,${image}`}});
  }
  const payload = await omegaRequest(settings.omegaEndpoint, key, {
    model: settings.omegaModel, temperature: 0, max_tokens: 1600,
    response_format: {type: 'json_object'}, messages: [{role: 'user', content}],
  });
  return validateReview(parseJsonText(payload.choices?.[0]?.message?.content));
}

export async function testOmega(settings) {
  const key = process.env.OMEGAPLUS_API_KEY;
  if (!key) throw new Error('Save an Omega Plus API key first.');
  const payload = await omegaRequest(settings.omegaEndpoint, key, {
    model: settings.omegaModel, temperature: 0, max_tokens: 8,
    messages: [{role: 'user', content: 'Reply with exactly: connected'}],
  }, 60000);
  if (!payload.choices?.[0]?.message) throw new Error('Omega Plus returned an unexpected response.');
  return true;
}

export async function analyzeJob(filename, provider, settings, log = () => {}) {
  const file = path.resolve(filename), folder = path.dirname(file);
  const job = JSON.parse(await readFile(file, 'utf8'));
  if (job.schemaVersion !== 1) throw new Error('Unsupported job format.');
  if (!['complete', 'needs_review'].includes(job.status))
    throw new Error('Finish and download the generated video before AI analysis.');
  const before = await digest(job.output);
  const {files, metadata} = await buildEvidence(job, folder, log);
  const review = provider === 'codex' ? await codexReview(job, folder, files)
    : provider === 'omega' ? await omegaReview(job, files, settings)
      : (() => { throw new Error('Unknown analysis provider.'); })();
  if (before !== await digest(job.output)) throw new Error('The AI video changed during analysis.');
  const deliveryPass = metadata.width === 3840 && metadata.height === 2160 &&
    !(job.reviewFindings ?? []).length;
  const result = {
    schemaVersion: 1, provider, createdAt: new Date().toISOString(),
    evidence: files.map(file => path.relative(folder, file)),
    outputSha256: before, deliveryPass,
    visualReview: review,
    materialFidelityVerified: false,
    finalGate: deliveryPass && review.visualVerdict === 'similar' ? 'manual_material_review_required' : 'failed',
    limitation: 'Pixel comparison cannot prove preservation of V-Ray shaders, UVs, textures, geometry, lighting, or render elements.',
  };
  const resultPath = path.join(folder, 'analysis', `${provider}-analysis.json`);
  await writeFile(resultPath, JSON.stringify(result, null, 2));
  job.aiAnalysis = result;
  job.materialFidelityGuaranteed = false;
  await saveJob(file, job);
  log(`Analysis saved. Gate: ${result.finalGate}. Material fidelity remains unverified.`);
  return result;
}
