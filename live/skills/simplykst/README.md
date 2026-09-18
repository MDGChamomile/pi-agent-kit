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

The calculator section of the [methodology](references/methodology.md#계산-도구-입력) is the canonical input and scoring contract. See the runnable [synthetic example](examples/input.json) and [sector profiles](references/sector-weights.json). Invalid inputs fail safely with diagnostics on stderr and exit code 2; the calculator cannot validate disclosure quality, source independence, economic sector selection, or investment outcomes.

The offline test suite covers the input contract, weighted scoring, rounding, missing evidence, readiness gates, risk precedence, sector limits, CLI errors, and the runnable example. The [validation record](references/validation.md) separates offline checks and public-source/browser smoke checks from still-incomplete real-company end-to-end analysis.

## Report presentation

Reports lead with the conclusion, valuation, and conditions that would change the assessment, followed by four-column factor tables and calculation/source detail. Material withholding reasons, missing-score ranges, and risk caps remain visible in the first summary. See the [synthetic before/after excerpts](examples/report-layout.md); these check information preservation, not measured reader comprehension or full real-company execution.

The short report-writing guidance draws on the meaning-clarity principles of [fluent-korean's non-coding style at ce8683f](https://github.com/snflkd/fluent-korean/blob/ce8683f/plugins/fluent-korean/output-styles/fluent-korean-not-coding.md). The finance-specific rules and examples here are independently written adaptations, not a reproduction of the full style or a claim of equivalent results. No plugin, remote document loading during analysis, global configuration change, or editing agent is required.

## License

[MIT](LICENSE). Keep the bundled license notice when copying or redistributing this skill.
