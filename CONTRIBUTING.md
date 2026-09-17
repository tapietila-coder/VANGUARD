# Contributing to VANGUARD

This repository is public for visibility, but the code is licensed
**all rights reserved** (see `LICENSE`) — there is no open license grant to
reuse, modify, or redistribute it. External pull requests are not accepted
at this time.

## Working in this repo (owner/maintainer workflow)

`master` is protected: the `pytest` CI check must pass before a branch can
be merged, and this applies to admins too. The workflow is:

1. Create a branch: `git checkout -b <topic>`
2. Make changes, keeping to the existing honesty standard — no fabricated
   data, no fake "connected" status for systems that aren't real (see
   `README.md` and `VANGUARD_DISCOVERY.md` for what that means in practice).
3. Run the test suite locally before pushing:
   ```
   .venv/Scripts/python.exe -m pytest -q
   ```
4. Push the branch and open a PR against `master`.
5. Wait for the `pytest` check to pass, then merge (squash) and delete the
   branch.

## Local setup

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev,detect]"
cp .env.example .env
.venv/Scripts/python.exe -m pytest -q
```

See `README.md` for how to run the API itself, and `docs/SECURITY.md`
before changing anything auth- or secrets-related.
