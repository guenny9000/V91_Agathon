import unittest

from v91.audit_deep import AuditDeep


class AuditDeepTests(unittest.TestCase):
    def test_empty_chain_is_valid(self):
        audit = AuditDeep()
        self.assertTrue(audit.verify_chain())

    def test_hash_chain_detects_payload_tampering(self):
        audit = AuditDeep()
        first_hash = audit.update_chain({"value": 1})
        second_hash = audit.update_chain({"value": 2})
        self.assertTrue(audit.verify_chain())
        self.assertEqual(audit.blocks[1]["prev_hash"], first_hash)
        self.assertEqual(audit.blocks[1]["sequence"], 1)
        self.assertEqual(audit.hash_chain[1], second_hash)
        audit.blocks[0]["payload"]["value"] = 99
        self.assertFalse(audit.verify_chain())

    def test_verifier_rejects_previous_hash_tampering(self):
        audit = AuditDeep()
        audit.update_chain({"value": 1})
        audit.update_chain({"value": 2})
        audit.blocks[1]["prev_hash"] = AuditDeep.ZERO_HASH
        self.assertFalse(audit.verify_chain())

    def test_verifier_rejects_sequence_tampering(self):
        audit = AuditDeep()
        audit.update_chain({"value": 1})
        audit.blocks[0]["sequence"] = 5
        self.assertFalse(audit.verify_chain())

    def test_verifier_rejects_hash_index_divergence(self):
        audit = AuditDeep()
        audit.update_chain({"value": 1})
        audit.hash_chain[0] = "0" * 64
        self.assertFalse(audit.verify_chain())

    def test_malformed_block_returns_false_not_exception(self):
        audit = AuditDeep()
        audit.update_chain({"value": 1})
        audit.blocks[0] = None
        self.assertFalse(audit.verify_chain())

    def test_invalid_payload_does_not_mutate_chain(self):
        audit = AuditDeep()
        audit.update_chain({"value": 1})
        blocks_before = [dict(block) for block in audit.blocks]
        hashes_before = list(audit.hash_chain)
        with self.assertRaises(ValueError):
            audit.update_chain({"not_json": float("nan")})
        self.assertEqual(audit.blocks, blocks_before)
        self.assertEqual(audit.hash_chain, hashes_before)
        self.assertTrue(audit.verify_chain())

    def test_signature_covers_exact_canonical_payload(self):
        audit = AuditDeep()
        payload = {"b": 2, "a": 1}
        signature = audit.sign_data(payload)
        self.assertTrue(audit.verify_signature({"a": 1, "b": 2}, signature))
        self.assertFalse(audit.verify_signature({"a": 1, "b": 3}, signature))


if __name__ == "__main__":
    unittest.main()
