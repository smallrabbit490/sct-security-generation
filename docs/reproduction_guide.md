# Reproduction Guide

1. Clone the repository and create `.env.local` from `.env.example`.
2. Confirm Docker Desktop is running and build the validator images.
3. Run `python -m compileall src methods tools`.
4. Run `python -m unittest discover -s tests -v`.
5. Run `python tools/check_repository.py`.
6. Run one task per method with a short timeout and inspect the trace.
7. Run Base and Plus as separate jobs. Never reuse final-test failures as
   experience input.
8. Save large outputs outside Git or under ignored `translation_work/`.

The repository is intentionally conservative about completion claims. A JSONL
file proves that a row was written; it does not prove that compilation,
functional testing, and security testing all passed.
