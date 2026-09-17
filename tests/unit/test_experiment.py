"""
Unit tests for the experiment harness and the condition switches it relies on: inline citations, the ungrounded instructor path, negotiation
verdicts, scenario generation, conditions, cost accounting and the A2 baseline.
"""

import itertools
import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.agents.rag_instructor import (
    CITATION_INSTRUCTION,
    NO_CONTEXT_ANSWER,
    RAGInstructor,
    extract_inline_citations,
)
from src.agents.syllabus_planner import SyllabusPlanner, _final_verdict
from src.config import config
from src.experiment import scenarios
from src.experiment.conditions import CONDITIONS
from src.experiment.runner import cost_usd
from src.experiment.single_agent import SingleAgentTutor
from src.models.learner_profile import LearnerModel
from src.orchestrator import LearningOrchestrator, learner_level_for
from src.utils.document_loader import Document


def _doc(text, doc_id="py03-data-structures/pydocs_datastructures"):
    return Document(content=text, metadata={"source": "5. Data Structures", "doc_id": doc_id,
                                            "strand": doc_id.split("/")[0], "chunk_id": f"{doc_id}#0"})


class TestInlineCitations:
    def test_numbers_and_validity(self):
        found = extract_inline_citations("Lists are mutable.[1] Tuples are not [2, 7]. See [Source 3].", 5)
        assert [(c["passage_index"], c["valid"]) for c in found] == [(1, True), (2, True), (7, False), (3, True)]

    def test_code_is_not_a_citation(self):
        answer = (
            "Indexing uses `a[0]`.[1]\n"
            "```python\nsquares = [1, 4, 9]\nprint(squares[2])\n```\n"
            "Slices return new lists[2][3]."
        )
        assert [c["passage_index"] for c in extract_inline_citations(answer, 3)] == [1, 2, 3]

    def test_ranges_semicolons_and_titles(self):
        found = extract_inline_citations("a [1-3] b [2; 4] c [Source 5: Data types] ~~~\nx = [9]\n~~~", 5)
        assert [c["passage_index"] for c in found] == [1, 2, 3, 2, 4, 5]

    def test_unterminated_code_block_is_masked(self):
        assert extract_inline_citations("Text [1]\n```python\nx = [2]\n", 2) == [
            {"marker": "[1]", "offset": 5, "passage_index": 1, "valid": True}
        ]


class TestNegotiationVerdict:
    @pytest.mark.parametrize("text,expected", [
        ("Looks good.\nAPPROVED", "APPROVED"),
        ("Needs work.\n**CONTINUE**", "CONTINUE"),
        ("This is not yet APPROVED, please revise.\nCONTINUE", "CONTINUE"),
        ("I have approved nothing yet.", None),
        ("", None),
        ("NOT APPROVED", None),
        ("Status: NOT APPROVED", None),
        ("UNAPPROVED", None),
        ("Good.\n**APPROVED** ✅", "APPROVED"),
        ("Revise.\nCONTINUE\n---", "CONTINUE"),
        ("Verdict: approved.", "APPROVED"),
    ])
    def test_final_line_decides(self, text, expected):
        assert _final_verdict(text) == expected


@patch("src.agents.rag_instructor.make_chat_model")
class TestInstructorConditions:
    def test_citation_instruction_toggle(self, mock_factory):
        with_it = RAGInstructor(vector_store=MagicMock()).prompt_template.template
        without = RAGInstructor(vector_store=MagicMock(), citation_instruction=False).prompt_template.template
        assert CITATION_INSTRUCTION in with_it
        assert "Citation requirements" not in without
        assert without.endswith("understandable parts\n\n**Answer:**")

    def test_ungrounded_path_never_retrieves(self, mock_factory):
        mock_factory.return_value.invoke.return_value = AIMessage(content="A list is ordered.")
        instructor = RAGInstructor(vector_store=None, grounded=False)
        response = instructor.teach("Teach me about lists", learner_level="novice")
        assert response.mode == "ungrounded"
        assert response.refused is False
        assert response.answer == "A list is ordered."
        assert "Context from educational materials" not in response.prompt
        assert "**Learner Level:** novice" in response.prompt
        assert instructor.citation_instruction is False

    def test_grounded_instructor_requires_store(self, mock_factory):
        with pytest.raises(ValueError):
            RAGInstructor(vector_store=None)

    def test_grounded_without_passages_refuses_without_calling_model(self, mock_factory):
        store = MagicMock()
        store.search.return_value = []
        response = RAGInstructor(vector_store=store).teach("Teach me about lists")
        assert response.refused is True
        assert response.answer == NO_CONTEXT_ANSWER
        mock_factory.return_value.invoke.assert_not_called()

    def test_grounded_uses_pinned_retrieval_and_records_citations(self, mock_factory):
        mock_factory.return_value.invoke.return_value = AIMessage(content="Lists are mutable.[1]")
        store = MagicMock()
        store.search.return_value = [(_doc("Lists are mutable."), 0.6)]
        response = RAGInstructor(vector_store=store).teach("Teach me about lists")
        kwargs = store.search.call_args.kwargs
        assert kwargs["top_k"] == config.rag.top_k
        assert kwargs["min_similarity"] == config.rag.similarity_threshold
        assert response.inline_citations[0]["passage_index"] == 1
        assert "[Source 1: 5. Data Structures]" in response.prompt
        assert len(response.citations) == 1


class TestPlannerDiagnostics:
    @patch("src.agents.syllabus_planner.make_chat_model")
    def test_single_shot_keeps_extracted_syllabus_before_rescaling(self, mock_factory):
        module = {"title": "Basics", "outcomes": ["Write simple programs"], "difficulty": "medium",
                  "topics": [f"Topic number {i}" for i in range(12)], "estimated_hours": 10.0}
        syllabus = {
            "topic": "Python", "duration_weeks": 4, "weekly_time_hours": 5.0,
            "modules": [{**module, "id": "m01-basics"}, {**module, "id": "m02-more"}],
        }
        model = MagicMock()
        model.invoke.side_effect = [AIMessage(content="Proposal\nREADY"), AIMessage(content=json.dumps(syllabus))]
        mock_factory.return_value = model

        planner = SyllabusPlanner(learner=LearnerModel(name="T"))
        final = planner.generate_syllabus("Python", duration_weeks=4, weekly_hours=5.0, max_negotiation_rounds=0)

        # Only the designer and the extractor were called
        assert model.invoke.call_count == 2
        assert planner.last_run["rounds_completed"] == 0
        assert planner.last_run["approved"] is False
        assert not {"scale_hours_up", "scale_hours_down"} & set(planner.last_run["repairs"])
        extracted = planner.last_run["extracted_syllabus"]["modules"]
        assert sum(m["estimated_hours"] for m in extracted) == 20.0
        assert [h["role"] for h in planner.last_run["negotiation_history"]] == ["advocate", "designer"]
        assert planner.last_run["schema_errors_raw"]  # no meta block in the reply
        assert planner.last_run["schema_valid_as_extracted"] is True  # content itself is valid
        # The content-justification step pushes an on-budget syllabus over the 20 h budget (B14)
        assert "justify_hours_by_content" in planner.last_run["repairs"]
        assert sum(m["estimated_hours"] for m in final["modules"]) > 20.0
        # What is returned is schema-valid, hours on the schema's 0.5 grid, metadata from the learner
        assert planner.last_run["schema_valid_final"] is True
        assert all(m["estimated_hours"] * 2 == int(m["estimated_hours"] * 2) for m in final["modules"])
        assert final["total_estimated_hours"] == sum(m["estimated_hours"] for m in final["modules"])
        assert final["learner_profile"]["preferences"]["learning_style"] == "visual"

    @patch("src.agents.syllabus_planner.make_chat_model")
    def test_style_copied_from_profile_does_not_change_the_repair_path(self, mock_factory):
        syllabus = {
            "topic": "Python", "duration_weeks": 4, "weekly_time_hours": 5.0,
            "learner_profile": {"preferences": {"learning_style": "reading_writing"}},
            "modules": [{"id": "m01-basics", "title": "Basics", "outcomes": ["Write simple programs"],
                         "topics": ["Variables", "Types"], "estimated_hours": 20.0}],
        }
        learner = LearnerModel(name="T", learning_style=["reading_writing"])
        planner = SyllabusPlanner(learner=learner)
        planner.last_run = {"repairs": []}
        final = planner.finalise_syllabus(syllabus, duration_weeks=4, weekly_hours=5.0)
        assert "auto_fix_schema_issues" not in planner.last_run["repairs"]
        assert final["learner_profile"]["preferences"]["learning_style"] == "reading"
        assert planner.last_run["schema_valid_final"] is True

    def test_hours_as_text_do_not_crash(self):
        planner = SyllabusPlanner(learner=LearnerModel(name="T"))
        planner.last_run = {"repairs": []}
        syllabus = {"modules": [{"id": "m01-a", "title": "A", "outcomes": ["Write programs"],
                                 "topics": ["Variables"], "estimated_hours": "about 6 hours"}]}
        final = planner.finalise_syllabus(syllabus, duration_weeks=1, weekly_hours=5.0)
        assert final["total_estimated_hours"] == 5.0


class TestScenarios:
    def test_full_factorial(self):
        data = scenarios.generate()
        combos = [tuple(s["factors"].values()) for s in data["scenarios"]]
        assert len(combos) == 24 == len(set(combos))
        levels = data["factor_levels"]
        expected = set(itertools.product(
            levels["prior_knowledge"], levels["time_budget"], levels["goal_profile"], levels["preference_profile"]
        ))
        got = {(f["prior_knowledge"], f["time_budget"], f["goal_profile"], f["preference_profile"])
               for f in (s["factors"] for s in data["scenarios"])}
        assert got == expected

    def test_generation_is_deterministic(self):
        assert scenarios.serialise(scenarios.generate()) == scenarios.serialise(scenarios.generate())
        assert scenarios.generate(seed=1)["scenarios"][0]["learner"]["learner_id"] != \
            scenarios.generate()["scenarios"][0]["learner"]["learner_id"]

    def test_committed_file_is_reproducible(self):
        path = scenarios.scenario_file()
        assert path.read_bytes() == scenarios.serialise(scenarios.generate())

    def test_learners_carry_scenario_factors(self):
        data = scenarios.generate()
        for scenario in data["scenarios"]:
            learner = scenarios.build_learner(scenario)
            factors = scenario["factors"]
            assert learner.get_goals() == data["factor_levels"]["goal_profile"][factors["goal_profile"]]["goals"]
            assert learner_level_for(learner) == factors["prior_knowledge"]
            prefs = data["factor_levels"]["preference_profile"][factors["preference_profile"]]
            assert learner.learning_style == prefs["learning_style"]
            assert learner.pace == prefs["pace"]
            assert learner.difficulty_preference == prefs["difficulty_preference"]


class TestConditions:
    def test_ablation_table(self):
        c = CONDITIONS
        assert set(c) == {"A1", "A2", "A3", "A4", "A5"}
        assert (c["A1"].retrieval, c["A1"].citation_instruction, c["A1"].max_negotiation_rounds > 0) == (True, True, True)
        assert c["A2"].single_agent and not any(x.single_agent for k, x in c.items() if k != "A2")
        assert not c["A3"].retrieval
        assert c["A4"].max_negotiation_rounds == 0 and c["A4"].retrieval
        assert not c["A5"].citation_instruction and c["A5"].retrieval


class TestRunnerRecords:
    def test_placeholder_items_are_invalid(self):
        from src.agents.assessment_generator import AssessmentQuestion
        from src.experiment.runner import _item_record
        question = AssessmentQuestion(
            question_id="q-1", question_text="What is x?", question_type="multiple_choice",
            difficulty="easy", module_id="m01-a",
            options=[{"option_id": "A", "text": "Option A", "is_correct": True},
                     {"option_id": "B", "text": "Option B", "is_correct": False}],
            generation_meta={"parse_fallback": True},
        )
        record = _item_record(question)
        assert record["placeholder"] is True and record["valid"] is False

    @patch("src.agents.assessment_generator.make_chat_model")
    def test_generator_keeps_questions_containing_code(self, mock_factory):
        from src.agents.assessment_generator import AssessmentGenerator
        item = {"question_text": "What prints?\n```python\nprint(1)\n```", "options": [
            {"option_id": "A", "text": "1", "is_correct": True},
            {"option_id": "B", "text": "2", "is_correct": False}], "explanation": "e"}
        mock_factory.return_value.invoke.return_value = AIMessage(content="```json\n" + json.dumps(item) + "\n```")
        question = AssessmentGenerator(vector_store=None).generate_question("m01-a", "print", use_rag=False)
        assert question.generation_meta["parse_fallback"] is False
        assert question.question_text.startswith("What prints?")
        assert question.generation_meta["call_id"]

    def test_failed_path(self, tmp_path):
        from src.experiment.runner import failed_path
        assert failed_path(tmp_path / "S01.json").name == "S01.failed.json"


class TestCost:
    def test_cached_tokens_billed_at_cached_rate(self):
        calls = [{"input_tokens": 1_000_000, "cached_input_tokens": 500_000, "output_tokens": 1_000_000}]
        assert cost_usd(calls, "gpt-5.4-mini") == pytest.approx(0.5 * 0.75 + 0.5 * 0.075 + 4.50)

    def test_unpriced_model(self):
        assert cost_usd([{"input_tokens": 1, "output_tokens": 1}], "mistral:7b") is None


class TestOrchestratorConditions:
    def test_no_retrieval_builds_ungrounded_instructor(self, tmp_path):
        with patch("src.agents.rag_instructor.make_chat_model"), \
             patch("src.agents.assessment_generator.make_chat_model"), \
             patch("src.agents.grading_agent.make_chat_model"):
            orch = LearningOrchestrator(learner=LearnerModel(name="T"), persist_dir=tmp_path,
                                        syllabus={"modules": [{"id": "m01-a", "topics": ["x"]}]},
                                        retrieval=False)
            orch.start_teaching_session(module_id="m01-a")
        assert orch.instructor.grounded is False
        assert orch.assessment_generator.vector_store is None
        assert orch._rag_active() is False

    def test_learner_level_from_prior_knowledge(self):
        learner = LearnerModel(name="T")
        assert learner_level_for(learner) == "novice"
        learner.add_prior_knowledge("Python programming", "intermediate")
        learner.add_prior_knowledge("Git", "advanced")
        assert learner_level_for(learner) == "advanced"


class TestSingleAgentBaseline:
    @patch("src.experiment.single_agent.make_chat_model")
    @patch("src.agents.syllabus_planner.make_chat_model")
    def test_plans_teaches_and_assesses_with_one_agent(self, _planner_factory, factory):
        syllabus = {
            "topic": "Python", "duration_weeks": 4, "weekly_time_hours": 5.0,
            "modules": [{"id": "m01-data", "title": "Data", "outcomes": ["o"], "topics": ["lists"], "estimated_hours": 5.0}],
        }
        item = {"question_text": "Which is mutable?", "options": [
            {"option_id": "A", "text": "list", "is_correct": True},
            {"option_id": "B", "text": "tuple", "is_correct": False},
        ], "explanation": "Lists are mutable", "bloom_level": "understand"}
        llm = MagicMock()
        llm.invoke.side_effect = [
            AIMessage(content=json.dumps(syllabus)),
            AIMessage(content="Lists are mutable.[1]"),
            AIMessage(content="```json\n" + json.dumps(item) + "\n```"),
        ]
        factory.return_value = llm
        store = MagicMock()
        store.search.return_value = [(_doc("Lists are mutable."), 0.6)]

        learner = scenarios.build_learner(scenarios.generate()["scenarios"][0])
        tutor = SingleAgentTutor(learner=learner, vector_store=store, learner_level="novice", model_name="m")
        final = tutor.generate_syllabus("Python", duration_weeks=4, weekly_hours=5.0)
        lesson = tutor.teach_topic("lists")
        question = tutor.generate_question("m01-data", "lists", "easy")

        assert factory.call_count == 1  # one agent
        assert final["modules"][0]["id"] == "m01-data"
        assert tutor.last_run["extraction_fallback"] is False
        assert lesson["inline_citations"][0]["valid"] is True
        assert "Recommend accessible" in lesson["prompt"]  # the same agent's system prompt
        question.validate()
        assert question.generation_meta["retrieval_hits"] == 1
        for call in store.search.call_args_list:
            assert call.kwargs["top_k"] == config.rag.top_k
            assert call.kwargs["min_similarity"] == config.rag.similarity_threshold
