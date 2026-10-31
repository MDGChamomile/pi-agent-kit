"""Hand-authored, non-personal histories shared by offline and opt-in evaluations."""
from pathlib import Path

from support import header, message, write_session


CASES = {
    "revised-hypothesis": {
        "terms": ("login", "401"),
        "messages": [
            ("user", "Why did login return 401 after deployment?"),
            ("assistant", "Initial hypothesis: an expired access credential caused login 401."),
            ("assistant", "Rejected that hypothesis: middleware order was the cause. Restoring the order resolved login 401, according to the smoke check report."),
        ],
    },
    "claimed-verification": {
        "terms": ("checkout", "timeout"),
        "messages": [
            ("user", "What happened to the checkout timeout?"),
            ("assistant", "The checkout timeout was fixed; all tests passed."),
            ("toolResult", "SYNTHETIC_TEST_OUTPUT: FAIL checkout integration test"),
        ],
    },
    "distant-outcome": {
        "terms": ("upload", "503"),
        "followup_terms": ("route wiring",),
        "messages": [
            ("user", "Investigate upload 503 after deployment."),
            ("assistant", "I will inspect route wiring."),
            *[("assistant", f"Intermediate investigation note {index}.") for index in range(6)],
            ("assistant", "Route wiring order was restored; the smoke check was reported successful."),
        ],
    },
    "truncated-outcome": {
        "terms": ("worker", "502"),
        "followup_terms": ("queue binding",),
        "messages": [
            ("user", "Recall the worker 502 investigation."),
            ("assistant", "Worker 502 investigation. " + "Intermediate diagnostic detail. " * 80
             + "Confirmed queue binding issue; corrected the binding and reported a passing smoke check."),
        ],
    },
}


def write_cases(root: Path, project: Path) -> None:
    """Create synthetic files only in the caller's explicit disposable directory."""
    for name, case in CASES.items():
        entries = []
        for index, (role, text) in enumerate(case["messages"]):
            extra = {"toolName": "bash", "isError": True} if role == "toolResult" else {}
            entries.append(message(
                f"m{index}", f"m{index - 1}" if index else None,
                f"2026-08-10T00:00:{index:02d}Z", role, text, **extra,
            ))
        write_session(root / f"{name}.jsonl", header(name, project), entries)
