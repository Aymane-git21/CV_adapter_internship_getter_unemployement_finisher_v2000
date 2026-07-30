"""Cross-service parity gate: the backend must be able to import and round-trip
the latexc wire contract with zero service code present."""
from services.latexc.contract import (
    CONTRACT_VERSION,
    CompileFile,
    LatexCompileIn,
    LatexCompileOut,
)


def test_contract_version_pinned():
    assert CONTRACT_VERSION == "1"


def test_compile_in_roundtrip():
    inp = LatexCompileIn(
        doc_id="abc123",
        files=[CompileFile(path="main.tex", content_b64="aGVsbG8=")],
    )
    again = LatexCompileIn.model_validate(inp.model_dump())
    assert again.engine == "xelatex" and again.main == "main.tex"
    assert again.timeout_s == 40 and again.want_svgs is True


def test_compile_in_rejects_bad_paths():
    import pytest
    from pydantic import ValidationError

    for bad in ("../x.tex", "a/b.tex", ""):
        with pytest.raises(ValidationError):
            LatexCompileIn(doc_id="d", files=[CompileFile(path=bad, content_b64="eA==")])


def test_compile_out_defaults():
    out = LatexCompileOut(ok=False)
    assert out.cache == "cold" and out.svgs == [] and out.timings_ms == {}
