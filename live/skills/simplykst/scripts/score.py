"""Offline arithmetic only; never fetch data or assess evidence automatically."""
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

IDS = {"trading": set("MLEFVS"), "investing": set("VQGBRO")}
RISKS = {"halted", "delisting_confirmed", "going_concern", "capital_impaired",
         "default", "adverse_audit", "disclaimer_audit", "material_qualified_audit"}
SEVERE = RISKS - {"halted", "delisting_confirmed", "material_qualified_audit"}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("Expected a finite JSON number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Expected a finite JSON number")
    return result


def fmt(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate(view, data):
    if view not in IDS:
        raise ValueError("Unknown perspective")
    if type(data.get("essentials_ready")) is not bool:
        raise ValueError("essentials_ready must be explicit boolean")
    factors = data["factors"]
    if len(factors) != 6 or {f["id"] for f in factors} != IDS[view]:
        raise ValueError("Exactly six unique perspective-specific factors required")
    flags = data.get("confirmed_risks", [])
    if not isinstance(flags, list) or any(r not in RISKS for r in flags):
        raise ValueError("Unknown confirmed risk")
    if flags and not data.get("risk_evidence"):
        raise ValueError("Confirmed risk needs evidence")
    weighted = Decimal(0)
    coverage = Decimal(0)
    total = Decimal(0)
    grade_a = Decimal(0)
    grade_ab = Decimal(0)
    contributions = {}
    for factor in factors:
        weight = number(factor["weight"])
        if weight < 5 or weight > 100:
            raise ValueError("Each weight must be at least 5")
        total += weight
        if not factor.get("reason"):
            raise ValueError("Each factor requires rationale or missing-data reason")
        score = factor["score"]
        if score is None:
            contributions[factor["id"]] = None
            continue
        score = number(score)
        if score < 0 or score > 5 or score % Decimal("0.5") != 0:
            raise ValueError("Factor scores must be 0..5 in 0.5 steps")
        if factor.get("grade") not in {"A", "B", "C"} or not factor.get("sources"):
            raise ValueError("Scored factors require evidence grade and sources")
        weighted += weight * score
        coverage += weight
        if factor["grade"] == "A":
            grade_a += weight
        if factor["grade"] in {"A", "B"}:
            grade_ab += weight
        contributions[factor["id"]] = fmt(weight * score / 100)
    if total != 100:
        raise ValueError("Weights must sum to 100")
    lower = weighted / 100
    upper = (weighted + 5 * (100 - coverage)) / 100
    raw = weighted / coverage if coverage else None
    cap = Decimal(5)
    if set(flags) & SEVERE:
        cap = Decimal(2 if view == "trading" else 1)
    if view == "investing" and "material_qualified_audit" in flags:
        cap = min(cap, Decimal(2))
    if view == "trading" and set(flags) & {"halted", "delisting_confirmed"}:
        cap = Decimal(0)
    ready = coverage >= 70 and data["essentials_ready"]
    status = "rated" if ready and coverage >= 85 else "provisional" if ready else "withheld"
    confidence = "low"
    if ready and grade_ab >= coverage * Decimal("0.8"):
        confidence = "medium"
    if ready and coverage >= 85 and grade_a >= coverage * Decimal("0.8") and grade_ab == coverage:
        confidence = "high"
    return {
        "status": status, "recommendation": fmt(min(raw, cap)) if ready else None,
        "observed_mean": fmt(raw) if raw is not None else None,
        "coverage_pct": fmt(coverage), "confidence": confidence,
        "uncapped_missing_range": [fmt(lower), fmt(upper)],
        "risk_cap": fmt(cap),
        "capped_missing_range": [fmt(min(lower, cap)), fmt(min(upper, cap))],
        "contributions_full_weight": contributions,
    }


def main():
    if len(sys.argv) != 2:
        raise ValueError("Usage: python3 score.py INPUT.json")
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle, parse_float=Decimal)
    if set(data) != set(IDS):
        raise ValueError("Input must contain trading and investing")
    return {view: calculate(view, data[view]) for view in IDS}


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False, indent=2))
    except (ValueError, InvalidOperation, KeyError, TypeError, OSError):
        print("Invalid input: check schema, weights, scores and evidence fields.", file=sys.stderr)
        sys.exit(2)
