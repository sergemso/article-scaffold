# latexmk configuration for reproducible, out-of-tree builds.
# This file is read automatically when latexmk runs from the paper/ directory.

# Output directory (relative to the paper/ directory where latexmk runs).
# All .aux, .bbl, .log, .pdf, etc. go into build/.
$out_dir = 'build';

# Halt on first error and show file:line numbers.
$pdf_mode = 1;                 # use pdflatex
$pdflatex = 'pdflatex -interaction=nonstopmode -file-line-error -halt-on-error %O %S';
$bibtex_use = 2;               # run bibtex when needed

# Fixed SOURCE_DATE_EPOCH for reproducible PDF timestamps.
# In CI, the workflow can override this with the commit timestamp.
# The epoch is set to a fixed default so local builds are reproducible.
$ENV{'SOURCE_DATE_EPOCH'} //= 1609459200;  # 2021-01-01 00:00:00 UTC

# Continuous preview mode (not used by Make/CI).
$preview_mode = 0;
$preview_continuous_mode = 0;

# Clean up build/ directory with `latexmk -C` or `make clean`.
$clean_ext = 'build/*';

# Ensure the output directory exists.
$do_cd = 0;
$force_mode = 1;

# Quiet mode: reduce noise in CI logs.
$silent = 0;

# Maximum number of runs (default is 5, which is fine).
$max_repeat = 5;