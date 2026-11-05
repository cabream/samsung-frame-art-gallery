import unittest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from src.api.tv import (
    SlideshowRequest,
    get_slideshow_status,
    set_slideshow_status,
)
from src.services.tv_client import TVClient


class TestSlideshowApiAndClient(unittest.IsolatedAsyncioTestCase):
    def test_slideshow_request_validation(self):
        # Standard durations (3 min to 7 days)
        for duration in [0, 3, 5, 10, 15, 30, 60, 120, 360, 720, 1440, 10080]:
            req = SlideshowRequest(enabled=True, duration=duration, shuffle=True)
            self.assertEqual(req.duration, duration)

        # Negative duration should fail
        with self.assertRaises(ValidationError):
            SlideshowRequest(enabled=True, duration=-1)

    async def test_get_slideshow_status_endpoint(self):
        mock_tv_client = MagicMock()
        mock_tv_client.get_slideshow_status.return_value = {
            "value": "15",
            "type": "shuffleslideshow",
            "category_id": "MY-C0002"
        }

        with patch("src.api.tv.require_tv_client", return_value=mock_tv_client):
            status = await get_slideshow_status()
            self.assertEqual(status["value"], "15")
            self.assertEqual(status["category_id"], "MY-C0002")

    async def test_set_slideshow_status_endpoint(self):
        mock_tv_client = MagicMock()
        mock_tv_client.set_slideshow_status.return_value = {"result": "ok"}

        with patch("src.api.tv.require_tv_client", return_value=mock_tv_client):
            req = SlideshowRequest(enabled=True, duration=1440, shuffle=False)
            res = await set_slideshow_status(req)
            self.assertTrue(res["success"])
            mock_tv_client.set_slideshow_status.assert_called_once_with(True, 1440, False)

    def test_tv_client_set_slideshow_status_enabled(self):
        client = TVClient("192.168.1.100")
        mock_tv = MagicMock()
        mock_art = MagicMock()
        mock_tv.art.return_value = mock_art
        mock_art.set_slideshow_status.return_value = {"result": "ok"}
        client._tv = mock_tv

        res = client.set_slideshow_status(enabled=True, duration=120, shuffle=True)
        self.assertEqual(res, {"result": "ok"})
        mock_art.set_slideshow_status.assert_called_once_with(duration=120, type=True, category=2)

    def test_tv_client_set_slideshow_status_disabled(self):
        client = TVClient("192.168.1.100")
        mock_tv = MagicMock()
        mock_art = MagicMock()
        mock_tv.art.return_value = mock_art
        mock_art.set_slideshow_status.return_value = {"result": "ok"}
        client._tv = mock_tv

        res = client.set_slideshow_status(enabled=False, duration=15, shuffle=True)
        self.assertEqual(res, {"result": "ok"})
        mock_art.set_slideshow_status.assert_called_once_with(duration=0)

    def test_tv_client_fallback_to_auto_rotation(self):
        client = TVClient("192.168.1.100")
        mock_tv = MagicMock()
        mock_art = MagicMock()
        mock_art.set_slideshow_status.side_effect = Exception("Not supported")
        mock_art.set_auto_rotation_status.return_value = {"result": "ok_auto_rotation"}
        mock_tv.art.return_value = mock_art
        client._tv = mock_tv

        res = client.set_slideshow_status(enabled=True, duration=360, shuffle=False)
        self.assertEqual(res, {"result": "ok_auto_rotation"})
        mock_art.set_auto_rotation_status.assert_called_once_with(duration=360, type=False, category=2)


if __name__ == "__main__":
    unittest.main()
