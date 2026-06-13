from backend.app.security import hash_password, verify_password


def test_hash_roundtrip():
    h = hash_password("s3cret-password")
    assert h.startswith("pbkdf2:sha256:")
    assert verify_password("s3cret-password", h)
    assert not verify_password("wrong", h)


def test_werkzeug_format_compat():
    # Format produced by werkzeug.generate_password_hash (method/salt/hash).
    h = hash_password("hello12345")
    method, salt, digest = h.split("$", 2)
    assert method.split(":")[0] == "pbkdf2"
    assert len(salt) == 32
    assert len(digest) == 64


def test_unknown_scheme_fails_closed():
    assert not verify_password("x", "scrypt:32768:8:1$abc$def")
    assert not verify_password("x", None)
    assert not verify_password("x", "garbage")
