# Discussion, draft text

Draft prose for the two new subsections of Section 5 that do not depend on the results still being
collected: applicability (R2 asked for it explicitly) and limitations (R1 and R2). The subsections
that rewrite around E2 and E3 are left unwritten until those results exist.

Every claim below is traceable to a recorded artefact: `data/corpus/python_v1/index_report.json`,
`data/scenarios/scenarios_v1.json`, `results/e1_ablation/gpt-5.4-mini/analysis.md`, and
`results/e1_determinism_probe/`.

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

## Not yet written

- **5.2 The Scaffolding Hypothesis**: rewrite around what E1 shows, including where it runs against
  the hypothesis.
- **5.3 Verifiability**: rebuild around E3 once the annotation study exists. The submitted claim of a
  correlation between citation density and learning outcomes is withdrawn, not restated.
- **5.4 Diminishing Returns**: rewrite around E2 once the backend arms are complete.
