# Contributing to Injection Noise Watermark

First off, thank you for considering a contribution to Injection Noise Watermark! It's people like you that make this project such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps which reproduce the problem** in as many details as possible
* **Provide specific examples** to demonstrate the steps
* **Describe the behavior you observed** and point out what exactly is the problem with that behavior
* **Explain which behavior you expected** to see instead and why
* **Include screenshots and animated GIFs** if possible
* **Include your environment details** (Python version, PyTorch version, GPU/CPU, OS)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* **Use a clear and descriptive title**
* **Provide a step-by-step description** of the suggested enhancement
* **Provide specific examples** to demonstrate the steps or use cases
* **Describe the current behavior** and **explain the expected behavior**
* **Explain why this enhancement** would be useful

### Pull Requests

* Fill in the required template
* Follow the Python style guide (see below)
* Include appropriate test cases
* Update documentation as needed
* End all files with a newline

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Clone your fork
git clone https://github.com/YOUR_USERNAME/tree-ring-watermark.git
cd tree-ring-watermark

# Add upstream remote
git remote add upstream https://github.com/YuxinWenRick/tree-ring-watermark.git
```

### 2. Create Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all extras
pip install -e ".[dev,docs,serving,benchmark]"

# Install pre-commit hooks
pre-commit install
```

### 3. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
# or for bugfixes:
git checkout -b fix/bug-description
```

## Style Guide

### Python Style

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with some additional conventions:

* **Line length**: Maximum 100 characters
* **Type hints**: Use type hints for all function arguments and returns
* **Docstrings**: Use Google-style docstrings for all public functions/classes
* **Imports**: Use isort for import sorting
* **Formatting**: Use Black for code formatting

### Code Quality Tools

We use several tools to maintain code quality:

```bash
# Format code with Black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Lint with ruff
ruff check src/ tests/ --fix

# Type check with mypy
mypy src/tree_ring_watermark
```

### Docstring Format

```python
def function_name(param1: str, param2: int) -> bool:
    """Short description of what the function does.
    
    Longer description if needed. Explain the algorithm,
    special cases, or important notes.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When param2 is negative
        
    Examples:
        >>> result = function_name("test", 42)
        >>> assert result is True
    """
    pass
```

## Testing

All contributions must include tests. We use pytest for testing:

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src/tree_ring_watermark --cov-report=html

# Run specific test file
pytest tests/test_config.py -v

# Run tests matching pattern
pytest -k "pattern" -v

# Run only fast tests (skip slow/gpu tests)
pytest -m "not slow and not gpu"
```

### Writing Tests

* Place tests in the `tests/` directory
* Use descriptive test names starting with `test_`
* Use assertions instead of print statements
* Mark slow/GPU tests appropriately:

```python
import pytest

@pytest.mark.slow
def test_slow_operation():
    pass

@pytest.mark.gpu
def test_requires_gpu():
    pass
```

## Documentation

* Keep README.md up-to-date
* Add docstrings to all public APIs
* Update CHANGELOG.md for significant changes
* Link related issues in PRs

## Commit Messages

Write clear, descriptive commit messages:

```
[type] Brief description (50 chars max)

Longer explanation if needed. Explain why this change
was made, not just what changed. Reference issues with
fixes #123 or closes #456.

- Bullet point for significant changes
- Another bullet if needed
```

Types:
* `feat`: New feature
* `fix`: Bug fix
* `docs`: Documentation update
* `test`: Test addition/modification
* `refactor`: Code refactoring
* `style`: Code style changes (formatting, etc.)
* `chore`: Build, dependency, or tooling changes

## Pull Request Process

1. Update the README.md and CHANGELOG.md with details of changes
2. Add tests for new functionality
3. Ensure all tests pass: `pytest tests/`
4. Ensure code quality checks pass:
   ```bash
   black --check src/ tests/
   ruff check src/ tests/
   mypy src/tree_ring_watermark
   ```
5. Request review from maintainers
6. Address feedback and push updates

## Submitting Changes

```bash
# Commit your changes
git commit -m "[type] Description of changes"

# Push to your fork
git push origin feature/your-feature-name

# Create Pull Request on GitHub
# - Provide clear description
# - Reference any related issues
# - Include before/after behavior if applicable
```

## Review Process

* At least one maintainer review required
* Automated tests must pass
* No merge conflicts
* Code coverage should not decrease
* All conversations must be resolved

## Additional Notes

### Project Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features and improvements.

### Reporting Security Issues

Please DO NOT open public issues for security vulnerabilities. Email security@aimz.media instead.

### Questions?

* Check existing issues and discussions
* Ask in GitHub Discussions
* Email us at patrick@huggingface.co

## Recognition

Contributors will be recognized in:
* CONTRIBUTORS.md
* Release notes
* GitHub contributors page

Thank you for contributing! 🚀
