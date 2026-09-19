# Discussion, draft text

Draft prose for Section 5: the two new subsections the revision map calls for, applicability (R2)
and limitations (R1, R2), and the two rewrites whose evidence now exists, the scaffolding hypothesis
(E1) and diminishing returns (E2). Verifiability waits on the annotation study.

Every claim below is traceable to a recorded artefact: `data/corpus/python_v1/index_report.json`,
`data/scenarios/scenarios_v1.json`, `results/e1_ablation/gpt-5.4-mini/analysis.md`,
`results/e2_backends/backends.md`, and `results/e1_determinism_probe/`.

---

## 5.x Where this approach applies

> The corpus findings in §3.5.1 are not only a description of how this system was built. They mark
> the boundary of the approach.
>
> Retrieval-grounded tutoring of this kind needs a body of open, well-indexed prose that can be found
> by the vocabulary a syllabus generates. Introductory programming meets the first condition and fails
> the second. Of 43 documents retrieved automatically by the topic keywords that LearnX itself
> produces, 36 were off-topic for the strand that asked for them. The failures were not random: the
> query "Tuples" returned a paper on dilations of unitary tuples and the mathematics article "Tuple",
> "Inheritance" returned a p-adic measures paper and an article on inheritance in law, "Sets"
> returned set theory, and "Classes" returned biological taxonomy. The vocabulary of introductory
> programming is largely borrowed, and keyword retrieval cannot recover which sense was meant.
>
> The approach therefore suits domains with three properties. First, an open literature dense enough
> that a module's topics are actually covered, since a retriever that finds nothing produces a refusal
> rather than a lesson, which happened for 12.2% of responses here. Second, a technical vocabulary
> that does not collide with other disciplines, or a corpus curated in advance so that collision does
> not matter. Third, subject matter that is taught adequately in prose. The last is the sharpest
> restriction for programming: grounded instruction in this system wrote a median of 1.5 code blocks
> per response against 22 when retrieval was removed, because a prose corpus gives a model little to
> imitate. A tutor that must demonstrate rather than explain is poorly served by a corpus of
> encyclopaedia articles, whatever its retrieval quality.
>
> Curated documentation avoided all three problems here, which suggests the practical form of the
> approach: curation at the corpus boundary, not keyword retrieval at query time.

---

## 5.x Limitations

> **Scope of the evidence.** The evaluation measures what the system produces, not what a learner
> gains from it. No human learners took part, no learning outcome was measured, and nothing here
> supports a claim about pedagogical effectiveness. The scenarios are experimental inputs that fix the
> profile the system is given; they do not model learner behaviour and produce no scores of their own.
> This is a deliberate restriction of the contribution rather than an accident of the design, and it
> follows from the withdrawal described in §1: the earlier version of this work reported learning
> gains that had not been measured.
>
> **One domain, one corpus.** Everything reported comes from a single introductory Python corpus of 12
> documents and 533 chunks across four strands. The corpus findings above are specific to that
> vocabulary, and the planning and grounding results are specific to a domain whose modules are short
> and whose prerequisites are largely linear. Whether the same ablation profile appears in a domain
> with denser prerequisite structure is untested.
>
> **Assessment format.** Items are generated in quiz format and are scored for schema validity, not
> for whether they assess what they claim to assess. Higher-order skills, and any skill that requires
> producing a working artefact, are outside what this instrument can see. The adaptive difficulty
> mechanism is implemented but is not evaluated anywhere in this paper: the runs generate assessment
> items and never answer them, so the adaptation path never executes.
>
> **Twenty-four scenarios, one run each.** The scenario set is a full factorial over four factors, and
> the unit of analysis is the scenario, which gives 24 paired observations per contrast. That is enough
> to detect a large effect and not enough to detect a small one. A contrast reported here as
> unsupported should be read as not demonstrated at this sample size, not as demonstrated absent.
>
> **Runs are not reproducible, and this was measured rather than assumed.** Every call was made at
> temperature 0 with a fixed seed. Running one scenario three times under identical settings produced
> three different syllabi from a byte-identical prompt, and because the syllabi differed the runs
> shared no comparable lesson. Coarse structure was stable (six modules, an extracted syllabus of
> exactly the budgeted hours, two negotiation rounds ending in approval, complete citation coverage);
> refusal rate, citations per response and cost varied by a few percentage points. Results should be
> read as a single sample from a distribution whose spread is reported in §4.x, not as fixed values.
>
> **Automatic measures answer only what can be decided mechanically.** Citation markers are checked
> against the passages actually supplied, which detects a citation pointing outside the set but says
> nothing about whether a cited passage supports the sentence attached to it. That question is
> answered by the two-rater study, on a sample rather than on every claim, and one of the two raters
> is an author of this paper.
>
> **The strand-crossing measure depends on a judgement.** Retrieval is counted as crossing strands
> when a passage comes from a strand other than the one the module's title and topics describe. That
> comparison is made against the module's declared subject rather than against the passages it
> retrieved, because judging retrieval against its own output would score uniformly wrong retrieval as
> perfect. It still rests on an automatic reading of what a module is about.

---

## 5.2 The scaffolding hypothesis, tested

> The submitted version asserted that decomposing the tutor into negotiating agents improves the
> plans it produces. E1 tested that assertion against a single-agent baseline given the identical
> model, corpus, retrieval stack, citation instruction and syllabus schema, differing only in that one
> agent plans, teaches and assesses. The prediction was fixed in advance, and it was not supported.
>
> The direction is the uncomfortable part: the single agent scored higher, not lower, on the composite
> of planning constraints, and the difference is concentrated in one place. The multi-agent pipeline
> hands a free-text negotiation to an extraction step, and that step copies prose into a field the
> schema defines as module identifiers: "Comfort with variables and assignment" where an identifier
> belongs. Scored while ignoring that single field, the two architectures are indistinguishable, 0.96
> against 0.96.
>
> So the finding is not that decomposition is worthless. It is that decomposition as implemented here
> buys nothing the single agent cannot produce, and costs a fidelity loss at the handoff between the
> conversation and the artefact. That is a narrower and more useful claim than the original one, and
> it points at a fix inside the architecture rather than away from it: validating the syllabus at the
> handoff, which §3.4 of the submitted manuscript already claimed the system did.
>
> Two cautions belong with it. The composite counts a prerequisite failure twice, once through schema
> validity and once through the prerequisite checks, and removing that overlap halves the apparent
> effect while leaving the decision unchanged. And 24 scenarios can detect a large effect, not a small
> one, so this is evidence that decomposition does not help much here, not proof that it never helps.

---

## 5.4 Diminishing returns across model generations

> Reviewer 5 objected that the submitted baselines were outdated generations, and that without current
> models the results would confound architecture with model progress. E2 answers that by holding the
> architecture fixed and varying the model across five backends in two tiers and two generations.
>
> The answer is a null result, and it is worth stating as one. Paired by scenario, the composite does
> not separate the three proprietary models at all: the difference against the mid-tier model is 0.000
> with an interval of [0.000, 0.000], and against the older model 0.000 with [0.000, 0.071]. Over the
> same 24 scenarios the current model costs $6.11 against $0.57, which is 10.7 times the price for a
> difference this design cannot measure.
>
> The per-check ordering runs against model recency rather than with it. The oldest proprietary model
> produced the most schema-valid syllabi, 0.83 against the current model's 0.54, and the most
> resolvable prerequisites, 0.88 against 0.75. The reason is visible in the artefacts: the current
> model plans more ambitiously, producing 946 instructional responses across the scenario set against
> 474, and the extraction step fails more often on longer and more discursive plans. Where the current
> model does lead is on the learner's own constraints, satisfying the time budget in every scenario
> against 0.79, and covering the stated goal in 0.92 against 0.62.
>
> The practical reading is that capability and suitability are not the same axis. A stronger model
> writes a richer plan and strains a brittle handoff; the constraint that actually protects the learner
> is met more often by the stronger model, and the constraint that protects the pipeline is met more
> often by the weaker one. A deployment choosing on price would not be paying for measurably better
> plans here, which is the opposite of the cost-effectiveness story the submitted version told.
>
> This is not a claim that model progress does not matter. It is a claim about one pipeline, one
> corpus, one domain and 24 scenarios, where the binding constraint on quality turned out to be an
> architectural seam rather than the model behind it.

---

## Not yet written

- **5.3 Verifiability**: rebuild around E3 once the annotation study exists. The submitted claim of a
  correlation between citation density and learning outcomes is withdrawn, not restated.
- **5.1 Bridging the divide**: keep the access and sovereignty argument, remove every implication that
  equivalent learning was demonstrated.
- **6 Conclusion**: write last, mirroring the revised contributions.
