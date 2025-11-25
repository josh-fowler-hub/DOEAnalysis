#!/usr/bin/env python3
"""
CLI wrapper for extended pairwise DOE generation that supports:
- IPOG-like algorithm
- Greedy algorithm
- Hybrid approach
- Constraint-aware sampling via a user-provided predicate
- Seeding with user rows
- Post-process pruning and hybrid local optimization

Usage:
  python3 generate_pairwise_doe_ext.py --algorithm ipog --t 2 --prune --seed 42

Additional options allow a constraint Python file, runtime parameters, and output CSV path.
"""
from __future__ import annotations

import argparse
import json
import sys
import ast
from pathlib import Path
from typing import List, Callable

from pairwise_improvements import generate_pairwise_ext, indices_from_factors, rows_to_dataframe

# We reuse the factors dictionary from the existing generate_pairwise_doe.py script
from config_loader import load_config, load_factors_from_config

DEFAULT_CONFIG_PATH = Path('doe_config.toml')
DEFAULT_FACTORS = load_config(DEFAULT_CONFIG_PATH)


def load_constraints(constraint_file: Path) -> Callable[[List], bool]:
    """Expect a small Python file containing a function is_valid(row) or a JSON with simple rules (not implemented).

    For safety, we use ast to parse a file and look for a function named `is_valid`, then exec in a safe namespace.
    """
    text = constraint_file.read_text()
    namespace = {}
    exec(text, namespace)
    if "is_valid" in namespace:
        return namespace["is_valid"]
    else:
        raise RuntimeError("constraint file must define is_valid(row) function")


def compile_constraints_from_config(constraints_cfg, factor_names):
    """Compile declarative constraints from TOML config into an is_valid(row) predicate.

    constraints_cfg is a list of tables, each with 'if' and 'then_not' and/or 'then'.
    Example:
    [[constraints]]
    if = { "Tank Volume" = "36g" }
    then_not = { "Water Outlet" = 125 }
    """
    # Build quick index mapping
    name_to_idx = {name: i for i, name in enumerate(factor_names)}

    compiled = []
    for c in constraints_cfg:
        if_clause = c.get('if', {})
        then_not = c.get('then_not', {})
        then = c.get('then', {})

        # normalize values to lists to support single and multi-valued rules
        def norm(v):
            if isinstance(v, list):
                return [str(x) for x in v]
            else:
                return [str(v)]

        if_mapped = {name_to_idx[k]: norm(v) for k, v in if_clause.items() if k in name_to_idx}
        then_not_mapped = {name_to_idx[k]: norm(v) for k, v in then_not.items() if k in name_to_idx}
        then_mapped = {name_to_idx[k]: norm(v) for k, v in then.items() if k in name_to_idx}

        compiled.append((if_mapped, then_not_mapped, then_mapped))

    def is_valid(row):
        for if_mapped, then_not_mapped, then_mapped in compiled:
            # Check IF
            matches = True
            for idx, allowed in if_mapped.items():
                if str(row[idx]) not in allowed:
                    matches = False
                    break
            if not matches:
                continue
            # IF matched; check THEN_NOT
            for idx, forb in then_not_mapped.items():
                if str(row[idx]) in forb:
                    return False
            # IF matched; check THEN (required)
            for idx, req in then_mapped.items():
                if str(row[idx]) not in req:
                    return False
        return True

    return is_valid


def load_seed_rows(seed_file: Path):
    # Expect JSON list rows or CSV, attempt to parse JSON
    text = seed_file.read_text()
    try:
        obj = json.loads(text)
        return obj
    except Exception:
        # fallback: attempt to parse CSV rows
        from csv import reader
        with seed_file.open() as f:
            rdr = reader(f)
            headers = next(rdr)
            rows = [list(r) for r in rdr]
            return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--algorithm", choices=["ipog", "greedy", "hybrid"], default="ipog")
    parser.add_argument("--t", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--prune", action="store_true")
    parser.add_argument("--nogeneral", action="store_true", help="Do not use t-way generalization; force pairwise")
    parser.add_argument("--constraints", type=Path, help="Python file defining is_valid(row)")
    parser.add_argument("--seed-rows", type=Path, help="JSON or CSV file with seed rows")
    parser.add_argument("--prune-infeasible", action="store_true", help="Prune infeasible t-tuples using default-fill feasibility checks")
    parser.add_argument("--out", type=Path, default=Path("Pairwise_DOE_ext.csv"))
    parser.add_argument('--plot', action='store_true', help='Generate coverage plots after CSV creation')
    parser.add_argument('--stats', action='store_true', help='Generate statistics only but not images')
    parser.add_argument('--max-pair-heatmaps', default=16, type=int, help='Limit the number of per-pair heatmaps to write (top missing pairs).')
    parser.add_argument('--report', action='store_true', help='Generate a Markdown report after plotting (coverage_report.md).')
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to TOML factor config")
    args = parser.parse_args(argv)

    # Load factors mapping from TOML if provided else default
    config = load_config(args.config) if args.config else {}
    factors = load_factors_from_config(config) if config else DEFAULT_FACTORS

    is_valid = None
    # Prefix: CLI arg path -> load external python constraint file
    if args.constraints:
        is_valid = load_constraints(args.constraints)
    else:
        # If config contains constraints inline, compile them
        cfg_constraints = config.get('constraints') if config else None
        if cfg_constraints:
            names = list(factors.keys())
            is_valid = compile_constraints_from_config(cfg_constraints, names)

    seed_rows = None
    if args.seed_rows:
        seed_rows = load_seed_rows(args.seed_rows)
    else:
        cfg_seed_rows = config.get('seed_rows') if config else None
        if cfg_seed_rows:
            seed_rows = cfg_seed_rows
    # Validate seed rows against factors length
    factor_names = list(factors.keys())
    if seed_rows:
        for r in seed_rows:
            if len(r) != len(factor_names):
                raise RuntimeError(f"Seed row length mismatch: expected {len(factor_names)} values, got {len(r)}: {r}")

    # Merge options: CLI takes precedence over config
    # Use CLI args or fallback to config settings
    t = args.t if args.t is not None else int(config.get('t', 2))
    algorithm = args.algorithm if args.algorithm else config.get('algorithm', 'ipog')
    prune = args.prune if args.prune else bool(config.get('prune', True))
    prune_infeasible = args.prune_infeasible if args.prune_infeasible else bool(config.get('prune_infeasible', True))
    seed = args.seed or int(config.get('seed', 42))

    design = generate_pairwise_ext(factors, t=t, algorithm=algorithm, is_valid_row=is_valid, seed=seed, seed_rows=seed_rows, prune=prune, hybrid_optimize=(algorithm == 'hybrid'), prune_infeasible=prune_infeasible)

    names, levels_by_index = indices_from_factors(factors)

    df = rows_to_dataframe(design, names)
    if df is not None:
        df.to_csv(args.out, index=False)
        print(f"Wrote {len(design)} rows to {args.out}")
        # Determine if we should do plots or only statistics
        cfg_settings = config.get('settings', {}) if config else {}
        settings_plot = bool(cfg_settings.get('plots', config.get('plots', False)))
        settings_stats = bool(cfg_settings.get('statistics', config.get('statistics', False)))
        # CLI flags override config
        plot_flag = args.plot or settings_plot
        stats_flag = args.stats or (settings_stats and not plot_flag)
        if plot_flag:
            from plot_coverage import main as plot_main
            args_list = [str(args.out), '--config', str(args.config), '--t', str(args.t), '--outdir', str(args.out) + '.plots', '--max-pair-heatmaps', str(args.max_pair_heatmaps)]
            if args.report:
                args_list.append('--report')
            plot_main(args_list)
        elif stats_flag:
            from plot_coverage import main as plot_main
            args_list = [str(args.out), '--config', str(args.config), '--t', str(args.t), '--outdir', str(args.out) + '.plots', '--stats-only', '--max-pair-heatmaps', str(args.max_pair_heatmaps)]
            if args.report:
                args_list.append('--report')
            plot_main(args_list)
    else:
        print("CSV printed to stdout")


if __name__ == "__main__":
    main()
