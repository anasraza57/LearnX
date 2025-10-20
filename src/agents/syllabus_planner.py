"""
Syllabus Planner - Phase 5 Enhanced Multi-Agent System

Uses role-playing agents to negotiate and generate personalized syllabus:
- Learner Advocate: Represents learner's goals, constraints, preferences
- Curriculum Designer: Represents pedagogical best practices, domain expertise
- Structured negotiation protocol for module selection, ordering, pacing
- Outputs validated JSON conforming to syllabus.schema.json
"""

import os
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from langchain.chat_models import ChatOpenAI
from langchain.prompts.chat import (
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.schema import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from ..utils.validation import SchemaValidator
from ..models.learner_profile import LearnerModel


class DiscussAgent:
    """Base agent class for multi-agent discussion."""

    def __init__(
        self,
        system_message: SystemMessage,
        model: ChatOpenAI,
    ) -> None:
        self.system_message = system_message
        self.model = model
        self.init_messages()

    def reset(self) -> None:
        self.init_messages()
        return self.stored_messages

    def init_messages(self) -> None:
        self.stored_messages = [self.system_message]

    def update_messages(self, message: BaseMessage) -> List[BaseMessage]:
        self.stored_messages.append(message)
        return self.stored_messages

    def step(
        self,
        input_message: HumanMessage,
    ) -> AIMessage:
        messages = self.update_messages(input_message)
        output_message = self.model(messages)
        self.update_messages(output_message)
        return output_message


class LearnerAdvocateAgent(DiscussAgent):
    """
    Represents the learner's interests, goals, and constraints.

    Advocates for:
    - Alignment with learner's stated goals
    - Realistic pacing based on available time
    - Appropriate difficulty given prior knowledge
    - Learning style accommodations
    """

    def __init__(
        self,
        learner: LearnerModel,
        topic: str,
        duration_weeks: int,
        weekly_hours: float,
        model: Optional[ChatOpenAI] = None,
    ):
        self.learner = learner
        self.topic = topic
        self.duration_weeks = duration_weeks
        self.weekly_hours = weekly_hours

        system_prompt = self._create_system_prompt()
        system_message = SystemMessage(content=system_prompt)

        model = model or ChatOpenAI(temperature=0.3, model_name="gpt-3.5-turbo")
        super().__init__(system_message, model)

    def _create_system_prompt(self) -> str:
        goals = self.learner._data.get("goals", [])
        learning_style = self.learner._data.get("learning_style", "mixed")
        pace = self.learner._data.get("pace", "moderate")
        difficulty_pref = self.learner._data.get("difficulty_preference", "medium")

        return f"""You are a Learner Advocate representing {self.learner.name}.

Your role is to ensure the syllabus meets the learner's needs and constraints.

Learner Profile:
- Learning Goals: {', '.join(goals) if goals else 'General knowledge in ' + self.topic}
- Learning Style: {learning_style}
- Preferred Pace: {pace}
- Difficulty Preference: {difficulty_pref}
- Available Time: {self.weekly_hours} hours/week for {self.duration_weeks} weeks
- Total Time Budget: {self.weekly_hours * self.duration_weeks} hours

Topic: {self.topic}

Your objectives in negotiation:
1. Ensure modules align with learner's stated goals
2. Keep total estimated hours within time budget
3. Advocate for appropriate difficulty progression (start easier, build up)
4. Ensure prerequisites are clear and achievable
5. Request resources that match learning style when possible

Negotiation protocol:
- Review Curriculum Designer's proposals critically
- Point out misalignments with goals or constraints
- Suggest adjustments to pacing, difficulty, or scope
- Approve when syllabus meets learner's needs
- Use clear, direct language focused on learner benefit

End your response with:
- "CONTINUE" if more negotiation needed
- "APPROVED" if syllabus meets all criteria"""

    def get_initial_requirements(self) -> str:
        """Generate initial requirements message for negotiation."""
        goals = self.learner._data.get("goals", [])

        requirements = f"""I represent {self.learner.name}, who wants to learn about: {self.topic}

Learner Goals:
{chr(10).join(f'- {goal}' for goal in goals) if goals else f'- Gain foundational knowledge in {self.topic}'}

Constraints:
- Available study time: {self.weekly_hours} hours per week
- Duration: {self.duration_weeks} weeks
- Total time budget: {self.weekly_hours * self.duration_weeks} hours
- Preferred pace: {self.learner._data.get('pace', 'moderate')}
- Current level: {self.learner._data.get('difficulty_preference', 'beginner')}

Please design a syllabus that:
1. Directly addresses these learning goals
2. Fits within the time constraints
3. Starts at appropriate difficulty and builds progressively
4. Includes 4-8 modules with clear learning outcomes
5. Specifies realistic time estimates for each module

What modules do you propose?"""

        return requirements


class CurriculumDesignerAgent(DiscussAgent):
    """
    Represents pedagogical expertise and domain knowledge.

    Responsible for:
    - Designing well-structured module sequences
    - Defining clear learning outcomes
    - Selecting appropriate topics and prerequisites
    - Estimating realistic completion times
    - Recommending quality resources
    """

    def __init__(
        self,
        topic: str,
        model: Optional[ChatOpenAI] = None,
    ):
        self.topic = topic

        system_prompt = self._create_system_prompt()
        system_message = SystemMessage(content=system_prompt)

        model = model or ChatOpenAI(temperature=0.4, model_name="gpt-3.5-turbo")
        super().__init__(system_message, model)

    def _create_system_prompt(self) -> str:
        return f"""You are an expert Curriculum Designer specializing in {self.topic}.

Your role is to design pedagogically sound, well-structured syllabi.

Design principles:
1. **Logical Progression**: Module order follows natural learning sequence
2. **Clear Outcomes**: Each module has specific, measurable learning outcomes
3. **Appropriate Scope**: Topics are focused and achievable
4. **Realistic Timing**: Time estimates account for study, practice, and assessment
5. **Prerequisite Clarity**: Dependencies between modules are explicit
6. **Resource Quality**: Recommend accessible, high-quality materials

Module design guidelines:
- 4-8 modules for comprehensive coverage without overwhelming
- Each module: 3-12 hours typically (adjust based on complexity)
- Include 2-4 learning outcomes per module
- List 3-6 specific topics per module
- Recommend 2-3 key resources per module

When responding to Learner Advocate:
- Propose specific module structures with titles, outcomes, topics, time estimates
- Justify your design choices with pedagogical reasoning
- Be receptive to constraint adjustments
- Refine proposals based on feedback
- Provide actionable, concrete designs (not vague suggestions)

Format your proposals clearly with:
- Module titles and IDs (format: m01-topic-name)
- Learning outcomes (what learner will be able to do)
- Specific topics covered
- Estimated hours
- Prerequisites (if any)
- Brief resource suggestions

Respond with "READY" when your proposal is complete and awaiting feedback."""

    def create_initial_proposal(self, requirements: str) -> str:
        """Generate initial module proposal based on requirements."""
        prompt = f"""Based on these learner requirements:

{requirements}

Please design an initial syllabus with specific modules. For each module provide:
- ID (format: m01-descriptive-slug)
- Title
- Learning outcomes (3-4 specific outcomes)
- Topics covered (4-6 specific topics)
- Estimated hours
- Prerequisites (if applicable)

Design 5-7 modules that comprehensively cover {self.topic} while respecting the time constraints.

READY"""

        return prompt


class SyllabusPlanner:
    """
    Multi-agent syllabus planner with negotiation protocol.

    Orchestrates negotiation between Learner Advocate and Curriculum Designer
    to produce personalized, validated syllabi.
    """

    def __init__(
        self,
        learner: LearnerModel,
        validator: Optional[SchemaValidator] = None,
    ):
        self.learner = learner
        self.validator = validator or SchemaValidator("syllabus")
        self.negotiation_history: List[Dict[str, str]] = []

    def generate_syllabus(
        self,
        topic: str,
        duration_weeks: int = 8,
        weekly_hours: float = 5.0,
        max_negotiation_rounds: int = 3,
    ) -> Dict[str, Any]:
        """
        Generate personalized syllabus through multi-agent negotiation.

        Args:
            topic: Main subject/topic for the course
            duration_weeks: Course duration in weeks
            weekly_hours: Available study time per week
            max_negotiation_rounds: Maximum rounds of negotiation

        Returns:
            Validated syllabus dictionary conforming to schema
        """
        # Initialize agents
        advocate = LearnerAdvocateAgent(
            learner=self.learner,
            topic=topic,
            duration_weeks=duration_weeks,
            weekly_hours=weekly_hours,
        )

        designer = CurriculumDesignerAgent(topic=topic)

        # Start negotiation
        print(f"\n{'='*70}")
        print(f"Generating Personalized Syllabus: {topic}")
        print(f"Learner: {self.learner.name}")
        print(f"Duration: {duration_weeks} weeks × {weekly_hours} hrs/week = {duration_weeks * weekly_hours} hours total")
        print(f"{'='*70}\n")

        # Round 1: Learner Advocate states requirements
        requirements = advocate.get_initial_requirements()
        print(f"📋 Learner Advocate (Requirements):\n{requirements}\n")
        self.negotiation_history.append({"role": "advocate", "content": requirements})

        # Round 2: Curriculum Designer proposes initial design
        designer_prompt = designer.create_initial_proposal(requirements)
        designer_response = designer.step(HumanMessage(content=designer_prompt))
        print(f"🎓 Curriculum Designer (Initial Proposal):\n{designer_response.content}\n")
        self.negotiation_history.append({"role": "designer", "content": designer_response.content})

        # Negotiation rounds
        current_response = designer_response.content
        for round_num in range(max_negotiation_rounds):
            print(f"--- Negotiation Round {round_num + 1} ---\n")

            # Advocate reviews proposal
            advocate_review = advocate.step(HumanMessage(content=current_response))
            print(f"📋 Learner Advocate (Review):\n{advocate_review.content}\n")
            self.negotiation_history.append({"role": "advocate", "content": advocate_review.content})

            # Check if approved
            if "APPROVED" in advocate_review.content.upper():
                print("✅ Syllabus approved by Learner Advocate!\n")
                break

            # Designer refines based on feedback
            designer_refinement = designer.step(HumanMessage(content=advocate_review.content))
            print(f"🎓 Curriculum Designer (Refinement):\n{designer_refinement.content}\n")
            self.negotiation_history.append({"role": "designer", "content": designer_refinement.content})

            current_response = designer_refinement.content

        # Extract structured syllabus from negotiation
        print("🔧 Structuring final syllabus...\n")
        structured_syllabus = self._extract_structured_syllabus(
            negotiation_history=self.negotiation_history,
            topic=topic,
            duration_weeks=duration_weeks,
            weekly_hours=weekly_hours,
        )

        # Validate
        errors = self.validator.validate(structured_syllabus)
        if errors:
            print(f"⚠️  Schema validation warnings: {len(errors)} issues")
            for error in errors[:3]:  # Show first 3
                print(f"  - {error}")
            # Auto-fix common issues
            structured_syllabus = self._auto_fix_schema_issues(structured_syllabus)

        print("✅ Syllabus generation complete!\n")
        return structured_syllabus

    def _extract_structured_syllabus(
        self,
        negotiation_history: List[Dict[str, str]],
        topic: str,
        duration_weeks: int,
        weekly_hours: float,
    ) -> Dict[str, Any]:
        """
        Extract structured JSON syllabus from negotiation history using LLM.
        """
        # Combine negotiation history
        history_text = "\n\n".join([
            f"{entry['role'].upper()}: {entry['content']}"
            for entry in negotiation_history
        ])

        extraction_prompt = f"""Based on this syllabus negotiation:

{history_text}

Extract a structured JSON syllabus with this exact format:

{{
  "meta": {{
    "schema_version": 1,
    "created_at": "{datetime.now(timezone.utc).isoformat()}",
    "generated_by": "EduGPT-MultiAgent-v2"
  }},
  "topic": "{topic}",
  "duration_weeks": {duration_weeks},
  "weekly_time_hours": {weekly_hours},
  "learner_profile": {{
    "goals": ["goal1", "goal2"],
    "prior_knowledge": "beginner|intermediate|advanced",
    "preferences": {{
      "learning_style": "mixed",
      "pacing": "moderate"
    }}
  }},
  "modules": [
    {{
      "id": "m01-slug-format",
      "title": "Module Title",
      "description": "Brief description",
      "outcomes": ["outcome 1", "outcome 2", "outcome 3"],
      "topics": ["topic1", "topic2", "topic3"],
      "prerequisites": [],
      "estimated_hours": 8.0,
      "assessment": {{
        "type": "quiz",
        "passing_threshold": 70,
        "adaptive": true
      }}
    }}
  ]
}}

CRITICAL REQUIREMENTS:
1. Module IDs MUST match pattern: m01-lowercase-with-hyphens (m01, m02, m03, etc.)
2. Extract ALL modules discussed in negotiation (typically 5-7)
3. Include specific learning outcomes and topics from the conversation
4. Use realistic time estimates mentioned by designer
5. Set prior_knowledge based on learner's difficulty preference
6. Return ONLY the JSON, no additional text

JSON:"""

        # Use a fresh model for extraction
        extractor_model = ChatOpenAI(temperature=0.1, model_name="gpt-3.5-turbo")
        response = extractor_model([HumanMessage(content=extraction_prompt)])

        # Parse JSON from response
        json_str = response.content.strip()
        # Remove markdown code blocks if present
        if json_str.startswith("```"):
            json_str = json_str.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        json_str = json_str.strip()

        try:
            syllabus = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parsing failed: {e}")
            print(f"Response was: {json_str[:200]}...")
            # Fallback to basic structure
            syllabus = self._create_fallback_syllabus(topic, duration_weeks, weekly_hours)

        # Ensure computed fields
        total_hours = sum(m.get("estimated_hours", 0) for m in syllabus.get("modules", []))
        syllabus["total_estimated_hours"] = total_hours
        syllabus["workload_feasible"] = total_hours <= (duration_weeks * weekly_hours * 1.1)  # 10% buffer

        return syllabus

    def _create_fallback_syllabus(
        self,
        topic: str,
        duration_weeks: int,
        weekly_hours: float,
    ) -> Dict[str, Any]:
        """Create basic fallback syllabus if extraction fails."""
        goals = self.learner._data.get("goals", [f"Learn {topic}"])
        difficulty = self.learner._data.get("difficulty_preference", "medium")
        prior_knowledge = "beginner" if difficulty == "easy" else "intermediate" if difficulty == "medium" else "advanced"

        return {
            "meta": {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "generated_by": "EduGPT-MultiAgent-v2-Fallback",
            },
            "topic": topic,
            "duration_weeks": duration_weeks,
            "weekly_time_hours": weekly_hours,
            "learner_profile": {
                "goals": goals,
                "prior_knowledge": prior_knowledge,
                "preferences": {
                    "learning_style": self.learner._data.get("learning_style", "mixed"),
                    "pacing": self.learner._data.get("pace", "moderate"),
                },
            },
            "modules": [
                {
                    "id": f"m0{i+1}-{topic.lower().replace(' ', '-')}-basics",
                    "title": f"{topic} Module {i+1}",
                    "description": f"Introduction to core concepts in {topic}",
                    "outcomes": [
                        f"Understand fundamental concepts of {topic}",
                        f"Apply basic techniques in {topic}",
                    ],
                    "topics": [f"Topic {j+1}" for j in range(3)],
                    "prerequisites": [] if i == 0 else [f"m0{i}-{topic.lower().replace(' ', '-')}-basics"],
                    "estimated_hours": (duration_weeks * weekly_hours) / 4,
                    "assessment": {
                        "type": "quiz",
                        "passing_threshold": 70,
                        "adaptive": True,
                    },
                }
                for i in range(4)
            ],
            "total_estimated_hours": duration_weeks * weekly_hours,
            "workload_feasible": True,
        }

    def _auto_fix_schema_issues(self, syllabus: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to auto-fix common schema validation issues."""
        # Fix module ID patterns
        for i, module in enumerate(syllabus.get("modules", [])):
            if "id" in module:
                module_id = module["id"]
                # Ensure starts with m + two digits
                if not module_id.startswith("m"):
                    module["id"] = f"m{i+1:02d}-{module_id}"
                elif not module_id[1:3].isdigit():
                    module["id"] = f"m{i+1:02d}-{module_id[1:]}"
                # Ensure lowercase and hyphenated
                module["id"] = module["id"].lower().replace("_", "-").replace(" ", "-")

        # Ensure meta fields
        if "meta" not in syllabus:
            syllabus["meta"] = {}
        syllabus["meta"].setdefault("schema_version", 1)
        syllabus["meta"].setdefault("created_at", datetime.now(timezone.utc).isoformat())
        syllabus["meta"].setdefault("generated_by", "EduGPT-MultiAgent-v2")

        # Ensure required fields have defaults
        syllabus.setdefault("duration_weeks", 8)
        syllabus.setdefault("weekly_time_hours", 5.0)

        return syllabus

    def save_syllabus(self, syllabus: Dict[str, Any], output_dir: Path) -> Path:
        """Save syllabus to JSON file."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"syllabus_{self.learner.learner_id}_{uuid.uuid4().hex[:8]}.json"
        filepath = output_dir / filename

        with open(filepath, "w") as f:
            json.dump(syllabus, f, indent=2)

        print(f"💾 Syllabus saved to: {filepath}")
        return filepath


# Legacy function for backward compatibility
def generate_syllabus(topic: str, task: str) -> str:
    """
    Legacy syllabus generation function (original EduGPT implementation).

    NOTE: This uses the old role-playing approach without structured output.
    For new code, use SyllabusPlanner class instead.
    """
    # Original implementation preserved for backward compatibility
    assistant_role_name = "Instructor"
    user_role_name = "Teaching Assistant"
    word_limit = 50

    assistant_inception_prompt = """Never forget you are a {assistant_role_name} and I am a {user_role_name}. Never flip roles! Never instruct me!
We share a common interest in collaborating to successfully complete a task.
You must help me to complete the task.
Here is the task: {task}. Never forget our task!
I must instruct you based on your expertise and my needs to complete the task.

I must give you one instruction at a time.
You must write a specific solution that appropriately completes the requested instruction.
You must decline my instruction honestly if you cannot perform the instruction due to physical, moral, legal reasons or your capability and explain the reasons.
Do not add anything else other than your solution to my instruction.
You are never supposed to ask me any questions you only answer questions.
You are never supposed to reply with a flake solution. Explain your solutions.
Your solution must be declarative sentences and simple present tense.
Unless I say the task is completed, you should always start with:

Solution: <YOUR_SOLUTION>

<YOUR_SOLUTION> should be specific and provide preferable implementations and examples for task-solving.
Always end <YOUR_SOLUTION> with: Next request."""

    user_inception_prompt = """Never forget you are a {user_role_name} and I am a {assistant_role_name}. Never flip roles! You will always instruct me.
We share a common interest in collaborating to successfully complete a task.
I must help you to complete the task.
Here is the task: {task}. Never forget our task!
You must instruct me based on my expertise and your needs to complete the task ONLY in the following two ways:

1. Instruct with a necessary input:
Instruction: <YOUR_INSTRUCTION>
Input: <YOUR_INPUT>

2. Instruct without any input:
Instruction: <YOUR_INSTRUCTION>
Input: None

The "Instruction" describes a task or question. The paired "Input" provides further context or information for the requested "Instruction".

You must give me one instruction at a time.
I must write a response that appropriately completes the requested instruction.
I must decline your instruction honestly if I cannot perform the instruction due to physical, moral, legal reasons or my capability and explain the reasons.
You should instruct me not ask me questions.
Now you must start to instruct me using the two ways described above.
Do not add anything else other than your instruction and the optional corresponding input!
Keep giving me instructions and necessary inputs until you think the task is completed.
When the task is completed, you must only reply with a single word <TASK_DONE>.
Never say <TASK_DONE> unless my responses have solved your task."""

    def get_sys_msgs(assistant_role_name: str, user_role_name: str, task: str):
        assistant_sys_template = SystemMessagePromptTemplate.from_template(
            template=assistant_inception_prompt
        )
        assistant_sys_msg = assistant_sys_template.format_messages(
            assistant_role_name=assistant_role_name,
            user_role_name=user_role_name,
            task=task,
        )[0]

        user_sys_template = SystemMessagePromptTemplate.from_template(
            template=user_inception_prompt
        )
        user_sys_msg = user_sys_template.format_messages(
            assistant_role_name=assistant_role_name,
            user_role_name=user_role_name,
            task=task,
        )[0]

        return assistant_sys_msg, user_sys_msg

    # Task specification
    task_specifier_sys_msg = SystemMessage(
        content="You can make a task more specific."
    )
    task_specifier_prompt = """Here is a task that {assistant_role_name} will help {user_role_name} to complete: {task}.
Please make it more specific. Be creative and imaginative.
Please reply with the specified task in {word_limit} words or less. Do not add anything else."""
    task_specifier_template = HumanMessagePromptTemplate.from_template(
        template=task_specifier_prompt
    )
    task_specify_agent = DiscussAgent(
        task_specifier_sys_msg, ChatOpenAI(temperature=1.0)
    )

    # Get specified task
    task_specifier_msg = task_specifier_template.format_messages(
        assistant_role_name=assistant_role_name,
        user_role_name=user_role_name,
        task=task,
        word_limit=word_limit,
    )[0]
    specified_task_msg = task_specify_agent.step(task_specifier_msg)
    specified_task = specified_task_msg.content
    assistant_sys_msg, user_sys_msg = get_sys_msgs(
        assistant_role_name, user_role_name, specified_task
    )

    assistant_agent = DiscussAgent(
        assistant_sys_msg, ChatOpenAI(temperature=0.2)
    )
    user_agent = DiscussAgent(user_sys_msg, ChatOpenAI(temperature=0.2))

    # Reset agents
    assistant_agent.reset()
    user_agent.reset()

    # Initialize chats
    assistant_msg = HumanMessage(
        content=(
            f"{user_sys_msg.content}. "
            "Now start to give me introductions one by one. "
            "Only reply with Instruction and Input."
        )
    )

    user_msg = HumanMessage(content=f"{assistant_sys_msg.content}")
    user_msg = assistant_agent.step(user_msg)

    print(f"Specified task prompt:\n{specified_task}\n")
    conversation_history = []

    # Role-playing session
    chat_turn_limit, n = 5, 0
    while n < chat_turn_limit:
        n += 1
        user_ai_msg = user_agent.step(assistant_msg)
        user_msg = HumanMessage(content=user_ai_msg.content)

        print(f"AI User ({user_role_name}):\n\n{user_msg.content}\n\n")
        conversation_history.append("AI User:" + user_msg.content)
        assistant_ai_msg = assistant_agent.step(user_msg)
        assistant_msg = HumanMessage(content=assistant_ai_msg.content)
        conversation_history.append("AI Assistant:" + assistant_msg.content)
        print(
            f"AI Assistant ({assistant_role_name}):\n\n{assistant_msg.content}\n\n"
        )
        if "<TASK_DONE>" in user_msg.content:
            break

    # Summarize to syllabus
    summarizer_sys_msg = SystemMessage(
        content="Summarize this converasion into a {topic} course syllabus form"
    )
    summarizer_prompt = """Here is a comversation history that {assistant_role_name} have disccuss with {user_role_name}: {conversation_history}.
    Please summarize this converasion into a course syllabus form with the topic from user input."""
    summarizer_template = HumanMessagePromptTemplate.from_template(
        template=summarizer_prompt
    )
    summarizer_agent = DiscussAgent(
        summarizer_sys_msg, ChatOpenAI(temperature=1.0)
    )
    summarizer_msg = summarizer_template.format_messages(
        assistant_role_name=assistant_role_name,
        user_role_name=user_role_name,
        conversation_history=conversation_history,
    )[0]
    summarizered_msg = summarizer_agent.step(summarizer_msg)
    return summarizered_msg.content
