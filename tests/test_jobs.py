import tempfile
import unittest
from pathlib import Path
from maxrunway.jobs import create_job, sha256


class JobsTests(unittest.TestCase):
    def test_unique_exports_cannot_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as folder:
            a, _ = create_job(folder, 'Camera/A', 0, 119, 24, 'video', 'Slow push')
            b, _ = create_job(folder, 'Camera/A', 0, 119, 24, 'video', 'Slow push')
            self.assertNotEqual(a, b)
            self.assertEqual(a.parent.parent, Path(folder).resolve())

    def test_invalid_duration_does_not_create_job(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'whole seconds'):
                create_job(folder, 'Camera', 0, 100, 24, 'video', 'Slow push')
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_native_full_range_does_not_have_ai_duration_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            _, job = create_job(folder, 'Camera', 0, 999, 24, 'native', '')
            self.assertEqual(job['lastFrame'], 999)

    def test_guided_shot_uses_inclusive_end_pose_and_sparse_anchors(self):
        with tempfile.TemporaryDirectory() as folder:
            job_path, job = create_job(folder, 'Orbit', 0, 240, 24, 'guided', 'Follow camera',
                                       anchor_count=8, loop=True)
            self.assertEqual(job['duration'], 10)
            self.assertEqual(job['anchorCount'], 8)
            self.assertTrue(job['loop'])
            self.assertTrue((job_path.parent / 'guide' / 'preview').is_dir())

    def test_guided_fractional_duration_is_rejected_before_folder_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, '0–240'):
                create_job(folder, 'Camera', 0, 239, 24, 'guided', 'Follow camera')
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_hash_detects_changed_material_master_file(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'frame.exr'
            file.write_bytes(b'original render')
            before = sha256(file)
            file.write_bytes(b'changed render')
            self.assertNotEqual(before, sha256(file))


if __name__ == '__main__':
    unittest.main()
