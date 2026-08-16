# Release checklist

Before creating a Fitness release (`YYYY.MM.RR-betaXX` for beta, `YYYY.MM.RR` for stable):

- [ ] `pytest` passes locally.
- [ ] HACS validation GitHub Action passes with no ignored checks.
- [ ] Hassfest GitHub Action passes.
- [ ] `manifest.json` version matches the intended Git tag exactly.
- [ ] `hacs.json`, `README.md`, issue tracker and documentation URLs are valid.
- [ ] Integration and repository brand assets exist.
- [ ] No secrets or private diagnostics are included.
- [ ] CHANGELOG / release notes describe user-visible changes.
- [ ] Create an annotated Git tag matching the manifest version.
- [ ] Push the tag.
- [ ] Create a GitHub Release (pre-release for beta versions).
- [ ] Verify HACS can install/update the release from the custom repository.

For submission to the HACS default repository, also confirm the current HACS inclusion requirements and wait until the HACS + hassfest workflows are green before opening the submission PR.
