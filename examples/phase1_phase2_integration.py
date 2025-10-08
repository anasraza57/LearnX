"""
Integration Example: Phase 1 (Syllabus Planning) + Phase 2 (Learner Model)

This demonstrates the complete workflow:
1. Generate a personalized syllabus (Phase 1)
2. Create a learner profile (Phase 2)
3. Enroll learner in syllabus
4. Track progress through lessons and assessments
5. Get recommendations for next steps
6. View analytics and progress
"""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

from src.models.learner_profile import LearnerModel
from src.utils.progress import mastery_histogram, mastery_by_category


def example_phase1_syllabus():
    """
    Mock syllabus from Phase 1 (in reality, this comes from syllabus_planner agent).
    """
    return {
        "meta": {
            "schema_version": 1,
            "created_at": "2025-10-08T10:00:00Z",
            "generated_by": "syllabus_planner_agent",
        },
        "topic": "Machine Learning Fundamentals",
        "duration_weeks": 8,
        "weekly_time_hours": 6,
        "total_estimated_hours": 48,
        "modules": [
            {
                "id": "m01-python-basics",
                "title": "Python Basics for ML",
                "description": "Essential Python programming for machine learning",
                "topics": ["Variables", "Functions", "Data Structures", "NumPy basics"],
                "outcomes": [
                    "Write Python scripts for data manipulation",
                    "Use NumPy for array operations",
                ],
                "estimated_hours": 8,
                "prerequisites": [],
            },
            {
                "id": "m02-data-analysis",
                "title": "Data Analysis with Pandas",
                "description": "Data wrangling and exploration",
                "topics": ["DataFrames", "Data cleaning", "EDA", "Visualization"],
                "outcomes": [
                    "Clean and prepare datasets",
                    "Perform exploratory data analysis",
                ],
                "estimated_hours": 10,
                "prerequisites": ["m01-python-basics"],
            },
            {
                "id": "m03-supervised-learning",
                "title": "Supervised Learning",
                "description": "Classification and regression fundamentals",
                "topics": [
                    "Train/validation/test splits",
                    "Linear Regression",
                    "Logistic Regression",
                    "Model Evaluation",
                ],
                "outcomes": [
                    "Build and evaluate classification models",
                    "Understand bias-variance tradeoff",
                ],
                "estimated_hours": 12,
                "prerequisites": ["m02-data-analysis"],
            },
            {
                "id": "m04-neural-networks",
                "title": "Neural Networks Intro",
                "description": "Deep learning fundamentals",
                "topics": [
                    "Perceptrons",
                    "Backpropagation",
                    "Activation Functions",
                    "Keras basics",
                ],
                "outcomes": [
                    "Build simple neural networks",
                    "Train models using Keras",
                ],
                "estimated_hours": 12,
                "prerequisites": ["m03-supervised-learning"],
            },
            {
                "id": "m05-advanced-topics",
                "title": "Advanced Topics",
                "description": "CNN, RNN, and deployment",
                "topics": ["CNNs", "RNNs", "Model Deployment", "Production ML"],
                "outcomes": [
                    "Implement CNNs for image tasks",
                    "Deploy ML models to production",
                ],
                "estimated_hours": 6,
                "prerequisites": ["m04-neural-networks"],
            },
        ],
    }


def main():
    print("=" * 70)
    print("Phase 1 + Phase 2 Integration Example")
    print("=" * 70)

    # ========== PHASE 1: Generate Syllabus ==========
    print("\n📚 PHASE 1: Generating Syllabus...")
    syllabus = example_phase1_syllabus()
    print(f"   Topic: {syllabus['topic']}")
    print(f"   Duration: {syllabus['duration_weeks']} weeks")
    print(f"   Total Hours: {syllabus['total_estimated_hours']}")
    print(f"   Modules: {len(syllabus['modules'])}")

    # ========== PHASE 2: Create Learner Profile ==========
    print("\n👤 PHASE 2: Creating Learner Profile...")

    learner = LearnerModel(
        learner_id="learner-" + "550e8400-e29b-41d4-a716-446655440001",
        name="Alice Chen",
        email="alice.chen@example.com",
        learning_style=["visual", "kinesthetic"],
        pace="moderate",
        difficulty_preference="medium",
        validate=False,  # Skip validation for example speed
    )

    print(f"   Created: {learner.name} ({learner.learner_id})")
    print(f"   Learning Style: {learner.learning_style}")
    print(f"   Pace: {learner.pace}")

    # ========== ENROLL IN SYLLABUS ==========
    print("\n📝 Enrolling learner in syllabus...")
    syllabus_id = "ml-fundamentals-2025"
    learner.enroll_in_syllabus(syllabus_id, total_modules=len(syllabus["modules"]))
    print(f"   Enrolled in: {syllabus_id}")

    # ========== SIMULATE LEARNING JOURNEY ==========
    print("\n🎓 Simulating Learning Journey...")

    # Module 1: Python Basics
    print("\n   Module 1: Python Basics for ML")
    learner.start_module("m01-python-basics")
    learner.record_assessment(
        module_id="m01-python-basics",
        score=75.0,
        difficulty="easy",
        time_taken_minutes=45,
        hints_used=2,
    )
    learner.complete_module(
        module_id="m01-python-basics", score=75.0, time_spent_minutes=180
    )
    print("      ✓ Completed with score: 75%")

    # Module 2: Data Analysis
    print("\n   Module 2: Data Analysis with Pandas")
    learner.start_module("m02-data-analysis")
    learner.record_assessment(
        module_id="m02-data-analysis",
        score=82.0,
        difficulty="medium",
        time_taken_minutes=50,
        hints_used=1,
    )
    learner.complete_module(
        module_id="m02-data-analysis", score=82.0, time_spent_minutes=240
    )
    print("      ✓ Completed with score: 82%")

    # Module 3: In Progress
    print("\n   Module 3: Supervised Learning")
    learner.start_module("m03-supervised-learning")
    learner.record_assessment(
        module_id="m03-supervised-learning",
        score=68.0,
        difficulty="medium",
        time_taken_minutes=55,
        hints_used=3,
    )
    print("      ⏳ In progress (68% on first assessment)")

    # ========== ANALYTICS & RECOMMENDATIONS ==========
    print("\n📊 Analytics & Progress Report")
    print("=" * 70)

    # Overall progress
    print(f"\n   Overall Completion: {learner.overall_completion_percent:.1f}%")
    print(f"   Overall Mastery Level: {learner.overall_mastery_level}")
    print(f"   Total Study Time: {learner.to_dict()['progress']['total_study_time_minutes'] / 60:.1f} hours")

    # Performance analytics
    analytics = learner.to_dict()["performance_analytics"]
    print(f"\n   Average Score: {analytics['average_score']:.1f}%")
    print(f"   Performance Trend: {analytics['performance_trend']}")
    print(f"   Recommended Difficulty: {analytics['recommended_difficulty']}")

    # Mastery summary
    print("\n   📈 Mastery Summary:")
    summary = learner.get_mastery_summary()
    print(f"      Mean: {summary['mean']:.1f}")
    print(f"      Median: {summary['median']:.1f}")
    print(f"      Range: {summary['min']:.1f} - {summary['max']:.1f}")
    print(f"\n      Distribution by Level:")
    for level, count in summary["by_level"].items():
        if count > 0:
            print(f"         {level.capitalize()}: {count}")

    # Strengths & Weaknesses
    learner.identify_strengths_weaknesses(threshold=75.0)
    analytics = learner.to_dict()["performance_analytics"]
    print(f"\n   💪 Strengths: {', '.join(analytics['strengths']) if analytics['strengths'] else 'None yet'}")
    print(f"   ⚠️  Weaknesses: {', '.join(analytics['weaknesses']) if analytics['weaknesses'] else 'None yet'}")

    # Weak modules
    weak = learner.weak_modules(k=3, threshold=70.0)
    print(f"\n   📉 Modules Needing Attention: {', '.join(weak) if weak else 'None'}")

    # ========== RECOMMENDATIONS ==========
    print("\n🎯 Recommendations")
    print("=" * 70)

    # Next modules to study
    next_modules = learner.recommend_next_modules(
        syllabus_modules=syllabus["modules"],
        k=3,
        mastery_threshold=70.0,
    )
    print("\n   📚 Recommended Next Modules:")
    for i, module_id in enumerate(next_modules, 1):
        module = next((m for m in syllabus["modules"] if m["id"] == module_id), None)
        if module:
            print(f"      {i}. {module['title']} ({module_id})")
            print(f"         Topics: {', '.join(module['topics'][:3])}")

    # Feasibility check
    feasible = learner.weekly_load_feasible(
        syllabus_duration_weeks=syllabus["duration_weeks"],
        syllabus_total_hours=syllabus["total_estimated_hours"],
    )
    print(f"\n   ⏰ Weekly Load Feasible: {'✅ Yes' if feasible else '❌ No (too heavy)'}")

    # ========== SAVE PROFILE ==========
    print("\n💾 Saving learner profile...")
    # Note: In production, you'd fix validation errors before saving
    # For demo, we'll save the raw dict
    import json
    save_dir = Path(__file__).parent.parent / "data" / "profiles" / learner.learner_id
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / "learner.json"
    with open(save_path, "w") as f:
        json.dump(learner.to_dict(), f, indent=2)
    print(f"   Saved to: {save_path}")

    print("\n" + "=" * 70)
    print("✅ Integration Complete!")
    print("=" * 70)

    # ========== ADVANCED ANALYTICS ==========
    print("\n📊 Advanced Analytics (using utils.progress)")
    print("=" * 70)

    # Get mastery scores
    module_progress = learner.to_dict()["progress"]["module_progress"]
    mastery_scores = {
        module_id: progress.get("best_score", 0.0)
        for module_id, progress in module_progress.items()
    }

    # Histogram
    print("\n   Distribution Histogram:")
    hist = mastery_histogram(mastery_scores, bin_size=10)
    for bin_label, count in hist:
        bar = "█" * count
        print(f"      {bin_label}: {bar} ({count})")

    # Category breakdown
    categories = mastery_by_category(mastery_scores)
    print("\n   By Category:")
    for category, modules in categories.items():
        if modules:
            print(f"      {category.capitalize()}: {', '.join(modules)}")

    print("\n✨ Example completed successfully!")


if __name__ == "__main__":
    main()
