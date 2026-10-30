# Design Write-up

**The idea in one line: AI reads, rules score, people decide.** The flow is in [diagram/process_flow.png](diagram/process_flow.png); the prompt is in [PROMPTS.md](PROMPTS.md); the result for the samples is in [ranking.json](ranking.json).

## 1. AI vs. rules

| Step | Who | Why |
|---|---|---|
| Upload, pick category | Person | |
| PDF to text, file hash, keyword scan for injected instructions | Code | Mechanical work; needs no judgement |
| **Pull facts out of each proposal** (licence holder, price, weeks, warranty years, install count, team items), each with an exact quote | **AI** | Proposals are free text written differently by every bidder. Reading "all-in", "to be confirmed after award" or "since 2021" is where AI adds value |
| Check that every quote really appears in the document | Code | Catches invented facts |
| Mandatory pass/fail checks, weighted scores, ranking, reason text | Code | These must be exact, repeatable and explainable. |
| Confirm facts, clear flags, accept or override ranking, award | Person | Accountability stays with a human |

I drew the line at **interpretation vs. judgement**. AI turns messy text into structured facts. It never sees other proposals and never gives a score, so it cannot "prefer" a bidder. Scoring formulas live in the admin's criteria config (for example price = lowest eligible price ÷ this price; team = 25 points per checklist item), so admins change them in screens rather than in code or prompts.

## 2. Consistency and explainability

- **Scores are repeatable by construction.** Given the same confirmed facts and the same criteria version, the scorer always gives the same numbers. Ranking twice gives the same result.
- **The AI step can vary slightly between runs**, so its output is **stored and reused**, not regenerated. Re-ranking reads the stored, human-confirmed facts. Re-extraction happens only when a file or field changes.
- **Structured output** (a JSON schema built from the criteria) means the AI can only return the fields we asked for.
- **Explainability:** for every proposal the reviewer sees a per-criterion table (fact, quote, rule, points). The one-line reason is generated from that table, not written by AI. Example: E lost 9 points on experience.

## 3. Human in the loop

Three checkpoints:

1. **Confirm facts** (after extraction). The reviewer sees each value beside its quote and can correct or fill it. Fields with failed quotes or AI "uncertainties" are highlighted.
2. **Resolve flags.** Flagged proposals are held, not dropped. The reviewer can clear the flag (re-score), ask the bidder for clarification, or reject.
3. **Review the ranking.** The reviewer can override any score or rank, but must enter a reason. The award is always a human decision.

**Audit log** (append-only, one record per run): file hashes; criteria version; model name, prompt version and request ID; raw AI output with quotes; validation failures; flags; every human edit or override (who, when, old value, new value, reason); final scores and ranking.

## 4. Changing criteria

- Saving criteria creates a **new version**; old versions are never edited. Each run is pinned to one version, which is shown on the ranking.
- If criteria change after scoring, existing results are marked **"scored under v1, current is v2"** and are never silently updated.
- **Weight or formula change only:** re-score instantly from the stored facts. No AI call is needed, and the reviewer sees old and new rankings side by side.
- **New or changed fields** (for example a new "Indigenous partnership" criterion): only those fields are re-extracted, then re-confirmed by the reviewer.
- **Once an award is made, its run is locked.**

## 5. Risks and safeguards

| Risk | Safeguard |
|---|---|
| **Wrong extraction** | Quote required for every value; fact-confirmation checkpoint; range checks (price vs. budget, weeks vs. limit) |
| **Made-up facts** | AI told to return null when not stated; code discards any value whose quote is not found in the document |
| **Manipulation / prompt injection** (Proposal C) | Proposal text wrapped as untrusted data; AI never scores; independent keyword scan plus AI reporting; any hit flags the bid for a person |
| **Missing information treated as zero** (Proposal D) | Missing required facts raise a flag ("ask the bidder"), not a silent low score |
| **Tempting but ineligible bid** (Proposal B, cheapest) | Mandatory gates run before scoring; an ineligible bid is never ranked, however cheap |
| **Bias** (favouring polished bids) | AI only extracts; scores use facts, not writing style; overrides are logged so patterns can be reviewed |
| **Ambiguous admin wording** | Each field has a written definition the admin owns; edge cases go to the reviewer |
| **Scanned or poor PDFs** | OCR with a quality warning; low-text files go straight to manual review |
| **Cost / outage** | One call per proposal, only when files or fields change; re-scoring is free; if the API fails, the reviewer types facts in manually |

## Sample result

A ranks 1st (98.0), E 2nd (88.7). C is flagged (hidden instruction; would score 78.8 on merit, still below E). D is flagged (no committed schedule). B is ineligible (licence held by a subcontractor). Clearing C or D later does not change A's or E's score. Details: [ranking.json](ranking.json).

## Assumptions

- "Last 5 years" counts back from 2026. C's "since 2020" may include older installs, so it is noted for the reviewer, not penalised automatically.
- "Monitoring plan" means post-installation performance monitoring; C's weekly progress reports do not count.
- "Named project lead" counts when the bidder commits a specific lead now (A, C, D, E), even without giving the person's name; the reviewer confirms the name at fact checking. "Will be assigned" (B) does not count.
- Experience points use bands (12+ installs = 100, 10–11 = 85, 8–9 = 70, 5–7 = 50, 1–4 = 25). This is an admin setting, not something the AI decides.
