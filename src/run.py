"""
LearnX: Complete Learning System with Landing Page

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
    """Format a question for display with progress bar at top."""
    if not question:
        return "No question available"

    # Calculate progress percentage
    progress_pct = (question_num / total) * 100

    # Handle both dict and object forms
    if hasattr(question, 'question_text'):
        question_text = question.question_text
        question_type = question.question_type
        options = getattr(question, 'options', None)
    else:
        question_text = question.get('question_text', 'Unknown question')
        question_type = question.get('question_type', 'open_ended')
        options = question.get('options', None)

    output = f"""
## Progress: {question_num}/{total}
<div style="background: #f0f0f0; border-radius: 10px; height: 20px; margin: 10px 0;">
    <div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); width: {progress_pct:.1f}%; height: 20px; border-radius: 10px; transition: width 0.3s;"></div>
</div>

---

**Difficulty**: {difficulty.upper()}

**Question**: {question_text}

"""

    if question_type == 'multiple_choice' and options:
        output += "**Options**:\n"
        for opt in options:
            # Handle both dict and object forms for options
            if hasattr(opt, 'option_id'):
                opt_id = opt.option_id
                opt_text = opt.text
            else:
                opt_id = opt.get('option_id', '?')
                opt_text = opt.get('text', '')
            output += f"- **{opt_id}**. {opt_text}\n"
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

## 🎯 Learning Preferences
- **Learning Style**: {', '.join(learning_style) if learning_style else 'visual'}
- **Pace**: {pace.upper()}
- **Difficulty**: {difficulty.upper()}

## 📚 Goals & Background
- **Goals** ({len(goals_list)}): {goals_display}
- **Interests** ({len(interests_list)}): {interests_display}
- **Prior Knowledge** ({prior_knowledge_count}): {prior_knowledge_display}

---

✅ Profile saved! Proceed to **Tab 2** to generate your personalised syllabus.
"""

        return profile_summary, json.dumps(learner_data, indent=2), gr.update(interactive=False)

    except Exception as e:
        return f"❌ Error: {str(e)}", "", gr.update(interactive=True)


# ==================== Phase 5: Generate Syllabus ====================

def generate_syllabus_ui(topic: str, duration_weeks: int, weekly_hours: float):
    """Generate personalised syllabus with visible loading states."""
    global current_orchestrator, current_learner

    # Immediately show a loading message and disable the button
    yield (
        "<div style='margin-top: 40px;'>⏳ Preparing to generate your personalised syllabus…</div>",
        gr.update(choices=["Checking prerequisites…"], value=None, interactive=False),
        gr.update(value="Generating…", interactive=False)
    )

    try:
        if not current_learner:
            yield ("❌ Error: Please create a learner profile first", gr.update(), gr.update(value="Generate Syllabus", interactive=True))
            return
        if not topic:
            yield ("❌ Error: Please enter a topic", gr.update(), gr.update(value="Generate Syllabus", interactive=True))
            return

        # Step 1: create orchestrator
        yield (
            "<div style='margin-top: 40px;'>🔧 Setting up the learning orchestrator…</div>",
            gr.update(choices=["Setting up…"], value=None, interactive=False),
            gr.update(value="Generating…", interactive=False)
        )
        current_orchestrator = LearningOrchestrator(
            learner=current_learner,
            persist_dir=persist_dir,
        )

        # Step 2: kick off generation
        yield (
            "<div style='margin-top: 40px;'>📚 Generating syllabus (fetching OER, structuring modules, mapping prerequisites)…</div>",
            gr.update(choices=["Generating syllabus…"], value=None, interactive=False),
            gr.update(value="Generating…", interactive=False)
        )

        # Generate syllabus (long-running)
        syllabus = current_orchestrator.generate_syllabus(
            topic=topic,
            duration_weeks=duration_weeks,
            weekly_hours=weekly_hours,
            save_to_disk=True,
            auto_fetch_content=True,
        )

        # Step 3: finishing touches
        yield (
            "<div style='margin-top: 40px;'>✅ Finalizing and saving syllabus…</div>",
            gr.update(choices=["Finalizing…"], value=None, interactive=False),
            gr.update(value="Generating…", interactive=False)
        )

        # Build output
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

        module_id_to_title = {m.get('id'): m.get('title') for m in syllabus.get('modules', [])}
        for i, module in enumerate(syllabus.get('modules', []), 1):
            prereqs = module.get('prerequisites', [])
            prereq_names = [module_id_to_title.get(pr_id, pr_id) for pr_id in prereqs]
            prereq_str = f"\n   - Prerequisites: {', '.join(prereq_names)}" if prereq_names else ""
            output += f"\n### Module {i}: {module.get('title')}"
            output += f"\n   - Estimated Time: {module.get('estimated_hours')} hours"
            output += f"\n   - Topics: {', '.join(module.get('topics', []))}"
            output += prereq_str + "\n"

        output += "\n---\n\n✅ Syllabus saved! Proceed to **Tab 3** to enroll in a module and start learning."

        dropdown_update = update_module_dropdown()

        # Final yield: show result, update dropdown, restore original text and re-enable button
        yield (
            output,
            dropdown_update,
            gr.update(value="Generate Syllabus", interactive=True)
        )

    except Exception as e:
        # Show error and re-enable the button
        yield (f"❌ Error: {str(e)}", gr.update(), gr.update(value="Generate Syllabus", interactive=True))


# ==================== Phase 5: Learning Session ====================

def get_available_modules():
    """
    Get list of available modules (only modules user can enroll in).
    Returns a list of available module names with checkmark indicator.
    """
    global current_orchestrator, current_learner

    if not current_orchestrator or not current_orchestrator.syllabus:
        return []

    modules = current_orchestrator.syllabus.get('modules', [])
    if not modules:
        return []

    available_modules = []
    learner_data = current_learner.to_dict() if current_learner else {}
    module_progress = learner_data.get('progress', {}).get('module_progress', {})

    for module in modules:
        module_title = module.get('title', 'Untitled Module')

        # Check if prerequisites are met
        prerequisites = module.get('prerequisites', [])
        is_available = True

        if prerequisites:
            for prereq_id in prerequisites:
                prereq_status = module_progress.get(prereq_id, {})
                prereq_score = prereq_status.get('best_score', 0.0)

                # Require at least 70% mastery on prerequisites
                if prereq_score < 70.0:
                    is_available = False
                    break

        # Only add available modules to the list
        if is_available:
            available_modules.append(module_title)

    return available_modules


def update_module_dropdown():
    """Update the module dropdown after syllabus generation or enrollment."""
    available_modules = get_available_modules()

    if not available_modules:
        return gr.update(choices=["No modules available"], value=None, interactive=False)

    # Return dropdown with only available modules
    return gr.update(choices=available_modules, value=None, interactive=True)


def get_module_id_from_name(module_name: str) -> Optional[str]:
    """Convert module name to module ID."""
    global current_orchestrator

    if not current_orchestrator or not current_orchestrator.syllabus:
        return None

    modules = current_orchestrator.syllabus.get('modules', [])
    for module in modules:
        if module.get('title') == module_name:
            return module.get('id')

    return None


def enroll_module_ui(module_name: str):
    """Enroll learner in a module by name."""
    global current_orchestrator

    try:
        if not current_orchestrator or not current_orchestrator.syllabus:
            return "❌ Error: Please generate a syllabus first", gr.update(), gr.update(interactive=False), gr.update(interactive=True)

        if not module_name or module_name == "No modules available":
            return "❌ Error: Please select a module", gr.update(), gr.update(interactive=False), gr.update(interactive=True)

        # Convert module name to module ID
        module_id = get_module_id_from_name(module_name)
        if not module_id:
            return f"❌ Error: Module '{module_name}' not found", gr.update(), gr.update(interactive=False), gr.update(interactive=True)

        result = current_orchestrator.enroll_learner(module_id)

        # Update dropdown to reflect any changes in module availability
        dropdown_update = update_module_dropdown()

        output = f"""
✅ **Enrolled Successfully!**

**Module**: {result['title']}
"""

        # Add prior knowledge insights if any
        prior_knowledge = result.get('prior_knowledge', {})
        if prior_knowledge:
            output += "\n\n### 🎓 Your Prior Knowledge\n"
            output += "Great! You already have experience in:\n"
            for topic, level in prior_knowledge.items():
                level_emoji = {"beginner": "🌱", "intermediate": "🌿", "advanced": "🌳", "expert": "🏆"}.get(level, "📚")
                output += f"- **{topic}** ({level_emoji} {level.capitalize()})\n"
            output += "\n*This will help you learn faster in related topics!*\n"

        # Show acceleration opportunities
        if result.get('acceleration_available'):
            skip_suggested = result.get('skip_suggested', [])
            output += "\n\n### 🚀 Acceleration Available!\n"
            output += result.get('acceleration_message', 'You can skip some topics based on your prior knowledge.')
            output += "\n\n**Topics you may skip:**\n"
            for item in skip_suggested:
                topic = item.get('topic', 'Unknown')
                level = item.get('prior_level', 'intermediate')
                reason = item.get('reason', '')
                output += f"- **{topic}** - {reason}\n"
            output += "\n*We'll start at an increased difficulty to match your level.*\n"

        output += "\nYou can now start learning by clicking \"Start Module Lessons\" below."

        # Enable the Start Module Lessons button and disable the Enroll button
        return output, dropdown_update, gr.update(interactive=True), gr.update(interactive=False)

    except Exception as e:
        return f"❌ Error: {str(e)}", gr.update(), gr.update(interactive=False), gr.update(interactive=True)


def start_teaching_ui():
    """Start teaching session."""
    global current_orchestrator
    
    try:
        if not current_orchestrator or not current_orchestrator.current_module_id:
            return "❌ Error: Please enroll in a module first"
        
        result = current_orchestrator.start_teaching_session(load_documents=True)

        # Get module name instead of ID
        module = current_orchestrator._find_module(result['module_id'])
        module_name = module.get('title', 'Unknown Module') if module else 'Unknown Module'

        return f"""
✅ **Teaching Session Started!**

**Module**: {module_name}
**RAG Enabled**: {result.get('rag_enabled', False)}

Teaching session is ready! You can now ask questions or start lessons.
"""
    
    except Exception as e:
        return f"❌ Error: {str(e)}"


def start_module_lessons_ui():
    """Start teaching session and display module lessons with visible loading states."""
    global current_orchestrator

    # Immediately show loading message and disable button
    yield (
        "<div style='margin-top: 40px;'>⏳ Preparing to load module lessons…</div>",
        gr.update(value="Loading…", interactive=False)
    )

    try:
        if not current_orchestrator or not current_orchestrator.current_module_id:
            yield ("❌ Error: Please enroll in a module first", gr.update(value="🚀 Start Module Lessons", interactive=True))
            return

        # Step 1: Start teaching session
        yield (
            "<div style='margin-top: 40px;'>🔧 Starting teaching session and loading documents…</div>",
            gr.update(value="Loading…", interactive=False)
        )

        # Auto-start teaching session if not already started
        try:
            current_orchestrator.start_teaching_session(load_documents=True)
        except Exception:
            # Teaching session might already be started, continue anyway
            pass

        # Step 2: Get module lessons
        yield (
            "<div style='margin-top: 40px;'>📚 Generating personalised lessons for all topics…</div>",
            gr.update(value="Loading…", interactive=False)
        )

        # Get module lessons
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
                    url = citation.get('url')
                    source_type_str = citation.get('source_type', 'document')
                    page = citation.get('page')

                    # Get emoji for source type
                    type_emoji = {
                        "wikipedia": "📖",
                        "book": "📚",
                        "website": "🌐",
                        "article": "📄",
                        "video": "🎥",
                        "course": "🎓",
                        "tutorial": "💡",
                        "paper": "📜"
                    }.get(source_type_str, "📑")

                    # Format citation
                    if url:
                        citation_text = f"[{source_name}]({url})"
                    else:
                        citation_text = source_name

                    if page:
                        citation_text += f", page {page}"

                    output += f"- {type_emoji} {citation_text}\n"

            output += "\n---\n"

        output += """

💬 **Questions?** Use the "Ask a Question" section below.

✅ **Next Steps**: Take the assessment to test your understanding!
"""

        # Final yield: show result, restore original text and re-enable button
        yield (
            output,
            gr.update(value="🚀 Start Module Lessons", interactive=True)
        )

    except Exception as e:
        # Show error and re-enable button
        yield (f"❌ Error: {str(e)}", gr.update(value="🚀 Start Module Lessons", interactive=True))


def ask_question_ui(question: str):
    """Ask a question - automatically searches current module first, then all modules if needed."""
    global current_orchestrator

    try:
        if not current_orchestrator or not current_orchestrator.instructor:
            return "❌ Error: Please start a teaching session first"

        if not question:
            return "❌ Error: Please enter a question"

        # Handle greetings and casual conversation
        question_lower = question.lower().strip()
        greetings = ['hi', 'hello', 'hey', 'greetings', 'good morning', 'good afternoon', 'good evening']

        if question_lower in greetings or len(question_lower.split()) <= 2 and any(g in question_lower for g in greetings):
            return f"""
👋 **Hello!**

I'm your AI learning assistant. I'm here to help you understand the material better.

**You can ask me:**
- Questions about topics in your current module
- Clarifications on concepts you're learning
- Examples or explanations in different ways
- Questions about topics from other modules too!

**Examples:**
- "What are Python variables?"
- "Can you explain inheritance with an example?"
- "What's the difference between lists and tuples?"

What would you like to learn about?
"""

        # Detect off-topic questions (weather, sports, etc.)
        off_topic_keywords = ['weather', 'sports', 'news', 'movie', 'recipe', 'game', 'music', 'stock', 'price']
        if any(keyword in question_lower for keyword in off_topic_keywords) and not any(edu in question_lower for edu in ['learn', 'teach', 'explain', 'course', 'module']):
            return f"""
❌ **Off-Topic Question**

I'm a learning assistant focused on helping you with your course material. I can't answer questions about {question_lower.split()[0] if len(question_lower.split()) > 0 else 'that topic'}.

**I can help with:**
- Topics from your current module
- Concepts from other modules in your syllabus
- Examples and explanations

Try asking about something related to your learning goals! 📚
"""

        # Try current module first
        result = current_orchestrator.teach(question=question, search_all_modules=False)

        # If no citations found or confidence is low, try searching all modules
        if not result.get('citations') or len(result['citations']) == 0:
            result = current_orchestrator.teach(question=question, search_all_modules=True)
            searched_elsewhere = True
        else:
            searched_elsewhere = False

        # Check if still no relevant results
        if not result.get('citations') or len(result['citations']) == 0:
            return f"""
⚠️ **No Relevant Information Found**

I couldn't find information about "{question}" in your course materials.

**Possible reasons:**
- This topic might not be covered in your syllabus yet
- The question might be too specific or off-topic
- Try rephrasing your question

**Suggestions:**
- Ask about topics from your current module
- Try broader questions like "What is...?" or "How does...?"
- Check the module topics to see what's covered

Would you like to ask something else?
"""

        output = ""

        # Add note if searched across all modules
        if searched_elsewhere:
            output += "💡 *Note: Answer found by searching across all modules (not in current module)*\n\n---\n\n"

        output += f"""**Answer:**

{result['response']}

---

**📚 Sources:**
"""

        if result.get('citations') and len(result['citations']) > 0:
            for i, citation in enumerate(result['citations'], 1):
                source_name = citation.get('source', 'Unknown')
                url = citation.get('url')
                source_type_str = citation.get('source_type', 'document')
                page_info = citation.get('page')
                content_excerpt = citation.get('content', '')

                # Get emoji for source type
                type_emoji = {
                    "wikipedia": "📖",
                    "book": "📚",
                    "website": "🌐",
                    "article": "📄",
                    "video": "🎥",
                    "course": "🎓",
                    "tutorial": "💡",
                    "paper": "📜"
                }.get(source_type_str, "📑")

                # Format citation with URL
                if url:
                    output += f"\n**{i}. {type_emoji} [{source_name}]({url})**"
                else:
                    output += f"\n**{i}. {type_emoji} {source_name}**"

                if page_info:
                    output += f" (Page {page_info})"

                if content_excerpt:
                    excerpt = content_excerpt[:150].strip()
                    if len(content_excerpt) > 150:
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
    """Start adaptive assessment with intelligent defaults and visible loading states."""
    global current_orchestrator

    # Immediately show loading message
    yield (
        "<div style='margin-top: 40px;'>⏳ Preparing assessment…</div>",
        "",
        gr.update(visible=False),
        gr.update(value="Loading…", interactive=False),
        gr.update(value="Submit Answer"),
        "submit"
    )

    try:
        if not current_orchestrator or not current_orchestrator.current_module_id:
            yield ("❌ Error: Please enroll and complete teaching first", "", gr.update(visible=False), gr.update(value="🚀 Start Assessment", interactive=True), gr.update(value="Submit Answer"), "submit")
            return

        # Show progress during assessment generation
        yield (
            "<div style='margin-top: 40px;'>📝 Generating adaptive questions…</div>",
            "",
            gr.update(visible=False),
            gr.update(value="Loading…", interactive=False),
            gr.update(value="Submit Answer"),
            "submit"
        )

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
"""

        # Final yield: show info, question, make answer section visible, disable start button, set state to "submit"
        yield (info_output, question_output, gr.update(visible=True), gr.update(value="🚀 Start Assessment", interactive=False), gr.update(value="Submit Answer", variant="primary"), "submit")

    except Exception as e:
        yield (f"❌ Error: {str(e)}", "", gr.update(visible=False), gr.update(value="🚀 Start Assessment", interactive=True), gr.update(value="Submit Answer"), "submit")


def submit_answer_ui(answer: str, current_state: str):
    """Submit answer and show feedback, or move to next question."""
    global current_orchestrator

    try:
        if not current_orchestrator or not current_orchestrator.current_quiz_session:
            return "❌ Error: No active assessment", "", gr.update(), gr.update(value="Submit Answer"), "submit", gr.update(visible=False), gr.update(visible=True)

        # State machine: "submit" = waiting for answer, "next" = showing feedback
        if current_state == "submit":
            # User is submitting an answer
            if not answer or not answer.strip():
                return "❌ Error: Please provide an answer", "", gr.update(), gr.update(value="Submit Answer"), "submit", gr.update(visible=False), gr.update(visible=True)

            result = current_orchestrator.submit_answer(answer=answer.strip())

            feedback_output = f"""
{"✅ Correct!" if result['is_correct'] else "❌ Incorrect"}

**Your Answer**: {answer}
**Score**: {result['score']:.1f} points
**Feedback**: {result['feedback']}
"""

            if not result['assessment_complete']:
                # Show feedback and change button to "Next Question", keep answer section visible, hide complete button
                return feedback_output, "", gr.update(value="", interactive=False), gr.update(value="Next Question", variant="secondary"), "next", gr.update(visible=False), gr.update(visible=True)
            else:
                feedback_output += f"""
🎉 **{result.get('message', 'Assessment complete!')}**

Click 'Complete Assessment' below to see your results.
"""
                # Show the complete button when assessment is done, hide answer section
                return feedback_output, "", gr.update(value=""), gr.update(value="Submit Answer"), "submit", gr.update(visible=True), gr.update(visible=False)

        elif current_state == "next":
            # User is moving to next question after seeing feedback
            # Get the next question from the orchestrator's current state
            quiz_session = current_orchestrator.current_quiz_session

            if not quiz_session or quiz_session.status == "completed":
                return "Assessment complete!", "", gr.update(value=""), gr.update(value="Submit Answer"), "submit", gr.update(visible=True), gr.update(visible=False)

            # Get current question (which is the next one after the last submit)
            current_q_num = len(quiz_session.responses) + 1

            if current_q_num <= len(quiz_session.questions):
                current_question = quiz_session.questions[current_q_num - 1]
                current_difficulty = quiz_session.difficulty_progression[-1] if quiz_session.difficulty_progression else "medium"

                try:
                    question_output = _format_question_display(
                        current_question,
                        current_q_num,
                        quiz_session.num_questions,
                        current_difficulty
                    )
                except Exception as format_error:
                    return f"❌ Error formatting question: {str(format_error)}\n\nQuestion type: {type(current_question)}", "", gr.update(), gr.update(value="Submit Answer"), "submit", gr.update(visible=False), gr.update(visible=True)

                # Clear feedback, show new question, change button back to "Submit Answer", enable input and clear it, hide complete button
                return "", question_output, gr.update(value="", interactive=True), gr.update(value="Submit Answer", variant="primary"), "submit", gr.update(visible=False), gr.update(visible=True)
            else:
                return "Assessment complete!", "", gr.update(value=""), gr.update(value="Submit Answer"), "submit", gr.update(visible=True), gr.update(visible=False)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"❌ Error: {str(e)}\n\n```\n{error_details}\n```", "", gr.update(), gr.update(value="Submit Answer"), "submit", gr.update(visible=False), gr.update(visible=True)


def complete_assessment_ui():
    """Complete assessment."""
    global current_orchestrator, current_learner

    try:
        if not current_orchestrator or not current_orchestrator.current_quiz_session:
            return "❌ Error: No active assessment", "", gr.update(interactive=False)

        result = current_orchestrator.complete_assessment()
        metrics = result.get('metrics', {})

        # Calculate correct answers from score and total questions
        total_questions = result.get('total_questions', 0)
        answered_questions = result.get('answered_questions', total_questions)
        score_percentage = result.get('score', 0)
        correct_answers = int((score_percentage / 100) * answered_questions) if answered_questions > 0 else 0

        output = f"""
# 🎉 Assessment Complete!

## 📊 Results

**Final Score**: {result['score']:.1f}%
**Status**: {"✅ **PASSED**" if result['passed'] else "❌ **FAILED**"}
**Questions**: {total_questions}
**Answered**: {answered_questions}
**Correct (approx)**: {correct_answers}
**Time**: {metrics.get('time_taken_minutes', 0):.1f} min

## 📈 Mastery

- **Before**: {metrics.get('mastery_before', 0):.1f}%
- **After**: {metrics.get('mastery_after', 0):.1f}%
- **Change**: {metrics.get('mastery_delta', 0):+.1f}%

## 🎯 Next Steps

"""

        # Enable enroll button only if assessment is passed
        enroll_btn_state = gr.update(interactive=True) if result['passed'] else gr.update(interactive=False)

        if result['passed']:
            next_module_id = current_orchestrator._get_next_module(current_orchestrator.current_module_id)
            if next_module_id:
                next_module = current_orchestrator._find_module(next_module_id)
                output += f"""
✅ **Congratulations!** Module completed!

**Next**: Enroll in **{next_module.get('title')}** from the Teaching Session tab.
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

        return output, json.dumps(result, indent=2), enroll_btn_state

    except Exception as e:
        return f"❌ Error: {str(e)}", "", gr.update(interactive=False)


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
        title="LearnX - Personalised AI Learning",
        theme=gr.themes.Soft(primary_hue="purple", secondary_hue="blue"),
        css=custom_css
    ) as demo:

        # Landing Page
        with gr.Column(visible=True) as landing_page:
            gr.HTML('<h1 class="landing-title">🎓 LearnX</h1>')
            gr.Markdown("""
            <div style="text-align: center; font-size: 1.2em; color: #666; margin-bottom: 30px;">
            AI-Powered Personalised Learning Platform
            </div>
            
            ## Transform Your Learning Journey with AI
            
            Experience revolutionary AI-powered education with multi-agent teaching, adaptive assessments, and personalised learning pathways.
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
                <h1 style="margin: 0;">🎓 LearnX Learning Platform</h1>
                <p style="margin: 5px 0 0 0;">Your Personalised AI-Powered Learning Journey</p>
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
                gr.Markdown("### Generate Personalised Syllabus")

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

            with gr.Tab("3️⃣ Teaching Session"):
                gr.Markdown("### RAG-Based Interactive Teaching")

                with gr.Column():
                    gr.Markdown("#### 📚 Select a Module")
                    module_dropdown = gr.Dropdown(
                        label="Choose a Module to Enroll",
                        choices=["Generate a syllabus first"],
                        interactive=False,
                        info="Modules with unmet prerequisites are not shown"
                    )
                    enroll_btn = gr.Button("Enroll in Module", variant="primary")
                    enroll_output = gr.Markdown()

                    gr.Markdown("---")

                    start_lessons_btn = gr.Button("🚀 Start Module Lessons", variant="primary", size="lg", interactive=False)
                    lessons_output = gr.Markdown()

                    gr.Markdown("---")

                    question_input = gr.Textbox(label="Ask a Question", placeholder="What is a variable?")
                    ask_btn = gr.Button("Ask Question")
                    answer_output = gr.Markdown()

                # Connect syllabus generation button to update dropdown
                generate_btn.click(
                    fn=generate_syllabus_ui,
                    inputs=[topic_input, duration_input, hours_input],
                    outputs=[syllabus_output, module_dropdown, generate_btn]
                )

                enroll_btn.click(
                    fn=enroll_module_ui,
                    inputs=[module_dropdown],
                    outputs=[enroll_output, module_dropdown, start_lessons_btn, enroll_btn]
                )

                start_lessons_btn.click(
                    fn=start_module_lessons_ui,
                    outputs=[lessons_output, start_lessons_btn]
                )
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
                    question_output = gr.Markdown()

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

                    # Hidden state to track submit vs next
                    button_state = gr.State("submit")

                    gr.Markdown("---")

                    complete_btn = gr.Button("✅ Complete Assessment & View Results", variant="secondary", size="lg", visible=False)
                    complete_output = gr.Markdown()
                    complete_json = gr.Code(language="json", label="Results", visible=False)
                
                start_assessment_btn.click(
                    start_assessment_ui,
                    outputs=[assessment_output, question_output, answer_section, start_assessment_btn, submit_btn, button_state]
                )

                submit_btn.click(
                    submit_answer_ui,
                    inputs=[answer_input, button_state],
                    outputs=[feedback_output, question_output, answer_input, submit_btn, button_state, complete_btn, answer_section]
                )
                
                complete_btn.click(
                    complete_assessment_ui,
                    outputs=[complete_output, complete_json, enroll_btn]
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
    demo.queue()  # Enable queue for loading states
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
