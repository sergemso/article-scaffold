.PHONY: pdf docx html quick clean all validate hooks metadata metadata-check upgrade analysis analysis-check supp supp-pdf diff arxiv wordcount spell watch figures

PAPER_DIR = paper

# Pandoc is optional; the DOCX/HTML targets are skipped by CI if unavailable.
PANDOC ?= pandoc

# Read the selected citation style from metadata.yaml so DOCX and HTML use the
# same choice as the LaTeX bibliography. The fallback keeps make usable before
# the first metadata regeneration.
CITATION_STYLE ?= $(shell python3 -c 'import yaml; print((yaml.safe_load(open("metadata.yaml")) or {}).get("citation_style", "numeric"))' 2>/dev/null || echo numeric)

# Optional Word reference template at the repository root. Put a
# reference.docx there to control DOCX styles; it is never used by the PDF.
REFERENCE_DOCX ?= reference.docx

# Pandoc does not read LaTeX \graphicspath, so point it at every place a
# figure may live. Paths are relative to the repository root, where `make`
# runs; the PDF build still uses paper/article.tex's \graphicspath unchanged.
DOCX_RESOURCE_PATH = paper:paper/figures:.
# Empirical projects may also include generated tables in paper/tables/.
ifneq ($(wildcard paper/tables),)
DOCX_RESOURCE_PATH := $(DOCX_RESOURCE_PATH):paper/tables
endif

all: pdf

# ─────────────────────────────────────────────────────────────
# Build targets
# ─────────────────────────────────────────────────────────────

pdf:
	python3 -m scripts.article build pdf
	cp $(PAPER_DIR)/build/article.pdf $(PAPER_DIR)/article.pdf
	@echo "PDF built: $(PAPER_DIR)/article.pdf"

# The CLI owns the modern DOCX plan. The inline fallback keeps generated
# repositories usable with pre-2.11 pandoc (which has no --citeproc).
docx:
	@if $(PANDOC) --help 2>/dev/null | grep -q -- '--citeproc'; then \
		python3 -m scripts.article build docx --citation-style=$(CITATION_STYLE); \
	else \
		CITEPROC=""; \
		if command -v pandoc-citeproc >/dev/null 2>&1; then \
			CITEPROC="--filter pandoc-citeproc"; \
		fi; \
		REFERENCE=""; \
		if [ -f "$(REFERENCE_DOCX)" ]; then \
			REFERENCE="--reference-doc=$(REFERENCE_DOCX)"; \
		fi; \
		BIBLIOGRAPHY=""; \
		if [ -n "$$CITEPROC" ]; then \
			BIBLIOGRAPHY="--bibliography=paper/refs.bib"; \
		fi; \
		$(PANDOC) \
			--output=manuscript.docx \
			--from=latex \
			--to=docx \
			$$CITEPROC \
			$$BIBLIOGRAPHY \
			--resource-path=$(DOCX_RESOURCE_PATH) \
			$$REFERENCE \
			paper/article.tex; \
	fi
	@echo "DOCX built: manuscript.docx"
	@echo "Figures are read in place through --resource-path; PDF sources are not modified."

html:
	@CITEPROC=""; \
	if $(PANDOC) --help 2>/dev/null | grep -q -- '--citeproc'; then \
		CITEPROC="--citeproc"; \
	elif command -v pandoc-citeproc >/dev/null 2>&1; then \
		CITEPROC="--filter pandoc-citeproc"; \
	fi; \
	BIBLIOGRAPHY=""; \
	if [ -n "$$CITEPROC" ]; then \
		BIBLIOGRAPHY="--bibliography=paper/refs.bib"; \
	fi; \
	$(PANDOC) \
		--output=manuscript.html \
		--from=latex \
		--to=html5 \
		$$CITEPROC \
		$$BIBLIOGRAPHY \
		--resource-path=$(DOCX_RESOURCE_PATH) \
		paper/article.tex
	@echo "HTML built: manuscript.html"

quick:
	cd $(PAPER_DIR) && pdflatex -interaction=nonstopmode article.tex
	@echo "Quick (single-pass) PDF built — cross-refs may be wrong"

# ─────────────────────────────────────────────────────────────
# Empirical analysis — explicit, reproducible, and never part of `pdf`.
# Outputs are written to paper/figures/ and paper/tables/; the manuscript
# includes them conditionally so a clean checkout still builds before the
# first analysis run. Heavy scientific packages are an opt-in extra.
# ─────────────────────────────────────────────────────────────

analysis:
	@python3 analysis/analyze.py

analysis-check:
	@python3 analysis/analyze.py --check

# ─────────────────────────────────────────────────────────────
# Supplementary materials — PDF for extended data, code, etc.
# ─────────────────────────────────────────────────────────────

# Builds every standalone supplementary document: paper/supplementary.tex
# and each paper/supplementary/*.tex that has a \documentclass. Each PDF is
# written next to its source (paper/supplementary/NAME.pdf).
supp-pdf:
	python3 -m scripts.article build supp

supp: supp-pdf

# ─────────────────────────────────────────────────────────────
# Local validation — same checks as .github/workflows/validate-latex.yml
# Used by the pre-push hook in scripts/pre-push.
# ─────────────────────────────────────────────────────────────

validate:
	@python3 scripts/validate-paper.py
	@echo "All validation checks passed."

# Install or reinstall the pre-push hook. Safe to run repeatedly.
hooks:
	@mkdir -p scripts/githooks
	@cp scripts/pre-push scripts/githooks/pre-push
	@chmod +x scripts/githooks/pre-push
	@if command -v git >/dev/null 2>&1; then \
		git config --local core.hooksPath scripts/githooks; \
		echo "Installed pre-push hook -> scripts/githooks/pre-push"; \
	else \
		echo "WARNING: git not found; hook copied but not enabled."; \
	fi

# ─────────────────────────────────────────────────────────────
# Regenerate derived metadata from metadata.yaml
# Updates CITATION.cff, .zenodo.json, README.md citation block,
# and paper/article.tex title/author/date fields.
# ─────────────────────────────────────────────────────────────

metadata:
	@python3 -m scripts.article metadata
	@echo "Metadata-derived files regenerated."

metadata-check:
	@python3 -m scripts.article metadata --check

# Show what a template upgrade would change. Read-only; see docs/cli.md for
# `upgrade --apply` and `upgrade --finish`.
upgrade:
	@python3 -m scripts.article upgrade --plan

# ─────────────────────────────────────────────────────────────

clean:
	cd $(PAPER_DIR) && latexmk -C
	rm -rf $(PAPER_DIR)/build
	rm -f $(PAPER_DIR)/article.pdf $(PAPER_DIR)/supplementary.pdf $(PAPER_DIR)/supplementary/*.pdf
	rm -rf $(PAPER_DIR)/supplementary/build
	rm -f manuscript.docx manuscript.html manuscript.pdf
	@echo "Build artifacts cleaned"

# ─────────────────────────────────────────────────────────────
# Authoring tools — not part of pdf/CI unless explicitly invoked
# Each target fails with an actionable message if its tool is missing.
# ─────────────────────────────────────────────────────────────

diff:
	python3 -m scripts.article diff --old-ref=$(OLD_REF) --new-ref=$(NEW_REF) --output=$(OUTPUT)

arxiv:
	python3 -m scripts.article arxiv --output=$(OUTPUT)

wordcount:
	python3 -m scripts.article wordcount

spell:
	python3 -m scripts.article spell

watch:
	python3 -m scripts.article watch

figures:
	python3 -m scripts.article figures
