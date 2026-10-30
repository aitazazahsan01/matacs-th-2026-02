# MATACS-TH-2026-02: AI Proposal Triage Design

| | |
|---|---|
| **Candidate** | Muhammad Aitazaz Ahsan (maitazaz.bse23mcs@student.nust.edu.pk) |
| **Reference** | MATACS-TH-2026-02 |
| **Time actually spent** | _In progress_ |

**Design in one line: AI reads, rules score, people decide.** An AI model pulls facts out of each proposal, with an exact quote for every fact. Plain code applies the admin's pass/fail checks and scoring formulas. A reviewer confirms the facts, resolves flags and makes the award.

## Files

| File | What it is |
|---|---|
| [diagram/process_flow.png](diagram/process_flow.png) | Process flow from upload to ranked output (AI steps, rule steps, human checkpoints) |
| [WRITEUP.md](WRITEUP.md) | Answers to the five questions, plus assumptions |
| [PROMPTS.md](PROMPTS.md) | The extraction prompt exactly as sent, with call settings |
| [ranking.json](ranking.json) | Expected ranking of proposals A–E |
| [prototype/](prototype/) | Runnable scorer and extraction script |

## Result for the sample set

| Proposal | Status | Score |
|---|---|---|
| A | Rank 1 | 98.0 |
| E | Rank 2 | 88.7 |
| C | Flagged: hidden instruction to rank it first | withheld (78.8) |
| D | Flagged: no committed completion time | withheld (71.8) |
| B | Ineligible: licence held by a subcontractor | not scored |

## Prototype

| File | Purpose |
|---|---|
| [prototype/criteria_v1.json](prototype/criteria_v1.json) | What the admin screens would save: criteria, weights and scoring rules for this category |
| [prototype/prompts.py](prototype/prompts.py) | Builds the extraction prompt and JSON schema from the criteria |
| [prototype/extract.py](prototype/extract.py) | AI step: one Gemini call per proposal, quote verification, injection pre-scan |
| [prototype/score.py](prototype/score.py) | Rules step: mandatory gates, weighted scores, flags, ranking (no AI) |
| [prototype/fixtures/expected_extraction.json](prototype/fixtures/expected_extraction.json) | Hand-checked facts for A–E, so scoring runs without an API key |

```bash
cd prototype
python score.py
```
