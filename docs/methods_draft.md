# Methods, draft text

Draft prose for the methods sections the revision map rewrites, written from what the system does
and what the runs measured. Section numbers follow the submitted manuscript; check them against the
new LaTeX draft before pasting (handoff §5.0). Every number here comes from a recorded artefact:
`data/corpus/python_v1/index_report.json`, `data/scenarios/scenarios_v1.json`, and
`results/e1_ablation/gpt-5.4-mini/analysis.md`.

No claim below goes beyond what those files show.

---

## 3.4 Schema-driven artefact protocol (accuracy correction)

The submitted text says the agents exchange schema-validated JSON. They do not, and the revision
should say what happens instead.

> The Learner Advocate and the Curriculum Designer exchange free text. The advocate opens with a
> statement of the learner's goals, prior knowledge, preferences and time budget; the designer
> proposes modules in prose; the advocate reviews and either requests changes or approves, ending its
> turn with an explicit verdict. Only after the exchange does a separate extraction step convert the
> transcript into JSON, and only that JSON is validated against the syllabus schema. Validation is
> therefore a boundary condition on the pipeline's output, not a constraint on the exchange itself.

This distinction is not cosmetic: §4.x reports that the extraction step is where the multi-agent
pipeline loses fidelity, and that the single-agent baseline, which writes JSON directly, does not
have that failure at all.

---

## 3.5.1 Corpus and preprocessing (rewrite)

> The corpus covers four strands of an introductory Python curriculum: basics, control flow and
> functions, data structures, and object-oriented programming. Each strand was populated in two ways.
>
> **Automatic retrieval.** The system's own fetcher queried Wikipedia and arXiv with the topic
> keywords that LearnX syllabi generate for these strands (for example "Lists", "Tuples",
> "Dictionaries", "Sets", "List comprehensions" for the data-structures strand). This reproduces what
> the deployed system does when it populates a new module.
>
> **Curated retrieval.** The corresponding chapters of the official Python 3.11 tutorial were fetched
> for each strand.
>
> Retrieval by keyword alone proved a poor fit for the domain. Of 43 automatically retrieved
> documents, 36 (84%) were off-topic for the strand that requested them: all 24 arXiv papers, and 12
> of 19 Wikipedia articles. The failures are instructive rather than incidental. The query "Tuples"
> returned "Dilations of unitary tuples" from arXiv and the mathematics article "Tuple"; "Inheritance"
> returned "Diophantine inheritance for p-adic measures" and an article on inheritance in law;
> "Classes" returned "Class (taxonomy)"; "Sets" returned "Set (mathematics)"; "Lists" returned "List
> of lists of lists". The vocabulary of introductory programming collides with mathematics, biology
> and law, and keyword retrieval has no way to tell which sense is wanted.
>
> Each document was labelled on-topic or off-topic by a documented rule (curated documentation is
> on-topic; an automatically retrieved document is on-topic if it mentions Python at least twice, or
> is a Wikipedia article using at least three programming terms), with author review recorded per
> document. Three false positives were overridden: the Unix tool "Expect" and two arXiv papers that
> use Python without teaching it. Only on-topic documents were indexed, and the labels are published
> with the corpus manifest.
>
> The indexed corpus is 12 documents and 533 chunks: 142 chunks for basics, 180 for control flow and
> functions, 74 for data structures, and 137 for object-oriented programming.

**Limitation to state here rather than in §5:** a corpus assembled this way is prose-heavy. §4.x
reports the consequence, which is that grounded instruction contains far fewer worked code examples
than ungrounded instruction.

---

## 3.5.2 Indexing and retrieval (accuracy correction)

> Documents are chunked to 800 characters with 150 characters of overlap, on paragraph boundaries
> where possible. Chunks are embedded with sentence-transformers all-MiniLM-L6-v2 (384 dimensions,
> unit-normalised) and stored in a single ChromaDB collection. Retrieval returns the top 5 chunks by
> cosine similarity and discards any chunk below a similarity of 0.35. The same parameters are used by
> the instructor, the assessment generator and the single-agent baseline, so no condition retrieves
> more or better context than another.
>
> There is no fallback retry at a larger k. Results are returned in similarity order, so a larger k
> cannot introduce a passage above a threshold that the first k all failed to meet; the fallback
> parameter present in earlier configuration was unused and has been removed.
>
> When nothing clears the threshold the instructor returns a fixed refusal rather than answering
> unsupported; this happened for 115 of 946 responses (12.2%) under the full architecture.
> Low-confidence retrieval, meaning every passage returned sits within 0.05 of the threshold, is
> recorded separately over the responses that retrieved anything, and occurred for 17.6% of them. Conflicting passages are not detected automatically; the
> annotation study records contradiction at claim level.
>
> Retrieved passages carry the strand they came from, which makes it measurable how often retrieval
> crosses strands: 44% of passages supplied to the full architecture came from a strand other than the
> one the module's title and topics describe. Judging that against the strand the module is about
> matters, since judging it against the passages the module itself retrieved would score uniformly
> wrong retrieval as perfect.

---

## 3.5.3 Citation generation and validation (rewrite)

> Each retrieved passage is presented to the instructor numbered, and the instructor is instructed to
> end every statement that rests on the context with the number of the supporting passage in square
> brackets, to cite only passages that support the statement, and not to cite its own examples or
> invent numbers. Markers are then parsed from the response and checked against the passages actually
> supplied, so a citation pointing outside the supplied set is detectable without human judgement.
> Code blocks are masked before parsing, so Python list literals are not mistaken for citations.
>
> The instruction is what produces attribution. Without it the system emits only a list of retrieved
> sources appended to the response: under the ablation that removes it, none of the 814 answered
> responses carried a single inline citation, and in the ungrounded condition only one response of
> 919 did, with eight bracketed numbers and no passages behind them. With the instruction, all 831
> answered responses carried at least one marker, 15,261 in total, a median of 18 per response. Of
> those, 5 (0.03%) pointed outside the set of passages supplied, all five in a single response citing
> a source numbered 6 when it had been given five; every other marker referred to a passage that
> existed. The other citing conditions produce such markers at a similar rate (0.10% and 0.09%).
>
> A marker is counted only where it is an attribution. Two forms are excluded by rule, because both
> would otherwise be read as citations pointing nowhere: a bracket opening a line and followed by a
> source, which is the bibliography a model sometimes appends rather than an inline attribution, and a
> bracket holding three or more numbers, which in prose is a list of values such as "the last three
> elements [9, 16, 25]" far more often than a citation of three sources at once. Code spans and fenced
> blocks are masked before matching. The measure is recomputed from the response text for every run,
> so a change to this rule applies to every condition and backend alike.
>
> Whether a cited passage in fact supports the claim attached to it is not decidable automatically and
> is measured by the two-rater study in §3.6.

---

## 3.6 Experimental design (rewrite)

> The system is evaluated by running it over a fixed set of controlled learner scenarios and recording
> what it produces. A scenario is an experimental input: it fixes the profile the system is given and
> generates no scores of its own. No human learners are involved, and no learner behaviour is
> simulated.

### 3.6.2 Controlled learner scenarios

> Twenty-four scenarios form a full factorial over four factors: prior knowledge (novice,
> intermediate, advanced), time budget (20 hours over 4 weeks, 40 hours over 8 weeks), goal profile
> (broad foundations across all four strands, or a narrow applied focus on data structures) and
> preference profile (reading-writing style with slow pace and easy difficulty, or kinesthetic style
> with fast pace and hard difficulty). The set is generated once from a fixed seed, written to a
> versioned file, and reused byte-identically across every condition and backend; its hash is recorded
> in every result file.
>
> The unit of analysis is the system artefact, not the learner. Each scenario yields one syllabus, one
> instructional response per syllabus topic, and one assessment item per topic.

### 3.6.2a Scenario factors (new table)

> The scenario set is a 3 x 2 x 2 x 2 full factorial over four factors, generated once from seed 20260917 and
> reused byte-identically across every condition and backend as version `v1`.

| Factor | Levels | What it varies |
|---|---|---|
| Prior knowledge | novice, intermediate, advanced | What the learner is assumed to know already |
| Time budget | 4 weeks at 5 h/week (20 h total); 8 weeks at 5 h/week (40 h total) | The constraint the syllabus must fit |
| Goal profile | broad: broad foundations across all four modules; narrow: narrow applied focus on one strand (data structures) | Whether the plan must span the curriculum or concentrate on one strand |
| Preference profile | P1: reading_writing style, slow pace, easy difficulty; P2: kinesthetic style, fast pace, hard difficulty | How instruction and assessment are asked to adapt |

> The 24 cells are the full crossing of these levels, so every combination appears
> exactly once and each factor is balanced against the others. A scenario fixes the profile the system
> is given and nothing else: it produces no scores and models no learner behaviour.

---

### 3.6.5 Conditions and backends

> Five conditions isolate one component each, all on the same model, corpus and scenarios: the full
> architecture; a single-agent baseline given the identical model, retrieval stack, citation
> instruction and syllabus format, differing only in that one agent plans, teaches and assesses; the
> full architecture without retrieval; without the negotiation protocol; and without the citation
> instruction. The single-agent prompt is published in full in Appendix E.
>
> The model backend is then varied with the architecture held fixed, over five models spanning two
> tiers and two generations within each tier: a current proprietary model, a mid-tier proprietary
> model, the older proprietary model used in the submitted version, the older open-weight model used
> in the submitted version, and a current open-weight model. Every arm runs the full architecture over
> the same 24 scenarios, so the arm for the reference model serves both the ablation and this
> comparison.
>
> Two choices in the open-weight tier should be stated rather than assumed. The current open-weight
> model is smaller than the older one, 4B parameters against 7B, because the two current models that
> would have matched the size could not complete the protocol on the available hardware: both
> generated around 8,000 tokens per call and needed between 28 minutes and two hours per scenario
> against nine minutes for the model used. The open-weight comparison therefore varies generation and
> size together and cannot isolate either. Every local model is served with its context window pinned
> to 32,768 tokens and its sampling parameters set to match the other arms, because a model pulled
> from a registry can carry its own temperature and penalties, and the serving default truncates long
> prompts without reporting it.

### 3.6.6 Evaluation metrics

> Reported measures are corpus composition; planning quality (schema validity of the syllabus as the
> agents produced it, time budget satisfaction, prerequisite graph resolvable and acyclic, goal
> coverage, module count); grounding (retrieval hit rate, low-confidence retrieval, citations per
> response, cross-strand retrieval); faithfulness from the annotation study; assessment item validity;
> failure rates per pipeline stage; and operational cost (input, cached and output tokens, latency per
> response, cost per scenario at dated prices, and for local backends energy and amortised hardware
> rather than zero).
>
> Two measurement choices are worth stating. Planning quality is measured on the syllabus as the
> agents produced it, before the deterministic post-processing that repairs the schema and rescales
> module hours, because that post-processing is identical in every condition and would mask the
> differences between them. Code produced in instruction is judged per code block rather than per
> response, because a response containing twenty examples is more likely to contain one broken block
> than a response containing one.

### 3.6.7 Statistical analysis

> Every call is made with the same sampling policy: temperature 0, a fixed seed, and a cap of 8,192
> tokens on a single completion. The cap bounds a model that fails to terminate rather than shaping a
> well-behaved one: across the 9,159 calls of the ablation the largest completion was 3,921 tokens and
> none reached 4,096, and no call in any reported run was stopped by the cap. Backends whose context
> window cannot hold the longest prompt alongside the cap are run with a smaller one, recorded per run.
> A call the cap stops is recorded as truncated and counted, so a cut-off artefact is never read as a
> model failing a check.

> Responses are nested within scenarios and are not independent, so the scenario is the unit of
> analysis: for each scenario and condition a single rate is computed, giving 24 paired observations
> per contrast. Contrasts use the Wilcoxon signed-rank test with the median paired difference, a
> bootstrap confidence interval and Cliff's delta; binary per-scenario outcomes use an exact McNemar
> test; descriptive proportions use Wilson score intervals. The primary outcome and the predicted
> direction of each contrast were fixed before the runs, and a contrast counts as supported only if
> the 95% interval on the paired difference excludes zero in that direction.
>
> The primary outcome is a composite of seven planning constraints, and prerequisites are a schema
> field, so a syllabus whose prerequisites are written as prose fails two of the seven for one
> reason. The composite is reported as it was declared, and the primary contrast is also reported
> under four alternative definitions of it, including one that judges schema validity without the
> prerequisites field. The decision is the same under all five; the effect size is not, and is
> therefore never quoted without saying which composite produced it. Sampling variation was
> minimised by running every call at temperature 0 with a fixed seed, and the residual variation this
> leaves is reported in §4.x rather than assumed away.

---

## Notes for whoever writes the final text

- The determinism probe belongs in the methods or the limitations: temperature 0 with a fixed seed is
  not reproducibility on this API, and the measured residual variation should be stated plainly.
- The post-processing finding (every final syllabus exceeding its time budget after the repair step)
  belongs in the results as a system failure, not hidden in the methods.
- Do not describe the question-answering path as working: it filters retrieval on a module identifier
  that indexed chunks have never carried, so it always returns the canned refusal.
- The adaptive assessment must be described as implemented rather than evaluated. The runs generate
  assessment items and never answer them, so difficulty adaptation never executes in any experiment.
  The implemented rule is two consecutive correct answers to move up and two consecutive wrong to move
  down, across five levels; the accuracy thresholds in the configuration are read by nothing, and a
  different score-based rule is used only to recommend a difficulty after a quiz ends.
