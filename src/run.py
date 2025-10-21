"""
EduGPT-PersonalisedLearning: Complete Learning System with Landing Page

This Gradio interface demonstrates all 5 phases with a beautiful landing page.
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
from src.orchestrator import LearningOrchestrator, PASS_THRESHOLD

# Load environment variables
load_dotenv()

# Global state
current_orchestrator: Optional[LearningOrchestrator] = None
current_learner: Optional[LearnerModel] = None

# Use absolute path for persistence
persist_dir = Path(__file__).parent.parent / "data"
persist_dir.mkdir(exist_ok=True)


# ==================== UI Helper Functions ====================

def _format_question_display(question: dict, question_num: int, total: int, difficulty: str) -> str:
    """Format a question for display."""
    if not question:
        return "No question available"

    output = f"""
## 📝 Question {question_num} of {total}

**Difficulty**: {difficulty.upper()}

**Question**: {question['question_text']}

"""

    if question['question_type'] == 'multiple_choice' and question.get('options'):
        output += "**Options**:\n"
        for opt in question['options']:
            output += f"- **{opt['option_id']}**. {opt['text']}\n"
        output += "\n💡 *Enter the letter of your answer (e.g., A, B, C, D)*"
    else:
        output += "💡 *Type your answer below*"

    return output


# ==================== Phase 1 & 2: Learner Profile ====================

def create_learner_profile(name, email, goals, interests, prior_topic1, prior_level1, prior_topic2, prior_level2, prior_topic3, prior_level3, learning_style, pace, difficulty):
    """Create a new learner profile."""
    global current_learner

    try:
        # Parse inputs
        goals_list = [g.strip() for g in goals.split(',') if g.strip()]
        interests_list = [i.strip() for i in interests.split(',') if i.strip()]

        # Create learner
        current_learner = LearnerModel(
            name=name,
            email=email if email else None,
            learning_style=learning_style if learning_style else ["visual"],
            pace=pace,
            difficulty_preference=difficulty
        )

        # Add goals
        for goal in goals_list:
            current_learner.add_goal(goal)

        # Add interests
        for interest in interests_list:
            current_learner.add_interest(interest)

        # Add prior knowledge
        prior_knowledge_count = 0
        if prior_topic1 and prior_level1:
            current_learner.add_prior_knowledge(prior_topic1, prior_level1)
            prior_knowledge_count += 1
        if prior_topic2 and prior_level2:
            current_learner.add_prior_knowledge(prior_topic2, prior_level2)
            prior_knowledge_count += 1
        if prior_topic3 and prior_level3:
            current_learner.add_prior_knowledge(prior_topic3, prior_level3)
            prior_knowledge_count += 1

        # Save profile
        profile_path = persist_dir / "profiles" / f"{current_learner.learner_id}.json"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        current_learner.save(profile_path)

        learner_data = current_learner.to_dict()

        # Build detailed summary
        goals_display = ', '.join(goals_list) if goals_list else 'None'
        interests_display = ', '.join(interests_list) if interests_list else 'None'
        prior_knowledge_display = ', '.join([f"{k} ({v})" for k, v in current_learner.get_prior_knowledge().items()]) if prior_knowledge_count > 0 else 'None'

        profile_summary = f"""
✅ **Learner Profile Created Successfully!**

## 👤 Personal Information
- **Name**: {current_learner.name}
- **Email**: {email if email else 'Not provided'}
- **ID**: {current_learner.learner_id}

## 🎯 Learning Preferences
- **Learning Style**: {', '.join(learning_style) if learning_style else 'visual'}
- **Pace**: {pace.upper()}
- **Difficulty**: {difficulty.upper()}

## 📚 Goals & Background
- **Goals** ({len(goals_list)}): {goals_display}
- **Interests** ({len(interests_list)}): {interests_display}
- **Prior Knowledge** ({prior_knowledge_count}): {prior_knowledge_display}

---

✅ Profile saved! Proceed to **Tab 2** to generate your personalized syllabus.
"""

        return profile_summary, json.dumps(learner_data, indent=2), gr.update(interactive=False)

    except Exception as e:
        return f"❌ Error: {str(e)}", "", gr.update(interactive=True)


# ==================== Phase 5: Generate Syllabus ====================

def generate_syllabus_ui(topic: str, duration_weeks: int, weekly_hours: float):
    """Generate personalized syllabus."""
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
        
        # Generate syllabus
        syllabus = current_orchestrator.generate_syllabus(
            topic=topic,
            duration_weeks=duration_weeks,
            weekly_hours=weekly_hours,
            save_to_disk=True,
            auto_fetch_content=True,
        )
        
        output = f"""
✅ **Syllabus Generated Successfully!**

## 📚 Course Overview
- **Topic**: {syllabus.get('topic')}
- **Duration**: {syllabus.get('duration_weeks')} weeks
- **Weekly Time Commitment**: {syllabus.get('weekly_time_hours')} hours/week
- **Total Modules**: {len(syllabus.get('modules', []))}

## 📖 Learning Resources
📚 **OER Content**: Automatically fetched from Wikipedia, arXiv, and AI generation

## 📋 Course Modules
"""

        for i, module in enumerate(syllabus.get('modules', []), 1):
            prereqs = module.get('prerequisites', [])
            prereq_str = f"\n   - Prerequisites: {', '.join(prereqs)}" if prereqs else ""

            output += f"\n### Module {i}: {module.get('title')}"
            output += f"\n   - **Module ID**: `{module.get('id')}` (use this to enroll)"
            output += f"\n   - Estimated Time: {module.get('estimated_hours')} hours"
            output += f"\n   - Topics: {', '.join(module.get('topics', []))}"
            output += prereq_str
            output += "\n"

        output += "\n---\n\n✅ Syllabus saved! Proceed to **Tab 3** to enroll in a module and start learning."

        return output

    except Exception as e:
        return f"❌ Error: {str(e)}"


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
        return f"❌ Error: {str(e)}"


def start_teaching_ui():
    """Start teaching session."""
    global current_orchestrator
    
    try:
        if not current_orchestrator or not current_orchestrator.current_module_id:
            return "❌ Error: Please enroll in a module first"
        
        result = current_orchestrator.start_teaching_session(load_documents=True)
        
        return f"""
✅ **Teaching Session Started!**

**Session ID**: {result['teaching_session_id']}
**Module**: {result['module_id']}
**RAG Enabled**: {result.get('rag_enabled', False)}

Teaching session is ready!
"""
    
    except Exception as e:
        return f"❌ Error: {str(e)}"


def start_module_lessons_ui():
    """Start proactive teaching."""
    global current_orchestrator
    
    try:
        if not current_orchestrator or not current_orchestrator.current_module_id:
            return "❌ Error: Please enroll in a module first"
        
        result = current_orchestrator.teach_module_content()
        
        output = f"""
✅ **Module Lessons: {result['module_title']}**

📚 **Total Topics**: {result['total_topics']}

---

"""
        
        for lesson in result['lessons']:
            output += f"""
## 📖 Topic {lesson['topic_number']}: {lesson['topic']}

{lesson['content']}

"""
            
            if lesson.get('citations'):
                output += "\n**Sources:**\n"
                for i, citation in enumerate(lesson['citations'][:3], 1):
                    source_name = citation.get('source', 'Unknown')
                    relevance = citation.get('relevance_score', 0.0)
                    
                    source_type = "🔬" if 'arxiv' in source_name.lower() else "📚" if 'wikipedia' in source_name.lower() else "📄"
                    
                    output += f"- {source_type} {source_name} ({relevance:.0%})\n"
            
            output += "\n---\n"
        
        output += """

💬 **Questions?** Use the "Ask a Question" section below.

✅ **Next Steps**: Take the assessment to test your understanding!
"""
        
        return output
    
    except Exception as e:
        return f"❌ Error: {str(e)}"


def ask_question_ui(question: str):
    """Ask a question."""
    global current_orchestrator
    
    try:
        if not current_orchestrator or not current_orchestrator.instructor:
            return "❌ Error: Please start a teaching session first"
        
        if not question:
            return "❌ Error: Please enter a question"
        
        result = current_orchestrator.teach(question=question)
        
        output = f"""
**Answer:**

{result['response']}

---

**📚 Sources:**
"""
        
        if result.get('citations') and len(result['citations']) > 0:
            for i, citation in enumerate(result['citations'], 1):
                source_name = citation.get('source', 'Unknown')
                page_info = citation.get('page')
                content_excerpt = citation.get('content', '')
                relevance = citation.get('relevance_score', 0.0)
                
                source_type = "🔬 arXiv" if 'arxiv' in source_name.lower() else "📚 Wikipedia" if 'wikipedia' in source_name.lower() or source_name.endswith('.md') else "🤖 AI-Generated" if 'synthetic' in source_name.lower() else "📄 Document"
                
                output += f"\n**{i}. {source_type}: {source_name}**"
                
                if page_info:
                    output += f" (Page {page_info})"
                
                output += f"\n   *Relevance: {relevance:.0%}*"
                
                if content_excerpt:
                    excerpt = content_excerpt[:200].strip()
                    if len(content_excerpt) > 200:
                        excerpt += "..."
                    output += f"\n   > {excerpt}"
                
                output += "\n"
        else:
            output += "\n*No citations available*"
        
        return output
    
    except Exception as e:
        return f"❌ Error: {str(e)}"


# ==================== Phase 4: Assessment ====================

def start_assessment_ui():
    """Start adaptive assessment with intelligent defaults."""
    global current_orchestrator
    
    try:
        if not current_orchestrator or not current_orchestrator.current_module_id:
            return "❌ Error: Please enroll and complete teaching first", "", gr.update(visible=False)
        
        result = current_orchestrator.start_assessment()
        
        question_output = _format_question_display(
            result['current_question'],
            result['current_question_number'],
            result['total_questions'],
            result['starting_difficulty']
        )
        
        info_output = f"""
✅ **Assessment Started!**

**Module**: {result['module_title']}
**Total Questions**: {result['total_questions']} (auto-determined)
**Starting Difficulty**: {result['starting_difficulty']}
**Adaptive**: Yes

**Why this difficulty?** {result['difficulty_reason']}

---

{question_output}
"""
        
        return info_output, "", gr.update(visible=True)
    
    except Exception as e:
        return f"❌ Error: {str(e)}", "", gr.update(visible=False)


def submit_answer_ui(answer: str):
    """Submit answer and get next question."""
    global current_orchestrator
    
    try:
        if not current_orchestrator or not current_orchestrator.current_quiz_session:
            return "❌ Error: No active assessment", "", gr.update(visible=True)
        
        if not answer or not answer.strip():
            return "❌ Error: Please provide an answer", "", gr.update(visible=True)
        
        result = current_orchestrator.submit_answer(answer=answer.strip())
        
        feedback_output = f"""
{"✅ Correct!" if result['is_correct'] else "❌ Incorrect"}

**Your Answer**: {answer}
**Score**: {result['score']:.1f} points
**Feedback**: {result['feedback']}

**Progress**: Question {result['question_number']} of {result['total_questions']} completed
**Current Difficulty**: {result['current_difficulty']}
**Remaining**: {result['questions_remaining']}

---

"""
        
        if not result['assessment_complete']:
            next_q = _format_question_display(
                result['next_question'],
                result['next_question_number'],
                result['total_questions'],
                result['current_difficulty']
            )
            feedback_output += next_q
            return feedback_output, "", gr.update(visible=True)
        else:
            feedback_output += f"""
🎉 **{result.get('message', 'Assessment complete!')}**

Click 'Complete Assessment' below to see your results.
"""
            return feedback_output, "", gr.update(visible=False)
    
    except Exception as e:
        return f"❌ Error: {str(e)}", "", gr.update(visible=True)


def complete_assessment_ui():
    """Complete assessment."""
    global current_orchestrator, current_learner
    
    try:
        if not current_orchestrator or not current_orchestrator.current_quiz_session:
            return "❌ Error: No active assessment", ""
        
        result = current_orchestrator.complete_assessment()
        metrics = result.get('metrics', {})
        
        output = f"""
# 🎉 Assessment Complete!

## 📊 Results

**Final Score**: {result['score']:.1f}%
**Status**: {"✅ **PASSED**" if result['passed'] else "❌ **FAILED**"}
**Questions**: {result['total_questions']}
**Correct**: {result['correct_answers']}
**Time**: {metrics.get('time_taken_minutes', 0):.1f} min

## 📈 Mastery

- **Before**: {metrics.get('mastery_before', 0):.1f}%
- **After**: {metrics.get('mastery_after', 0):.1f}%
- **Change**: {metrics.get('mastery_delta', 0):+.1f}%

## 🎯 Next Steps

"""
        
        if result['passed']:
            next_module_id = current_orchestrator._get_next_module(current_orchestrator.current_module_id)
            if next_module_id:
                next_module = current_orchestrator._find_module(next_module_id)
                output += f"""
✅ **Congratulations!** Module completed!

**Next**: Enroll in **{next_module.get('title')}** (ID: `{next_module_id}`)
"""
            else:
                output += "🎊 **Outstanding!** All modules completed!"
        else:
            output += f"""
📚 **Keep Learning!** Review and try again.

You need {PASS_THRESHOLD * 100:.0f}% to pass. Next attempt will be adapted to your level.
"""
        
        if current_learner:
            current_learner.save(persist_dir / "profiles" / f"{current_learner.learner_id}.json")
        
        return output, json.dumps(result, indent=2)
    
    except Exception as e:
        return f"❌ Error: {str(e)}", ""


def get_learner_progress_ui():
    """Get real-time progress."""
    global current_orchestrator, current_learner
    
    try:
        if not current_learner:
            return "❌ Error: Create a learner profile first"
        
        learner_data = current_learner.to_dict()
        progress = learner_data.get('progress', {})
        analytics = learner_data.get('performance_analytics', {})
        
        current_module_name = "None"
        if current_orchestrator and current_orchestrator.current_module_id:
            module = current_orchestrator._find_module(current_orchestrator.current_module_id)
            if module:
                current_module_name = f"{module.get('title')}"
        
        total_modules = len(current_orchestrator.syllabus.get('modules', [])) if current_orchestrator and current_orchestrator.syllabus else 0
        completed_modules = len(progress.get('modules_completed', []))
        completion_pct = (completed_modules / total_modules * 100) if total_modules > 0 else 0
        
        output = f"""
# 📊 Progress Dashboard

## 👤 Profile
- **Name**: {current_learner.name}
- **ID**: {current_learner.learner_id}
- **Mastery**: {current_learner.overall_mastery_level.upper()}

## 📈 Progress

- **Current Module**: {current_module_name}
- **Completed**: {completed_modules} / {total_modules} ({completion_pct:.0f}%)
- **Study Time**: {progress.get('total_study_time_minutes', 0):.0f} min

## 🎯 Performance

- **Average Score**: {analytics.get('average_score', 0):.1f}%
- **Assessments**: {len(analytics.get('assessment_history', []))}
- **Trend**: {analytics.get('performance_trend', 'N/A').upper()}
- **Recommended Difficulty**: {current_learner.recommended_difficulty.upper()}

## 📚 Modules

"""
        
        module_progress = progress.get('module_progress', {})
        if module_progress:
            for module_id, mod_data in module_progress.items():
                status_icon = "✅" if mod_data.get('status') == 'completed' else "🔄" if mod_data.get('status') == 'in_progress' else "⏸️"
                
                module_title = module_id
                if current_orchestrator and current_orchestrator.syllabus:
                    mod_obj = current_orchestrator._find_module(module_id)
                    if mod_obj:
                        module_title = mod_obj.get('title', module_id)
                
                output += f"""
### {status_icon} {module_title}

- **Status**: {mod_data.get('status', 'unknown').upper()}
- **Best Score**: {mod_data.get('best_score', 0):.1f}%
- **Mastery**: {mod_data.get('mastery_level', 'novice').upper()}
- **Time**: {mod_data.get('time_spent_minutes', 0):.0f} min

"""
        else:
            output += "\n*No modules started yet*\n"
        
        return output
    
    except Exception as e:
        return f"❌ Error: {str(e)}"


# ==================== Gradio UI ====================

def create_interface():
    """Create interface with landing page."""
    
    custom_css = """
    .landing-title {
        font-size: 3.5em !important;
        font-weight: 700 !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        text-align: center;
        margin: 40px 0 20px 0;
    }
    .feature-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border-radius: 15px !important;
        padding: 25px !important;
        margin: 10px 0 !important;
        box-shadow: 0 6px 12px rgba(102, 126, 234, 0.3) !important;
    }
    .feature-box * {
        color: white !important;
    }
    .feature-box h3 {
        color: white !important;
        font-weight: 700 !important;
        margin-bottom: 10px !important;
        font-size: 1.3em !important;
    }
    .feature-box p {
        opacity: 0.95 !important;
        line-height: 1.6 !important;
    }
    """
    
    with gr.Blocks(
        title="EduGPT - Personalized AI Learning",
        theme=gr.themes.Soft(primary_hue="purple", secondary_hue="blue"),
        css=custom_css
    ) as demo:
        
        # Landing Page
        with gr.Column(visible=True) as landing_page:
            gr.HTML('<h1 class="landing-title">🎓 EduGPT</h1>')
            gr.Markdown("""
            <div style="text-align: center; font-size: 1.2em; color: #666; margin-bottom: 30px;">
            AI-Powered Personalized Learning Platform
            </div>
            
            ## Transform Your Learning Journey with AI
            
            Experience revolutionary AI-powered education with multi-agent teaching, adaptive assessments, and personalized learning pathways.
            """)
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("""
                    ### 🤖 Multi-Agent Teaching
                    AI agents collaborate to design your perfect syllabus
                    """, elem_classes="feature-box")
                
                with gr.Column():
                    gr.Markdown("""
                    ### 📚 RAG-Based Learning
                    Learn from Wikipedia, arXiv, and AI with full citations
                    """, elem_classes="feature-box")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("""
                    ### 🎯 Adaptive Assessment
                    Real-time difficulty adjustment based on performance
                    """, elem_classes="feature-box")
                
                with gr.Column():
                    gr.Markdown("""
                    ### 📈 Mastery Tracking
                    Track progress with detailed analytics
                    """, elem_classes="feature-box")
            
            gr.Markdown("""
            ---
            
            ### 🌟 Features
            
            ✅ Zero Content Preparation - Auto-fetches from multiple sources  
            ✅ Proactive Teaching - AI leads systematic topic coverage  
            ✅ Full Transparency - Every fact cited with sources  
            ✅ Smart Prerequisites - Ensures proper knowledge progression  
            
            ---
            """)
            
            start_btn = gr.Button("🚀 Start Your Learning Journey", variant="primary", size="lg")
        
        # Main App
        with gr.Column(visible=False) as main_app:
            gr.HTML("""
            <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; margin-bottom: 20px;">
                <h1 style="margin: 0;">🎓 EduGPT Learning Platform</h1>
                <p style="margin: 5px 0 0 0;">Your Personalized AI-Powered Learning Journey</p>
            </div>
            """)
            
            with gr.Tab("1️⃣ Learner Profile"):
                gr.Markdown("### Create Your Learner Profile")
                
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("#### 👤 Personal Information")
                        name_input = gr.Textbox(label="Full Name", placeholder="Alice Chen")
                        email_input = gr.Textbox(label="Email (optional)", placeholder="alice@example.com")

                        gr.Markdown("#### 🎯 Learning Goals & Interests")
                        goals_input = gr.Textbox(
                            label="Learning Goals (comma-separated)",
                            placeholder="Master Python, Build web apps, Learn machine learning",
                            lines=2
                        )
                        interests_input = gr.Textbox(
                            label="Interests (comma-separated)",
                            placeholder="Programming, Data Science, AI, Web Development",
                            lines=2
                        )

                        gr.Markdown("#### 📚 Prior Knowledge")
                        gr.Markdown("*Add up to 3 topics you already know*")

                        with gr.Row():
                            prior_topic1 = gr.Textbox(label="Topic 1", placeholder="e.g., Programming")
                            prior_level1 = gr.Dropdown(
                                choices=["beginner", "intermediate", "advanced", "expert"],
                                label="Level",
                                value="beginner"
                            )

                        with gr.Row():
                            prior_topic2 = gr.Textbox(label="Topic 2 (optional)", placeholder="e.g., Mathematics")
                            prior_level2 = gr.Dropdown(
                                choices=["beginner", "intermediate", "advanced", "expert"],
                                label="Level"
                            )

                        with gr.Row():
                            prior_topic3 = gr.Textbox(label="Topic 3 (optional)", placeholder="e.g., Statistics")
                            prior_level3 = gr.Dropdown(
                                choices=["beginner", "intermediate", "advanced", "expert"],
                                label="Level"
                            )

                        gr.Markdown("#### 🧠 Learning Preferences")
                        learning_style_input = gr.CheckboxGroup(
                            choices=["visual", "auditory", "kinesthetic", "reading_writing"],
                            label="Learning Style (select all that apply)",
                            value=["visual"]
                        )
                        pace_input = gr.Radio(
                            choices=["slow", "moderate", "fast"],
                            label="Learning Pace",
                            value="moderate"
                        )
                        difficulty_input = gr.Radio(
                            choices=["very_easy", "easy", "medium", "hard"],
                            label="Preferred Difficulty Level",
                            value="medium"
                        )

                        create_btn = gr.Button("✨ Create My Learning Profile", variant="primary", size="lg")

                    with gr.Column():
                        profile_output = gr.Markdown()
                        profile_json = gr.Code(language="json", label="Profile Data (JSON)", visible=False)

                create_btn.click(
                    create_learner_profile,
                    inputs=[name_input, email_input, goals_input, interests_input,
                           prior_topic1, prior_level1, prior_topic2, prior_level2, prior_topic3, prior_level3,
                           learning_style_input, pace_input, difficulty_input],
                    outputs=[profile_output, profile_json, create_btn]
                )
            
            with gr.Tab("2️⃣ Generate Syllabus"):
                gr.Markdown("### Generate Personalized Syllabus")

                with gr.Row():
                    with gr.Column():
                        topic_input = gr.Textbox(
                            label="Learning Topic",
                            placeholder="Python Programming"
                        )
                        duration_input = gr.Slider(1, 16, 8, step=1, label="Duration (weeks)")
                        hours_input = gr.Slider(1, 20, 5, step=0.5, label="Weekly Hours")
                        generate_btn = gr.Button("Generate Syllabus", variant="primary")

                    with gr.Column():
                        syllabus_output = gr.Markdown()

                generate_btn.click(
                    generate_syllabus_ui,
                    inputs=[topic_input, duration_input, hours_input],
                    outputs=[syllabus_output]
                )
            
            with gr.Tab("3️⃣ Teaching Session"):
                gr.Markdown("### RAG-Based Interactive Teaching")
                
                with gr.Column():
                    enroll_input = gr.Textbox(label="Module ID", placeholder="m01-introduction-to-python")
                    enroll_btn = gr.Button("Enroll in Module")
                    enroll_output = gr.Markdown()
                    
                    gr.Markdown("---")
                    
                    start_teaching_btn = gr.Button("Start Teaching Session")
                    teaching_output = gr.Markdown()
                    
                    gr.Markdown("---")
                    
                    start_lessons_btn = gr.Button("🚀 Start Module Lessons", variant="primary", size="lg")
                    lessons_output = gr.Markdown()
                    
                    gr.Markdown("---")
                    
                    question_input = gr.Textbox(label="Ask a Question", placeholder="What is a variable?")
                    ask_btn = gr.Button("Ask Question")
                    answer_output = gr.Markdown()
                
                enroll_btn.click(enroll_module_ui, inputs=[enroll_input], outputs=[enroll_output])
                start_teaching_btn.click(start_teaching_ui, outputs=[teaching_output])
                start_lessons_btn.click(start_module_lessons_ui, outputs=[lessons_output])
                ask_btn.click(ask_question_ui, inputs=[question_input], outputs=[answer_output])
            
            with gr.Tab("4️⃣ Assessment"):
                gr.Markdown("""
                ### 🎯 Adaptive Assessment
                
                **How it works:**
                - Questions auto-determined based on module topics
                - Difficulty based on your performance history
                - Adapts in real-time as you answer
                - One question at a time for better focus
                """)
                
                with gr.Column():
                    start_assessment_btn = gr.Button("🚀 Start Assessment", variant="primary", size="lg")
                    assessment_output = gr.Markdown()
                    
                    gr.Markdown("---")
                    
                    with gr.Column(visible=False) as answer_section:
                        gr.Markdown("### Your Answer")
                        answer_input = gr.Textbox(
                            label="Type your answer",
                            placeholder="For MCQ, enter letter (A/B/C/D). For open-ended, write your answer.",
                            lines=3
                        )
                        submit_btn = gr.Button("Submit Answer", variant="primary")
                    
                    feedback_output = gr.Markdown()
                    
                    gr.Markdown("---")
                    
                    complete_btn = gr.Button("✅ Complete Assessment & View Results", variant="secondary", size="lg")
                    complete_output = gr.Markdown()
                    complete_json = gr.Code(language="json", label="Results", visible=False)
                
                start_assessment_btn.click(
                    start_assessment_ui,
                    outputs=[assessment_output, feedback_output, answer_section]
                )
                
                submit_btn.click(
                    submit_answer_ui,
                    inputs=[answer_input],
                    outputs=[feedback_output, answer_input, answer_section]
                ).then(
                    lambda: "",
                    outputs=[answer_input]
                )
                
                complete_btn.click(
                    complete_assessment_ui,
                    outputs=[complete_output, complete_json]
                )
            
            with gr.Tab("5️⃣ Progress"):
                gr.Markdown("### Learner Progress & Analytics")
                
                refresh_btn = gr.Button("Refresh Progress", variant="primary")
                progress_output = gr.Markdown()
                
                refresh_btn.click(get_learner_progress_ui, outputs=[progress_output])
        
        # Transition handler
        start_btn.click(
            lambda: (gr.update(visible=False), gr.update(visible=True)),
            outputs=[landing_page, main_app]
        )
    
    return demo


if __name__ == "__main__":
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in environment variables")
        print("Please create a .env file with your OpenAI API key")
        sys.exit(1)
    
    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
