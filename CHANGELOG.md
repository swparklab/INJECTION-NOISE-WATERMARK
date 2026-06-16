# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Modern Python packaging with `pyproject.toml` (PEP 517/518 compliant)
- Comprehensive type hints and docstrings (Google style)
- New `WatermarkConfig` dataclass for centralized configuration
- New `Watermarker` class with clean API for watermark injection
- New `Detector` and `DetectionResult` classes for watermark detection
- Pattern generation strategies (Ring, Random, Zero, Const patterns)
- Core modules reorganized under `src/tree_ring_watermark/`
  - `core/watermark.py`: Watermark injection and distortion
  - `core/detection.py`: Detection metrics and p-value calculation
  - `core/patterns.py`: Pattern generation strategies
  - `io.py`: I/O utilities (JSON, JSONL)
  - `pipelines/`: Abstract pipeline interfaces
- Comprehensive test suite
  - `test_config.py`: Configuration validation
  - `test_patterns.py`: Pattern generation tests
- GitHub Actions CI/CD pipeline
  - Code quality checks (ruff, black, isort)
  - Type checking (mypy)
  - Test automation on Python 3.10, 3.11, 3.12
- Documentation
  - Updated README with comprehensive examples
  - CONTRIBUTING.md with development guidelines
  - CHANGELOG.md (this file)
- Support for Python 3.10+ (dropped 3.7-3.9 support)

### Changed
- Migrated legacy `optim_utils.py` to structured `core/watermark.py`
- Migrated `io_utils.py` to clean `io.py` module
- Configuration now uses dataclasses instead of argparse
- Improved code organization with clear separation of concerns
- Enhanced error handling and validation

### Deprecated
- Old run script variants (use unified configuration instead)
- Direct use of `argparse` for configuration (use `WatermarkConfig` instead)

### Removed
- Root-level Python scripts (now under proper package structure)
- Unused imports and dead code from legacy modules

### Fixed
- Type safety issues across codebase
- Import paths and circular dependencies
- Documentation consistency

### Security
- None at this time

## [0.2.0] - 2024-06-17

### Added
- Initial phase 1 restructuring
- Package reorganization (src/ layout)
- Type hints and docstrings
- Test infrastructure

### Notes
- This is a major restructuring to modernize the codebase
- Previous version was 0.0.2 based on setup.py

---

## [0.0.2] - Original Release

Original release with:
- Basic watermark injection functionality
- Pattern generation in Fourier domain
- Detection metrics
- Support for various distortion attacks
- Integration with Stable Diffusion
