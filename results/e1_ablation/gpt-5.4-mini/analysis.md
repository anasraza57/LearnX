# e1 results: gpt-5.4-mini

Runs: 120 across conditions A1, A2, A3, A4, A5. Unit of analysis: the scenario (D28). Intervals are 95% and the decision rule is D29.

## Coverage

| Condition | Scenarios | Responses | Items | Cost (USD) | Median response latency (s) |
|---|---|---|---|---|---|
| A1 | 24 | 946 | 946 | 6.11 | 4.2 |
| A2 | 24 | 714 | 714 | 4.59 | 4.7 |
| A3 | 24 | 919 | 919 | 10.92 | 11.0 |
| A4 | 24 | 899 | 899 | 5.58 | 4.2 |
| A5 | 24 | 911 | 911 | 6.41 | 4.5 |

## Pre-registered contrasts

| Contrast | Isolates | Outcome | Median A | Median B | Paired difference | 95% CI | Cliff's delta (unpaired) | p | Supported |
|---|---|---|---|---|---|---|---|---|---|
| A1 vs A2 | agent decomposition | constraint_satisfaction_rate | 0.857 | 1.000 | 0.000 | [-0.143, +0.000] | -0.385 | 0.011 (Wilcoxon signed-rank) | no (predicted higher) |
| A1 vs A3 | retrieval grounding | unsupported_claim_rate | pending E3 annotation | | | | | | |
| A1 vs A4 | the negotiation protocol | time_budget_satisfied | 1.000 | 1.000 | 0.125 | [+0.000, +0.292] | 0.125 | 0.250 (exact McNemar) | no (predicted higher) |
| | | proportions | 1.000 [+0.862, +1.000] | 0.875 [+0.690, +0.957] | McNemar exact | discordant 3 (3 vs 0) | | 0.250 | |
| A1 vs A5 | the citation instruction | misattribution_rate | pending E3 annotation | | | | | | |
| A1 vs A5 | the citation instruction | missing_citation_rate | pending E3 annotation | | | | | | |

## Automatic measures by condition

| Measure | A1 | A2 | A3 | A4 | A5 |
|---|---|---|---|---|---|
| no_passage_above_threshold | 0.093 | 0.082 | n/a | 0.056 | 0.099 |
| low_confidence_retrieval | 0.176 | 0.163 | n/a | 0.159 | 0.177 |
| off_strand_passage_rate | 0.438 | 0.425 | n/a | 0.430 | 0.476 |
| model_written_refusal | 0.098 | 0.000 | 0.000 | 0.094 | 0.090 |
| response_without_citation | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| invalid_citation_marker_rate | 0.000 | 0.000 | n/a | 0.000 | n/a |
| citations_per_response | 19.349 | 15.333 | 0.000 | 20.613 | 0.000 |
| code_blocks_per_response | 1.477 | 3.350 | 22.488 | 1.789 | 2.923 |
| code_block_parse_failure | 0.000 | 0.000 | 0.020 | 0.000 | 0.007 |
| response_with_broken_code | 0.000 | 0.000 | 0.205 | 0.000 | 0.033 |
| item_valid | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| item_placeholder | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| item_retrieval_failed | 0.169 | 0.080 | n/a | 0.107 | 0.132 |

## Planning checks by condition

| Check | A1 | A2 | A3 | A4 | A5 |
|---|---|---|---|---|---|
| schema_valid_as_extracted | 0.54 [+0.35, +0.72] | 0.96 [+0.80, +0.99] | 0.58 [+0.39, +0.76] | 0.71 [+0.51, +0.85] | 0.54 [+0.35, +0.72] |
| schema_valid_ignoring_prerequisites | 0.96 [+0.80, +0.99] | 0.96 [+0.80, +0.99] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| extraction_parsed | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| time_budget_satisfied | 1.00 [+0.86, +1.00] | 0.96 [+0.80, +0.99] | 1.00 [+0.86, +1.00] | 0.88 [+0.69, +0.96] | 1.00 [+0.86, +1.00] |
| module_count_in_range | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| goal_covered | 0.92 [+0.74, +0.98] | 0.92 [+0.74, +0.98] | 0.92 [+0.74, +0.98] | 0.96 [+0.80, +0.99] | 0.92 [+0.74, +0.98] |
| prerequisites_present | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| prerequisites_resolvable | 0.75 [+0.55, +0.88] | 0.96 [+0.80, +0.99] | 0.75 [+0.55, +0.88] | 0.92 [+0.74, +0.98] | 0.75 [+0.55, +0.88] |
| prerequisites_acyclic | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| final_hours_over_budget | 1.00 [+0.86, +1.00] | 0.92 [+0.74, +0.98] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| all_constraints_satisfied | 0.46 [+0.28, +0.65] | 0.79 [+0.60, +0.91] | 0.50 [+0.31, +0.69] | 0.71 [+0.51, +0.85] | 0.50 [+0.31, +0.69] |

## Planning checks against A1, paired by scenario (exact McNemar)

These are descriptive: the composite in the contrasts table is the pre-registered outcome, and the p-values below are not corrected for the number of checks.

| Check | A1 vs A2 | A1 vs A3 | A1 vs A4 | A1 vs A5 |
|---|---|---|---|---|
| schema_valid_as_extracted | 0.54 vs 0.96, discordant 0/10, p=0.002 | 0.54 vs 0.58, discordant 4/5, p=1.000 | 0.54 vs 0.71, discordant 2/6, p=0.289 | 0.54 vs 0.54, discordant 4/4, p=1.000 |
| schema_valid_ignoring_prerequisites | 0.96 vs 0.96, discordant 1/1, p=1.000 | 0.96 vs 1.00, discordant 0/1, p=1.000 | 0.96 vs 1.00, discordant 0/1, p=1.000 | 0.96 vs 1.00, discordant 0/1, p=1.000 |
| extraction_parsed | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| time_budget_satisfied | 1.00 vs 0.96, discordant 1/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 0.88, discordant 3/0, p=0.250 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| module_count_in_range | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| goal_covered | 0.92 vs 0.92, discordant 1/1, p=1.000 | 0.92 vs 0.92, discordant 2/2, p=1.000 | 0.92 vs 0.96, discordant 1/2, p=1.000 | 0.92 vs 0.92, discordant 2/2, p=1.000 |
| prerequisites_present | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| prerequisites_resolvable | 0.75 vs 0.96, discordant 0/5, p=0.062 | 0.75 vs 0.75, discordant 2/2, p=1.000 | 0.75 vs 0.92, discordant 1/5, p=0.219 | 0.75 vs 0.75, discordant 2/2, p=1.000 |
| prerequisites_acyclic | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| final_hours_over_budget | 1.00 vs 0.92, discordant 2/0, p=0.500 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| all_constraints_satisfied | 0.46 vs 0.79, discordant 2/10, p=0.039 | 0.46 vs 0.50, discordant 6/7, p=1.000 | 0.46 vs 0.71, discordant 2/8, p=0.109 | 0.46 vs 0.50, discordant 5/6, p=1.000 |

## Negotiation

Runs with negotiation enabled: 72. Approved: 72. Reached the round limit without approval: 0. No revision occurred: 0. Role inversion suspected (needs confirmation by reading the transcript): 2.

## Pooled totals (over every unit, not per scenario)

| Quantity | A1 | A2 | A3 | A4 | A5 |
|---|---|---|---|---|---|
| Responses | 946 | 714 | 919 | 899 | 911 |
| Assessment items | 946 | 714 | 919 | 899 | 911 |
| Items failing their schema | 4 (0.42%) | 0 (0.00%) | 2 (0.22%) | 1 (0.11%) | 0 (0.00%) |
| Placeholder items | 4 (0.42%) | 0 (0.00%) | 0 (0.00%) | 1 (0.11%) | 0 (0.00%) |
| Code blocks written | 1558 | 2315 | 20283 | 1698 | 2630 |
| Code blocks that do not parse | 3 (0.19%) | 4 (0.17%) | 442 (2.18%) | 11 (0.65%) | 21 (0.80%) |
| Citation markers emitted | 16474 | 10244 | 0 | 17224 | 0 |
| Citation markers pointing outside the passages | 5 (0.03%) | 10 (0.10%) | 0 | 15 (0.09%) | 0 |

## E4 failure taxonomy: rates by stage

Each row is a failure mode from the taxonomy. Values are the mean of the per-scenario rates, since the scenario is the unit of analysis (D28), over the unit named. Claim support and citation correctness come from the annotation study (E3).

| Stage | Failure mode | Unit | A1 | A2 | A3 | A4 | A5 |
|---|---|---|---|---|---|---|---|
| Retrieval (instruction) | No passage above threshold | per response | 0.118 | 0.089 | n/a | 0.070 | 0.107 |
| Retrieval (instruction) | All passages near threshold | per response | 0.186 | 0.169 | n/a | 0.163 | 0.195 |
| Retrieval (instruction) | Passage from another strand | per passage | 0.454 | 0.450 | n/a | 0.454 | 0.484 |
| Retrieval (assessment) | No passage retrieved for the item | per item | 0.173 | 0.102 | n/a | 0.111 | 0.154 |
| Planning | Schema invalid as extracted | per scenario | 0.458 | 0.042 | 0.417 | 0.292 | 0.458 |
| Planning | Reply was not parseable JSON | per scenario | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Planning | Time budget not satisfied | per scenario | 0.000 | 0.042 | 0.000 | 0.125 | 0.000 |
| Planning | Prerequisites unresolvable | per scenario | 0.250 | 0.042 | 0.250 | 0.083 | 0.250 |
| Planning | Prerequisite graph cyclic | per scenario | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Planning | Stated goal uncovered | per scenario | 0.083 | 0.083 | 0.083 | 0.042 | 0.083 |
| Planning | Final syllabus over budget after repair | per scenario | 1.000 | 0.917 | 1.000 | 1.000 | 1.000 |
| Negotiation | No revision occurred | per scenario | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Negotiation | Round limit without approval | per scenario | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Negotiation | Role inversion suspected | per scenario | 0.042 | 0.000 | 0.000 | 0.000 | 0.042 |
| Response | Canned refusal (the retrieval failure above) | per response | 0.118 | 0.089 | n/a | 0.070 | 0.107 |
| Response | Refusal written by the model | per response | 0.116 | 0.013 | 0.000 | 0.096 | 0.102 |
| Response | Truncated at the token limit | per response | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Response | Code block that does not parse | per code block | 0.002 | 0.002 | 0.022 | 0.006 | 0.007 |
| Assessment | Item fails its schema | per item | 0.004 | 0.000 | 0.002 | 0.001 | 0.000 |
| Assessment | Placeholder item (reply unparseable) | per item | 0.004 | 0.000 | 0.000 | 0.001 | 0.000 |
| Grounding and citation | Unsupported claim | per claim | pending E3 | pending E3 | pending E3 | pending E3 | pending E3 |
| Grounding and citation | Misattributed citation | per claim | pending E3 | pending E3 | pending E3 | pending E3 | pending E3 |
| Grounding and citation | Missing citation | per claim | pending E3 | pending E3 | pending E3 | pending E3 | pending E3 |

## Not computed here

Claim support, citation correctness and whether an item is answerable from the corpus come from the E3 annotation study and are not approximated by any measure above.

