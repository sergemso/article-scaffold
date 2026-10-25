#!/bin/sh
# Tools the template's PDF build and the tests that run it need: TeX Live and pandoc.
set -e
sudo apt-get update
sudo apt-get install -y --no-install-recommends pandoc latexmk biber lmodern \
  texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
  texlive-science texlive-bibtex-extra texlive-publishers
