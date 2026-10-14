"""In-memory audit hash chain and Ed25519 signing helpers.

These primitives support integrity checks; they do not make storage immutable
or establish the truth of the signed statement.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

ZERO_HASH = "0" * 64


class AuditDeep:
    ZERO_HASH = ZERO_HASH

    def __init__(self) -> None:
        self.blocks: list[dict[str, Any]] = []
        self.hash_chain: list[str] = []
        self._private_key = Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

    @staticmethod
    def serialize_data(data: Any) -> str:
        try:
            return json.dumps(
                data, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Audit data must be JSON-serializable without NaN or Infinity.") from exc

    @classmethod
    def _hash_block(cls, block: dict[str, Any]) -> str:
        body = {key: value for key, value in block.items() if key != "hash"}
        return hashlib.sha256(cls.serialize_data(body).encode("utf-8")).hexdigest()

    def update_chain(self, data: Any) -> str:
        # Validate and canonicalize before mutating in-memory state.
        self.serialize_data(data)
        previous = self.hash_chain[-1] if self.hash_chain else self.ZERO_HASH
        block: dict[str, Any] = {
            "sequence": len(self.blocks),
            "prev_hash": previous,
            "payload": data,
        }
        digest = self._hash_block(block)
        block["hash"] = digest
        self.blocks.append(block)
        self.hash_chain.append(digest)
        return digest

    def verify_chain(self) -> bool:
        previous = self.ZERO_HASH
        if len(self.blocks) != len(self.hash_chain):
            return False
        for index, block in enumerate(self.blocks):
            if not isinstance(block, dict):
                return False
            if block.get("sequence") != index or block.get("prev_hash") != previous:
                return False
            try:
                digest = self._hash_block(block)
            except (TypeError, ValueError):
                return False
            if block.get("hash") != digest or self.hash_chain[index] != digest:
                return False
            previous = digest
        return True

    def sign_data(self, data: Any) -> bytes:
        serialized = self.serialize_data(data).encode("utf-8")
        return self._private_key.sign(serialized)

    def verify_signature(self, data: Any, signature: bytes) -> bool:
        try:
            serialized = self.serialize_data(data).encode("utf-8")
            self._public_key.verify(signature, serialized)
            return True
        except (InvalidSignature, TypeError, ValueError):
            return False

    def public_key_bytes(self) -> bytes:
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
