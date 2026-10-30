"""Rule-based scoring: turns extracted facts into eligibility, scores and a ranking.

No AI runs here. The same criteria file and the same extracted facts always give
the same output, which is what makes the ranking repeatable and auditable.

Usage:
    python score.py                                   # uses the hand-checked fixture
    python score.py --extraction output/extraction.json --out ../ranking.json
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def check_condition(value, cond):
    op = cond["op"]
    if op == "present":
        return value not in (None, "")
    if value is None:
        return False
    if op == "eq":
        return value == cond["value"]
    if op == "gte":
        return value >= cond["value"]
    raise ValueError(f"Unknown op {op}")


def evaluate_mandatory(criterion, values):
    """Return (passed, reason)."""
    failed = []
    for cond in criterion["rule"]["conditions"]:
        v = values.get(cond["field"])
        if not check_condition(v, cond):
            failed.append(f"{cond['field']}={v!r}")
    if failed:
        return False, f"{criterion['name']}: failed ({', '.join(failed)})"
    return True, f"{criterion['name']}: passed"


def pool_values(pool, crit_id, field):
    return [p["values"][crit_id].get(field) for p in pool]


def score_weighted(criterion, values, pool, project):
    """Return (score_0_100, flags, warnings, note)."""
    rule = criterion["rule"]
    kind = rule["kind"]
    flags, warnings = [], []

    if kind == "bands":
        v = values.get(rule["field"])
        score = 0
        if v is not None:
            score = next((b["score"] for b in rule["bands"] if v >= b["min"]), 0)
        warn = rule.get("warn_if")
        if warn:
            limit = project["reference_year"] - 5 if warn["value_from"] == "reference_year_minus_5" else warn["value"]
            wv = values.get(warn["field"])
            if wv is not None and warn["op"] == "lt" and wv < limit:
                warnings.append(warn["message"])
        return score, flags, warnings, f"{v} qualifying installs"

    if kind == "lowest_is_best":
        field, limit = rule["field"], project[rule["limit_from"]]
        v = values.get(field)
        valid = [x for x in pool_values(pool, criterion["id"], field) if x is not None and x <= limit]
        if v is None:
            flags.append(f"{criterion['name']}: not stated in proposal")
            return 0, flags, warnings, "not stated"
        if v > limit:
            flags.append(f"{criterion['name']}: {v} exceeds limit {limit}")
            return 0, flags, warnings, f"{v} (over limit)"
        return 100 * min(valid) / v, flags, warnings, f"{v} (best in pool {min(valid)})"

    if kind == "highest_is_best_parts":
        score, notes = 0, []
        for part in rule["parts"]:
            v = values.get(part["field"])
            best = max((x for x in pool_values(pool, criterion["id"], part["field"]) if x is not None), default=None)
            if v is not None and best:
                score += part["share"] * v / best
            notes.append(f"{part['field']}={v}")
        return score, flags, warnings, ", ".join(notes)

    if kind == "checklist":
        hits = [f for f in rule["fields"] if values.get(f) is True]
        missing = [f for f in rule["fields"] if f not in hits]
        note = f"{len(hits)}/{len(rule['fields'])}" + (f" (missing: {', '.join(missing)})" if missing else "")
        return 100 * len(hits) / len(rule["fields"]), flags, warnings, note

    raise ValueError(f"Unknown rule kind {kind}")


def run(criteria_path, extraction_path):
    criteria = load_json(criteria_path)
    extraction = load_json(extraction_path)
    if extraction.get("criteria_version") != criteria["criteria_version"]:
        raise SystemExit("Extraction was made with a different criteria version; re-extract before scoring.")

    project = criteria["project"]
    mandatory = [c for c in criteria["criteria"] if c["type"] == "mandatory"]
    weighted = [c for c in criteria["criteria"] if c["type"] == "weighted"]
    assert sum(c["weight"] for c in weighted) == 100, "Weights must add to 100"

    proposals = extraction["proposals"]
    results = {}
    for p in proposals:
        checks = [evaluate_mandatory(c, p["values"][c["id"]]) for c in mandatory]
        results[p["proposal"]] = {
            "proposal": p["proposal"],
            "mandatory": [r for _, r in checks],
            "eligible": all(ok for ok, _ in checks),
            "flags": [], "warnings": list(p.get("uncertainties", [])), "criteria": [],
        }
        if p.get("embedded_instructions") or p.get("prescan_hits"):
            where = "; ".join(i.get("where", "?") for i in p.get("embedded_instructions", []))
            results[p["proposal"]]["flags"].append(
                f"Possible manipulation: text addressed to the reviewer/AI ({where or 'pre-scan match'}). Ignored for scoring; human must review.")

    # Comparative rules (price, timeline, warranty) only compare proposals that passed the
    # mandatory gates. Flagged-but-eligible proposals stay in the pool so that clearing a
    # flag later does not change anyone else's score.
    pool = [p for p in proposals if results[p["proposal"]]["eligible"]]

    for p in pool:
        r = results[p["proposal"]]
        total = 0.0
        for c in weighted:
            s, flags, warnings, note = score_weighted(c, p["values"][c["id"]], pool, project)
            pts = s * c["weight"] / 100
            total += pts
            r["flags"] += flags
            r["warnings"] += warnings
            r["criteria"].append({"id": c["id"], "score": round(s, 1), "weight": c["weight"],
                                  "points": round(pts, 2), "basis": note})
        r["provisional_score"] = round(total, 1)

    for r in results.values():
        r["status"] = "ineligible" if not r["eligible"] else ("flagged" if r["flags"] else "ranked")

    ranked = sorted((r for r in results.values() if r["status"] == "ranked"),
                    key=lambda r: (-r["provisional_score"], r["proposal"]))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i

    meta = {"criteria_version": criteria["criteria_version"],
            "criteria_sha": file_hash(criteria_path), "extraction_sha": file_hash(extraction_path)}
    return results, meta


def one_line_reason(r):
    if r["status"] == "ineligible":
        failed = [m for m in r["mandatory"] if "failed" in m]
        return "Fails mandatory check - " + "; ".join(failed) + ". Not scored."
    weakest = min(r["criteria"], key=lambda c: c["points"] - c["weight"])
    lost = weakest["weight"] - weakest["points"]
    if r["status"] == "flagged":
        return (" ".join(f.rstrip(".") + "." for f in r["flags"]) +
                f" Provisional score {r['provisional_score']} withheld until a reviewer clears this.")
    return (f"Passes both mandatory checks; scores {r['provisional_score']}/100; "
            f"most points lost on {weakest['id']} (-{lost:.1f}: {weakest['basis']}).")


def to_ranking_json(results):
    order = {"ranked": 0, "flagged": 1, "ineligible": 2}
    rows = sorted(results.values(), key=lambda r: (order[r["status"]], r.get("rank", 99), r["proposal"]))
    return [{"proposal": r["proposal"], "rank": r.get("rank"), "status": r["status"],
             "score": r["provisional_score"] if r["status"] == "ranked" else None,
             "reason": one_line_reason(r)} for r in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--criteria", default=HERE / "criteria_v1.json")
    ap.add_argument("--extraction", default=HERE / "fixtures" / "expected_extraction.json")
    ap.add_argument("--out", default=HERE / "output" / "ranking.json")
    args = ap.parse_args()

    if not Path(args.extraction).exists():
        raise SystemExit(f"{args.extraction} not found - run extract.py first (or omit --extraction to use the fixture).")
    results, meta = run(args.criteria, args.extraction)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(to_ranking_json(results), indent=2) + "\n", encoding="utf-8")
    report = HERE / "output" / "score_report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"run": meta, "results": results}, indent=2) + "\n", encoding="utf-8")

    for r in sorted(results.values(), key=lambda r: r["proposal"]):
        print(f"{r['proposal']}  {r['status']:<10} rank={r.get('rank')}  score={r.get('provisional_score')}")
        for c in r["criteria"]:
            print(f"     {c['id']:<10} {c['score']:>5} x {c['weight']}% = {c['points']:>5}   {c['basis']}")
        for f in r["flags"]:
            print(f"     FLAG: {f}")
        for w in r["warnings"]:
            print(f"     note: {w}")
    print(f"\nWrote {out} and {report}")


if __name__ == "__main__":
    main()
