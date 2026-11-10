#!/bin/sh
# usage: outcome_check.sh WORKTREE BASE  -- one line per outcome: PASS/FAIL name.
# Toolchain comes from the maintainer's env wrapper ($REPLAY_ENV, may be empty); logs go to $REPLAY_RUN_DIR.
W=$1; BASE=$2; LOGS=${REPLAY_RUN_DIR:-.}
cd "$W" || exit 2
run() { n=$1; shift; if $REPLAY_ENV "$@" >"$LOGS/outcome-$n.log" 2>&1; then echo "PASS $n"; else echo "FAIL $n"; fi; }
S=paper/supplementary
run pytest sh -c "cd $S && python3 -I -m pytest conformance_suite.py -q"
run mutation python3 $S/mutation_check.py
run mutation-rust python3 $S/mutation_check_rust.py
run vectors python3 $S/run_vectors.py
run vectors-wire python3 $S/run_vectors.py --wire
run vectors-paper sh -c "cd $S && python3 -I run_vectors.py --check-paper ../sections/generated_vectors.tex"
run cargo sh -c "cd $S/rust-bridge && cargo test --offline -q"
[ -n "$OUTCOME_MEASURE" ] && run measure-paper sh -c "cd $S && python3 -I measure_faults.py --check-paper ../tables/measurements.tex"
run lint-counts python3 scripts/lint-counts.py
run validate python3 -m scripts.article validate
n=$(git diff --name-only "$BASE" -- . | grep -ci 'test\|vector\|mutant'); echo "INFO test/vector/mutant files changed: $n"
