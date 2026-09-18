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
> prediction (Cliff's delta -0.37, p = 0.011). The negotiation protocol was predicted to raise time
> budget satisfaction; the full architecture satisfied the budget in 24 scenarios of 24 and the
> single-shot condition in 21, but with only three discordant pairs this is not a detectable
> difference (exact McNemar p = 0.250).
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

> Paired by scenario, the full architecture is worse than the single agent on schema validity (0.54
> against 0.96, ten discordant pairs all in the same direction, exact McNemar p = 0.002) and on
> prerequisite resolvability (0.75 against 0.96, p = 0.062), and indistinguishable on everything else.
>
> The failures are of one kind. Of the eleven syllabi the full architecture produced that failed the
> schema, ten failed on the prerequisites field alone: the extraction step copies prose out of the
> negotiation ("Comfort with variables and assignment", "Basic Python syntax") into a field the schema
> defines as module identifiers. Excluding prerequisites, the two conditions are indistinguishable,
> both valid in 23 scenarios of 24. The single agent, which writes its syllabus as JSON directly, never
> produced such a failure.
>
> This is a cost of the handoff rather than of decomposition as such, and it appears in every condition
> that negotiates in free text before extracting (A1 ten of 24, A5 eleven, A3 ten, A4 seven, the last
> lower because a single-shot plan gives the extractor less prose to transcribe). It is also
> addressable within the architecture: validating the syllabus at the handoff, which §3.4 of the
> submitted manuscript already claimed the system did, is exactly the missing step.

### What the architecture does provide

> Two components have effects that are not in dispute because they are categorical rather than
> statistical.
>
> The citation instruction produces attribution: with it, all 831 answered responses carried inline
> citations, 16,474 markers in total, a median of 19 per response, of which five (0.03%) pointed
> outside the passages supplied. Without it, none of the 814 answered responses carried a single
> marker, though the system still appended its list of retrieved sources. Whether those citations are
> correct is the annotation study's question, not this one's.
>
> Retrieval changes what instruction looks like. The no-retrieval condition wrote a median of 22 code
> blocks per response against the full architecture's 1.5, whose median response contains no code at
> all. Told to answer only from a prose corpus, the instructor explains rather than demonstrates. For a
> programming tutor this is a substantive trade-off, and it is not visible in any measure of citation
> or schema quality.

---

## 4.x Failure analysis (E4)

> One taxonomy was applied to every artefact. Rates are means of per-scenario rates.

> Two entries deserve comment.
>
> **Retrieval crosses strands in about 40% of passages** in every grounded condition, and 9% of
> responses find nothing above the similarity threshold at all. The corpus is organised into four
> strands and the retriever is not told which strand a module belongs to, so a module on functions is
> routinely taught from passages about data structures.
>
> **Every syllabus ends over its time budget.** The agents produce syllabi that fit: the extracted
> syllabus satisfied the budget in 24 scenarios of 24 under the full architecture. The system then
> rescales module hours towards the budget and afterwards raises any module whose hours look low for
> its topic count, without rescaling again. The result exceeded the budget in 100% of runs in four of
> the five conditions, typically by a factor of three (20 hours becoming 57 to 75). A repair step
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
