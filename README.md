# MATACS-TH-2026-02: AI Proposal Triage Design

| | |
|---|---|
| **Candidate** | Muhammad Aitazaz Ahsan (maitazaz.bse23mcs@student.nust.edu.pk) |
| **Reference** | MATACS-TH-2026-02 |
| **Time actually spent** | 2 hrs |

**Design in one line: AI reads, rules score, people decide.** An AI model pulls facts out of each proposal, with an exact quote for every fact. Plain code applies the admin's pass/fail checks and scoring formulas. A reviewer confirms the facts, resolves flags and makes the award.

## Files

| File | What it is |
|---|---|
| [diagram/process_flow.png](diagram/process_flow.png) | Process flow from upload to ranked output (AI steps, rule steps, human checkpoints) |
| [WRITEUP.md](WRITEUP.md) | Answers to the five questions, plus assumptions |
| [PROMPTS.md](PROMPTS.md) | The extraction prompt exactly as sent, with call settings |
| [ranking.json](ranking.json) | Expected ranking of proposals A–E |
| [prototype/](prototype/) | Optional: runnable scorer and extraction script |

## Result for the sample set

| Proposal | Status | Score |
|---|---|---|
| A | Rank 1 | 98.0 |
| E | Rank 2 | 88.7 |
| C | Flagged: hidden instruction to rank it first | withheld (78.8) |
| D | Flagged: no committed completion time | withheld (71.8) |
| B | Ineligible: licence held by a subcontractor | not scored |

## Prototype (optional extra)

| File | Purpose |
|---|---|
| [prototype/criteria_v1.json](prototype/criteria_v1.json) | What the admin screens would save: criteria, weights and scoring rules for this category |
| [prototype/prompts.py](prototype/prompts.py) | Builds the extraction prompt and JSON schema from the criteria |
| [prototype/extract.py](prototype/extract.py) | AI step: one Gemini call per proposal, quote verification, injection pre-scan |
| [prototype/score.py](prototype/score.py) | Rules step: mandatory gates, weighted scores, flags, ranking (no AI) |
| [prototype/fixtures/expected_extraction.json](prototype/fixtures/expected_extraction.json) | Hand-checked facts for A–E, so scoring runs without an API key |
| [prototype/output/ranking_live.json](prototype/output/ranking_live.json) | Ranking produced from the live Gemini run |

```bash
cd prototype
python score.py                     # scores A-E from the fixture, prints the breakdown

# Live AI extraction with Gemini (free API key from Google AI Studio):
# copy .env.example to .env and set GEMINI_API_KEY
pip install -r requirements.txt
# put each proposal's text in prototype/samples/A.txt ... E.txt (git-ignored)
python extract.py
python score.py --extraction output/extraction.json
```

**Live test:** running `extract.py` with `gemini-3.8-flash` on A–E reproduced the hand-checked fixture exactly (all 25 fields). No quotes failed verification, and Proposal C's hidden instruction was caught by both the model and the keyword pre-scan. The scorer output from that run is in [prototype/output/ranking_live.json](prototype/output/ranking_live.json).

Proposal text is not included in this repository, as the brief requires. The fixture stores structured values only.

## How I used AI tools


I used Claude (through Claude Code) as an assistant during the assessment to help understand the requirements, structure the solution, draft the documentation and prompts, and generate prototype code.

The overall approach, technical decisions, and final evaluation were reviewed and determined by me. I used Gemini for the proposal extraction step and tested the prototype using my own API key. I also independently reviewed the extracted information against the original proposals and corrected AI-generated outputs wherever necessary. This included adjusting the model configuration and reviewing how certain criteria were interpreted to ensure the final results aligned with the assessment requirements.

When Gemini questioned whether "a named project lead" counts without an actual name, I decided it does, since the admin's intent is a committed lead and the reviewer confirms the name at fact checking.