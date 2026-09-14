import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {createReadStream, createWriteStream} from 'node:fs';
import {access, rename} from 'node:fs/promises';
import {Readable} from 'node:stream';
import {pipeline} from 'node:stream/promises';
import path from 'node:path';

export async function digest(file) {
  const hash = createHash('sha256');
  for await (const part of createReadStream(file)) hash.update(part);
  return hash.digest('hex');
}

export async function verifySources(job) {
  if (!job.frames?.length) throw new Error('Render the job before preparing a Runway request.');
  const verify = async frames => {
    for (let i = 0; i < frames.length; i++) {
      const f = frames[i];
      if (f.index !== i) throw new Error('The exported frame sequence has a gap.');
      if (await digest(f.master) !== f.masterSha256 || await digest(f.preview) !== f.previewSha256)
        throw new Error('An exported frame changed. Create a new job before continuing.');
    }
  };
  await verify(job.frames);
  if (job.mode === 'guided') {
    if (job.guideFrames?.length !== job.lastFrame - job.firstFrame + 1)
      throw new Error('The full-rate camera guide is incomplete.');
    await verify(job.guideFrames);
  }
}

export function command(program, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(program, args, {windowsHide: true, shell: false});
    let stdout = '', stderr = '';
    child.stdout.on('data', b => { stdout = (stdout + b).slice(-1000000); });
    child.stderr.on('data', b => { stderr = (stderr + b).slice(-8000); });
    child.on('error', () => reject(new Error(program + ' is unavailable. Add it to PATH and restart 3ds Max.')));
    child.on('close', code => code === 0 ? resolve(stdout) : reject(new Error(program + ' failed: ' + stderr.slice(-2000))));
  });
}

export async function probe(file) {
  const info = JSON.parse(await command(process.env.MAXRUNWAY_FFPROBE || 'ffprobe',
    ['-v', 'error', '-select_streams', 'v:0', '-show_streams', '-show_format', '-of', 'json', file]));
  const stream = info.streams?.[0];
  if (!stream) throw new Error('No video stream found.');
  return {width: stream.width, height: stream.height,
    duration: Number(stream.duration ?? info.format?.duration),
    frameRate: stream.avg_frame_rate, codec: stream.codec_name, pixelFormat: stream.pix_fmt};
}

export async function exists(file) { try { await access(file); return true; } catch { return false; } }

export async function encodePreview(job, folder) {
  const output = path.join(folder, 'preview', 'native_review.mp4');
  if (await exists(output)) return output;
  const temp = path.join(folder, 'preview', 'native_review.partial.mp4');
  await command(process.env.MAXRUNWAY_FFMPEG || 'ffmpeg', ['-hide_banner', '-loglevel', 'error', '-n',
    '-framerate', String(job.fps), '-start_number', '0',
    '-i', path.join(folder, 'preview', 'frame_%06d.png'), '-frames:v', String(job.frames.length),
    '-vf', 'scale=in_range=full:out_range=tv:out_color_matrix=bt709',
    '-c:v', 'libx264', '-crf', '12', '-preset', 'medium', '-pix_fmt', 'yuv420p',
    '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709',
    '-color_trc', 'bt709', '-movflags', '+faststart', temp]);
  await rename(temp, output);
  return output;
}

export async function encodeGuide(job, folder) {
  if (job.mode !== 'guided') throw new Error('Only guided jobs have a camera guide.');
  const output = path.join(folder, 'preview', 'camera_guide_24fps.mp4');
  if (await exists(output)) return output;
  const temp = path.join(folder, 'preview', 'camera_guide_24fps.partial.mp4');
  await command(process.env.MAXRUNWAY_FFMPEG || 'ffmpeg', ['-hide_banner', '-loglevel', 'error', '-n',
    '-framerate', String(job.fps), '-start_number', '0',
    '-i', path.join(folder, 'guide', 'preview', 'frame_%06d.png'),
    '-frames:v', String(job.guideFrames.length),
    '-vf', `scale=${job.guideWidth}:${job.guideHeight}:force_original_aspect_ratio=decrease,pad=${job.guideWidth}:${job.guideHeight}:(ow-iw)/2:(oh-ih)/2:black`,
    '-c:v', 'libx264', '-crf', '15', '-preset', 'medium', '-pix_fmt', 'yuv420p',
    '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709',
    '-color_trc', 'bt709', '-movflags', '+faststart', temp]);
  await rename(temp, output);
  return output;
}

export async function download(url, file) {
  if (await exists(file)) throw new Error('Output already exists; refusing to replace it.');
  if (new URL(url).protocol !== 'https:') throw new Error('Runway download must use HTTPS.');
  const response = await fetch(url, {signal: AbortSignal.timeout(600000)});
  if (!response.ok || !response.body) throw new Error('Download failed: HTTP ' + response.status);
  const type = response.headers.get('content-type') ?? '';
  if (/text\/|application\/json/.test(type)) throw new Error('Runway returned a document instead of a video.');
  const temporary = file + '.' + Date.now() + '.partial';
  await pipeline(Readable.fromWeb(response.body), createWriteStream(temporary, {flags: 'wx'}));
  await rename(temporary, file);
}
