import unittest

from v91.audit_deep import AuditDeep


class AuditDeepTests(unittest.TestCase):
    def test_hash_chain_detects_payload_tampering(self):
        audit = AuditDeep()
        audit.update_chain({"value": 1})
        audit.update_chain({"value": 2})
        self.assertTrue(audit.verify_chain())
        audit.blocks[0]["payload"]["value"] = 99
        self.assertFalse(audit.verify_chain())

    def test_malformed_block_returns_false_not_exception(self):
        audit = AuditDeep()
        audit.update_chain({"value": 1})
        audit.blocks[0] = None
        self.assertFalse(audit.verify_chain())

    def test_signature_covers_exact_canonical_payload(self):
        audit = AuditDeep()
        payload = {"b": 2, "a": 1}
        signature = audit.sign_data(payload)
        self.assertTrue(audit.verify_signature({"a": 1, "b": 2}, signature))
        self.assertFalse(audit.verify_signature({"a": 1, "b": 3}, signature))


if __name__ == "__main__":
    unittest.main()
