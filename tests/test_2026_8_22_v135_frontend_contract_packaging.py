from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v135_has_no_stale_unreleased_131_frontend_contracts():
    stale = []
    for path in [ROOT / "custom_components" / "fitness", ROOT / "tests"]:
        for candidate in path.rglob("*"):
            if not candidate.is_file() or candidate.suffix not in {".py", ".js"}:
                continue
            if ("unreleased-" + "131") in candidate.read_text(encoding="utf-8", errors="ignore"):
                stale.append(str(candidate.relative_to(ROOT)))
    assert stale == []
