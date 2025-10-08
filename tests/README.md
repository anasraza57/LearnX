# Tests

Comprehensive test suite for EduGPT-PersonalisedLearning following pytest conventions.

## Structure

```
tests/
├── conftest.py                             # Shared fixtures and pytest configuration
├── unit/                                   # Unit tests (isolated, fast)
│   ├── test_config.py                      # Configuration and token tracking tests
│   ├── test_validation.py                  # Syllabus schema validation tests
│   ├── test_learner_profile_validation.py  # Learner profile validation tests
│   └── test_learner_model.py               # Learner model functionality tests
└── integration/                            # Integration tests (multiple components)
    └── (future tests)
```

## Running Tests

### Quick Test Suite (Recommended - Fast)
Run only the fast tests for quick validation:
```bash
pytest tests/unit/test_config.py tests/unit/test_validation.py tests/unit/test_learner_profile_validation.py --no-cov -q
```
**Result:** 52 tests pass in < 1 second ✅

### Run all tests (includes slow tests)
```bash
pytest tests/unit/ --no-cov
```
**Note:** This will take 5-10 minutes due to slow learner model tests. All tests pass.

### Run with coverage
```bash
pytest tests/unit/test_config.py tests/unit/test_validation.py tests/unit/test_learner_profile_validation.py --cov=src --cov-report=html
```

### Run specific test file
```bash
pytest tests/unit/test_config.py -v
pytest tests/unit/test_validation.py -v
pytest tests/unit/test_learner_profile_validation.py -v
```

### Run specific test class
```bash
pytest tests/unit/test_config.py::TestConfig -v
pytest tests/unit/test_learner_model.py::TestLearnerModelCreation -v  # Fast tests only
```

### Run specific test
```bash
pytest tests/unit/test_config.py::TestConfig::test_config_singleton -v
```

### Run tests by marker
```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Verbose output
```bash
pytest -v
```

### Show local variables on failure
```bash
pytest --showlocals
```

### Disable output capture (see print statements)
```bash
pytest -s
```

## Test Categories

### Unit Tests

- **test_config.py** (18 tests) ✅
  - Configuration initialization and validation
  - Token tracker functionality
  - Thread safety and deadlock prevention
  - RAG configuration validation
  - Singleton pattern enforcement
  - Environment variable handling

- **test_validation.py** (18 tests) ✅
  - JSON Schema validation for syllabuses
  - Auto-repair functionality
  - Workload feasibility checks
  - Prerequisite validation (topological sorting)
  - Module ID uniqueness
  - Type coercion (strings → numbers)
  - Deep copy mutation prevention
  - Unknown key stripping

- **test_learner_profile_validation.py** (16 tests) ✅
  - JSON Schema validation for learner profiles
  - Completion percentage consistency
  - Module progress consistency checks
  - Assessment history validation
  - Current module validation
  - Learning style and mastery level enums
  - Score range validation (0-100)

- **test_learner_model.py** (35 tests) ⚠️
  - Learner profile creation and initialization (5 tests - fast ✅)
  - Enrollment and progress tracking (5 tests - slow ⏱️)
  - Mastery level computation (6 tests - slow ⏱️)
  - Assessment tracking and history (3 tests - slow ⏱️)
  - Adaptive difficulty recommendations (4 tests - slow ⏱️)
  - Performance trend analysis (3 tests - slow ⏱️)
  - Strengths/weaknesses identification (2 tests - slow ⏱️)
  - Profile persistence (save/load) (4 tests - slow ⏱️)
  - Thread safety (2 tests - slow ⏱️)
  - String representation (1 test - fast ✅)

  **Note:** Some learner model tests run slowly (30-60s each) due to JSON Schema validation being called on every operation. All tests pass correctly.

### Integration Tests
- (To be added in Phase 3+)

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
- `valid_profile` - Complete, valid learner profile dict (in test_learner_profile_validation.py)
- `temp_schema_file` - Temporary JSON schema file
- `reset_token_tracker` - Auto-fixture that resets token tracker before each test
- `fast_learner_model` - Auto-fixture that disables validation in LearnerModel for faster tests

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

## Test Summary

**Total Tests:** 87 tests across 4 test files

**Fast Tests (< 1 second):** 52 tests
- test_config.py: 18 tests ✅
- test_validation.py: 18 tests ✅
- test_learner_profile_validation.py: 16 tests ✅

**Slow Tests (30-60s each):** 35 tests
- test_learner_model.py: 35 tests ⚠️ (all pass, but slow due to validation)

**Overall Status:** ✅ All tests passing

## Current Coverage

Run the quick test suite with coverage:
```bash
pytest tests/unit/test_config.py tests/unit/test_validation.py tests/unit/test_learner_profile_validation.py --cov=src --cov-report=html
```

**Covered modules:**
- `src/config.py` - Configuration system
- `src/utils/validation.py` - Schema validation (syllabuses & learner profiles)
- `src/utils/progress.py` - Progress analytics
- `src/models/learner_profile.py` - Learner model (basic tests)

**To view detailed coverage:**
```bash
open htmlcov/index.html
```
