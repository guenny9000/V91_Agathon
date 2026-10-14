import json
import tempfile
import unittest
from pathlib import Path

from v91.audit import HashChainAuditLogger


class HashChainAuditLoggerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "audit.jsonl"
        self.logger = HashChainAuditLogger(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_append_and_verify(self):
        first = self.logger.log("CREATE", "test-user", {"value": 1})
        second = self.logger.log("UPDATE", "test-user", {"value": 2})
        records = self.logger.verify_chain()
        self.assertEqual(first["seq"], 0)
        self.assertEqual(second["seq"], 1)
        self.assertEqual(len(records), 2)
        self.assertTrue(records[0]["timestamp"].endswith("Z"))

    def test_tampering_is_detected(self):
        self.logger.log("CREATE", "test-user", {"value": 1})
        record = json.loads(self.path.read_text(encoding="utf-8"))
        record["additional_info"]["value"] = 9
        self.path.write_text(json.dumps(record) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.logger.verify_chain()

    def test_empty_existing_file_fails_closed(self):
        self.path.touch()
        logger = HashChainAuditLogger(self.path)
        with self.assertRaisesRegex(ValueError, "empty"):
            logger.log("CREATE", "test-user")

    def test_existing_lock_blocks_append(self):
        lock_path = self.path.with_name(self.path.name + ".lock")
        lock_path.write_text("other process", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lock exists"):
            self.logger.log("CREATE", "test-user")
        self.assertFalse(self.path.exists())

    def test_non_json_additional_info_is_rejected(self):
        with self.assertRaises(ValueError):
            self.logger.log("CREATE", "test-user", {"not_json": float("nan")})
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
