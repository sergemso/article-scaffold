# `data/`

Input data for the empirical analysis pipeline.

The committed fixture is deliberately tiny and is only a starting point:

```text
data/raw/observations.csv   # group,value
data/checksums.sha256       # SHA-256 of every tracked input
```

`make analysis` verifies the checksums before reading anything. If you edit or
replace an input, update the checksum deliberately, for example from the
repository root:

```bash
sha256sum data/raw/observations.csv > data/checksums.sha256
```

Do not edit generated files under `paper/figures/` or `paper/tables/` by hand;
regenerate them with `make analysis`. The analysis is standard-library-only by
default, so it runs in a clean checkout without installing scientific Python.
