"""
Validation framework for AI Modding Suite.
Provides concrete, working rules for common text/CFG hygiene and structure checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
import string
from typing import List, Optional


class Severity(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class ValidationIssue:
    rule_id: str
    message: str
    severity: Severity
    line: Optional[int] = None  # 1-based line number when applicable


@dataclass
class ValidationResult:
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        return all(i.severity != Severity.ERROR for i in self.issues)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def extend(self, issues: List[ValidationIssue]) -> None:
        self.issues.extend(issues)

    def as_text(self) -> str:
        if not self.issues:
            return "No issues found."
        lines = []
        for i in self.issues:
            loc = f" (line {i.line})" if i.line is not None else ""
            lines.append(f"[{i.severity.value}] {i.rule_id}{loc}: {i.message}")
        return "\n".join(lines)


class BaseRule:
    rule_id: str = "BASE"

    def check(self, text: str) -> List[ValidationIssue]:  # pragma: no cover - interface
        return []


class RuleNonEmptyFile(BaseRule):
    rule_id = "non_empty_file"

    def check(self, text: str) -> List[ValidationIssue]:
        if text.strip() == "":
            return [ValidationIssue(self.rule_id, "File is empty or only whitespace.", Severity.ERROR, None)]
        return []


class RuleNoNullBytes(BaseRule):
    rule_id = "no_null_bytes"

    def check(self, text: str) -> List[ValidationIssue]:
        if "\x00" in text:
            return [ValidationIssue(self.rule_id, "Contains NUL (\x00) byte(s).", Severity.ERROR, None)]
        return []


class RuleNoNonPrintable(BaseRule):
    rule_id = "no_non_printable"

    def check(self, text: str) -> List[ValidationIssue]:
        printable = set(string.printable) | {"\t", "\n", "\r"}
        issues: List[ValidationIssue] = []
        for idx, line in enumerate(text.splitlines(), start=1):
            bad = [ch for ch in line if ch not in printable]
            if bad:
                issues.append(
                    ValidationIssue(
                        self.rule_id,
                        f"Non-printable characters found: {repr(''.join(sorted(set(bad))))}",
                        Severity.WARNING,
                        idx,
                    )
                )
        return issues


class RuleMaxLineLength(BaseRule):
    rule_id = "max_line_length"

    def __init__(self, max_len: int = 200) -> None:
        self.max_len = max_len

    def check(self, text: str) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        for idx, line in enumerate(text.splitlines(), start=1):
            if len(line) > self.max_len:
                issues.append(
                    ValidationIssue(
                        self.rule_id,
                        f"Line length {len(line)} exceeds limit {self.max_len}.",
                        Severity.WARNING,
                        idx,
                    )
                )
        return issues


class RuleIniDuplicateKeys(BaseRule):
    rule_id = "ini_duplicate_keys"

    def check(self, text: str) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        seen = set()
        key_re = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*.*$")
        for idx, line in enumerate(text.splitlines(), start=1):
            if line.strip().startswith(('#', ';')):
                continue
            m = key_re.match(line)
            if not m:
                continue
            key = m.group(1).lower()
            if key in seen:
                issues.append(ValidationIssue(self.rule_id, f"Duplicate key '{key}'.", Severity.WARNING, idx))
            else:
                seen.add(key)
        return issues


class RuleBalancedBrackets(BaseRule):
    rule_id = "balanced_brackets"

    pairs = {')': '(', ']': '[', '}': '{'}
    opens = set(pairs.values())
    closes = set(pairs.keys())

    def check(self, text: str) -> List[ValidationIssue]:
        stack: List[tuple[str, int]] = []  # (char, line)
        issues: List[ValidationIssue] = []
        for idx, line in enumerate(text.splitlines(), start=1):
            for ch in line:
                if ch in self.opens:
                    stack.append((ch, idx))
                elif ch in self.closes:
                    if not stack or stack[-1][0] != self.pairs[ch]:
                        issues.append(ValidationIssue(self.rule_id, f"Unmatched '{ch}'.", Severity.ERROR, idx))
                    else:
                        stack.pop()
        for ch, line in stack:
            issues.append(ValidationIssue(self.rule_id, f"Unclosed '{ch}'.", Severity.ERROR, line))
        return issues


class CfgValidator:
    """Composite validator applying a curated set of rules suitable for generic CFG/text files."""

    def __init__(self, max_line_length: int = 200) -> None:
        self.rules: List[BaseRule] = [
            RuleNonEmptyFile(),
            RuleNoNullBytes(),
            RuleNoNonPrintable(),
            RuleMaxLineLength(max_line_length),
            RuleIniDuplicateKeys(),
            RuleBalancedBrackets(),
        ]

    def validate(self, text: str) -> ValidationResult:
        result = ValidationResult()
        for rule in self.rules:
            result.extend(rule.check(text))
        return result
