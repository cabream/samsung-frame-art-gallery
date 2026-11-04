import asyncio
import io
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image

from src.api.met import (
    preview_met_artwork,
    upload_met_artwork,
    MetPreviewRequest,
    MetUploadRequest,
    MAX_CONCURRENT_DOWNLOADS,
)


class TestMetApiConcurrency(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Create a sample test JPEG image
        img = Image.new("RGB", (200, 200), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        self.sample_jpeg = buf.getvalue()

    async def test_preview_met_artwork_concurrency_limit(self):
        max_seen_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def mock_fetch_image(url):
            nonlocal max_seen_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_seen_concurrent:
                    max_seen_concurrent = current_concurrent
            # Simulate network latency
            await asyncio.sleep(0.02)
            async with lock:
                current_concurrent -= 1
            return self.sample_jpeg

        mock_client = MagicMock()
        mock_client.get_object.side_effect = lambda oid: {
            "objectID": oid,
            "title": f"Painting {oid}",
            "primaryImageSmall": f"http://example.com/{oid}.jpg",
        }
        # fetch_image in asyncio.to_thread runs in thread, so wrap it
        def sync_fetch_image(url):
            nonlocal max_seen_concurrent, current_concurrent
            current_concurrent += 1
            if current_concurrent > max_seen_concurrent:
                max_seen_concurrent = current_concurrent
            import time
            time.sleep(0.01)
            current_concurrent -= 1
            return self.sample_jpeg

        mock_client.fetch_image.side_effect = sync_fetch_image

        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        with patch("src.api.met.get_met_client", return_value=mock_client), \
             patch("src.api.met.get_preview_cache", return_value=mock_cache):

            # Request 12 previews simultaneously
            req = MetPreviewRequest(object_ids=list(range(1, 13)), crop_percent=0, matte_percent=10)
            res = await preview_met_artwork(req)

            self.assertEqual(len(res["previews"]), 12)
            self.assertLessEqual(max_seen_concurrent, MAX_CONCURRENT_DOWNLOADS)
            for p in res["previews"]:
                self.assertTrue(p["original_url"].startswith("data:image/jpeg;base64,"))
                self.assertTrue(p["processed_url"].startswith("data:image/jpeg;base64,"))

    async def test_preview_met_artwork_missing_objects_handled(self):
        mock_client = MagicMock()
        # Object 2 has no image, object 3 does not exist
        def get_obj(oid):
            if oid == 1:
                return {"objectID": 1, "title": "Good", "primaryImageSmall": "http://example.com/1.jpg"}
            elif oid == 2:
                return {"objectID": 2, "title": "No Image"}
            return None

        mock_client.get_object.side_effect = get_obj
        mock_client.fetch_image.return_value = self.sample_jpeg

        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        with patch("src.api.met.get_met_client", return_value=mock_client), \
             patch("src.api.met.get_preview_cache", return_value=mock_cache):

            req = MetPreviewRequest(object_ids=[1, 2, 3], crop_percent=0, matte_percent=10)
            res = await preview_met_artwork(req)

            # Only object 1 should produce a preview
            self.assertEqual(len(res["previews"]), 1)
            self.assertEqual(res["previews"][0]["id"], 1)

    async def test_upload_met_artwork_bounded_and_sequential(self):
        mock_client = MagicMock()
        mock_client.get_object.side_effect = lambda oid: {
            "objectID": oid,
            "title": f"Painting {oid}",
            "primaryImage": f"http://example.com/{oid}.jpg",
        }
        mock_client.fetch_image.return_value = self.sample_jpeg

        mock_tv_client = MagicMock()
        mock_tv_client.upload_artwork.side_effect = lambda data, display: {"content_id": "tv_123"}

        with patch("src.api.met.get_met_client", return_value=mock_client), \
             patch("src.api.met.require_tv_client", return_value=mock_tv_client):

            req = MetUploadRequest(object_ids=[10, 20], crop_percent=0, matte_percent=10, display=True)
            res = await upload_met_artwork(req)

            self.assertEqual(len(res["results"]), 2)
            self.assertTrue(res["results"][0]["success"])
            self.assertTrue(res["results"][1]["success"])
            self.assertEqual(mock_tv_client.upload_artwork.call_count, 2)


if __name__ == "__main__":
    unittest.main()
