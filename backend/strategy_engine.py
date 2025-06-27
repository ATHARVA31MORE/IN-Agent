import json
from pathlib import Path

def match_case(clause, text):
    cases = json.loads(Path("data/mock_cases.json").read_text())
    for case in cases:
        if clause == case["clause"] or case["description"].lower() in text.lower():
            return {
                "matched_case": case["description"],
                "strategy": case["strategy"],
                "payout": case["payout"],
                "outcome": case["outcome"]
            }
    return {"strategy": "General Appeal", "outcome": "Unknown", "payout": 0}
