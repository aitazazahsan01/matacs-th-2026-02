# MATACS-TH-2026-02: AI Proposal Triage Design

| | |
|---|---|
| **Candidate** | Muhammad Aitazaz Ahsan (maitazaz.bse23mcs@student.nust.edu.pk) |
| **Reference** | MATACS-TH-2026-02 |
| **Time actually spent** | _In progress_ |

**Design in one line: AI reads, rules score, people decide.** An AI model pulls facts out of each proposal, with an exact quote for every fact. Plain code applies the admin's pass/fail checks and scoring formulas. A reviewer confirms the facts, resolves flags and makes the award.

## Structure

- `prototype/criteria_v1.json`: RFP scoring criteria, weights, and rules
