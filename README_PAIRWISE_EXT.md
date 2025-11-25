# Pairwise DOE — Extended tools

This folder contains:

- `pairwise_improvements.py`: Implementation for IPOG-like algorithm, greedy and hybrid solvers, t-way support, pruning and optimization.
- `generate_pairwise_doe_ext.py`: CLI wrapper to run IPOG, greedy, or hybrid strategies with options for constraints, seeds, pruning, and t parameter.
- `validate_pairwise_doe.py`: CLI validator that checks a CSV DOE file covers all required t-way tuples.

## Usage examples

1. Run IPOG-like generator using a TOML config (recommended)

```bash
python3 generate_doe.py --config doe_config.toml
```

This will run the algorithm, respecting `settings` in the TOML (algorithm, t, prune, seed, etc), `factors` for the factors mapping, `constraints` for inline constraints and `seed_rows` for pre-seeded rows.

1. (Alternative) Run greedy generator or other algorithm using CLI options or TOML config

```bash
python3 generate_pairwise_doe_ext.py --algorithm greedy --t 2 --out Pairwise_DOE_greedy.csv
python3 validate_pairwise_doe.py Pairwise_DOE_greedy.csv --t 2
```


1. Run hybrid algorithm with constraints defined in the TOML or using a separate constraint file (legacy)

```bash
python3 generate_pairwise_doe_ext.py --algorithm hybrid --t 2 --constraints constraints.py --prune --out Pairwise_DOE_hybrid.csv
```

```bash
python3 generate_pairwise_doe_ext.py --algorithm hybrid --t 2 --constraints constraints.py --prune --out Pairwise_DOE_hybrid.csv
```

1. Generate a Markdown report summarizing coverage, tables and plots

```bash
# CLI: generate plots and create a markdown report
python3 generate_pairwise_doe_ext.py --config doe_config.toml --out Pairwise_DOE_report.csv --plot --report

# If you use the single entrypoint with TOML, set `settings.report = true` in `doe_config.toml` and `settings.plots = true`.
python3 generate_doe.py --config doe_config.toml
```
