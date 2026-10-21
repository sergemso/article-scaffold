.PHONY: pdf docx quick clean all validate hooks metadata metadata-check

PAPER_DIR = paper

# Pandoc is optional; the DOCX target is skipped by CI if it is unavailable.
PANDOC ?= pandoc

# Optional Word reference template at the repository root. Put a
# reference.docx there to control DOCX styles; it is never used by the PDF.
REFERENCE_DOCX ?= reference.docx

# Pandoc does not read LaTeX \graphicspath, so point it at every place a
# figure may live. Paths are relative to the repository root, where `make`
# runs; the PDF build still uses paper/article.tex's \graphicspath unchanged.
DOCX_RESOURCE_PATH = paper:paper/figures:.

all: pdf

# ─────────────────────────────────────────────────────────────
# Build targets
# ─────────────────────────────────────────────────────────────

pdf:
	python3 -m scripts.article build pdf
	@echo "PDF built: $(PAPER_DIR)/article.pdf"

# The CLI owns the modern DOCX plan. The inline fallback keeps generated
# repositories usable with pre-2.11 pandoc (which has no --citeproc).
docx:
	@if $(PANDOC) --help 2>/dev/null | grep -q -- '--citeproc'; then \
		python3 -m scripts.article build docx; \
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

quick:
	cd $(PAPER_DIR) && pdflatex -interaction=nonstopmode article.tex
	@echo "Quick (single-pass) PDF built — cross-refs may be wrong"

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

# ─────────────────────────────────────────────────────────────

clean:
	cd $(PAPER_DIR) && latexmk -C || rm -f *.aux *.bbl *.blg *.log *.out *.toc *.lof *.lot *.fls *.fdb_latexmk *.synctex.gz *.pdf
	rm -f manuscript.docx manuscript.pdf
	@echo "Build artifacts cleaned"
