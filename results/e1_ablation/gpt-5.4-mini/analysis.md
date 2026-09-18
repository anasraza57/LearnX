# e1 results: gpt-5.4-mini

Runs: 120 across conditions A1, A2, A3, A4, A5. Unit of analysis: the scenario (D28). Intervals are 95% and the decision rule is D29.

## Coverage

| Condition | Scenarios | Responses | Items | Cost (USD) | Median response latency (s) |
|---|---|---|---|---|---|
| A1 | 24 | 946 | 946 | 6.11 | 4.2 |
| A2 | 24 | 714 | 714 | 4.59 | 4.8 |
| A3 | 24 | 919 | 919 | 10.92 | 11.0 |
| A4 | 24 | 899 | 899 | 5.58 | 4.2 |
| A5 | 24 | 911 | 911 | 6.41 | 4.6 |

## Pre-registered contrasts

| Contrast | Isolates | Outcome | Median A | Median B | Median difference | 95% CI | Cliff's delta | p | Supported |
|---|---|---|---|---|---|---|---|---|---|
| A1 vs A2 | agent decomposition | constraint_satisfaction_rate | 0.857 | 1.000 | 0.000 | [-0.143, +0.000] | -0.365 | 0.021 | no (predicted higher) |
| A1 vs A3 | retrieval grounding | unsupported_claim_rate | pending E3 annotation | | | | | | |
| A1 vs A4 | the negotiation protocol | time_budget_satisfied | 1.000 | 1.000 | 0.000 | [+0.000, +0.000] | 0.125 | 0.083 | no (predicted higher) |
| | | proportions | 1.000 [+0.862, +1.000] | 0.875 [+0.690, +0.957] | McNemar exact | discordant 3 (3 vs 0) | | 0.250 | |
| A1 vs A5 | the citation instruction | misattribution_rate | pending E3 annotation | | | | | | |
| A1 vs A5 | the citation instruction | missing_citation_rate | pending E3 annotation | | | | | | |

## Automatic measures by condition

| Measure | A1 | A2 | A3 | A4 | A5 |
|---|---|---|---|---|---|
| no_passage_above_threshold | 0.093 | 0.082 | n/a | 0.056 | 0.099 |
| low_confidence_retrieval | 0.162 | 0.160 | n/a | 0.139 | 0.167 |
| off_strand_passage_rate | 0.410 | 0.394 | n/a | 0.377 | 0.415 |
| model_written_refusal | 0.083 | 0.000 | 0.000 | 0.083 | 0.078 |
| response_without_citation | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 |
| invalid_citation_marker_rate | 0.000 | 0.000 | n/a | 0.000 | n/a |
| citations_per_response | 19.349 | 15.333 | 0.000 | 20.613 | 0.000 |
| code_blocks_per_response | 1.477 | 3.350 | 22.488 | 1.789 | 2.923 |
| code_block_parse_failure | 0.008 | 0.000 | 0.022 | 0.016 | 0.019 |
| response_with_broken_code | 0.023 | 0.000 | 0.236 | 0.048 | 0.077 |
| item_valid | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| item_placeholder | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| item_retrieval_failed | 0.169 | 0.080 | n/a | 0.107 | 0.132 |

## Planning checks by condition

| Check | A1 | A2 | A3 | A4 | A5 |
|---|---|---|---|---|---|
| schema_valid_as_extracted | 0.54 [+0.35, +0.72] | 0.96 [+0.80, +0.99] | 0.58 [+0.39, +0.76] | 0.71 [+0.51, +0.85] | 0.54 [+0.35, +0.72] |
| extraction_parsed | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| time_budget_satisfied | 1.00 [+0.86, +1.00] | 0.96 [+0.80, +0.99] | 1.00 [+0.86, +1.00] | 0.88 [+0.69, +0.96] | 1.00 [+0.86, +1.00] |
| module_count_in_range | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| goal_covered | 0.83 [+0.64, +0.93] | 0.83 [+0.64, +0.93] | 0.92 [+0.74, +0.98] | 0.88 [+0.69, +0.96] | 0.79 [+0.60, +0.91] |
| prerequisites_present | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| prerequisites_resolvable | 0.75 [+0.55, +0.88] | 0.96 [+0.80, +0.99] | 0.75 [+0.55, +0.88] | 0.92 [+0.74, +0.98] | 0.75 [+0.55, +0.88] |
| prerequisites_acyclic | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| final_hours_over_budget | 1.00 [+0.86, +1.00] | 0.92 [+0.74, +0.98] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| all_constraints_satisfied | 0.42 [+0.24, +0.61] | 0.71 [+0.51, +0.85] | 0.50 [+0.31, +0.69] | 0.62 [+0.43, +0.79] | 0.46 [+0.28, +0.65] |

## Planning checks against A1, paired by scenario (exact McNemar)

| Check | A1 vs A2 | A1 vs A3 | A1 vs A4 | A1 vs A5 |
|---|---|---|---|---|
| schema_valid_as_extracted | 0.54 vs 0.96, discordant 0/10, p=0.002 | 0.54 vs 0.58, discordant 4/5, p=1.000 | 0.54 vs 0.71, discordant 2/6, p=0.289 | 0.54 vs 0.54, discordant 4/4, p=1.000 |
| extraction_parsed | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| time_budget_satisfied | 1.00 vs 0.96, discordant 1/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 0.88, discordant 3/0, p=0.250 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| module_count_in_range | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| goal_covered | 0.83 vs 0.83, discordant 2/2, p=1.000 | 0.83 vs 0.92, discordant 2/4, p=0.688 | 0.83 vs 0.88, discordant 3/4, p=1.000 | 0.83 vs 0.79, discordant 4/3, p=1.000 |
| prerequisites_present | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| prerequisites_resolvable | 0.75 vs 0.96, discordant 0/5, p=0.062 | 0.75 vs 0.75, discordant 2/2, p=1.000 | 0.75 vs 0.92, discordant 1/5, p=0.219 | 0.75 vs 0.75, discordant 2/2, p=1.000 |
| prerequisites_acyclic | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| final_hours_over_budget | 1.00 vs 0.92, discordant 2/0, p=0.500 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 | 1.00 vs 1.00, discordant 0/0, p=1.000 |
| all_constraints_satisfied | 0.42 vs 0.71, discordant 3/10, p=0.092 | 0.42 vs 0.50, discordant 6/8, p=0.791 | 0.42 vs 0.62, discordant 4/9, p=0.267 | 0.42 vs 0.46, discordant 5/6, p=1.000 |

## Negotiation

Runs with negotiation enabled: 72. Approved: 72. Reached the round limit without approval: 0. No revision occurred: 0. Role inversion suspected (needs confirmation by reading the transcript): 2.

## Not computed here

Claim support, citation correctness and whether an item is answerable from the corpus come from the E3 annotation study and are not approximated by any measure above.

