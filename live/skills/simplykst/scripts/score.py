"""Offline arithmetic only; never fetch data or assess evidence automatically."""
import argparse
import json
import sys
from pathlib import Path
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

IDS = {"trading": set("MLEFVS"), "investing": set("VQGBRO")}
RISKS = {"halted", "delisting_confirmed", "going_concern", "capital_impaired",
         "default", "adverse_audit", "disclaimer_audit", "material_qualified_audit"}
SEVERE = RISKS - {"halted", "delisting_confirmed", "material_qualified_audit"}


class InputError(ValueError):
    """Only fixed, safe diagnostics; never echo input values."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InputError('Usage: python3 score.py INPUT.json (or --help)')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value):
    return isinstance(value, list) and bool(value) and all(text(v) for v in value)


def baseline(view, data):
    with (Path(__file__).resolve().parents[1] / 'references/sector-weights.json').open(encoding='utf-8') as handle:
        profiles = json.load(handle)
    sector = data.get('sector')
    mix = {sector: 100} if isinstance(sector, str) else sector
    if not isinstance(mix, dict) or not 1 <= len(mix) <= 2 or any(k not in profiles for k in mix):
        raise InputError('sector must name one profile or map one/two profiles to percentages')
    mix = {k: number(v) for k, v in mix.items()}
    if any(v <= 0 for v in mix.values()) or sum(mix.values()) != 100:
        raise InputError('Sector percentages must be positive and sum to 100')
    return {id_: sum(profiles[k][view][id_] * v / 100 for k, v in mix.items()) for id_ in IDS[view]}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise InputError("Expected a finite JSON number")
    result = Decimal(str(value))
    if not result.is_finite():
        raise InputError("Expected a finite JSON number")
    return result


def fmt(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate(view, data):
    if view not in IDS:
        raise InputError("Unknown perspective")
    if not isinstance(data, dict):
        raise InputError('Perspective must be an object')
    base = baseline(view, data)
    if type(data.get("essentials_ready")) is not bool:
        raise InputError("essentials_ready must be explicit boolean")
    factors = data["factors"]
    if not isinstance(factors, list) or len(factors) != 6 or any(
        not isinstance(f, dict) or not isinstance(f.get('id'), str) for f in factors
    ) or {f['id'] for f in factors} != IDS[view]:
        raise InputError("Exactly six unique perspective-specific factors required")
    flags = data.get("confirmed_risks", [])
    if not isinstance(flags, list) or any(not isinstance(r, str) or r not in RISKS for r in flags):
        raise InputError("Unknown confirmed risk")
    if flags and not strings(data.get("risk_evidence")):
        raise InputError("Confirmed risk needs evidence")
    weighted = Decimal(0)
    coverage = Decimal(0)
    total = Decimal(0)
    grade_a = Decimal(0)
    grade_ab = Decimal(0)
    contributions = {}
    for factor in factors:
        weight = number(factor["weight"])
        if weight < 5 or weight > 100:
            raise InputError("Each weight must be between 5 and 100")
        if abs(weight - base[factor['id']]) > 10:
            raise InputError('Weight exceeds sector baseline by more than 10 percentage points')
        if weight != base[factor['id']] and not text(data.get('weight_reason')):
            raise InputError('Adjusted weights require weight_reason')
        total += weight
        if not text(factor.get("reason")):
            raise InputError("Each factor requires rationale or missing-data reason")
        score = factor["score"]
        if score is None:
            contributions[factor["id"]] = None
            continue
        score = number(score)
        if score < 0 or score > 5 or score % Decimal("0.5") != 0:
            raise InputError("Factor scores must be 0..5 in 0.5 steps")
        if factor.get("grade") not in ("A", "B", "C") or not strings(factor.get("sources")):
            raise InputError("Scored factors require evidence grade and source ID list")
        if score >= 4 and len({s.strip() for s in factor['sources']}) < 2:
            raise InputError('Scores >= 4 require at least two distinct evidence IDs')
        weighted += weight * score
        coverage += weight
        if factor["grade"] == "A":
            grade_a += weight
        if factor["grade"] in {"A", "B"}:
            grade_ab += weight
        contributions[factor["id"]] = fmt(weight * score / 100)
    if total != 100:
        raise InputError("Weights must sum to 100")
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
    market_restricted = view == 'investing' and bool(set(flags) & {'halted', 'delisting_confirmed'})
    ready = coverage >= 70 and data["essentials_ready"] and not market_restricted
    status = "rated" if ready and coverage >= 85 else "provisional" if ready else "withheld"
    confidence = "low"
    if coverage >= 70 and grade_ab >= coverage * Decimal("0.8"):
        confidence = "medium"
    if coverage >= 85 and grade_a >= coverage * Decimal("0.8") and grade_ab == coverage:
        confidence = "high"
    return {
        "status": status, "recommendation": fmt(min(raw, cap)) if ready else None,
        "withheld_reasons": (["coverage_below_70"] if coverage < 70 else [])
            + (["essentials_not_ready"] if not data['essentials_ready'] else [])
            + (["market_restricted"] if market_restricted else []),
        "observed_mean": fmt(raw) if raw is not None else None,
        "coverage_pct": fmt(coverage), "confidence": confidence,
        "uncapped_missing_range": [fmt(lower), fmt(upper)],
        "risk_cap": fmt(cap),
        "capped_missing_range": [fmt(min(lower, cap)), fmt(min(upper, cap))],
        "contributions_full_weight": contributions,
    }


def main():
    parser = Parser(prog='score.py', description='Offline simplykst scoring; no network access.',
        epilog='Schema: references/methodology.md; example: examples/input.json (relative to skill directory).')
    parser.add_argument('input', metavar='INPUT.json', help='One or both trading/investing objects; sector, essentials_ready and six factors required')
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as handle:
        data = json.load(handle, parse_float=Decimal)
    if not isinstance(data, dict) or not data or not set(data) <= set(IDS):
        raise InputError("Input must contain one or both of trading and investing only")
    return {view: calculate(view, data[view]) for view in IDS if view in data}


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False, indent=2))
    except InputError as exc:
        print(f'Invalid input: {exc}', file=sys.stderr)
        sys.exit(2)
    except (ValueError, InvalidOperation, KeyError, TypeError, OSError):
        print("Invalid input: check schema, weights, scores and evidence fields.", file=sys.stderr)
        sys.exit(2)
