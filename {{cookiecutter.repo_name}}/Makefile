.PHONY: pdf docx quick clean all validate metadata metadata-check

PAPER_DIR = paper

all: pdf

# ─────────────────────────────────────────────────────────────
# Build targets
# ─────────────────────────────────────────────────────────────

pdf:
	cd $(PAPER_DIR) && latexmk -pdf -interaction=nonstopmode -file-line-error article.tex
	@echo "PDF built: $(PAPER_DIR)/article.pdf"

docx:
	cd $(PAPER_DIR) && pandoc \
		--output=../manuscript.docx \
		--from=latex \
		--to=docx \
		--citeproc \
		--bibliography=refs.bib \
		article.tex
	@echo "DOCX built: manuscript.docx"

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

# ─────────────────────────────────────────────────────────────
# Regenerate derived metadata from metadata.yaml
# Updates CITATION.cff, .zenodo.json, README.md citation block,
# and paper/article.tex title/author/date fields.
# ─────────────────────────────────────────────────────────────

metadata:
	@python3 scripts/generate-metadata.py
	@echo "Metadata-derived files regenerated."

metadata-check:
	@python3 scripts/generate-metadata.py --check

# ─────────────────────────────────────────────────────────────

clean:
	cd $(PAPER_DIR) && latexmk -C || rm -f *.aux *.bbl *.blg *.log *.out *.toc *.lof *.lot *.fls *.fdb_latexmk *.synctex.gz *.pdf
	rm -f manuscript.docx manuscript.pdf
	@echo "Build artifacts cleaned"
