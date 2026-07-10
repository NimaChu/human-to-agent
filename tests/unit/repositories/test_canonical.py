from harness_foundry.repositories.canonical import canonical_bytes, canonical_text


def test_mapping_digest_input_ignores_key_order() -> None:
    assert canonical_bytes({"b": 2, "a": 1}) == canonical_bytes({"a": 1, "b": 2})


def test_markdown_normalizes_crlf_and_terminal_newline() -> None:
    assert canonical_text("# A\r\n\r\nBody") == b"# A\n\nBody\n"


def test_canonical_json_is_utf8_compact_and_stable() -> None:
    assert canonical_bytes({"text": "证据", "values": [2, 1]}) == (
        b'{"text":"\xe8\xaf\x81\xe6\x8d\xae","values":[2,1]}\n'
    )
