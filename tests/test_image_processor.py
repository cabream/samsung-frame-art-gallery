import unittest
import io
from PIL import Image
from pydantic import ValidationError

from src.services.image_processor import (
    _crop_image,
    _add_matte,
    _reframe_image,
    process_for_tv,
    generate_preview,
    TARGET_RATIO,
)
from src.api.tv import PreviewRequest, UploadRequest
from src.api.met import MetPreviewRequest, MetUploadRequest


class TestImageProcessorBounds(unittest.TestCase):
    def setUp(self):
        # Create a test image: 1000x800 RGB
        self.img = Image.new("RGB", (1000, 800), color="blue")
        buf = io.BytesIO()
        self.img.save(buf, format="JPEG")
        self.img_bytes = buf.getvalue()

        # RGBA test image
        self.rgba_img = Image.new("RGBA", (1000, 800), color=(0, 255, 0, 128))
        rgba_buf = io.BytesIO()
        self.rgba_img.save(rgba_buf, format="PNG")
        self.rgba_bytes = rgba_buf.getvalue()

    def test_crop_image_zero_percent(self):
        cropped = _crop_image(self.img, 0)
        self.assertEqual(cropped.size, (1000, 800))

    def test_crop_image_normal_percent(self):
        cropped = _crop_image(self.img, 25)
        # 25% from each edge: width = 1000 - 250*2 = 500, height = 800 - 200*2 = 400
        self.assertEqual(cropped.size, (500, 400))

    def test_crop_image_clamping_at_or_above_50_percent(self):
        # 50% or above previously collapsed the image to 0x0
        # Now it is clamped to 49%
        cropped_50 = _crop_image(self.img, 50)
        self.assertGreater(cropped_50.size[0], 0)
        self.assertGreater(cropped_50.size[1], 0)

        cropped_80 = _crop_image(self.img, 80)
        self.assertEqual(cropped_50.size, cropped_80.size)

    def test_crop_image_negative_percent(self):
        cropped_neg = _crop_image(self.img, -10)
        self.assertEqual(cropped_neg.size, (1000, 800))

    def test_add_matte_negative_percent(self):
        # Negative matte percent should clamp to 0 and not fail
        matted = _add_matte(self.img, -5)
        w, h = matted.size
        self.assertAlmostEqual(w / h, TARGET_RATIO, places=2)

    def test_add_matte_standard(self):
        matted = _add_matte(self.img, 10)
        w, h = matted.size
        self.assertAlmostEqual(w / h, TARGET_RATIO, places=2)

    def test_process_for_tv_output_format_and_ratio(self):
        data = process_for_tv(self.img_bytes, crop_percent=10, matte_percent=10)
        out_img = Image.open(io.BytesIO(data))
        self.assertEqual(out_img.format, "PNG")
        self.assertAlmostEqual(out_img.width / out_img.height, TARGET_RATIO, places=2)

    def test_process_for_tv_rgba_conversion(self):
        # RGBA should be converted to RGB with white matte without crash
        data = process_for_tv(self.rgba_bytes, crop_percent=0, matte_percent=10)
        out_img = Image.open(io.BytesIO(data))
        self.assertEqual(out_img.format, "PNG")
        self.assertAlmostEqual(out_img.width / out_img.height, TARGET_RATIO, places=2)

    def test_process_for_tv_with_reframe(self):
        data = process_for_tv(self.img_bytes, reframe_enabled=True, reframe_offset_x=0.5, reframe_offset_y=0.5)
        out_img = Image.open(io.BytesIO(data))
        self.assertEqual(out_img.format, "PNG")
        self.assertAlmostEqual(out_img.width / out_img.height, TARGET_RATIO, places=2)

    def test_generate_preview(self):
        orig_bytes, proc_bytes = generate_preview(self.img_bytes, crop_percent=15, matte_percent=5)
        orig_img = Image.open(io.BytesIO(orig_bytes))
        proc_img = Image.open(io.BytesIO(proc_bytes))
        self.assertEqual(orig_img.format, "JPEG")
        self.assertEqual(proc_img.format, "JPEG")
        self.assertAlmostEqual(proc_img.width / proc_img.height, TARGET_RATIO, places=1)


class TestRequestValidationBounds(unittest.TestCase):
    def test_tv_preview_request_crop_percent_validation(self):
        # Valid
        req = PreviewRequest(paths=["foo.jpg"], crop_percent=20, matte_percent=10)
        self.assertEqual(req.crop_percent, 20)

        # > 49 should fail
        with self.assertRaises(ValidationError):
            PreviewRequest(paths=["foo.jpg"], crop_percent=50)

        # < 0 should fail
        with self.assertRaises(ValidationError):
            PreviewRequest(paths=["foo.jpg"], crop_percent=-1)

        # negative matte should fail
        with self.assertRaises(ValidationError):
            PreviewRequest(paths=["foo.jpg"], matte_percent=-1)

    def test_tv_upload_request_validation(self):
        with self.assertRaises(ValidationError):
            UploadRequest(paths=["foo.jpg"], crop_percent=50)

    def test_met_preview_request_validation(self):
        with self.assertRaises(ValidationError):
            MetPreviewRequest(object_ids=[123], crop_percent=60)
        with self.assertRaises(ValidationError):
            MetPreviewRequest(object_ids=[123], matte_percent=-5)

    def test_met_upload_request_validation(self):
        with self.assertRaises(ValidationError):
            MetUploadRequest(object_ids=[123], crop_percent=50)


if __name__ == "__main__":
    unittest.main()
