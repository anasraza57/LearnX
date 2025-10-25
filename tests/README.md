# Tests

Comprehensive test suite for EduGPT-PersonalisedLearning following pytest conventions.

## Structure

```
tests/
├── conftest.py                             # Shared fixtures and pytest configuration
├── unit/                                   # Unit tests (isolated, fast)
│   ├── test_config.py                      # Configuration and token tracking
│   ├── test_validation.py                  # Syllabus schema validation
│   ├── test_learner_profile_validation.py  # Learner profile validation
│   ├── test_learner_model.py               # Learner model functionality
│   ├── test_rag_instructor.py              # RAG teaching with citations
│   ├── test_assessment_generator.py        # Question generation & validation
│   ├── test_grading_agent.py               # LLM-based grading
│   ├── test_quiz_session.py                # Adaptive quiz & scoring
│   ├── test_assessment_schemas.py          # Assessment & quiz schema
│   ├── test_orchestrator.py                # Complete pipeline orchestration
│   ├── test_syllabus_planner.py            # Multi-agent syllabus generation
│   ├── test_evaluation_metrics.py          # Evaluation metrics (learning gain, retention, etc.)
│   └── test_ab_testing.py                  # A/B testing framework
```

## Running Tests

### Quick Test Suite (Recommended - Fast)
Run only the fast tests for quick validation:
```bash
pytest tests/unit/test_config.py tests/unit/test_validation.py tests/unit/test_learner_profile_validation.py tests/unit/test_rag_instructor.py tests/unit/test_assessment_generator.py tests/unit/test_grading_agent.py tests/unit/test_quiz_session.py tests/unit/test_assessment_schemas.py tests/unit/test_orchestrator.py tests/unit/test_syllabus_planner.py --no-cov -q
```
**Result:** 185+ tests pass in < 3 seconds ✅

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

- **test_rag_instructor.py** (18 tests) ✅ **RAG Teaching**
  - RAG instructor basics (3 tests - fast ✅)
    - Teaching response format
    - Citation markdown formatting
    - Response with citations
  - RAG retrieval (3 tests - fast ✅)
    - Retrieval with min_similarity threshold
    - Zero-hit behavior (no matching documents)
    - Citations limited to top N results
  - Teaching session persistence (3 tests - fast ✅)
    - Session validates against schema
    - Session with syllabus mapping (Phase 1 integration)
    - Invalid session fails validation
  - Teach and save integration (1 test - fast ✅)
    - teach_and_save persists sessions correctly
  - Phase 2 integration (2 tests - fast ✅)
    - Add teaching history to learner profile
    - History limited to 100 entries
  - RAG configuration (1 test - fast ✅)
    - RAG config saved in session for reproducibility
  - **Go/No-Go Checklist (5 tests - fast ✅) - Production readiness**
    - End-to-end session validates against schema
    - ID patterns match schema regex
    - Zero-hit retrieval validates with empty citations
    - Phase 2 write-back creates history entry
    - Model and RAG config populated for reproducibility

- **test_assessment_generator.py** (15 tests) ✅ **Assessment Generation**
  - AssessmentQuestion validation (10 tests - fast ✅)
    - MCQ validation (options, correct answers, option_id format)
    - True/False validation
    - Points validation (0-100 range)
    - Page number normalization
  - Assessment generator (5 tests - fast ✅)
    - Initialization with/without RAG
    - Bloom's level suggestion
    - MCQ generation with RAG context
    - Question ID format (q-<uuid>)

- **test_grading_agent.py** (12 tests) ✅ **LLM Grading**
  - GradingResult dataclass (2 tests - fast ✅)
    - Creation and serialization
    - graded_by field tracking
  - Grading agent (10 tests - fast ✅)
    - Validation (empty answers, invalid points)
    - Essay and code response grading
    - Score normalization to 0-100
    - Fallback grading on errors
    - Batch grading

- **test_quiz_session.py** (23 tests) ✅ **Adaptive Quiz**
  - QuestionResponse (2 tests - fast ✅)
    - Creation with points field
    - Serialization
  - AdaptiveQuiz (21 tests - fast ✅)
    - Initialization and session ID format (qs-<uuid>)
    - teaching_session_id integration
    - Auto-grading (MCQ, True/False)
    - Validation (empty answers, duplicates)
    - Adaptive difficulty (increases/decreases after 2 correct/incorrect)
    - Points-weighted scoring
    - Quiz completion with integrity checks
    - Recommendations generation
    - Session reproducibility

- **test_assessment_schemas.py** (20 tests) ✅ **Schema Validation**
  - Assessment schema (11 tests - fast ✅)
    - Valid MCQ, True/False, Short Answer questions
    - Invalid ID/difficulty/question_type
    - Bloom's taxonomy validation
    - source_material with URI (file:// support)
  - Quiz session schema (9 tests - fast ✅)
    - Valid quiz session structure
    - question_response with points field
    - teaching_session_id (ts-<uuid>)
    - Recommendations with next_topic_id
    - graded_by field (auto/llm/human)

### Integration Tests
- RAG instructor integrates with syllabus and learner profile
- Assessment system integrates with RAG, learner profile, and syllabus
- Complete workflow example demonstrates end-to-end integration

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

- **test_orchestrator.py** (20 tests) ✅ **Pipeline Orchestration**
  - Orchestrator initialization
  - Learner enrollment
  - Teaching session management
  - Assessment orchestration
  - Mastery-based pathway adaptation
  - Session persistence (save/load)
  - Learner summaries

- **test_syllabus_planner.py** (15 tests) ✅ **Multi-Agent Syllabus**
  - Learner Advocate agent
  - Curriculum Designer agent
  - Negotiation protocol
  - Structured JSON extraction
  - Schema validation and auto-fixing
  - Workload feasibility calculation

- **test_evaluation_metrics.py** (19 tests) ✅ **Scientific Evaluation Metrics**
  - Learning gain calculations (8 tests - fast ✅)
    - Hake's normalized gain formula validation
    - Edge cases (no room to improve, perfect improvement)
    - Interpretation (high/medium/low gain)
    - Analysis of multiple learners
  - Retention metrics (3 tests - fast ✅)
    - Retention rate calculation
    - Forgetting rate calculation
    - Interpretation (excellent/good/poor retention)
  - Engagement metrics (1 test - fast ✅)
    - Completion rate, session time, learning streaks
  - Statistical comparisons (5 tests - fast ✅)
    - A/B test comparisons (t-tests, Cohen's d)
    - Baseline comparisons
    - No difference detection
    - Interpretation generation
  - Data persistence (2 tests - fast ✅)
    - Metrics saved to disk
    - Metrics loaded correctly

- **test_ab_testing.py** (21 tests) ✅ **A/B Testing Framework**
  - Experiment management (4 tests - fast ✅)
    - Experiment creation with variants
    - Allocation ratio validation (must sum to 1.0)
    - Start/stop experiment lifecycle
  - Learner assignment (6 tests - fast ✅)
    - Random assignment based on allocation ratio
    - Sticky assignments (same variant on repeated calls)
    - Force variant assignment for testing
    - Allocation distribution verification (50-50 split)
    - Get variant for assigned learners
  - Result recording (2 tests - fast ✅)
    - Record primary and secondary metrics
    - Error handling for unassigned learners
  - Statistical analysis (4 tests - fast ✅)
    - Analyze experiment results with t-tests
    - Variant statistics (mean, std, median)
    - Interpretation generation
    - Recommendations (ship it / don't ship)
  - Sample size calculation (2 tests - fast ✅)
    - Calculate required sample size for power analysis
    - Larger samples for smaller effect sizes
  - Data persistence (3 tests - fast ✅)
    - Experiments saved to disk
    - Assignments persisted
    - Results saved correctly

## Test Summary

**Total Tests:** 250+ tests across 13 test files

**Fast Tests (< 1 second):** 215+ tests
- test_config.py: 18 tests ✅
- test_validation.py: 18 tests ✅
- test_learner_profile_validation.py: 16 tests ✅
- test_rag_instructor.py: 18 tests ✅ (includes 5 go/no-go tests)
- test_assessment_generator.py: 15 tests ✅
- test_grading_agent.py: 12 tests ✅
- test_quiz_session.py: 23 tests ✅
- test_assessment_schemas.py: 20 tests ✅
- test_orchestrator.py: 20 tests ✅
- test_syllabus_planner.py: 15 tests ✅
- test_evaluation_metrics.py: 19 tests ✅
- test_ab_testing.py: 21 tests ✅

**Slow Tests (30-60s each):** 35 tests
- test_learner_model.py: 35 tests ⚠️ (all pass, but slow due to validation)

**Overall Status:** ✅ All tests passing

**System Coverage:**
- ✅ Configuration & Validation
- ✅ Learner Profile & Progress Tracking
- ✅ RAG-Based Teaching (with citations)
- ✅ Assessment Generation (with RAG)
- ✅ Adaptive Quizzing (auto & LLM grading)
- ✅ Points-Weighted Scoring
- ✅ Multi-Agent Syllabus Planning
- ✅ Complete Pipeline Orchestration
- ✅ Mastery-Based Adaptation
- ✅ Session Persistence
- ✅ Cross-System Integration
- ✅ Scientific Evaluation Metrics (learning gain, retention, engagement)
- ✅ A/B Testing Framework (controlled experiments, statistical analysis)

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
