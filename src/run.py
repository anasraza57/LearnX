"""
EduGPT-PersonalisedLearning: Complete Learning System Demo

This Gradio interface demonstrates all 5 phases:
- Phase 1: Configuration & Validation
- Phase 2: Learner Model
- Phase 3: RAG Instructor
- Phase 4: Adaptive Assessment
- Phase 5: Orchestrator & Integration
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import gradio as gr
from dotenv import load_dotenv

from src.models.learner_profile import LearnerModel
from src.orchestrator import LearningOrchestrator

# Load environment variables
load_dotenv()

# Global state
current_orchestrator: Optional[LearningOrchestrator] = None
current_learner: Optional[LearnerModel] = None
# Use project's data directory instead of temp directory
persist_dir = project_root / "data" / "sessions"
persist_dir.mkdir(parents=True, exist_ok=True)


# ==================== Phase 1 & 2: Learner Setup ====================

def create_learner_profile(
    name: str,
    goals: str,
    interests: str,
    prior_knowledge: str,
    learning_style: list,
    pace: str,
    difficulty_pref: str
):
    """Create a new learner profile."""
    global current_learner, current_orchestrator

    try:
        if not name:
            return "❌ Error: Please enter a name", ""

        # Parse inputs
        goals_list = [g.strip() for g in goals.split(",") if g.strip()]
        interests_list = [i.strip() for i in interests.split(",") if i.strip()]
        prior_knowledge_dict = {}
        if prior_knowledge:
            for item in prior_knowledge.split(","):
                if ":" in item:
                    key, val = item.split(":", 1)
                    prior_knowledge_dict[key.strip()] = val.strip()

        # Create learner
        current_learner = LearnerModel(
            name=name,
            learning_style=learning_style if learning_style else ["visual"],
            pace=pace,
            difficulty_preference=difficulty_pref,
        )

        # Update profile data
        learner_data = current_learner.to_dict()
        learner_data["goals"] = goals_list
        learner_data["interests"] = interests_list
        learner_data["prior_knowledge"] = prior_knowledge_dict

        # Save
        current_learner.save()

        # Reset orchestrator
        current_orchestrator = None

        profile_summary = f"""
✅ **Learner Profile Created Successfully!**

**ID**: {current_learner.learner_id}
**Name**: {current_learner.name}
**Learning Style**: {", ".join(learning_style) if learning_style else "visual"}
**Pace**: {pace}
**Difficulty Preference**: {difficulty_pref}
**Goals**: {len(goals_list)} goals
**Interests**: {len(interests_list)} interests

Profile saved to: `data/learner_profiles/{current_learner.learner_id}.json`
"""

        return profile_summary, json.dumps(learner_data, indent=2)

    except Exception as e:
        return f"❌ Error creating learner: {str(e)}", ""


# ==================== Phase 5: Generate Syllabus ====================

def generate_syllabus_ui(topic: str, duration_weeks: int, weekly_hours: float):
    """Generate personalized syllabus using multi-agent negotiation."""
    global current_orchestrator, current_learner

    try:
        if not current_learner:
            return "❌ Error: Please create a learner profile first", ""

        if not topic:
            return "❌ Error: Please enter a topic", ""

        # Create orchestrator
        current_orchestrator = LearningOrchestrator(
            learner=current_learner,
            persist_dir=persist_dir,
        )

        # Generate syllabus with auto-fetch enabled
        syllabus = current_orchestrator.generate_syllabus(
            topic=topic,
            duration_weeks=duration_weeks,
            weekly_hours=weekly_hours,
            save_to_disk=True,
            auto_fetch_content=True,  # Auto-fetch OER content
        )

        # Format output
        output = f"""
✅ **Syllabus Generated Successfully!**

**Topic**: {syllabus.get('topic')}
**Duration**: {syllabus.get('duration_weeks')} weeks
**Weekly Time**: {syllabus.get('weekly_time_hours')} hours/week
**Total Modules**: {len(syllabus.get('modules', []))}

📚 **OER Content**: Automatically fetched from Wikipedia, arXiv, and AI generation

**Modules:**
"""

        for i, module in enumerate(syllabus.get('modules', []), 1):
            prereqs = module.get('prerequisites', [])
            prereq_str = f" (Prerequisites: {', '.join(prereqs)})" if prereqs else ""

            # Show difficulty if available, otherwise omit
            difficulty = module.get('difficulty', '')
            difficulty_str = f" [{difficulty}]" if difficulty else ""

            output += f"\n{i}. **{module.get('title')}**{difficulty_str}{prereq_str}"
            output += f"\n   - **Module ID**: `{module.get('id')}` (use this to enroll)"
            output += f"\n   - Estimated: {module.get('estimated_hours')} hours"
            output += f"\n   - Topics: {', '.join(module.get('topics', []))}"

        return output, json.dumps(syllabus, indent=2)

    except Exception as e:
        return f"❌ Error generating syllabus: {str(e)}", ""


# ==================== Phase 5: Learning Session ====================

def enroll_module_ui(module_id: str):
    """Enroll learner in a module."""
    global current_orchestrator

    try:
        if not current_orchestrator or not current_orchestrator.syllabus:
            return "❌ Error: Please generate a syllabus first"

        result = current_orchestrator.enroll_learner(module_id)

        return f"""
✅ **Enrolled Successfully!**

**Module ID**: {result['module_id']}
**Title**: {result['title']}
**Session ID**: {result['session_id']}

You can now start teaching or take an assessment.
"""

    except Exception as e:
        return f"❌ Error enrolling: {str(e)}"


def start_teaching_ui():
    """Start teaching session with RAG instructor (auto-discovers documents)."""
    global current_orchestrator

    try:
        if not current_orchestrator or not current_orchestrator.current_module_id:
            return "❌ Error: Please enroll in a module first"

        # Start teaching session - RAG will auto-discover documents
        result = current_orchestrator.start_teaching_session(
            load_documents=True
        )

        return f"""
✅ **Teaching Session Started!**

**Session ID**: {result['teaching_session_id']}
**Module**: {result['module_id']}
**RAG Enabled**: {result.get('rag_enabled', False)}

Teaching session is ready. You can now ask questions!

💡 **Tip**: System automatically searches for PDF documents in:
   - `data/documents/{result['module_id']}/`
   - `data/documents/`
"""

    except Exception as e:
        return f"❌ Error starting teaching: {str(e)}"


def start_module_lessons_ui():
    """Start proactive teaching - agent teaches all topics in the module."""
    global current_orchestrator

    try:
        if not current_orchestrator or not current_orchestrator.current_module_id:
            return "❌ Error: Please enroll in a module first"

        # Teach all module content proactively
        result = current_orchestrator.teach_module_content()

        # Format output
        output = f"""
✅ **Module Lessons: {result['module_title']}**

📚 **Total Topics**: {result['total_topics']}

---

"""

        # Display each lesson
        for lesson in result['lessons']:
            output += f"""
## 📖 Topic {lesson['topic_number']}: {lesson['topic']}

{lesson['content']}

"""

            # Show citations for this lesson
            if lesson.get('citations'):
                output += "\n**Sources:**\n"
                for i, citation in enumerate(lesson['citations'][:3], 1):  # Show top 3
                    source_name = citation.get('source', 'Unknown')
                    relevance = citation.get('relevance_score', 0.0)

                    # Determine source type
                    if 'arxiv' in source_name.lower():
                        source_type = "🔬"
                    elif 'wikipedia' in source_name.lower():
                        source_type = "📚"
                    else:
                        source_type = "📄"

                    output += f"- {source_type} {source_name} ({relevance:.0%})\n"

            output += "\n---\n"

        output += f"""

💬 **Questions?** Use the "Ask a Question" section below for clarification.

✅ **Next Steps**: When ready, take the assessment to test your understanding!
"""

        return output

    except Exception as e:
        return f"❌ Error: {str(e)}"


def ask_question_ui(question: str):
    """Ask a question to the RAG instructor."""
    global current_orchestrator

    try:
        if not current_orchestrator or not current_orchestrator.instructor:
            return "❌ Error: Please start a teaching session first"

        if not question:
            return "❌ Error: Please enter a question"

        # Get teaching response
        result = current_orchestrator.teach(question=question)

        output = f"""
**Answer:**

{result['response']}

---

**📚 Sources & Citations:**
"""

        # Display detailed citations with source type indicators
        if result.get('citations') and len(result['citations']) > 0:
            for i, citation in enumerate(result['citations'], 1):
                source_name = citation.get('source', 'Unknown')
                page_info = citation.get('page')
                content_excerpt = citation.get('content', '')
                relevance = citation.get('relevance_score', 0.0)

                # Determine source type from filename
                source_type = "📄 Document"
                if 'arxiv' in source_name.lower():
                    source_type = "🔬 arXiv Paper"
                elif 'youtube' in source_name.lower():
                    source_type = "🎥 YouTube"
                elif 'wikipedia' in source_name.lower() or source_name.endswith('.md'):
                    source_type = "📚 Wikipedia"
                elif 'synthetic' in source_name.lower() or '_content.md' in source_name:
                    source_type = "🤖 AI-Generated"

                # Build citation display
                output += f"\n**{i}. {source_type}: {source_name}**"

                if page_info:
                    output += f" (Page {page_info})"

                output += f"\n   *Relevance: {relevance:.0%}*"

                # Show excerpt of cited content
                if content_excerpt:
                    excerpt = content_excerpt[:200].strip()
                    if len(content_excerpt) > 200:
                        excerpt += "..."
                    output += f"\n   > {excerpt}"

                output += "\n"
        else:
            output += "\n*No citations available (teaching without RAG documents)*"

        return output

    except Exception as e:
        return f"❌ Error: {str(e)}"


def start_assessment_ui(num_questions: int, difficulty: str):
    """Start adaptive assessment."""
    global current_orchestrator

    try:
        if not current_orchestrator or not current_orchestrator.current_module_id:
            return "❌ Error: Please enroll in a module first", ""

        result = current_orchestrator.start_assessment(
            num_questions=num_questions,
            difficulty=difficulty
        )

        questions_list = []
        for q in result['questions']:
            q_text = f"**Q{len(questions_list)+1}**: {q['question_text']}\n"
            if q['question_type'] == 'multiple_choice':
                for opt in q.get('options', []):
                    q_text += f"\n{opt['option_id']}. {opt['text']}"
            questions_list.append(q_text)

        output = f"""
✅ **Assessment Started!**

**Session ID**: {result['session_id']}
**Difficulty**: {result['difficulty']}
**Questions**: {result['num_questions']}

---

{chr(10).join(questions_list)}
"""

        return output, json.dumps(result['questions'], indent=2)

    except Exception as e:
        return f"❌ Error: {str(e)}", ""


def submit_answer_ui(question_num: int, answer: str):
    """Submit an answer to current assessment."""
    global current_orchestrator

    try:
        if not current_orchestrator or not current_orchestrator.current_quiz_session:
            return "❌ Error: No active assessment"

        if not answer:
            return "❌ Error: Please provide an answer"

        # Get current question
        questions = current_orchestrator.current_quiz_session.questions
        if question_num < 1 or question_num > len(questions):
            return f"❌ Error: Question number must be between 1 and {len(questions)}"

        question = questions[question_num - 1]

        # Submit answer
        result = current_orchestrator.submit_answer(
            question=question,
            learner_answer=answer
        )

        output = f"""
✅ **Answer Submitted!**

**Question {question_num}**: {question.question_text}
**Your Answer**: {answer}
**Correct**: {"✅ Yes" if result['is_correct'] else "❌ No"}
**Score**: {result['score']} points

**Feedback**: {result.get('feedback', 'No feedback available')}
"""

        return output

    except Exception as e:
        return f"❌ Error: {str(e)}"


def complete_assessment_ui():
    """Complete current assessment and get results."""
    global current_orchestrator

    try:
        if not current_orchestrator or not current_orchestrator.current_quiz_session:
            return "❌ Error: No active assessment", ""

        result = current_orchestrator.complete_assessment()

        output = f"""
✅ **Assessment Complete!**

**Score**: {result['score']:.1f}%
**Status**: {"✅ PASSED" if result['passed'] else "❌ FAILED"}
**Questions**: {result['total_questions']}
**Correct**: {result['correct_answers']}

**Mastery Tracking:**
- Before: {result.get('mastery_before', 0):.1f}
- After: {result.get('mastery_after', 0):.1f}
- Change: {result.get('mastery_delta', 0):+.1f}

**Recommendation**: {result.get('recommendation', 'Continue learning')}
"""

        return output, json.dumps(result, indent=2)

    except Exception as e:
        return f"❌ Error: {str(e)}", ""


def get_learner_progress_ui():
    """Get learner progress summary."""
    global current_orchestrator, current_learner

    try:
        if not current_learner:
            return "❌ Error: No learner profile created"

        learner_data = current_learner.to_dict()
        progress = learner_data.get('progress', {})
        analytics = learner_data.get('performance_analytics', {})

        output = f"""
📊 **Learner Progress Summary**

**Profile:**
- Name: {current_learner.name}
- ID: {current_learner.learner_id}
- Overall Mastery: {current_learner.overall_mastery_level}

**Progress:**
- Enrolled Syllabus: {progress.get('enrolled_syllabus_id', 'None')}
- Current Module: {progress.get('current_module_id', 'None')}
- Modules Completed: {len(progress.get('modules_completed', []))}
- Completion: {progress.get('overall_completion_percent', 0):.1f}%
- Total Study Time: {progress.get('total_study_time_minutes', 0)} minutes

**Performance:**
- Average Score: {analytics.get('average_score', 0):.1f}%
- Total Assessments: {len(analytics.get('assessment_history', []))}
- Performance Trend: {analytics.get('performance_trend', 'N/A')}
- Recommended Difficulty: {current_learner.recommended_difficulty}

**Module Progress:**
"""

        module_progress = progress.get('module_progress', {})
        if module_progress:
            for module_id, mod_data in module_progress.items():
                output += f"\n- **{module_id}**: {mod_data.get('status')} | Score: {mod_data.get('best_score', 0):.1f} | Mastery: {mod_data.get('mastery_level', 'N/A')}"
        else:
            output += "\n- No modules started yet"

        return output

    except Exception as e:
        return f"❌ Error: {str(e)}"


# ==================== Gradio UI ====================

def create_interface():
    """Create Gradio interface."""

    with gr.Blocks(title="EduGPT-PersonalisedLearning", theme=gr.themes.Soft()) as demo:
        gr.Markdown("""
            # 🎓 EduGPT-PersonalisedLearning
        """)

        # Tab 1: Learner Profile Setup
        with gr.Tab("1️⃣ Learner Profile"):
            gr.Markdown("### Create Your Learner Profile")

            with gr.Row():
                with gr.Column():
                    name_input = gr.Textbox(label="Name", placeholder="Alice Chen")
                    goals_input = gr.Textbox(
                        label="Learning Goals (comma-separated)",
                        placeholder="Master Python, Build web apps, Learn ML"
                    )
                    interests_input = gr.Textbox(
                        label="Interests (comma-separated)",
                        placeholder="Programming, Data Science, AI"
                    )
                    prior_knowledge_input = gr.Textbox(
                        label="Prior Knowledge (key:value pairs)",
                        placeholder="Programming:beginner, Math:intermediate"
                    )

                    learning_style_input = gr.CheckboxGroup(
                        choices=["visual", "auditory", "kinesthetic", "reading_writing"],
                        label="Learning Style",
                        value=["visual"]
                    )
                    pace_input = gr.Radio(
                        choices=["slow", "moderate", "fast"],
                        label="Learning Pace",
                        value="moderate"
                    )
                    difficulty_input = gr.Radio(
                        choices=["very_easy", "easy", "medium", "hard", "very_hard"],
                        label="Difficulty Preference",
                        value="medium"
                    )

                    create_btn = gr.Button("Create Learner Profile", variant="primary")

                with gr.Column():
                    profile_output = gr.Markdown()
                    profile_json = gr.Code(language="json", label="Profile JSON")

            create_btn.click(
                create_learner_profile,
                inputs=[name_input, goals_input, interests_input, prior_knowledge_input,
                       learning_style_input, pace_input, difficulty_input],
                outputs=[profile_output, profile_json]
            )

        # Tab 2: Generate Syllabus
        with gr.Tab("2️⃣ Generate Syllabus"):
            gr.Markdown("### Generate Personalized Syllabus")

            with gr.Row():
                with gr.Column():
                    topic_input = gr.Textbox(
                        label="Learning Topic",
                        placeholder="Python Programming for Beginners"
                    )
                    duration_input = gr.Slider(
                        minimum=1, maximum=16, value=8, step=1,
                        label="Duration (weeks)"
                    )
                    hours_input = gr.Slider(
                        minimum=1, maximum=20, value=5, step=0.5,
                        label="Weekly Hours"
                    )

                    generate_btn = gr.Button("Generate Syllabus", variant="primary")

                with gr.Column():
                    syllabus_output = gr.Markdown()
                    syllabus_json = gr.Code(language="json", label="Syllabus JSON")

            generate_btn.click(
                generate_syllabus_ui,
                inputs=[topic_input, duration_input, hours_input],
                outputs=[syllabus_output, syllabus_json]
            )

        # Tab 3: Teaching Session
        with gr.Tab("3️⃣ Teaching Session"):
            gr.Markdown("### RAG-Based Interactive Teaching")

            with gr.Column():
                enroll_module_input = gr.Textbox(
                    label="Module ID to Enroll",
                    placeholder="Copy the Module ID from the syllabus above (e.g., m01-introduction-to-python)"
                )
                enroll_btn = gr.Button("Enroll in Module")
                enroll_output = gr.Markdown()

                gr.Markdown("---")

                gr.Markdown("""
                **📚 RAG Document Discovery**

                The system automatically searches for PDF documents in:
                - `data/documents/<module_id>/`
                - `data/documents/`
                - `documents/<module_id>/`
                - `documents/`

                Place your course materials in any of these locations for automatic citation-based teaching.
                """)

                start_teaching_btn = gr.Button("Start Teaching Session")
                teaching_output = gr.Markdown()

                gr.Markdown("---")

                gr.Markdown("""
                **🎓 Proactive Teaching Mode**

                Click below to have the AI teach you all topics in the module sequentially.
                The agent will explain each topic with examples and citations.
                """)

                start_lessons_btn = gr.Button("🚀 Start Module Lessons", variant="primary", size="lg")
                lessons_output = gr.Markdown()

                gr.Markdown("---")

                gr.Markdown("**💬 Optional Q&A** - Ask questions for clarification")

                question_input = gr.Textbox(
                    label="Ask a Question",
                    placeholder="What is a variable in Python?"
                )
                ask_btn = gr.Button("Ask Question")
                answer_output = gr.Markdown()

            enroll_btn.click(
                enroll_module_ui,
                inputs=[enroll_module_input],
                outputs=[enroll_output]
            )

            start_teaching_btn.click(
                start_teaching_ui,
                inputs=[],
                outputs=[teaching_output]
            )

            start_lessons_btn.click(
                start_module_lessons_ui,
                inputs=[],
                outputs=[lessons_output]
            )

            ask_btn.click(
                ask_question_ui,
                inputs=[question_input],
                outputs=[answer_output]
            )

        # Tab 4: Adaptive Assessment
        with gr.Tab("4️⃣ Assessment"):
            gr.Markdown("### Adaptive Assessment System")

            with gr.Row():
                with gr.Column():
                    num_questions_input = gr.Slider(
                        minimum=1, maximum=10, value=3, step=1,
                        label="Number of Questions"
                    )
                    assessment_difficulty_input = gr.Radio(
                        choices=["easy", "medium", "hard"],
                        label="Starting Difficulty",
                        value="medium"
                    )
                    start_assessment_btn = gr.Button("Start Assessment", variant="primary")

                    gr.Markdown("---")

                    question_num_input = gr.Number(
                        label="Question Number",
                        value=1,
                        precision=0
                    )
                    answer_input = gr.Textbox(
                        label="Your Answer",
                        placeholder="Type your answer here"
                    )
                    submit_answer_btn = gr.Button("Submit Answer")

                    gr.Markdown("---")

                    complete_btn = gr.Button("Complete Assessment", variant="secondary")

                with gr.Column():
                    assessment_output = gr.Markdown()
                    assessment_json = gr.Code(language="json", label="Questions JSON")

                    answer_result_output = gr.Markdown()

                    complete_output = gr.Markdown()
                    complete_json = gr.Code(language="json", label="Results JSON")

            start_assessment_btn.click(
                start_assessment_ui,
                inputs=[num_questions_input, assessment_difficulty_input],
                outputs=[assessment_output, assessment_json]
            )

            submit_answer_btn.click(
                submit_answer_ui,
                inputs=[question_num_input, answer_input],
                outputs=[answer_result_output]
            )

            complete_btn.click(
                complete_assessment_ui,
                outputs=[complete_output, complete_json]
            )

        # Tab 5: Progress & Analytics
        with gr.Tab("5️⃣ Progress"):
            gr.Markdown("### Learner Progress & Analytics")

            refresh_btn = gr.Button("Refresh Progress", variant="primary")
            progress_output = gr.Markdown()

            refresh_btn.click(
                get_learner_progress_ui,
                outputs=[progress_output]
            )

        gr.Markdown("""
---
### 📚 About This System

This is a complete AI-powered personalised learning system featuring:
- **Multi-agent syllabus generation** with learner advocate and curriculum designer
- **RAG-based teaching** with source citations and context-aware responses
- **Adaptive assessment** with dynamic difficulty adjustment
- **Learner modeling** with mastery tracking and progress analytics
- **Complete orchestration** with session state management

Built with: Python, LangChain, OpenAI, FAISS, Gradio
        """)

    return demo


if __name__ == "__main__":
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not found in environment")
        print("Please create a .env file with your OpenAI API key")

    # Launch interface
    demo = create_interface()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        debug=True
    )
