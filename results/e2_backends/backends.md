# E2 backends: condition A1 across models

The architecture, corpus, scenarios and prompts are identical across these arms; only the model differs. Paired by scenario. Not pre-registered: reported descriptively.

## Coverage

| Backend | Scenarios | Responses | Items | API cost (USD) | Median latency (s) | Runs failed |
|---|---|---|---|---|---|---|
| gpt-5.4-mini | 24 | 946 | 946 | 6.11 | 4.2 | 0 |
| mistral:7b | 1 | 28 | 28 | n/a | 13.7 | 0 |

## Planning checks by backend (proportion of scenarios, 95% Wilson)

| Check | gpt-5.4-mini | mistral:7b |
|---|---|---|
| schema_valid_as_extracted | 0.54 [+0.35, +0.72] | 1.00 [+0.21, +1.00] |
| extraction_parsed | 1.00 [+0.86, +1.00] | 1.00 [+0.21, +1.00] |
| time_budget_satisfied | 1.00 [+0.86, +1.00] | 0.00 [+0.00, +0.79] |
| prerequisites_resolvable | 0.75 [+0.55, +0.88] | 1.00 [+0.21, +1.00] |
| goal_covered | 0.83 [+0.64, +0.93] | 1.00 [+0.21, +1.00] |
| all_constraints_satisfied | 0.42 [+0.24, +0.61] | 0.00 [+0.00, +0.79] |

## Automatic measures by backend (median of per-scenario rates)

| Measure | gpt-5.4-mini | mistral:7b |
|---|---|---|
| no_passage_above_threshold | 0.093 | 0.071 |
| low_confidence_retrieval | 0.162 | 0.071 |
| off_strand_passage_rate | 0.410 | 0.254 |
| model_written_refusal | 0.083 | 0.107 |
| response_without_citation | 0.000 | 0.000 |
| invalid_citation_marker_rate | 0.000 | 0.000 |
| citations_per_response | 19.349 | 7.846 |
| code_blocks_per_response | 1.477 | 1.643 |
| code_block_parse_failure | 0.008 | 0.152 |
| response_with_broken_code | 0.023 | 0.105 |
| item_valid | 1.000 | 0.857 |
| item_placeholder | 0.000 | 0.071 |
| item_retrieval_failed | 0.169 | 0.071 |

## Paired differences against gpt-5.4-mini

| Measure | vs mistral:7b |
|---|---|
| constraint_satisfaction_rate | +0.000 |
| schema_valid_as_extracted | -1.000 |
| time_budget_satisfied | +1.000 |
| no_passage_above_threshold | -0.048 |
| citations_per_response | +13.788 |
| item_valid | +0.143 |
| code_block_parse_failure | -0.152 |

Local backends report no API cost. Their cost of ownership (energy and amortised hardware) is computed separately by `python -m src.experiment.tco`.

