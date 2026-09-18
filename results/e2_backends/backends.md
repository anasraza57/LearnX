# E2 backends: condition A1 across models

The architecture, corpus, scenarios and prompts are identical across these arms; only the model differs. Paired by scenario. Not pre-registered: reported descriptively.

## Coverage

| Backend | Scenarios | Responses | Items | API cost (USD) | Median latency (s) | Calls stopped by the cap | Runs failed |
|---|---|---|---|---|---|---|---|
| gpt-5.4-mini | 24 | 946 | 946 | 6.11 | 4.2 | 0 | 0 |
| gpt-4o-mini | 24 | 534 | 534 | 0.57 | 10.1 | 0 | 0 |
| gpt-3.5-turbo | 24 | 474 | 474 | 1.21 | 3.3 | 0 | 0 |
| mistral-7b-32k | 24 | 649 | 649 | n/a | 14.8 | 2 | 0 |
| gemma3-4b-32k | 24 | 530 | 530 | n/a | 11.7 | 0 | 0 |

## Planning checks by backend (proportion of scenarios, 95% Wilson)

| Check | gpt-5.4-mini | gpt-4o-mini | gpt-3.5-turbo | mistral-7b-32k | gemma3-4b-32k |
|---|---|---|---|---|---|
| schema_valid_as_extracted | 0.54 [+0.35, +0.72] | 0.75 [+0.55, +0.88] | 0.83 [+0.64, +0.93] | 0.42 [+0.24, +0.61] | 0.25 [+0.12, +0.45] |
| extraction_parsed | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] | 1.00 [+0.86, +1.00] |
| time_budget_satisfied | 1.00 [+0.86, +1.00] | 0.79 [+0.60, +0.91] | 0.79 [+0.60, +0.91] | 0.38 [+0.21, +0.57] | 0.50 [+0.31, +0.69] |
| prerequisites_resolvable | 0.75 [+0.55, +0.88] | 0.79 [+0.60, +0.91] | 0.88 [+0.69, +0.96] | 0.62 [+0.43, +0.79] | 0.62 [+0.43, +0.79] |
| goal_covered | 0.92 [+0.74, +0.98] | 0.79 [+0.60, +0.91] | 0.62 [+0.43, +0.79] | 0.46 [+0.28, +0.65] | 0.83 [+0.64, +0.93] |
| all_constraints_satisfied | 0.46 [+0.28, +0.65] | 0.46 [+0.28, +0.65] | 0.42 [+0.24, +0.61] | 0.04 [+0.01, +0.20] | 0.08 [+0.02, +0.26] |

## Automatic measures by backend (median of per-scenario rates)

| Measure | gpt-5.4-mini | gpt-4o-mini | gpt-3.5-turbo | mistral-7b-32k | gemma3-4b-32k |
|---|---|---|---|---|---|
| no_passage_above_threshold | 0.093 | 0.092 | 0.019 | 0.058 | 0.000 |
| low_confidence_retrieval | 0.176 | 0.111 | 0.086 | 0.108 | 0.062 |
| off_strand_passage_rate | 0.444 | 0.381 | 0.338 | 0.324 | 0.324 |
| model_written_refusal | 0.098 | 0.000 | 0.000 | 0.000 | 0.000 |
| response_without_citation | 0.000 | 0.417 | 0.054 | 0.108 | 0.000 |
| invalid_citation_marker_rate | 0.000 | 0.000 | 0.000 | 0.003 | 0.000 |
| citations_per_response | 18.048 | 1.563 | 4.156 | 4.842 | 12.268 |
| code_blocks_per_response | 1.477 | 3.453 | 0.675 | 2.000 | 1.935 |
| code_block_parse_failure | 0.000 | 0.000 | 0.000 | 0.000 | 0.020 |
| response_with_broken_code | 0.000 | 0.000 | 0.000 | 0.000 | 0.047 |
| item_valid | 1.000 | 1.000 | 1.000 | 0.917 | 1.000 |
| item_placeholder | 0.000 | 0.000 | 0.000 | 0.018 | 0.000 |
| item_retrieval_failed | 0.169 | 0.082 | 0.025 | 0.064 | 0.015 |

## Paired differences against gpt-5.4-mini

| Measure | vs gpt-4o-mini | vs gpt-3.5-turbo | vs mistral-7b-32k | vs gemma3-4b-32k |
|---|---|---|---|---|
| constraint_satisfaction_rate | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.071] | +0.143 [+0.143, +0.286] | +0.143 [+0.000, +0.286] |
| schema_valid_as_extracted | +0.000 [+0.000, +0.000] | +0.000 [-1.000, +0.000] | +0.000 [+0.000, +1.000] | +0.500 [+0.000, +1.000] |
| time_budget_satisfied | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | +1.000 [+0.000, +1.000] | +0.500 [+0.000, +1.000] |
| no_passage_above_threshold | +0.024 [-0.037, +0.064] | +0.070 [+0.028, +0.121] | +0.031 [+0.004, +0.075] | +0.093 [+0.055, +0.167] |
| citations_per_response | +16.443 [+14.917, +17.998] | +13.779 [+11.958, +16.214] | +13.159 [+12.040, +15.368] | +5.678 [+4.400, +7.075] |
| item_valid | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | +0.083 [+0.067, +0.130] | +0.000 [+0.000, +0.000] |
| code_block_parse_failure | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | +0.000 [+0.000, +0.000] | -0.017 [-0.024, +0.000] |

Local backends report no API cost. Their cost of ownership (energy and amortised hardware) is computed separately by `python -m src.experiment.tco`.

