#!/usr/bin/env python3
"""Positive and negative cases for the PR title convention matcher."""

import check_pr_title

CASES = [
	("add model: claude-opus-5-5", True),
	("add model: openai/gpt-6-sol-pro", True),
	("remove model: gpt-4o", True),
	("sync: refresh catalog from live upstreams", True),
	("ci: enforce the pr title convention", True),
	("add grok-4.7 to whitelisted providers", False),
	("add model:", False),
	("add model: one and two", False),
	("Add Model: claude-opus-5-5", False),
	("sync:", False),
	("docs: fix a typo in the readme", False),
]

failures = 0
for title, expected in CASES:
	if check_pr_title.title_matches_convention(title) is expected:
		print(f"ok title: {title!r}")
	else:
		failures += 1
		print(f"FAIL title: {title!r} expected {expected}")

if failures:
	raise SystemExit(f"{failures} title-convention cases failed")
print(f"{len(CASES)} title-convention cases passed.")
