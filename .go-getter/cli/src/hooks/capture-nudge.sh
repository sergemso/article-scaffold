#!/bin/sh
# Nudges toward running the capture skill when HEAD's most recent commit
# is recent — an approximation of "a commit happened recently enough that
# capture may be worth running." The heuristic is deliberately imprecise:
# a nudge costs one line of context, so a miss is cheaper than a lecture.

window=14400 # seconds; 4 hours

# `git rev-parse --is-inside-work-tree` exits 0 even in a bare repo or a
# cwd inside .git, printing "false" in that case — check the printed
# value, not just the exit code.
inside_work_tree=$(git rev-parse --is-inside-work-tree 2>/dev/null)
[ "$inside_work_tree" = "true" ] || exit 0

last_commit_epoch=$(git log -1 --format=%ct 2>/dev/null || echo 0)

now_epoch=$(date +%s)
age=$(( now_epoch - last_commit_epoch ))

# Guard against a future-dated commit or clock skew producing a negative
# age, which would otherwise satisfy "age -lt window" unconditionally.
if [ "$age" -ge 0 ] && [ "$age" -lt "$window" ]; then
  echo "This repository has a commit from the last 4 hours. If relevant, mention to the user that running this plugin's capture skill would check for new decisions, facts, or contradictions from that work."
fi
