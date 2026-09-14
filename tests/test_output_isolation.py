import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class OutputIsolationTests(unittest.TestCase):
    def runtime(self, values, readonly=()):
        writes = []
        renderer = dict(values)
        def set_property(obj, key, value):
            if key in readonly:
                raise RuntimeError('read-only property: ' + key)
            writes.append((key, value))
            obj[key] = value
        runtime = SimpleNamespace(
            renderers=SimpleNamespace(current=renderer),
            maxOps=SimpleNamespace(GetCurRenderElementMgr=lambda: SimpleNamespace(NumRenderElements=lambda: 0)),
            isProperty=lambda obj, key: key in obj,
            getProperty=lambda obj, key: obj[key],
            setProperty=set_property,
        )
        with patch.dict(sys.modules, {'pymxs': SimpleNamespace(runtime=runtime)}):
            spec = importlib.util.spec_from_file_location('maxrunway.native_isolation_test', ROOT / 'maxrunway/native.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module, renderer, writes

    def test_already_safe_readonly_gpu_flags_are_not_written(self):
        native, renderer, writes = self.runtime({'output_saveRawFile': False, 'output_splitgbuffer': False}, {'output_saveRawFile', 'output_splitgbuffer'})
        with native.isolated_output(Path('unused')):
            self.assertFalse(renderer['output_saveRawFile'])
        self.assertEqual(writes, [])

    def test_changed_cpu_flags_are_restored_after_body_failure(self):
        native, renderer, _ = self.runtime({'output_saveRawFile': True})
        with self.assertRaisesRegex(ValueError, 'render failed'):
            with native.isolated_output(Path('unused')):
                self.assertFalse(renderer['output_saveRawFile'])
                raise ValueError('render failed')
        self.assertTrue(renderer['output_saveRawFile'])

    def test_required_readonly_change_fails_closed_without_rewrite(self):
        native, renderer, writes = self.runtime({'output_saveRawFile': True}, {'output_saveRawFile'})
        with self.assertRaisesRegex(RuntimeError, 'read-only'):
            with native.isolated_output(Path('unused')):
                self.fail('Unsafe output state must not reach rendering')
        self.assertTrue(renderer['output_saveRawFile'])
        self.assertEqual(writes, [])

    def test_partial_override_failure_rolls_back_prior_successes(self):
        native, renderer, writes = self.runtime({'output_saveRawFile': True, 'output_splitgbuffer': True}, {'output_splitgbuffer'})
        with self.assertRaises(RuntimeError):
            with native.isolated_output(Path('unused')):
                self.fail('Unsafe override')
        self.assertEqual(renderer, {'output_saveRawFile': True, 'output_splitgbuffer': True})
        self.assertEqual(writes, [('output_saveRawFile', False), ('output_saveRawFile', True)])

    def test_loop_anchor_sampling_omits_duplicate_end_pose(self):
        native, _, _ = self.runtime({})
        self.assertEqual(native.anchor_scene_frames(0, 240, 8, loop=True),
                         [0, 30, 60, 90, 120, 150, 180, 210])

    def test_non_loop_anchor_sampling_includes_both_ends(self):
        native, _, _ = self.runtime({})
        anchors = native.anchor_scene_frames(10, 250, 8, loop=False)
        self.assertEqual((anchors[0], anchors[-1]), (10, 250))


if __name__ == '__main__':
    unittest.main()
