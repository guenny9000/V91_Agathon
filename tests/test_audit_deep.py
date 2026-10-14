from v91.audit_deep import AuditDeep


def test_audit_deep_hash_chain_binds_previous_block():
    audit = AuditDeep()
    first = audit.update_chain({"a": 1, "nested": {"x": 2, "y": 3}})
    second = audit.update_chain({"b": 2})

    assert audit.blocks[0]["prev_hash"] == AuditDeep.ZERO_HASH
    assert audit.blocks[1]["prev_hash"] == first
    assert audit.blocks[1]["sequence"] == 1
    assert second == audit.hash_chain[1]
    assert audit.verify_chain() is True


def test_audit_deep_detects_payload_tampering():
    audit = AuditDeep()
    audit.update_chain({"sensitive": False})
    audit.blocks[0]["payload"]["sensitive"] = True
    assert audit.verify_chain() is False


def test_audit_deep_ed25519_sign_and_verify():
    audit = AuditDeep()
    data = {"message": "test", "nested": {"b": 2, "a": 1}}
    signature = audit.sign_data(data)
    assert audit.verify_signature(data, signature) is True
    assert audit.verify_signature({"message": "changed"}, signature) is False
    assert len(audit.public_key_bytes()) == 32


def test_audit_deep_rejects_non_json_values():
    audit = AuditDeep()
    try:
        audit.update_chain({"bad": float("nan")})
    except ValueError:
        pass
    else:
        raise AssertionError("NaN must not enter a canonical audit record")
