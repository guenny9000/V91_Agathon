"""In-memory hash-chain and Ed25519 signing helper.

The chain is held in memory only. It is not durable audit storage, WORM, or
proof of trusted identity; callers must protect private keys and persist records
through a separately reviewed storage layer.
"""
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class AuditDeep:
    ZERO_HASH = "0" * 64

    def __init__(self, private_key=None):
        self.private_key = private_key or Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.hash_chain = []
        self.blocks = []

    def serialize_data(self, data):
        """Return canonical JSON; reject non-JSON values and NaN/Infinity."""
        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def update_chain(self, data):
        """Add a hash that binds sequence, previous hash, and complete payload."""
        serialized = self.serialize_data(data)
        previous_hash = self.hash_chain[-1] if self.hash_chain else self.ZERO_HASH
        core = {
            "sequence": len(self.hash_chain),
            "prev_hash": previous_hash,
            "payload": json.loads(serialized),
        }
        core_bytes = self.serialize_data(core).encode("utf-8")
        current_hash = hashlib.sha256(core_bytes).hexdigest()
        self.blocks.append({**core, "hash": current_hash})
        self.hash_chain.append(current_hash)
        return current_hash

    def verify_chain(self):
        """Return False for malformed or modified in-memory records."""
        expected_previous = self.ZERO_HASH
        if len(self.blocks) != len(self.hash_chain):
            return False
        for index, block in enumerate(self.blocks):
            if not isinstance(block, dict):
                return False
            if set(block) != {"sequence", "prev_hash", "payload", "hash"}:
                return False
            sequence = block.get("sequence")
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence != index:
                return False
            previous_hash = block.get("prev_hash")
            if not isinstance(previous_hash, str) or previous_hash != expected_previous:
                return False
            stored_hash = block.get("hash")
            if not isinstance(stored_hash, str) or len(stored_hash) != 64:
                return False
            if any(character not in "0123456789abcdef" for character in stored_hash):
                return False
            core = {key: value for key, value in block.items() if key != "hash"}
            try:
                expected_hash = hashlib.sha256(
                    self.serialize_data(core).encode("utf-8")
                ).hexdigest()
            except (TypeError, ValueError):
                return False
            if stored_hash != expected_hash or self.hash_chain[index] != expected_hash:
                return False
            expected_previous = expected_hash
        return True

    def sign_data(self, data):
        """Sign canonical JSON with this instance's Ed25519 private key."""
        return self.private_key.sign(self.serialize_data(data).encode("utf-8"))

    def verify_signature(self, data, signature):
        """Verify a signature with this instance's public key."""
        if not isinstance(signature, bytes):
            return False
        try:
            self.public_key.verify(signature, self.serialize_data(data).encode("utf-8"))
            return True
        except (InvalidSignature, TypeError, ValueError):
            return False

    def public_key_bytes(self):
        """Export the raw public key; callers must bind it to a trusted identity."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )


if __name__ == "__main__":
    audit = AuditDeep()
    data = {"key": "value"}
    print("Serialized Data:", audit.serialize_data(data))
    print("SHA256 Hash:", audit.update_chain(data))
    signature = audit.sign_data(data)
    print("Signature valid:", audit.verify_signature(data, signature))
    print("In-memory chain valid:", audit.verify_chain())
