#!/bin/sh
# Nudges toward running the lint skill when enough recent commits have
# touched the knowledge base to make a full validation pass worthwhile —
# an approximation of "the KB has churned enough that drift may have
# accumulated." The heuristic is deliberately imprecise: a nudge costs one
# line of context, so a miss is cheaper than a lecture.

window_days=14
threshold=5      # commits touching the KB in that window

# `git rev-parse --is-inside-work-tree` exits 0 even in a bare repo or a
# cwd inside .git, printing "false" in that case — check the printed
# value, not just the exit code (same guard as capture-nudge.sh).
inside_work_tree=$(git rev-parse --is-inside-work-tree 2>/dev/null)
[ "$inside_work_tree" = "true" ] || exit 0

count=$(git log --oneline --since="${window_days} days ago" -- \
  docs/facts docs/decisions docs/guardrails docs/skills 2>/dev/null \
  | wc -l | tr -d ' ')

if [ "$count" -ge "$threshold" ]; then
  echo "This knowledge base has had $count commit(s) touching docs/{facts,decisions,guardrails,skills}/ in the last $window_days days. If relevant, mention to the user that running this plugin's lint skill would check the whole knowledge base for drift, contradictions, or stale debt that individual sessions wouldn't catch."
fi
