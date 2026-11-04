import json
import os
import tempfile
import unittest
import threading
from pathlib import Path
from unittest.mock import patch

import src.services.tv_settings as tv_settings
import src.services.collections as collections
import src.services.tv_thumbnail_cache as tv_thumbnail_cache
import src.services.tv_discovery as tv_discovery


class TestStorageResilience(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Patch paths
        self.settings_file = self.temp_path / "data" / "tv_settings.json"
        self.collections_file = self.temp_path / "data" / "collections.json"
        self.cache_dir = self.temp_path / "nested" / "thumbnails" / "tv"

        self.orig_settings_file = tv_settings.SETTINGS_FILE
        self.orig_collections_file = collections.COLLECTIONS_FILE
        self.orig_cache_dir = tv_thumbnail_cache.CACHE_DIR

        tv_settings.SETTINGS_FILE = self.settings_file
        collections.COLLECTIONS_FILE = self.collections_file
        tv_thumbnail_cache.CACHE_DIR = self.cache_dir

    def tearDown(self):
        tv_settings.SETTINGS_FILE = self.orig_settings_file
        collections.COLLECTIONS_FILE = self.orig_collections_file
        tv_thumbnail_cache.CACHE_DIR = self.orig_cache_dir
        self.temp_dir.cleanup()

    def test_tv_settings_defaults_and_atomic_save(self):
        # When file doesn't exist, returns default
        settings = tv_settings.load_settings()
        self.assertFalse(settings.configured)
        self.assertIsNone(settings.selected_tv_ip)

        # Save settings creates parent dir and writes atomically
        settings.selected_tv_ip = "192.168.1.50"
        settings.selected_tv_name = "Living Room TV"
        tv_settings.save_settings(settings)

        self.assertTrue(self.settings_file.exists())
        # Verify content
        loaded = tv_settings.load_settings()
        self.assertEqual(loaded.selected_tv_ip, "192.168.1.50")
        self.assertEqual(loaded.selected_tv_name, "Living Room TV")
        self.assertTrue(loaded.configured)

    def test_tv_settings_corrupted_json(self):
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text("NOT_VALID_JSON{[[", encoding="utf-8")

        # Corrupt file should not crash load_settings, returns defaults
        settings = tv_settings.load_settings()
        self.assertFalse(settings.configured)
        self.assertIsNone(settings.selected_tv_ip)

    def test_collections_crud_and_deduplication(self):
        # Initial empty
        data = collections.load_collections()
        self.assertEqual(len(data.collections), 0)

        # Create
        c = collections.create_collection("Favorites")
        self.assertEqual(c.name, "Favorites")
        c_id = c.id

        # Add items (local & met)
        item1 = collections.CollectionItem(type="local", path="art1.jpg")
        item2 = collections.CollectionItem(type="met", object_id=436535)
        item3_dup = collections.CollectionItem(type="local", path="art1.jpg")

        updated = collections.add_items_to_collection(c_id, [item1, item2, item3_dup])
        self.assertIsNotNone(updated)
        # item3_dup should have been skipped
        self.assertEqual(len(updated.items), 2)

        # Reorder items
        reordered = collections.reorder_collection_items(
            c_id,
            [{"type": "met", "object_id": 436535}, {"type": "local", "path": "art1.jpg"}]
        )
        self.assertEqual(reordered.items[0].type, "met")
        self.assertEqual(reordered.items[1].type, "local")

        # Rename
        renamed = collections.rename_collection(c_id, "Masterpieces")
        self.assertEqual(renamed.name, "Masterpieces")

        # Remove single item
        after_remove = collections.remove_items_from_collection(c_id, [{"type": "local", "path": "art1.jpg"}])
        self.assertEqual(len(after_remove.items), 1)
        self.assertEqual(after_remove.items[0].object_id, 436535)

        # Delete collection
        deleted = collections.delete_collection(c_id)
        self.assertTrue(deleted)
        self.assertEqual(len(collections.load_collections().collections), 0)

    def test_collections_corrupted_json(self):
        self.collections_file.parent.mkdir(parents=True, exist_ok=True)
        self.collections_file.write_text("{invalid json", encoding="utf-8")

        data = collections.load_collections()
        self.assertEqual(len(data.collections), 0)

    def test_concurrent_collection_modifications(self):
        c = collections.create_collection("Concurrent")
        c_id = c.id

        def worker(idx):
            item = collections.CollectionItem(type="local", path=f"image_{idx}.jpg")
            collections.add_items_to_collection(c_id, [item])

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        data = collections.load_collections()
        col = collections.get_collection_by_id(data, c_id)
        self.assertIsNotNone(col)
        self.assertEqual(len(col.items), 15)

    def test_tv_thumbnail_cache(self):
        cache = tv_thumbnail_cache.TVThumbnailCache()
        # Verify nested directory was created
        self.assertTrue(self.cache_dir.exists())

        # Cache miss
        self.assertIsNone(cache.get("test/1"))

        # Cache set and get
        test_data = b"image_bytes_123"
        cache.set("test/1", test_data)
        self.assertEqual(cache.get("test/1"), test_data)

        # Invalidate
        cache.invalidate("test/1")
        self.assertIsNone(cache.get("test/1"))

        # Invalidate nonexistent does not raise
        cache.invalidate("nonexistent")

        # Cleanup orphaned
        cache.set("keep", b"1")
        cache.set("orphan", b"2")
        removed = cache.cleanup_orphaned({"keep"})
        self.assertEqual(removed, 1)
        self.assertIsNotNone(cache.get("keep"))
        self.assertIsNone(cache.get("orphan"))

        # Clear
        cache.clear()
        self.assertIsNone(cache.get("keep"))


class TestTVDiscoveryResilience(unittest.TestCase):
    def test_ssdp_parsing(self):
        response = "HTTP/1.1 200 OK\r\nLOCATION: http://192.168.1.100:9197/dmr\r\nSERVER: SHP\r\n\r\n"
        loc = tv_discovery._parse_ssdp_response(response)
        self.assertEqual(loc, "http://192.168.1.100:9197/dmr")

        ip = tv_discovery._extract_ip_from_url(loc)
        self.assertEqual(ip, "192.168.1.100")

    def test_discovery_socket_failure_handling(self):
        # Test that socket creation failure doesn't trigger UnboundLocalError
        with patch("socket.socket", side_effect=OSError("Socket permission error")):
            result = tv_discovery.discover_tvs()
            self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
