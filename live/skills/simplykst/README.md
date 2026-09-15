# simplykst

`simplykst` is a Korean-language Pi skill for analyzing Korean listed companies, starting with DART disclosures. It reports separate **Trading (1–12 weeks)** and **Investing (1–3 years)** ratings out of **5.00**, using six factors per perspective and nine sector weighting profiles.

Read [`SKILL.md`](SKILL.md) for the workflow, [`references/methodology.md`](references/methodology.md) for scoring, and [`references/data-sources.md`](references/data-sources.md) for collection and credential safeguards.

## Requirements and installation

- Pi with web research tools; browser tools may be needed for public disclosure viewers.
- Python 3.10 or later for the optional offline calculator and tests. No third-party Python dependencies are required.
- Public DART access does not require an API key. This skill includes no OpenDART API integration or automated data collector.

From the repository root, copy only this skill directory into a Pi skill location. If an installation already exists, review the differences before replacing it.

```bash
mkdir -p ~/.pi/agent/skills
cp -R live/skills/simplykst ~/.pi/agent/skills/
```

Restart Pi or use `/reload`. With skill commands enabled:

```text
/skill:simplykst 삼성전자 보통주를 분석해 주세요.
```

The model can also select the skill for matching requests. Installation does not add web tools or configure credentials.

## Behavior and safety

- Reads the latest periodic disclosures, corrections, subsequent material disclosures, and relevant notes before relying on supplementary sources.
- Publishes factor evidence and weights, coverage, confidence, missing-data ranges, and confirmed-risk caps. Missing evidence is not scored as zero or average; inadequate coverage or missing essential evidence withholds the affected rating.
- Uses company-specific weighting adjustments only before scoring, within the documented limits.
- The analysis workflow makes public web requests and may use temporary files to extract documents. Reports are saved only when requested.
- The calculator reads a supplied JSON file and writes results to stdout. It makes no network requests. It validates sector/mixed-sector weight bounds and evidence-ID structure, but cannot assess source quality, independence, or economic sector selection.
- Any future API integration and secure key setup require separate authorization. Never put keys in chat, reports, command-line arguments, URLs used by general web tools, or the repository.

These ratings are analytical heuristics, not a backtested strategy, return probabilities, guaranteed returns, or personalized investment suitability assessments. Trading and Investing conclusions may differ.

## Calculator and verification

From this directory:

```bash
python3 -B scripts/score.py --help
python3 -B scripts/score.py examples/input.json
python3 -B tests/test_score.py
```

The input schema is documented in the methodology's calculator section. Supply one or both `trading` and `investing` objects, each with `sector`, all six factors, evidence, and an explicit essential-data readiness flag. Existing inputs must add `sector`; adjusted weights also require `weight_reason`. See the runnable [synthetic example](examples/input.json) and [sector profiles](references/sector-weights.json). Scores >= 4 need two distinct evidence IDs (these may reference independent metrics within one document). Unknown perspective/factor fields and duplicate JSON keys at any depth are rejected. Invalid inputs produce safe diagnostics on stderr and exit code 2. Individually rounded contributions may not sum to the displayed rating; the rating uses the unrounded weighted sum, with missing-data reweighting and risk caps handled separately. Confidence measures observed evidence separately from rating readiness; halted/delisting-confirmed shares withhold Investing ratings rather than automatically equating delisting with insolvency.

The 23 tests cover unequal-score weighted means (including missing factors), display rounding, unknown fields, duplicate JSON keys, risk-field typos, missing evidence, coverage/confidence boundaries, essential-data gating, risk precedence, sector/mixed-sector limits, profile-table consistency, CLI input/error handling, and the runnable example. CI runs unittest discovery. They do not validate actual disclosures or investment outcomes. The [validation record](references/validation.md) distinguishes public-source/browser access smoke checks from still-incomplete real-company end-to-end analysis. Full reference loading remains unchanged until complete cases establish that selective loading preserves the same controls.

## License

MIT, as provided by the repository-level [`LICENSE`](../../../LICENSE) file. Retain that notice when redistributing the skill.
