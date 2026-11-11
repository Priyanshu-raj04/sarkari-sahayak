"""Rule-based poisoned-tool detector: fast, offline, explainable. Covers EN, Hindi and Hinglish."""

import base64
import binascii
import unicodedata
from dataclasses import dataclass

import regex

from gatekeeper.models import Finding, Severity, ToolSpec


@dataclass(frozen=True, slots=True)
class Rule:
    rule_id: str
    severity: Severity
    message: str
    pattern: regex.Pattern[str]


def _r(rule_id: str, severity: Severity, message: str, pattern: str) -> Rule:
    return Rule(rule_id, severity, message, regex.compile(pattern, regex.IGNORECASE))


RULES: tuple[Rule, ...] = (
    _r(
        "GK001",
        "high",
        "Instruction override",
        r"ignore (all |any )?(previous|prior|above) (instructions|rules)"
        r"|disregard .{0,20}instructions",
    ),
    _r(
        "GK002",
        "high",
        "Instruction override (Hindi)",
        r"(पिछले|पहले के|ऊपर के)\s+(सभी\s+)?(निर्देश|नियम)\w*\s+(को\s+)?(अनदेखा|नज़रअंदाज़|नजरअंदाज|भूल)",
    ),
    _r(
        "GK003",
        "high",
        "Instruction override (Hinglish)",
        r"(pichhle|pichle|pehle ke)\s+(sab(hi)?\s+)?(instructions?|nirdesh|rules?)\s+(ko\s+)?"
        r"(ignore|bhool|bhul|andekha)",
    ),
    _r(
        "GK004",
        "high",
        "Sensitive file access",
        r"~/\.ssh|id_rsa|\.aws/credentials|\.env\b|/etc/passwd|mcp\.json|claude_desktop_config",
    ),
    _r(
        "GK005",
        "high",
        "Concealment from the user",
        r"(do not|don't|never) (tell|mention|inform|reveal)|without (telling|informing) the user"
        r"|user (ko|se) (mat|na) (batana|bataana)|उपयोगकर्ता को (मत|न) (बताएं|बताना)",
    ),
    _r(
        "GK006",
        "medium",
        "Hidden instruction block",
        r"<(important|system|instructions?|secret)>|\[\s*(system|hidden)\s*\]",
    ),
    _r(
        "GK007",
        "medium",
        "Cross-tool shadowing",
        r"(when|before|after|whenever) (using|calling) (the )?[`'\"]?\w+[`'\"]? tool|"
        r"(other|another) tool'?s? (behaviou?r|arguments?)",
    ),
    _r(
        "GK008",
        "medium",
        "Exfiltration via arguments",
        r"(include|put|pass|send|append) .{0,40}(in|into|as) (the )?[`'\"]?\w+[`'\"]? "
        r"(argument|parameter|field)",
    ),
)

_INVISIBLE = {"Cf"}  # format characters: zero-width, bidi overrides, tags
_B64 = regex.compile(r"[A-Za-z0-9+/]{40,}={0,2}")


def _invisible_chars(text: str) -> int:
    return sum(1 for ch in text if unicodedata.category(ch) in _INVISIBLE)


def _decoded_payloads(text: str) -> list[str]:
    out = []
    for m in _B64.finditer(text):
        try:
            out.append(base64.b64decode(m.group(), validate=True).decode("utf-8"))
        except (binascii.Error, UnicodeDecodeError):
            continue
    return out


def scan_tool(tool: ToolSpec) -> list[Finding]:
    """Scan the description AND every string inside the input schema (descriptions, enums...)."""
    texts = [tool.description, *_schema_strings(tool.input_schema)]
    texts += [p for t in texts for p in _decoded_payloads(t)]
    findings: list[Finding] = []
    for text in texts:
        normalized = unicodedata.normalize("NFKC", text)
        for rule in RULES:
            if rule.pattern.search(normalized):
                findings.append(
                    Finding(
                        tool=tool.name,
                        rule_id=rule.rule_id,
                        severity=rule.severity,
                        message=rule.message,
                        detector="heuristic",
                    )
                )
        if _invisible_chars(text) > 0:
            findings.append(
                Finding(
                    tool=tool.name,
                    rule_id="GK009",
                    severity="medium",
                    message="Invisible/format Unicode characters",
                    detector="heuristic",
                )
            )
    return list({(f.rule_id, f.tool): f for f in findings}.values())  # dedupe


def _schema_strings(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _schema_strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _schema_strings(v)]
    return []
