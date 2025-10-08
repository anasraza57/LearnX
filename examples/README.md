# EduGPT Integration Examples

This directory contains examples demonstrating how Phase 1 (Syllabus Planning) and Phase 2 (Learner Model) work together.

## Running the Examples

```bash
# From project root
python examples/phase1_phase2_integration.py
```

## phase1_phase2_integration.py

**Complete workflow demonstration:**

1. **Generate Syllabus** (Phase 1)
   - Mock syllabus for "Machine Learning Fundamentals"
   - 5 modules with prerequisites
   - 8 weeks, 48 total hours

2. **Create Learner Profile** (Phase 2)
   - Initialize learner with preferences
   - Enroll in syllabus

3. **Simulate Learning Journey**
   - Complete Module 1: Python Basics (75%)
   - Complete Module 2: Data Analysis (82%)
   - Start Module 3: Supervised Learning (68%)

4. **View Analytics**
   - Overall completion and mastery
   - Performance trends
   - Strengths and weaknesses
   - Mastery distribution

5. **Get Recommendations**
   - Next modules to study (prerequisite-aware)
   - Weak modules needing attention
   - Weekly load feasibility check

6. **Advanced Analytics**
   - Mastery histogram
   - Category breakdown (novice/beginner/intermediate/advanced/expert)

## Expected Output

```
======================================================================
Phase 1 + Phase 2 Integration Example
======================================================================

📚 PHASE 1: Generating Syllabus...
   Topic: Machine Learning Fundamentals
   Duration: 8 weeks
   Total Hours: 48
   Modules: 5

👤 PHASE 2: Creating Learner Profile...
   Created: Alice Chen (learner-550e8400-e29b-41d4-a716-446655440001)
   Learning Style: ['visual', 'kinesthetic']
   Pace: moderate

...

📊 Analytics & Progress Report
======================================================================

   Overall Completion: 100.0%
   Overall Mastery Level: intermediate
   Total Study Time: 7.0 hours

   Average Score: 75.0%
   Performance Trend: stable
   Recommended Difficulty: medium

   📈 Mastery Summary:
      Mean: 75.0
      Median: 75.0
      Range: 68.0 - 82.0

...

🎯 Recommendations
======================================================================

   📚 Recommended Next Modules:
      1. Supervised Learning (m03-supervised-learning)
         Topics: Train/validation/test splits, Linear Regression, Logistic Regression

   ⏰ Weekly Load Feasible: ❌ No (too heavy)

...

✨ Example completed successfully!
```

## Integration Points

### 1. Syllabus → Learner Model

```python
# Phase 1: Generate syllabus
syllabus = generate_syllabus(...)

# Phase 2: Enroll learner
learner = LearnerModel(name="Alice", ...)
learner.enroll_in_syllabus(
    syllabus_id="ml-2025",
    total_modules=len(syllabus["modules"])
)
```

### 2. Track Progress

```python
# Start module
learner.start_module("m01-python")

# Record assessment
learner.record_assessment(
    module_id="m01-python",
    score=85.0,
    difficulty="medium",
    time_taken_minutes=45
)

# Complete module
learner.complete_module(
    module_id="m01-python",
    score=85.0,
    time_spent_minutes=180
)
```

### 3. Get Recommendations

```python
# Prerequisite-aware next steps
next_modules = learner.recommend_next_modules(
    syllabus_modules=syllabus["modules"],
    k=3,
    mastery_threshold=70.0
)

# Weak areas
weak = learner.weak_modules(k=5, threshold=60.0)

# Feasibility check
feasible = learner.weekly_load_feasible(
    syllabus_duration_weeks=syllabus["duration_weeks"],
    syllabus_total_hours=syllabus["total_estimated_hours"]
)
```

### 4. Analytics

```python
from src.utils.progress import (
    mastery_summary,
    mastery_histogram,
    mastery_by_category
)

# Get mastery scores
module_progress = learner.to_dict()["progress"]["module_progress"]
mastery_scores = {
    module_id: progress["best_score"]
    for module_id, progress in module_progress.items()
}

# Summary statistics
summary = mastery_summary(mastery_scores)
# {'mean': 75.0, 'median': 75.0, 'min': 68.0, 'max': 82.0, ...}

# Distribution
histogram = mastery_histogram(mastery_scores)
# [('60-69', 1), ('70-79', 1), ('80-89', 1)]

# Categorize
categories = mastery_by_category(mastery_scores)
# {'novice': [], 'beginner': [], 'intermediate': [...], ...}
```

## Next Steps

After Phase 1 + Phase 2, the next phases would be:

- **Phase 3:** RAG Instructor (teaching with citations)
- **Phase 4:** Adaptive Assessment Agent
- **Phase 5:** Orchestrator to connect all agents

See project README for full roadmap.
