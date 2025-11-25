#!/usr/bin/env python3
"""
Entrypoint wrapper that loads a TOML config and runs the selected DOE generator.

Usage:
  python3 generate_doe.py --config doe_config.toml

The TOML should include:
- [factors] (table of factor -> list levels)
- algorithm = "ipog" | "greedy" | "hybrid"
- t = 2
- out = "Pairwise_DOE.csv"
- prune = true/false
- prune_infeasible = true/false
- constraints = "constraints.py"
- seed_rows = "seed_rows.json"
- seed = 42
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from config_loader import load_config, load_factors_from_config
from pairwise_improvements import generate_pairwise_ext, rows_to_dataframe, indices_from_factors


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, default=Path('doe_config.toml'))
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    factors = load_factors_from_config(cfg)

    settings = cfg.get('settings', {})
    algorithm = settings.get('algorithm', cfg.get('algorithm', 'ipog'))
    t = int(settings.get('t', cfg.get('t', 2)))
    out = Path(settings.get('out', cfg.get('out', 'Pairwise_DOE.csv')))
    prune = bool(settings.get('prune', cfg.get('prune', True)))
    prune_infeasible = bool(settings.get('prune_infeasible', cfg.get('prune_infeasible', True)))
    seed_val = int(settings.get('seed', cfg.get('seed', 42)))
    constraints_path: Optional[Path] = settings.get('constraints', cfg.get('constraints'))
    seed_rows_path = settings.get('seed_rows', cfg.get('seed_rows'))

    is_valid = None
    if constraints_path and isinstance(constraints_path, str) and Path(constraints_path).exists():
        from generate_pairwise_doe_ext import load_constraints
        is_valid = load_constraints(Path(constraints_path))
    else:
        cfg_constraints = cfg.get('constraints')
        if cfg_constraints:
            from generate_pairwise_doe_ext import compile_constraints_from_config
            names = list(factors.keys())
            is_valid = compile_constraints_from_config(cfg_constraints, names)

    seed_rows = None
    if seed_rows_path:
        from generate_pairwise_doe_ext import load_seed_rows
        if isinstance(seed_rows_path, str) and Path(seed_rows_path).exists():
            seed_rows = load_seed_rows(Path(seed_rows_path))
        elif isinstance(seed_rows_path, list):
            seed_rows = seed_rows_path
        else:
            # Not a path or inline list; ignore
            seed_rows = None

    # Validate seed rows length when provided
    if seed_rows:
        for r in seed_rows:
            if len(r) != len(factors):
                raise RuntimeError(f"Seed row length mismatch: expected {len(factors)} values, got {len(r)}: {r}")

    design = generate_pairwise_ext(
        factors,
        t=t,
        algorithm=algorithm,
        is_valid_row=is_valid,
        seed=seed_val,
        seed_rows=seed_rows,
        prune=prune,
        hybrid_optimize=(algorithm == 'hybrid'),
        prune_infeasible=prune_infeasible,
    )

    names, _levels = indices_from_factors(factors)
    df = rows_to_dataframe(design, names)
    if df is not None:
        df.to_csv(out, index=False)
        print(f"Wrote {len(design)} rows to {out}")
        # optionally plot
        try:
            from plot_coverage import main as plot_main
            settings_plot = bool(settings.get('plots', cfg.get('plots', False)))
            settings_statistics = bool(settings.get('statistics', cfg.get('statistics', False)))
            if settings_plot:
                max_heatmap = int(settings.get('max_pair_heatmaps', 16))
                report_flag = settings.get('report', cfg.get('report', False))
                args_list = [str(out), '--config', str(args.config), '--t', str(t), '--outdir', str(out) + '.plots', '--max-pair-heatmaps', str(max_heatmap)]
                if report_flag:
                    args_list.append('--report')
                plot_main(args_list)
            elif settings_statistics:
                max_heatmap = int(settings.get('max_pair_heatmaps', 16))
                report_flag = settings.get('report', cfg.get('report', False))
                args_list = [str(out), '--config', str(args.config), '--t', str(t), '--outdir', str(out) + '.plots', '--stats-only', '--max-pair-heatmaps', str(max_heatmap)]
                if report_flag:
                    args_list.append('--report')
                plot_main(args_list)
        except Exception as exc:
            print('Plotting was requested but failed:', exc)
    else:
        # rows_to_dataframe already printed to stdout
        print(f"Generated rows: {len(design)}")


if __name__ == '__main__':
    main()
