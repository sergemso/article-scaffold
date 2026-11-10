#!/bin/sh
# Order 3 adds the measure_faults paper check to the common outcome checks.
OUTCOME_MEASURE=1 exec sh "$(dirname "$0")/outcome_check.sh" "$@"
