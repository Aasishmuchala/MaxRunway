"""All 3ds Max access stays on the Max main thread. No network work here."""
from contextlib import contextmanager
from pathlib import Path
import re

from pymxs import runtime as rt
from .jobs import save_job, sha256


def cameras():
    return [c for c in rt.cameras if rt.superClassOf(c) == rt.Camera]


def renderer_name():
    return str(rt.classOf(rt.renderers.current))


def preflight():
    name = renderer_name()
    if 'vray' not in re.sub(r'[^a-z]', '', name.lower()):
        raise RuntimeError('Select V-Ray as the production renderer in Render Setup. Current: ' + name)
    if not cameras():
        raise RuntimeError('Create a scene camera before exporting a cinematic.')
    return name


@contextmanager
def isolated_output(folder):
    """Temporarily route V-Ray and Max element output to this fresh job."""
    renderer = rt.renderers.current
    old = {}
    elements = rt.maxOps.GetCurRenderElementMgr()
    filenames = []
    try:
        overrides = {
            'output_saveRawFile': False, 'output_splitgbuffer': False,
            'output_saveFile': False, 'output_fileOnly': False,
            'output_on': False, 'output_getsetsfrommax': True,
            'output_resumableRendering': False, 'output_progressiveAutoSave': 0.0,
        }
        for key, value in overrides.items():
            if rt.isProperty(renderer, key):
                previous = rt.getProperty(renderer, key)
                # GPU can expose an already-disabled CPU output flag read-only.
                # Do not write a no-op, but fail closed if a required change fails.
                if previous == value:
                    continue
                rt.setProperty(renderer, key, value)
                old[key] = previous
        # Rendering without outputfile keeps the native master under our control.
        # Existing element destinations are also redirected to prevent overwrites.
        for i in range(elements.NumRenderElements()):
            filenames.append((i, elements.GetRenderElementFilename(i)))
            elements.SetRenderElementFilename(i, str(folder / ('element_%02d.exr' % i)))
        yield
    finally:
        for i, filename in filenames:
            elements.SetRenderElementFilename(i, filename)
        for key, value in old.items():
            rt.setProperty(renderer, key, value)


def export_frame(camera, frame, folder, index, width=3840, height=2160,
                 master_dir='master', preview_dir='preview', element_dir='elements'):
    folder = Path(folder)
    master = folder / master_dir / ('frame_%06d.exr' % index)
    preview = folder / preview_dir / ('frame_%06d.png' % index)
    if master.exists() or preview.exists():
        raise FileExistsError('This frame already exists. Create a new export job.')
    element_folder = folder / element_dir / ('frame_%06d' % index)
    element_folder.mkdir(parents=True, exist_ok=False)
    # MAXScript helper handles its by-reference cancellation flag explicitly.
    render_one = rt.execute('''
    (fn maxRunwayRenderOne cam fr w h = (
        local wasCancelled = false
        local bm = render camera:cam frame:fr outputwidth:w outputheight:h pixelaspect:1.0 renderType:#normal outputHDRbitmap:true vfb:false progressbar:true cancelled:&wasCancelled quiet:true missingExtFilesAction:#abort missingUVWAction:#abort
        #(bm, wasCancelled)
    ))
    ''')
    bitmap = None
    with isolated_output(element_folder):
        try:
            bitmap, cancelled = render_one(camera, frame, width, height)
            if cancelled or bitmap is None:
                raise RuntimeError('Render cancelled; incomplete frame was not accepted.')
            if int(bitmap.width) != width or int(bitmap.height) != height:
                raise RuntimeError('Renderer returned unexpected dimensions.')
            bitmap.filename = str(master)
            rt.SetOutputColorConversion(bitmap, rt.Name('noConversion'))
            if not rt.save(bitmap):
                raise RuntimeError('Could not save the EXR master.')
            color_space = str(bitmap.colorSpace)
            bitmap.filename = str(preview)
            rt.SetOutputColorConversion(bitmap, rt.Name('automatic'))
            if not rt.save(bitmap):
                raise RuntimeError('Could not save the PNG review frame.')
        finally:
            if bitmap is not None:
                rt.close(bitmap)
    for path in (master, preview):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError('Missing or empty render output: ' + str(path))
    return {
        'index': index, 'sceneFrame': frame,
        'master': str(master), 'preview': str(preview),
        'masterSha256': sha256(master), 'previewSha256': sha256(preview),
        'renderColorSpace': color_space,
    }


def anchor_scene_frames(first, last, count, loop=False):
    """Evenly distribute appearance anchors; loops omit the duplicate final pose."""
    denominator = count if loop else count - 1
    return [int(round(first + (last - first) * index / denominator)) for index in range(count)]


def render_job(path, job, camera, on_progress=lambda *args: None, cancelled=lambda: False):
    job['renderer'] = preflight()
    job['maxVersion'] = str(rt.maxVersion())
    job['scenePath'] = str(rt.maxFilePath) + str(rt.maxFileName)
    job['status'] = 'rendering'
    save_job(path, job)
    if job['mode'] == 'guided':
        guide = list(range(job['firstFrame'], job['lastFrame'] + 1))
        anchors = anchor_scene_frames(job['firstFrame'], job['lastFrame'], job['anchorCount'], job.get('loop', False))
        work = [('guide', frame) for frame in guide] + [('anchor', frame) for frame in anchors]
    else:
        frames = [job['firstFrame']] if job['mode'] == 'image' else range(job['firstFrame'], job['lastFrame'] + 1)
        work = [('master', frame) for frame in frames]
    try:
        guide_index = anchor_index = 0
        for progress_index, (kind, frame) in enumerate(work):
            if cancelled():
                raise RuntimeError('Export cancelled between frames.')
            on_progress(progress_index, len(work), frame)
            if kind == 'guide':
                result = export_frame(camera, frame, Path(path).parent, guide_index,
                                      job['guideWidth'], job['guideHeight'],
                                      'guide/master', 'guide/preview', 'guide/elements')
                job['guideFrames'].append(result)
                guide_index += 1
            else:
                result = export_frame(camera, frame, Path(path).parent, anchor_index,
                                      job['width'], job['height'])
                job['frames'].append(result)
                anchor_index += 1
            save_job(path, job)
        job['status'] = 'rendered'
        save_job(path, job)
    except Exception as exc:
        job['status'] = 'render_failed'
        job['error'] = str(exc)
        save_job(path, job)
        raise
    return job
