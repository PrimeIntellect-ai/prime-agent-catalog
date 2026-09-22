#!/usr/bin/env python3
"""Validate a PR title against the model-tracking conventions.

ci.yml runs this on every pull request whose diff touches `models/`; the
title must follow one of the tracking formats documented in AGENTS.md:

- add a model:     `add model: <model-id>`
- remove a model:  `remove model: <model-id>`
- upstream drift, exporter fixes, sync blockers: `sync: <topic>`
- repo process or CI changes: `ci: <topic>`

PRs that do not touch `models/` are exempt. Enforced so a catalog change can
be tracked by model id from the PR list and `git log --grep` alone.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

TITLE_PATTERNS: tuple[re.Pattern[str], ...] = (
	re.compile(r"^add model: \S+$"),
	re.compile(r"^remove model: \S+$"),
	re.compile(r"^sync: .+"),
	re.compile(r"^ci: .+"),
)

SUPPORTED = "'add model: <model-id>', 'remove model: <model-id>', 'sync: <topic>', 'ci: <topic>'"


def title_matches_convention(title: str) -> bool:
	return any(pattern.match(title) for pattern in TITLE_PATTERNS)


def pr_touches_models(base_sha: str) -> bool:
	"""True when the PR diff (merge-base..HEAD) changes any path under models/."""
	merge_base = (
		subprocess.run(
			["git", "merge-base", base_sha, "HEAD"],
			capture_output=True,
			text=True,
			check=True,
		).stdout.strip()
	)
	diff = subprocess.run(
		["git", "diff", "--name-only", merge_base, "HEAD"],
		capture_output=True,
		text=True,
		check=True,
	).stdout
	return any(line.startswith("models/") for line in diff.splitlines() if line)


def main() -> int:
	base_sha = os.environ.get("BASE_SHA", "")
	title = os.environ.get("PR_TITLE", "")
	if not base_sha:
		print("check_pr_title: BASE_SHA not set; run from ci.yml", file=sys.stderr)
		return 1
	if not pr_touches_models(base_sha):
		print("ok: no models/ changes; title exempt")
		return 0
	if title_matches_convention(title):
		print(f"ok: title follows the tracking conventions: {title!r}")
		return 0
	print(
		f"PR title {title!r} does not match the tracking conventions; expected one of {SUPPORTED}",
		file=sys.stderr,
	)
	return 1


if __name__ == "__main__":
	sys.exit(main())
