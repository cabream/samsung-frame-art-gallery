import tempfile
import unittest
from pathlib import Path
from fastapi import HTTPException

from src.api.images import get_safe_path as get_safe_path_images
from src.api.tv import get_safe_path as get_safe_path_tv


class PathSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.images_dir = Path(self.temp_dir.name).resolve()

        # Patch IMAGES_DIR in both modules
        import src.api.images as api_images
        import src.api.tv as api_tv

        self.orig_images_dir = api_images.IMAGES_DIR
        self.orig_tv_images_dir = api_tv.IMAGES_DIR

        api_images.IMAGES_DIR = self.images_dir
        api_tv.IMAGES_DIR = self.images_dir

    def tearDown(self):
        import src.api.images as api_images
        import src.api.tv as api_tv

        api_images.IMAGES_DIR = self.orig_images_dir
        api_tv.IMAGES_DIR = self.orig_tv_images_dir
        self.temp_dir.cleanup()

    def test_safe_paths_allowed(self):
        for fn in [get_safe_path_images, get_safe_path_tv]:
            with self.subTest(fn=fn.__module__):
                res = fn("test.jpg")
                self.assertEqual(res, self.images_dir / "test.jpg")
                res_sub = fn("sub/folder/pic.jpeg")
                self.assertEqual(res_sub, self.images_dir / "sub" / "folder" / "pic.jpeg")

    def test_directory_traversal_escaping_root_rejected(self):
        for fn in [get_safe_path_images, get_safe_path_tv]:
            with self.subTest(fn=fn.__module__):
                with self.assertRaises(HTTPException) as cm:
                    fn("../outside.jpg")
                self.assertEqual(cm.exception.status_code, 403)
                self.assertEqual(cm.exception.detail, "Access denied")

    def test_sibling_directory_prefix_bypass_rejected(self):
        # A sibling directory whose name starts with the same string as images_dir
        sibling_dir_name = f"{self.images_dir.name}_extra"
        evil_relative = f"../{sibling_dir_name}/secret.jpg"

        for fn in [get_safe_path_images, get_safe_path_tv]:
            with self.subTest(fn=fn.__module__):
                with self.assertRaises(HTTPException) as cm:
                    fn(evil_relative)
                self.assertEqual(cm.exception.status_code, 403)
                self.assertEqual(cm.exception.detail, "Access denied")


if __name__ == "__main__":
    unittest.main()
