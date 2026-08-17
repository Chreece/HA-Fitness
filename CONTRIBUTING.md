# Contributing to Fitness

Thanks for helping improve Fitness.

## Development

Use Python 3.14.2 or newer to match current Home Assistant development requirements.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

The repository CI additionally runs the official HACS validator and Home Assistant hassfest.

## Pull requests

- Keep changes focused.
- Add/update tests when changing calculations, workout matching, normalization, or historical comparison behavior.
- Do not introduce a physiological formula without documenting its source, prerequisites, units, interpretation, and limitations.
- Preserve missing-data behavior: Fitness must not invent values when prerequisites are unavailable.
- Keep raw workout facts separate from derived/personal/AI interpretation.
- Never include Home Assistant tokens, passwords, email addresses, or other secrets in tests/issues.

## Versioning

`manifest.json` must match the Git tag exactly for every published release. Stable releases use `YYYY.M.RR`; alpha prereleases append `aXX`, and beta prereleases append `-betaXX`:

```text
2026.8.01a01
2026.8.01-beta01
2026.8.01
2026.8.02
```

The release helper (`harel`) uses this canonical tag form; do not add a different padded version to `manifest.json`.


## Automated dependency updates

Dependabot PRs may be squash-merged automatically only after the repository's
required CI checks pass. Normal contributor PRs are never auto-merged by the
Dependabot workflow.
