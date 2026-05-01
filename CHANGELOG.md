# Changelog

[0.2.0] - Unreleased
- Add support for python 3.14
- Drop support for python 3.9 and 3.10
- Update to support salt portal 1.0.2
- Update database schema to version 2 to support new outputs from salt portal. Most importantly:
  - Flag for upstream probes
  - Mass of salt and cft used per measurement
- Update dependencies
- Use ruff for code formatting

[0.1.1] - 2025-01-14

- Drop support for python 3.8
- Add support for python 3.13
- Fix bug with newer version of salt portal (0.6.3) which changed header names in exported meeasurement data

[0.1.0] - 2024-08-27

- First release