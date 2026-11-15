# Contributing

Open an issue describing the observable defect or learning objective before adding a large scenario or changing scoring rules. Keep improvements focused and include a meaningful failing regression for behavior changes.

Use Python 3.11-compatible standard-library runtime code. Install `.[dev]`, run `python -m pytest -q`, and build with `python -m build`. Test the resulting wheel outside the source tree so scenario and UI resources are included. Never add cloud credentials, external actions or a wildcard bind option.

AI-assisted contributions are welcome when disclosed in the PR, reviewed by the contributor, and accompanied by actual test results and known limitations. Do not claim that an assistant or this simulator validates real production safety. Describe scenario assumptions and preserve decision-time evidence rather than retroactive grading.
