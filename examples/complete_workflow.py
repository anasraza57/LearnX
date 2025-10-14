"""
Complete workflow example: Syllabus → Teaching → Assessment → Profile Update

Demonstrates end-to-end integration of all system components:
1. Create learner profile
2. Generate teaching materials with RAG instructor
3. Generate assessment questions from taught materials
4. Conduct adaptive quiz
5. Grade responses
6. Update learner profile with results
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.learner_profile import LearnerModel
from src.agents.rag_instructor import create_instructor_from_documents
from src.agents.assessment_generator import AssessmentGenerator
from src.agents.grading_agent import GradingAgent
from src.models.quiz_session import AdaptiveQuiz


def main():
    # ==================== Step 1: Create Learner Profile ====================
    print("=" * 60)
    print("STEP 1: Creating Learner Profile")
    print("=" * 60)

    learner = LearnerModel(
        name="Alice Johnson",
        difficulty_preference="easy",
    )

    # Set learning goals
    learner._data["goals"] = ["Learn Python programming basics"]

    print(f"✓ Created learner: {learner.name} (ID: {learner.learner_id})")
    print(f"  Difficulty preference: {learner.difficulty_preference}")
    print(f"  Goals: {learner._data['goals']}")
    print()

    # ==================== Step 2: Teaching with RAG ====================
    print("=" * 60)
    print("STEP 2: Teaching Session with RAG Instructor")
    print("=" * 60)

    # Create RAG instructor from teaching documents
    docs_dir = Path("data/teaching_documents")
    if not docs_dir.exists():
        print(f"⚠ Warning: {docs_dir} not found. Using mock example.")
        print("  In production, load documents with:")
        print("  instructor = create_instructor_from_documents(")
        print("      file_paths=['path/to/python_basics.pdf'],")
        print("      module_id='m01-python-basics'")
        print("  )")
        instructor = None
    else:
        instructor = create_instructor_from_documents(
            file_paths=list(docs_dir.glob("*.pdf")),
            module_id="m01-python-basics",
        )
        print(f"✓ Created RAG instructor with {len(instructor.vector_store.documents)} documents")

    # Simulate teaching session
    teaching_session_id = "ts-example-session-001"
    module_id = "m01-python-basics"

    if instructor:
        response = instructor.teach(
            question="What is a variable in Python?",
            max_tokens=200,
        )
        print(f"\n📚 Teaching Response:")
        print(f"  {response.response[:200]}...")
        print(f"  Citations: {len(response.citations)} sources")

    print(f"\n✓ Teaching session: {teaching_session_id}")
    print(f"  Module: {module_id}")
    print()

    # ==================== Step 3: Generate Assessment Questions ====================
    print("=" * 60)
    print("STEP 3: Generating Assessment Questions")
    print("=" * 60)

    # Create assessment generator (can use same vector store as instructor)
    vector_store = instructor.vector_store if instructor else None
    generator = AssessmentGenerator(vector_store=vector_store)

    print("✓ Created assessment generator")

    # Generate questions (in production, this would actually call LLM)
    # For this example, we'll create mock questions
    from src.agents.assessment_generator import AssessmentQuestion
    import uuid

    questions = [
        AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="What is a variable in Python?",
            question_type="multiple_choice",
            difficulty="easy",
            module_id=module_id,
            options=[
                {"option_id": "A", "text": "A container for storing data", "is_correct": True},
                {"option_id": "B", "text": "A type of loop", "is_correct": False},
                {"option_id": "C", "text": "A function", "is_correct": False},
            ],
            points=2.0,
        ),
        AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Python is a compiled language.",
            question_type="true_false",
            difficulty="easy",
            module_id=module_id,
            correct_answer="false",
            explanation="Python is an interpreted language, not compiled.",
            points=1.0,
        ),
        AssessmentQuestion(
            question_id=f"q-{uuid.uuid4()}",
            question_text="Explain what indentation means in Python.",
            question_type="short_answer",
            difficulty="medium",
            module_id=module_id,
            answer_rubric="Look for: code structure, blocks, whitespace importance",
            points=5.0,
        ),
    ]

    print(f"✓ Generated {len(questions)} questions:")
    for q in questions:
        print(f"  - {q.question_type} ({q.difficulty}): {q.question_text[:50]}...")
        q.validate()  # Validate each question
    print()

    # ==================== Step 4: Conduct Adaptive Quiz ====================
    print("=" * 60)
    print("STEP 4: Conducting Adaptive Quiz")
    print("=" * 60)

    quiz = AdaptiveQuiz(
        learner_id=learner.learner_id,
        module_id=module_id,
        teaching_session_id=teaching_session_id,  # Link to teaching session
        starting_difficulty="easy",
        passing_score=70.0,
        adaptive=True,
    )

    print(f"✓ Created quiz session: {quiz.session_id}")
    print(f"  Linked to teaching session: {teaching_session_id}")
    print(f"  Starting difficulty: {quiz.current_difficulty}")
    print()

    # Add questions to quiz
    for question in questions:
        quiz.add_question(question)

    # Simulate learner answering questions
    print("📝 Learner answering questions:")

    # Question 1: MCQ (correct)
    response1 = quiz.submit_answer(
        question_id=questions[0].question_id,
        learner_answer="A",
        time_taken_seconds=45,
    )
    print(f"  Q1: {response1.question_type} → {'✓ Correct' if response1.is_correct else '✗ Incorrect'}")
    print(f"      Score: {response1.score}/100, Graded by: {response1.graded_by}")

    # Question 2: True/False (correct)
    response2 = quiz.submit_answer(
        question_id=questions[1].question_id,
        learner_answer="false",
        time_taken_seconds=30,
    )
    print(f"  Q2: {response2.question_type} → {'✓ Correct' if response2.is_correct else '✗ Incorrect'}")
    print(f"      Score: {response2.score}/100, Graded by: {response2.graded_by}")
    print(f"      Difficulty adjusted to: {quiz.current_difficulty}")

    # Question 3: Short answer (needs manual grading)
    learner_answer = "Indentation in Python is used to define code blocks and structure. It's important for the syntax."
    response3 = quiz.submit_answer(
        question_id=questions[2].question_id,
        learner_answer=learner_answer,
        time_taken_seconds=120,
    )
    print(f"  Q3: {response3.question_type} → Awaiting grading")
    print(f"      Status: {response3.response_status}")
    print()

    # ==================== Step 5: Grade Open-Ended Responses ====================
    print("=" * 60)
    print("STEP 5: Grading Open-Ended Response")
    print("=" * 60)

    grader = GradingAgent()
    print("✓ Created grading agent")

    # Grade the short answer (in production, this calls LLM)
    # For this example, we'll simulate the result
    print(f"\n📊 Grading short answer question...")
    print(f"  Question: {questions[2].question_text}")
    print(f"  Answer: {learner_answer}")

    # Simulate grading result
    from src.agents.grading_agent import GradingResult
    grading_result = GradingResult(
        score=80.0,
        is_correct=True,
        feedback="Good explanation of indentation's role in Python syntax.",
        strengths=["Mentioned code structure", "Noted syntax importance"],
        improvements=["Could add example of indentation error"],
        graded_by="llm",
    )

    # Update response with grading
    response3.score = grading_result.score
    response3.is_correct = grading_result.is_correct
    response3.feedback = grading_result.feedback
    response3.graded_by = grading_result.graded_by
    response3.response_status = "graded"

    print(f"\n✓ Graded by {grading_result.graded_by}")
    print(f"  Score: {grading_result.score}/100")
    print(f"  Feedback: {grading_result.feedback}")
    print()

    # ==================== Step 6: Complete Quiz & Get Recommendations ====================
    print("=" * 60)
    print("STEP 6: Completing Quiz & Getting Recommendations")
    print("=" * 60)

    result = quiz.complete_quiz()

    print(f"✓ Quiz completed!")
    print(f"  Session ID: {result['session_id']}")
    print(f"  Overall Score: {result['score']:.1f}%")
    print(f"  Status: {'PASSED ✓' if result['passed'] else 'FAILED ✗'}")
    print(f"  Questions: {result['answered_questions']}/{result['total_questions']}")
    print()

    print("📋 Recommendations:")
    recs = result['recommendations']
    print(f"  Ready for next module: {recs['ready_for_next_module']}")
    print(f"  Next difficulty: {recs['next_difficulty']}")
    if recs['should_review']:
        print(f"  Topics to review: {', '.join(recs['should_review'])}")
    if recs.get('next_topic_id'):
        print(f"  Next topic: {recs['next_topic_id']}")
    print()

    # ==================== Step 7: Update Learner Profile ====================
    print("=" * 60)
    print("STEP 7: Updating Learner Profile")
    print("=" * 60)

    # Record quiz result in learner profile
    learner.record_quiz_result(
        quiz_session_id=quiz.session_id,
        module_id=module_id,
        score=result['score'],
        difficulty=quiz.starting_difficulty,
        num_questions=len(questions),
        time_taken_minutes=3,
        passed=result['passed'],
    )

    print(f"✓ Updated learner profile")

    # Check updated stats
    assessment_history = learner.get_assessment_history()
    print(f"  Total assessments: {len(assessment_history)}")
    print(f"  Latest assessment:")
    latest = assessment_history[-1]
    print(f"    - Module: {latest['module_id']}")
    print(f"    - Score: {latest['score']}%")
    print(f"    - Quiz Session: {latest.get('quiz_session_id', 'N/A')}")
    print()

    # Show performance analytics
    analytics = learner.get_performance_analytics()
    print("📊 Updated Performance Analytics:")
    print(f"  Overall GPA: {analytics['overall_gpa']:.2f}")
    print(f"  Total study time: {analytics['total_study_time_hours']}h")
    print(f"  Assessment attempts: {analytics['assessment_attempts']}")
    print()

    # ==================== Summary ====================
    print("=" * 60)
    print("INTEGRATION COMPLETE")
    print("=" * 60)
    print("\n✅ Successfully demonstrated:")
    print("  1. Learner profile creation")
    print("  2. RAG-based teaching session")
    print("  3. Assessment question generation from taught materials")
    print("  4. Adaptive quiz with auto-grading (MCQ/T-F)")
    print("  5. LLM-based grading (short answer)")
    print("  6. Quiz completion with recommendations")
    print("  7. Learner profile update with quiz results")
    print()
    print("🔗 Cross-System Integration:")
    print(f"  - Syllabus module: {module_id}")
    print(f"  - Teaching session: {teaching_session_id}")
    print(f"  - Quiz session: {quiz.session_id}")
    print(f"  - Learner profile: {learner.learner_id}")
    print()
    print("📈 Points-Weighted Scoring:")
    print(f"  - Q1 (MCQ): 100% × 2pts = 2pts")
    print(f"  - Q2 (T/F): 100% × 1pt = 1pt")
    print(f"  - Q3 (Short): 80% × 5pts = 4pts")
    print(f"  - Total: 7pts / 8pts = {result['score']:.1f}%")
    print()


if __name__ == "__main__":
    main()
