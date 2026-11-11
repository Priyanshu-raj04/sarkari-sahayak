"""Minimal SARIF 2.1.0 writer for GitHub code scanning."""

from typing import Any

from gatekeeper import __version__
from gatekeeper.models import Finding

REPO_URL = "https://github.com/Priyanshu-raj04/mcp-gatekeeper"
_LEVEL = {"high": "error", "medium": "warning", "low": "note"}
_SECURITY_SEVERITY = {"high": "8.0", "medium": "5.0", "low": "2.0"}  # GitHub maps this to severity


def to_sarif(findings: list[Finding], artifact_uri: str) -> dict[str, Any]:
    rules: dict[str, dict[str, Any]] = {}
    results = []
    for f in findings:
        rules.setdefault(
            f.rule_id,
            {
                "id": f.rule_id,
                "name": f.message.replace(" ", ""),
                "shortDescription": {"text": f.message},
                "properties": {
                    "security-severity": _SECURITY_SEVERITY[f.severity],
                    "tags": ["security", "mcp"],
                },
            },
        )
        results.append(
            {
                "ruleId": f.rule_id,
                "level": _LEVEL[f.severity],
                "message": {"text": f"Tool '{f.tool}': {f.message} (detector: {f.detector})"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": artifact_uri},
                            "region": {"startLine": 1},
                        }
                    }
                ],
                "partialFingerprints": {"toolRule": f"{f.tool}:{f.rule_id}"},
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "mcp-gatekeeper",
                        "version": __version__,
                        "informationUri": "https://github.com/Priyanshu-raj04/mcp-gatekeeper",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
