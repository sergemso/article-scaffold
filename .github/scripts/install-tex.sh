#!/bin/sh
# TeX Live packages the template's PDF build and the tests that run it need.
set -e
sudo apt-get update
sudo apt-get install -y --no-install-recommends latexmk biber lmodern \
  texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
  texlive-science texlive-bibtex-extra texlive-publishers
