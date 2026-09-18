# Results, draft text

Draft prose for the rebuilt results section, covering what has been measured so far: the ablation
(E1), the failure analysis (E4) and operational cost. Sections that depend on the annotation study
(E3) and the remaining backends (E2) are marked as such and left unwritten rather than sketched.

Numbers come from `results/e1_ablation/gpt-5.4-mini/analysis.md`, which any reader can regenerate from
the stored records. 120 runs, five conditions over 24 scenarios, one model
(`gpt-5.4-mini-2026-03-17`) at temperature 0 with a fixed seed, no failed runs.

---

## 4.x Component contribution (E1)

> Each condition removes one component and is otherwise identical: same model, same corpus, same
> scenarios, same retrieval parameters, same prompts. Four contrasts were fixed in advance with their
> predicted directions, and a contrast counts as supported only where the 95% interval on the paired
> difference excludes zero in the predicted direction.
>
> **Neither contrast that can be measured automatically supports its prediction.**
>
> Decomposition (full architecture against the single-agent baseline) was predicted to raise
> curriculum constraint satisfaction. It did not: the median scenario scored 0.86 under the full
> architecture and 1.00 under the single agent, with the paired difference running against the
> prediction (unpaired Cliff's delta -0.39, Wilcoxon p = 0.011). The negotiation protocol was predicted to raise time
> budget satisfaction; the full architecture satisfied the budget in 24 scenarios of 24 and the
> single-shot condition in 21, a difference of 12.5 percentage points, but the interval on that
> difference includes zero ([0.0, 29.2] points) and with three discordant pairs the exact McNemar
> test gives p = 0.250. The direction is as predicted; the evidence is not sufficient to claim it.
>
> The remaining two contrasts, grounding and the citation instruction, are measured by the annotation
> study and are reported in §4.x.

### Where the difference lies

> The composite outcome combines seven checks, so it is worth reporting which of them separate the
> conditions. Only two do, and both concern prerequisites.

| Check | A1 full | A2 single agent | A3 no retrieval | A4 no negotiation | A5 no citations |
|---|---|---|---|---|---|
| Schema valid as extracted | 0.54 | 0.96 | 0.58 | 0.71 | 0.54 |
| Prerequisites resolvable | 0.75 | 0.96 | 0.75 | 0.92 | 0.75 |
| Time budget satisfied | 1.00 | 0.96 | 1.00 | 0.88 | 1.00 |
| Goal covered | 0.92 | 0.92 | 0.92 | 0.96 | 0.92 |
| Module count in range | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| Prerequisite graph acyclic | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| All constraints satisfied | 0.46 | 0.79 | 0.50 | 0.71 | 0.50 |
| Schema valid ignoring prerequisites | 0.96 | 0.96 | 1.00 | 1.00 | 1.00 |

> Paired by scenario, the full architecture is worse than the single agent on schema validity (0.54
> against 0.96, ten discordant pairs all in the same direction, exact McNemar p = 0.002) and on
> prerequisite resolvability (0.75 against 0.96, p = 0.062), and indistinguishable on everything else.
>
> The failures are of one kind. The extraction step copies prose out of the negotiation ("Comfort
> with variables and assignment", "Basic Python syntax") into a field the schema defines as module
> identifiers. Scored while ignoring that one field, every condition is valid in 23 or 24 scenarios of
> 24 and they are indistinguishable from one another:

> Put differently, prerequisites are the **only** field on which the extraction step fails the schema
> at all. Invalid prerequisites appear in 10 of 24 runs under the full architecture, 11 without the
> citation instruction, 10 without retrieval and 7 without negotiation, the last lower because a
> single-shot plan gives the extractor less prose to transcribe. The single agent, which writes its
> syllabus as JSON directly, produced none in 24 runs.
>
> This is a cost of the handoff rather than of decomposition as such, and it is addressable within the
> architecture: validating the syllabus at the handoff, which §3.4 of the submitted manuscript already
> claimed the system did, is exactly the missing step.

### How much of the contrast is one failure counted twice

> Prerequisites are a schema field, so a prerequisite written as prose fails the schema check and the
> prerequisite checks alike and costs two of the seven composite constraints. The composite is
> reported as it was pre-registered, and the contrast is also recomputed under four other definitions
> of it:
>
> | Composite | A1 | A2 | Cliff's delta | p |
> |---|---|---|---|---|
> | As pre-registered, 7 checks | 0.89 | 0.97 | -0.385 | 0.011 |
> | Schema validity judged without the prerequisites field | 0.95 | 0.97 | -0.167 | 0.206 |
> | Without the schema check | 0.94 | 0.97 | -0.167 | 0.157 |
> | Without the prerequisite checks | 0.86 | 0.96 | -0.375 | 0.013 |
> | No overlap, and without the weak prerequisites_present check | 0.94 | 0.97 | -0.167 | 0.206 |
>
> The decision does not move: under every definition the difference runs against the predicted
> direction and the interval includes zero, so the contrast is unsupported either way. What the double
> counting affects is the size of the apparent disadvantage, roughly half of which is the same failure
> entering twice. The honest statement is the one the rows agree on: removing the prerequisites field
> leaves the two architectures separated by 0.02 on a seven-point composite, which this design cannot
> distinguish from no difference at all.

### What the architecture does provide

> Two components have effects that are not in dispute because they are categorical rather than
> statistical.
>
> The citation instruction produces attribution: with it, all 831 answered responses carried inline
> citations, 15,261 markers in total, a median of 18 per response, of which five (0.03%) pointed
> outside the passages supplied. Those five are one response in one scenario repeatedly citing a
> source numbered 6 when five passages had been given to it, which is the hallucinated attribution
> that checking markers against the supplied set exists to catch. The other citing conditions do the
> same a little more often: 9 of 9,305 markers (0.10%) in the single-agent baseline and 14 of
> 16,031 (0.09%) without negotiation. Without it, none of the 814 answered responses carried a single
> marker, though the system still appended its list of retrieved sources. Ungrounded instruction is
> almost as clean: one response of 919 produced eight bracketed numbers with no passages behind them
> at all. Whether those citations are
> correct is the annotation study's question, not this one's.
>
> Retrieval changes what instruction looks like, and improves it. The no-retrieval condition wrote a
> median of 22 code blocks per response against the full architecture's 1.5, whose median response
> contains no code at all: told to answer only from a prose corpus, the instructor explains rather
> than demonstrates. But the code it does write is sounder. Pooled over every block, 2.18% of the
> ungrounded condition's 20,283 blocks fail to parse against 0.19% of the full architecture's 1,558,
> an elevenfold difference, and only 63 of those 442 failures are errors written deliberately to
> illustrate a point. Grounding therefore trades the quantity of worked examples for their
> correctness, which is a trade-off a programming tutor has to make consciously.

---

## 4.x Failure analysis (E4)

> One taxonomy was applied to every artefact. Rates over scenarios are means of per-scenario rates;
> rates over responses, items, code blocks and citation markers are pooled over every unit, and the
> two are not interchangeable.

> Two entries deserve comment.
>
> **Retrieval crosses strands in about 44% of passages** in every grounded condition, judged against
> the strand a module's title and topics describe, and 12.2% of responses under the full architecture
> (115 of 946) find nothing above the similarity threshold at all. The corpus is organised into four
> strands and the retriever is not told which strand a module belongs to, so a module on functions is
> routinely taught from passages about data structures.
>
> **Every syllabus ends over its time budget.** The agents produce syllabi that fit: the extracted
> syllabus satisfied the budget in 24 scenarios of 24 under the full architecture. The system then
> rescales module hours towards the budget and afterwards raises any module whose hours look low for
> its topic count, without rescaling again. The result exceeded the budget in every run of four of
> the five conditions (22 of 24 in the fifth), by a median factor of 3.1 under the full
> architecture: a 20 hour budget came back as 61 to 83 hours. A repair step
> intended to make estimates realistic reliably destroys the constraint the planner satisfied.

---

## 4.x Operational cost

| Condition | Cost per 24 scenarios | Tokens per scenario | Output tokens | Cached input | Median latency |
|---|---|---|---|---|---|
| A1 full | $6.11 | 139,171 | 41,518 | 8% | 4.2 s |
| A2 single agent | $4.59 | 258,041 | 26,894 | 66% | 4.8 s |
| A3 no retrieval | $10.92 | 143,228 | 93,960 | 14% | 11.0 s |
| A4 no negotiation | $5.58 | 117,759 | 38,430 | 0% | 4.2 s |
| A5 no citation instruction | $6.41 | 140,740 | 44,631 | 9% | 4.6 s |

> Removing retrieval is the most expensive condition, not the cheapest: 79% more than the full
> architecture, because ungrounded answers are longer (94,000 output tokens per scenario against
> 42,000) and slower (11.0 s against 4.2 s median). Grounding constrains generation, and constrained
> generation is cheaper.
>
> The single agent consumes the most tokens in total but costs least, because carrying its syllabus in
> every prompt makes two thirds of its input cacheable. Any cost comparison between architectures has
> to account for caching or it will mistake prompt structure for efficiency.
>
> Prices are the provider's published per-token rates on the run date, recorded with the results. Cost
> per faithfully grounded response, which the revision substitutes for the withdrawn
> cost-effectiveness ratio, requires the annotation study and is reported in §4.x.
>
> One caveat belongs with the time budget result. The pre-registered outcome is measured on the
> syllabus as the agents produced it, because the repair step that follows is identical in every
> condition. On the syllabus actually delivered to the learner, every condition violates the budget
> in essentially every run, so a reader should not take 24 of 24 as a statement about the product.

---

## 4.x Reproducibility of the runs

> Every call was made at temperature 0 with a fixed seed. This minimises sampling variation but does
> not remove it. Running one scenario three times under identical settings produced three different
> syllabi: the first proposal differed substantially between runs from a byte-identical prompt of 776
> tokens, and because the syllabus differed, the runs shared no comparable lesson at all (40, 37 and
> 36 responses, no module and topic pair common to all three). What remained stable was the coarse
> structure: six modules each time, an extracted syllabus of exactly 20 hours against a 20 hour budget
> each time, two negotiation rounds ending in approval each time, and citation coverage of 100%. What
> varied: the refusal rate between 2.8% and 7.5%, citations per response between 21.1 and 23.7, and
> cost by about 6%.
>
> No run should be described as reproducible. The measured residual variation above is the honest
> statement of what a repeated run would differ by.

---

## Not yet written

- **§4.x citation faithfulness (E3)**: awaiting the two-rater study. The pilot pack is drawn.
- **§4.x model backends (E2)**: the first open-weight arm is running; the proprietary arms await API
  credit. The comparison table is generated by `analysis.py --arm`.
- **Cost of ownership for local backends**: `tco.py` computes it once power is measured with sudo.
