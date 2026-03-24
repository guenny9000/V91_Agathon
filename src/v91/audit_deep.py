import json
import hashlib
import ed25519

class AuditDeep:
    def __init__(self):
        self.hash_chain = []
        self.private_key, self.public_key = ed25519.create_keypair()

    def serialize_data(self, data):
        """Return a deterministic JSON serialization of the data."""
        return json.dumps(data, sort_keys=True)

    def update_chain(self, data):
        """Update the SHA256 hash chain with the new serialized data."""
        serialized = self.serialize_data(data)
        sha256_hash = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
        self.hash_chain.append(sha256_hash)
        return sha256_hash

    def sign_data(self, data):
        """Sign the serialized data using Ed25519."""
        serialized = self.serialize_data(data)
        signature = self.private_key.sign(serialized.encode('utf-8'))
        return signature

    def verify_signature(self, data, signature):
        """Verify the signature of the given data."""
        serialized = self.serialize_data(data)
        try:
            self.public_key.verify(signature, serialized.encode('utf-8'))
            return True
        except ed25519.BadSignatureError:
            return False

# Example usage (to be removed or replaced in production)
if __name__ == "__main__":
    audit = AuditDeep()
    data = {"key": "value"}
    print("Serialized Data:", audit.serialize_data(data))
    print("SHA256 Hash:", audit.update_chain(data))
    signature = audit.sign_data(data)
    print("Signature:", signature)
    print("Verification:", audit.verify_signature(data, signature))
