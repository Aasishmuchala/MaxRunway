"""Portable job contract shared by the Max panel and the Runway companion."""
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def save_job(path, data):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def create_job(root, camera, first, last, fps, mode, prompt, duration=5,
               anchor_count=8, loop=False):
    if mode not in ('native', 'image', 'video', 'guided'):
        raise ValueError('Choose native, image, video, or guided mode.')
    if last < first or fps <= 0:
        raise ValueError('Invalid frame range or frame rate.')
    if mode == 'image' and not 4 <= int(duration) <= 15:
        raise ValueError('AI animation duration must be 4–15 whole seconds.')
    if mode == 'video':
        seconds = (last - first + 1) / fps
        if not 4 <= seconds <= 15 or abs(seconds - round(seconds)) > 0.001:
            raise ValueError('AI sequence input must be 4–15 whole seconds. Use FPS × seconds frames.')
    if mode == 'guided':
        seconds = (last - first) / fps
        if not 4 <= seconds <= 15 or abs(seconds - round(seconds)) > 0.001:
            raise ValueError('Guided AI shots must span 4–15 whole seconds. At 24 fps, 10 seconds is frames 0–240 inclusive.')
        if not 2 <= int(anchor_count) <= 9:
            raise ValueError('Use 2–9 native 4K appearance anchors.')
    if mode != 'native' and not prompt.strip():
        raise ValueError('Describe the desired camera or scene motion.')
    name = re.sub(r'[^\w-]', '_', str(camera))[:48] or 'camera'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    folder = Path(root).resolve() / (stamp + '_' + name + '_' + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True, exist_ok=False)
    for child in ('master', 'preview', 'elements', 'runway', 'analysis'):
        (folder / child).mkdir()
    if mode == 'guided':
        for child in ('guide/master', 'guide/preview', 'guide/elements'):
            (folder / child).mkdir(parents=True)
    data = {
        'schemaVersion': 1, 'createdAt': datetime.now(timezone.utc).isoformat(),
        'camera': str(camera), 'firstFrame': int(first), 'lastFrame': int(last),
        'fps': float(fps), 'width': 3840, 'height': 2160, 'mode': mode,
        'duration': int(round((last - first) / fps)) if mode == 'guided' else int(duration),
        'prompt': prompt.strip(), 'anchorCount': int(anchor_count), 'loop': bool(loop),
        'guideWidth': 640, 'guideHeight': 360,
        'status': 'created', 'frames': [], 'guideFrames': [], 'materialFidelityGuaranteed': False,
        'masterPolicy': 'Native V-Ray EXR files are retained; AI output is a separate interpretation.',
    }
    path = folder / 'job.json'
    save_job(path, data)
    return path, data
