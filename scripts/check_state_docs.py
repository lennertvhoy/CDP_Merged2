#!/usr/bin/env python3
"""
State Documentation Hygiene Check

Enforces file size limits and content rules for live-state documentation.
Fails if any live-state file violates the governance rules.

Usage:
    python scripts/check_state_docs.py
    python scripts/check_state_docs.py --fix  # Auto-trim where safe

Exit codes:
    0 = all checks passed
    1 = one or more checks failed
"""

import re
import sys
import argparse
from pathlib import Path

# File limits and rules
RULES = {
    "STATUS.md": {
        "max_lines": 120,
        "max_headline_bullets": 7,
        "forbidden_patterns": [r"^## Current Headline.*\n([\s\S]*?)(?=^## |\Z)"],
    },
    "NEXT_ACTIONS.md": {
        "max_lines": 180,
        "forbidden_statuses": ["COMPLETE", "REMOVED"],
        "max_items": 10,
    },
    "PROJECT_STATE.yaml": {
        "max_lines": 900,
        "require_as_of_for_counts": True,
    },
    "AGENTS.md": {
        "max_lines": 1000,
    },
    "BACKLOG.md": {
        "max_now_items": 10,
    },
}

# Canonical terminology
AZURE_STATUS_SYNONYMS = [
    r"azure\s+deployment\s+path\s+paused",
    r"azure\s+deployment\s+disabled\s+not\s+paused",
    r"azure\s+deployment\s+paused\s+not\s+disabled",
]

CANONICAL_AZURE_STATUS = "azure_deployment_status: disabled_for_cost_control"
CANONICAL_AZURE_STATUS_HUMAN = "Azure deployment disabled for cost control"


def count_lines(filepath: Path) -> int:
    """Count non-empty lines in file."""
    if not filepath.exists():
        return 0
    content = filepath.read_text()
    return len([line for line in content.split("\n") if line.strip()])


def count_headline_bullets(content: str) -> int:
    """Count bullet points in headline section."""
    # Find "## Current Headline" or "## Headline" section
    match = re.search(r"##\s+(?:Current\s+)?Headline\s*\n([\s\S]*?)(?=\n## |\Z)", content)
    if not match:
        return 0
    section = match.group(1)
    # Count bullet points (lines starting with - or *)
    bullets = len(re.findall(r"^[\s]*[-*][\s]", section, re.MULTILINE))
    return bullets


def check_forbidden_statuses(content: str, forbidden: list[str]) -> list[str]:
    """Check for forbidden status markers."""
    found = []
    for status in forbidden:
        # Look for "Status: STATUS" or "**Status:** STATUS"
        pattern = rf"[Ss]tatus[:\*]*\s*{status}"
        if re.search(pattern, content):
            found.append(status)
    return found


def count_now_items(content: str) -> int:
    """Count items in BACKLOG.md NOW section."""
    # Find NOW section
    match = re.search(r"###\s+NOW.*?(?=###\s+NEXT|\Z)", content, re.DOTALL)
    if not match:
        return 0
    section = match.group(0)
    # Count table rows or list items
    rows = len(re.findall(r"^\|\s*\d+\s*\|", section, re.MULTILINE))
    return rows


def check_azure_terminology(content: str, filepath: str) -> list[str]:
    """Check for inconsistent Azure status terminology."""
    issues = []
    for synonym in AZURE_STATUS_SYNONYMS:
        if re.search(synonym, content, re.IGNORECASE):
            # Check if it's using the canonical form
            if CANONICAL_AZURE_STATUS not in content and CANONICAL_AZURE_STATUS_HUMAN not in content:
                issues.append(f"Non-canonical Azure status terminology found (use '{CANONICAL_AZURE_STATUS_HUMAN}')")
                break
    return issues


def check_freshness_dates(content: str, filepath: str) -> list[str]:
    """Check that mutable counts have freshness dates."""
    issues = []
    # Look for numeric counts without as_of timestamps
    # Pattern: number like 70,922 or 70922 followed by description
    count_patterns = [
        r"(?:website_url|geo_latitude|ai_description|cbe_enriched)[:\s=]+(\d{1,3}(?:,\d{3})+|\d+)",
        r"(?:total|count)[:\s=]+(\d{1,3}(?:,\d{3})+|\d{3,})\s+(?:companies|records|rows)",
    ]
    
    for pattern in count_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            # Check if there's an as_of or date nearby
            start = max(0, match.start() - 200)
            end = min(len(content), match.end() + 200)
            context = content[start:end]
            if not re.search(r"(?:as_of|updated_at|verified_at|checked_at|as of|@)\s*[:=]?\s*\d{4}", context, re.IGNORECASE):
                # Only flag in live-state files
                if filepath in ["STATUS.md", "BACKLOG.md"]:
                    issues.append(f"Count '{match.group(0)}' missing freshness date (as_of/verified_at)")
    
    return issues


def check_resolved_problems(content: str) -> list[str]:
    """Check for resolved problems in active_problems section."""
    issues = []
    # Find active_problems section
    match = re.search(r"active_problems:([\s\S]*?)(?=\n\w+:|\Z)", content)
    if match:
        section = match.group(1)
        # Count resolved items
        resolved = len(re.findall(r"status:\s*resolved", section, re.IGNORECASE))
        if resolved > 5:  # Allow some grace period
            issues.append(f"Found {resolved} resolved problems in active_problems (should move to WORKLOG)")
    return issues


def check_file(filepath: Path) -> list[str]:
    """Run all checks on a file."""
    issues = []
    filename = filepath.name
    
    if not filepath.exists():
        return [f"File not found: {filepath}"]
    
    content = filepath.read_text()
    lines = count_lines(filepath)
    
    # Check line limits
    if filename in RULES:
        rules = RULES[filename]
        
        if "max_lines" in rules:
            if lines > rules["max_lines"]:
                issues.append(f"Line count {lines} exceeds max {rules['max_lines']}")
        
        if "max_headline_bullets" in rules:
            bullets = count_headline_bullets(content)
            if bullets > rules["max_headline_bullets"]:
                issues.append(f"Headline has {bullets} bullets, max is {rules['max_headline_bullets']}")
        
        if "forbidden_statuses" in rules:
            forbidden = check_forbidden_statuses(content, rules["forbidden_statuses"])
            for status in forbidden:
                issues.append(f"Found forbidden status '{status}' (move to WORKLOG)")
        
        if "max_items" in rules and filename == "NEXT_ACTIONS.md":
            # Count P0/P1 items
            items = len(re.findall(r"^###\s+P[01]:", content, re.MULTILINE))
            if items > rules["max_items"]:
                issues.append(f"Found {items} active items, max is {rules['max_items']}")
        
        if "max_now_items" in rules and filename == "BACKLOG.md":
            now_items = count_now_items(content)
            if now_items > rules["max_now_items"]:
                issues.append(f"NOW section has {now_items} items, max is {rules['max_now_items']}")
    
    # Check Azure terminology
    issues.extend(check_azure_terminology(content, filename))
    
    # Check freshness dates for counts
    issues.extend(check_freshness_dates(content, filename))
    
    # Check for resolved problems in PROJECT_STATE.yaml
    if filename == "PROJECT_STATE.yaml":
        issues.extend(check_resolved_problems(content))
    
    return issues


def main():
    parser = argparse.ArgumentParser(description="Check state documentation hygiene")
    parser.add_argument("--fix", action="store_true", help="Attempt to auto-fix issues")
    args = parser.parse_args()
    
    root = Path("/var/home/ff/Documents/CDP_Merged")
    files_to_check = [
        root / "AGENTS.md",
        root / "STATUS.md",
        root / "PROJECT_STATE.yaml",
        root / "NEXT_ACTIONS.md",
        root / "BACKLOG.md",
    ]
    
    all_issues = []
    
    print("=" * 60)
    print("STATE DOCUMENTATION HYGIENE CHECK")
    print("=" * 60)
    
    for filepath in files_to_check:
        print(f"\n📄 {filepath.name}")
        issues = check_file(filepath)
        
        if issues:
            all_issues.extend([(filepath.name, issue) for issue in issues])
            for issue in issues:
                print(f"  ❌ {issue}")
        else:
            print("  ✅ All checks passed")
    
    print("\n" + "=" * 60)
    
    if all_issues:
        print(f"FAILED: {len(all_issues)} issue(s) found")
        print("\nSummary:")
        for filename, issue in all_issues:
            print(f"  - {filename}: {issue}")
        sys.exit(1)
    else:
        print("PASSED: All state documentation checks passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
