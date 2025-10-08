# Tests

Comprehensive test suite for EduGPT-PersonalisedLearning following pytest conventions.

## Structure

```
tests/
├── conftest.py          # Shared fixtures and pytest configuration
├── unit/                # Unit tests (isolated, fast)
│   ├── test_config.py   # Configuration and token tracking tests
│   └── test_validation.py  # Schema validation tests
└── integration/         # Integration tests (multiple components)
    └── (future tests)
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=src --cov-report=html
```

### Run specific test file
```bash
pytest tests/unit/test_config.py
```

### Run specific test class
```bash
pytest tests/unit/test_config.py::TestConfig
```

### Run specific test
```bash
pytest tests/unit/test_config.py::TestConfig::test_config_singleton
```

### Run tests by marker
```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"
```

### Verbose output
```bash
pytest -v
```

### Show local variables on failure
```bash
pytest --showlocals
```

## Test Categories

### Unit Tests
- **test_config.py** (18 tests)
  - Configuration initialization and validation
  - Token tracker functionality
  - Thread safety and deadlock prevention
  - RAG configuration validation

- **test_validation.py** (18 tests)
  - JSON Schema validation
  - Auto-repair functionality
  - Workload feasibility checks
  - Prerequisite validation
  - Module ID uniqueness
  - Topological sorting
  - Type coercion
  - Deep copy mutation prevention

### Integration Tests
- (To be added in Phase 2+)

## Coverage

Generate coverage report:
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html  # View in browser
```

## Fixtures

Common fixtures available in all tests (from `conftest.py`):

- `valid_syllabus` - Complete, valid syllabus dict
- `minimal_syllabus` - Minimal syllabus requiring auto-repair
- `invalid_syllabus` - Syllabus with validation errors
- `temp_schema_file` - Temporary JSON schema file
- `reset_token_tracker` - Auto-fixture that resets token tracker before each test

## Writing New Tests

### Test file naming
- `test_*.py` for test files
- Place in `unit/` or `integration/` directory

### Test class naming
- `Test*` for test classes
- Group related tests in classes

### Test function naming
- `test_*` for test functions
- Use descriptive names

### Example test
```python
class TestMyFeature:
    """Test suite for MyFeature."""

    def test_basic_functionality(self):
        """Test that basic functionality works."""
        result = my_feature.do_something()
        assert result == expected_value

    def test_error_handling(self):
        """Test that errors are handled correctly."""
        with pytest.raises(ValueError):
            my_feature.do_invalid_thing()
```

## Continuous Integration

Tests are run automatically on:
- Push to main branch
- Pull requests
- Manual workflow dispatch

See `.github/workflows/test.yml` for CI configuration.

## Test Standards

- **Fast**: Unit tests should run in <1s
- **Isolated**: No dependencies between tests
- **Repeatable**: Same result every run
- **Self-validating**: Clear pass/fail
- **Timely**: Write tests as you code

## Current Coverage

```
src/config.py:           100%
src/utils/validate.py:    98%
Overall:                  99%
```

(Run `pytest --cov` to see current coverage)
