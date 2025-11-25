#!/usr/bin/env python3
"""
Plot coverage statistics for a DOE CSV file.

Usage:
  python3 plot_coverage.py Pairwise_DOE.csv --config doe_config.toml --t 2 --outdir ./plots --show

Outputs:
- coverage_progress.png   : coverage fraction vs rows
- pair_freq_hist.png     : histogram of pair frequencies (how many times each pair appears)
- coverage_fraction_pie.png : pie chart showing overall covered vs missing tuples
- pair_coverage_matrix.png : heatmap matrix of coverage % for each factor pair
- heatmap_i_j.png         : per-pair level vs level heatmap of counts (for top missing pairs)
- top_missing_pairs_bar.png : bar chart of top missing pairs by #missing combos
- coverage_summary.txt   : text summary of coverage stats

The script requires matplotlib and pandas; use `pip install matplotlib pandas` if missing.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional
import math
import datetime
import statistics
import numpy as np

import matplotlib.pyplot as plt
import pandas as pd

from config_loader import load_config, load_factors_from_config
from pairwise_improvements import all_t_tuples, row_to_t_tuples


def compute_progression(df: pd.DataFrame, levels_by_index: list[list], t: int):
    rows = df.values.tolist()
    required = set(all_t_tuples(levels_by_index, t))
    present = set()
    progression = []
    pair_count = {}

    for idx, row in enumerate(rows, start=1):
        row_tuples = row_to_t_tuples(row, t)
        # update pair_count
        for p in row_tuples:
            pair_count[p] = pair_count.get(p, 0) + 1
        present.update(row_tuples)
        progression.append(len(present))

    missing = required - present
    return progression, pair_count, missing, required


def compute_pair_matrices(df: pd.DataFrame, levels_by_index: list[list]):
    """
    For each pair of factors (i, j), compute a counts matrix of shape (len(levels_i), len(levels_j)).
    Returns dict keyed by (i, j) -> numpy array of counts, plus a mapping of factor names to levels indices.
    """
    rows = df.values.tolist()
    n = len(levels_by_index)
    matrices = {}
    for i in range(n):
        for j in range(i + 1, n):
            li = levels_by_index[i]
            lj = levels_by_index[j]
            mat = np.zeros((len(li), len(lj)), dtype=int)
            matrices[(i, j)] = mat

    # create level index mapping per factor
    level_index = [ {v: k for k, v in enumerate(levels)} for levels in levels_by_index ]

    for row in rows:
        for i in range(n):
            for j in range(i + 1, n):
                vi = row[i]
                vj = row[j]
                # Some values may not be in level_index (e.g., NaN); skip if not found
                idx_i = level_index[i].get(vi)
                idx_j = level_index[j].get(vj)
                if idx_i is not None and idx_j is not None:
                    matrices[(i, j)][idx_i, idx_j] += 1

    return matrices


def compute_pair_coverage_stats(df: pd.DataFrame, levels_by_index: list[list]):
    """Return a dict of coverage % per factor pair (i,j) and set of missing combos per pair."""
    n = len(levels_by_index)
    covered_by_pair = {}
    missing_by_pair = {}
    total_by_pair = {}

    # build set of observed combos per pair
    rows = df.values.tolist()
    for i in range(n):
        for j in range(i + 1, n):
            observed = set()
            for row in rows:
                vi = row[i]
                vj = row[j]
                observed.add((vi, vj))
            total = len(levels_by_index[i]) * len(levels_by_index[j])
            covered = len([1 for combo in observed if combo[0] in levels_by_index[i] and combo[1] in levels_by_index[j]])
            covered_by_pair[(i, j)] = covered
            total_by_pair[(i, j)] = total
            # compute missing combos set
            all_pairs = set((a, b) for a in levels_by_index[i] for b in levels_by_index[j])
            missing = all_pairs - observed
            missing_by_pair[(i, j)] = missing

    coverage_pct = {k: 100.0 * covered_by_pair[k] / total_by_pair[k] for k in total_by_pair}
    return coverage_pct, covered_by_pair, total_by_pair, missing_by_pair


def compute_pair_count_stats(pair_count: dict):
    """Return summary statistics for pair_count values: mean/median/min/max/std/percentiles."""
    if not pair_count:
        return {}
    values = list(pair_count.values())
    stats = {}
    stats['count'] = len(values)
    stats['min'] = min(values)
    stats['max'] = max(values)
    stats['mean'] = statistics.mean(values)
    try:
        stats['median'] = statistics.median(values)
    except Exception:
        stats['median'] = 0
    try:
        stats['stdev'] = statistics.pstdev(values)
    except Exception:
        stats['stdev'] = 0.0
    # percentiles
    stats['p25'] = float(np.percentile(values, 25))
    stats['p50'] = float(np.percentile(values, 50))
    stats['p75'] = float(np.percentile(values, 75))
    stats['p90'] = float(np.percentile(values, 90))
    stats['p95'] = float(np.percentile(values, 95))
    return stats


def compute_factor_level_coverage(df: pd.DataFrame, levels_by_index: list[list], factor_names: list[str]):
    """Return a dict mapping factor name to (observed_count, total_count, percent)."""
    result = {}
    for i, fname in enumerate(factor_names):
        observed = set(df.iloc[:, i].dropna().unique().tolist())
        total = len(levels_by_index[i])
        result[fname] = (len(observed), total, 100.0 * len(observed) / total if total > 0 else 0.0)
    return result


def pretty_tuple(tup, factor_names=None):
    """Convert tuple-of-(idx,value) pairs into a human-friendly string."""
    if factor_names is None:
        return json.dumps(tup)
    parts = []
    for idx, val in tup:
        if 0 <= idx < len(factor_names):
            parts.append(f'{factor_names[idx]}={val}')
        else:
            parts.append(f'idx{idx}={val}')
    return ', '.join(parts)


def coverage_threshold_rows(progression, required_count, thresholds=[0.25, 0.5, 0.75, 0.9, 0.95, 1.0]):
    """Return dict mapping threshold fraction->row index where coverage first reaches that fraction (or None)."""
    rows_for_threshold = {}
    for thr in thresholds:
        target = math.ceil(thr * required_count)
        idx = next((i + 1 for i, covered in enumerate(progression) if covered >= target), None)
        rows_for_threshold[thr] = idx
    return rows_for_threshold


def plot_and_save(progression, pair_count, missing, required, outdir: str | Path, title='DOE Coverage', stats_only: bool = False,
                  df: Optional[pd.DataFrame] = None, factor_names: Optional[list[str]] = None,
                  levels_by_index: Optional[list[list]] = None, max_pair_heatmaps: int = 16, t: int = 2, report: bool = False):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # coverage progression
    x = list(range(1, len(progression) + 1))
    y = [p / len(required) for p in progression]

    plt.figure(figsize=(8, 4))
    plt.plot(x, y, marker='o')
    plt.xlabel('Rows (cumulative)')
    plt.ylabel('Coverage fraction')
    plt.title(f'{title}: Coverage progress (t-way)')
    plt.grid(True)
    plt.tight_layout()
    p1 = outdir / 'coverage_progress.png'
    if not stats_only:
        plt.savefig(p1)
        plt.close()

    # incremental coverage gain per row
    gains = []
    if progression:
        gains = [progression[0]] + [progression[i] - progression[i - 1] for i in range(1, len(progression))]
    if not stats_only and gains:
        plt.figure(figsize=(8, 3))
        plt.bar(range(len(gains)), gains)
        plt.xlabel('Row index')
        plt.ylabel('New t-tuples covered by row')
        plt.title(f'{title}: New tuples per added row')
        plt.tight_layout()
        p_gain = outdir / 'coverage_gain_per_row.png'
        plt.savefig(p_gain)
        plt.close()

    # pair frequency histogram
    freq_values = list(pair_count.values())
    plt.figure(figsize=(8, 4))
    plt.hist(freq_values, bins=range(1, max(freq_values) + 2), log=True)
    plt.xlabel('Pair count (how many rows include the pair)')
    plt.ylabel('Number of pairs (log scale)')
    plt.title(f'{title}: Pair frequency histogram')
    plt.tight_layout()
    p2 = outdir / 'pair_freq_hist.png'
    if not stats_only:
        plt.savefig(p2)
        plt.close()

    # Now create an overall pie/percentage chart of coverage
    if not stats_only:
        plt.figure(figsize=(6, 6))
        covered = len(required) - len(missing)
        remaining = len(missing)
        plt.pie([covered, remaining], labels=[f'Covered ({covered})', f'Missing ({remaining})'], autopct='%1.1f%%', colors=['#2ca02c', '#d62728'])
        plt.title(f'{title}: Overall coverage fraction')
        p3 = outdir / 'coverage_fraction_pie.png'
        plt.tight_layout()
        plt.savefig(p3)
        plt.close()
    else:
        p3 = None

    # Save textual summary
    summary_file = outdir / 'coverage_summary.txt'
    with summary_file.open('w', encoding='utf-8') as fh:
        fh.write(f'Total required tuples: {len(required)}\n')
        fh.write(f'Total covered tuples: {len(required) - len(missing)}\n')
        fh.write(f'Missing tuples: {len(missing)}\n')
        pct = 100.0 * (len(required) - len(missing)) / len(required) if len(required) > 0 else 0.0
        fh.write(f'Overall coverage percent: {pct:.2f}%\n')
        # Rows info
        if df is not None:
            fh.write(f'Total rows in CSV: {len(df)}\n')
            fh.write(f'Unique rows: {len(df.drop_duplicates())}\n')
        fh.write('\n')
        fh.write('\nExamples of missing tuples (first 20):\n')
        for p in list(missing)[:20]:
            fh.write(json.dumps(p) + '\n')

        # Additional stats
        fh.write('\nPair frequency statistics (per t-way tuple counts):\n')
        pair_stats = compute_pair_count_stats(pair_count)
        if pair_stats:
            fh.write(json.dumps(pair_stats, indent=2) + '\n')
            # Top/Bottom pairs by occurrence
            items = sorted(pair_count.items(), key=lambda kv: kv[1])
            fh.write('\nLeast frequent sample (first 10):\n')
            for k, v in items[:10]:
                fh.write(f'{pretty_tuple(list(k), factor_names)} -> {v}\n')
            fh.write('\nMost frequent sample (first 10):\n')
            for k, v in items[-10:]:
                fh.write(f'{pretty_tuple(list(k), factor_names)} -> {v}\n')
        else:
            fh.write('No pair frequency data available (t>2?)\n')

        # Per-factor level coverage
        if df is not None and factor_names is not None and levels_by_index is not None:
            fh.write('\nPer-factor level coverage:\n')
            factor_cov = compute_factor_level_coverage(df, levels_by_index, factor_names)
            for fname, (obs, tot, pctf) in factor_cov.items():
                fh.write(f'  {fname}: {obs}/{tot} levels observed ({pctf:.1f}%)\n')
            # incremental gain stats
            if gains:
                fh.write('\nPer-row new-tuple gains statistics:')
                try:
                    fh.write(f"\n  mean: {statistics.mean(gains):.2f}, median: {statistics.median(gains):.2f}, min: {min(gains)}, max: {max(gains)}\n")
                except Exception:
                    pass

    # Return the main plots and list of generated files (could be None for stats-only)
    files = [summary_file]
    if not stats_only:
        files.extend([p1, p2, p3])

    # Extra pair visualizations (heatmaps and coverage matrix)
    extra_files = []
    # Only compute pair-related heatmaps when t == 2 (pairwise)
    # For t==2, compute and optionally render pairwise matrices; in stats-only mode we'll still compute CSV and textual summary
    if t == 2 and df is not None and levels_by_index is not None and factor_names is not None:
        # Compute matrices and stats
        matrices = compute_pair_matrices(df, levels_by_index)
        coverage_pct, covered_by_pair, total_by_pair, missing_by_pair = compute_pair_coverage_stats(df, levels_by_index)

        # Coverage matrix across factor pairs
        n = len(levels_by_index)
        cov_matrix = np.full((n, n), np.nan, dtype=float)
        for (i, j), pct in coverage_pct.items():
            cov_matrix[i, j] = pct
            cov_matrix[j, i] = pct

        if not stats_only:
            plt.figure(figsize=(max(6, n), max(6, n)))
        im = plt.imshow(cov_matrix, vmin=0.0, vmax=100.0, cmap='viridis', interpolation='nearest')
        plt.colorbar(im, label='Coverage %')
        plt.title(f'{title}: Factor-pair coverage matrix (%)')
        plt.xticks(range(n), factor_names, rotation=90)
        plt.yticks(range(n), factor_names)
        plt.tight_layout()
        p_cov = outdir / 'pair_coverage_matrix.png'
        if not stats_only:
            plt.savefig(p_cov)
            plt.close()
            extra_files.append(p_cov)
        extra_files.append(p_cov)

        # Per-pair heatmaps for top-k missing pairs
        # Rank pairs by fraction missing (descending)
        missing_frac_pairs = sorted(missing_by_pair.items(), key=lambda kv: len(kv[1])/ (len(levels_by_index[kv[0][0]]) * len(levels_by_index[kv[0][1]])), reverse=True)
        top_pairs = missing_frac_pairs[:max_pair_heatmaps]
        for (i_j, missing_set) in top_pairs:
            i, j = i_j
            mat = matrices[(i, j)]
            fig, ax = plt.subplots(figsize=(6, 5))
            # Display counts; annotate missing (0) as white to highlight missing combos
            im2 = ax.imshow(mat, cmap='plasma', interpolation='nearest')
            cbar = fig.colorbar(im2, ax=ax)
            cbar.set_label('Count of rows containing (level_i, level_j)')
            ax.set_xticks(range(len(levels_by_index[j])))
            ax.set_xticklabels(levels_by_index[j], rotation=90)
            ax.set_yticks(range(len(levels_by_index[i])))
            ax.set_yticklabels(levels_by_index[i])
            ax.set_xlabel(factor_names[j])
            ax.set_ylabel(factor_names[i])
            ax.set_title(f'{title}: Heatmap for {factor_names[i]} x {factor_names[j]}')
            plt.tight_layout()
            fname = outdir / f'heatmap_{i}_{j}.png'
            if not stats_only:
                plt.savefig(fname)
                plt.close()
                extra_files.append(fname)

        # Bar chart of top missing pairs (# missing combos)
        pair_missing_counts = [(f'{factor_names[i]} | {factor_names[j]}', len(missing_set)) for (i, j), missing_set in missing_by_pair.items()]
        pair_missing_counts.sort(key=lambda x: x[1], reverse=True)
        top_missing = pair_missing_counts[:20]
        if top_missing:
            names, counts = zip(*top_missing)
            if not stats_only:
                plt.figure(figsize=(10, 6))
                plt.barh(names, counts)
                plt.xlabel('# missing combos for pair')
                plt.title(f'{title}: Top missing pairs (count of level combinations missing)')
                plt.gca().invert_yaxis()
                plt.tight_layout()
                p_bar = outdir / 'top_missing_pairs_bar.png'
                plt.savefig(p_bar)
                plt.close()
                extra_files.append(p_bar)

        # Append per-pair textual coverage stats to the summary file for readability
        if 'coverage_pct' in locals():
            with summary_file.open('a', encoding='utf-8') as fh:
                fh.write('\nPer-pair coverage (sorted ascending):\n')
                for (i, j), pct in sorted(coverage_pct.items(), key=lambda kv: kv[1]):
                    nm = f'{factor_names[i]} | {factor_names[j]}'
                    fh.write(f'  {nm}: {pct:.1f}% ({covered_by_pair[(i,j)]}/{total_by_pair[(i, j)]})\n')
                # Top missing pairs
                pair_missing_counts = [(f'{factor_names[i]} | {factor_names[j]}', len(missing_set)) for (i, j), missing_set in missing_by_pair.items()]
                pair_missing_counts.sort(key=lambda x: x[1], reverse=True)
                fh.write('\nTop missing pairs (by # missing combos):\n')
                for name, cnt in pair_missing_counts[:20]:
                    fh.write(f'  {name}: {cnt} missing combos\n')

        # Write per-pair coverage CSV (helpful for programmatic analysis)
        csv_path = outdir / 'coverage_stats.csv'
        with csv_path.open('w', encoding='utf-8') as cf:
            cf.write('factor_i,factor_j,levels_i,levels_j,covered,total,coverage_pct,missing_count\n')
            for (i, j), total in total_by_pair.items():
                covered = covered_by_pair[(i, j)]
                missing_cnt = len(missing_by_pair[(i, j)])
                fname_i = factor_names[i]
                fname_j = factor_names[j]
                cf.write(f'"{fname_i}","{fname_j}",{len(levels_by_index[i])},{len(levels_by_index[j])},{covered},{total},{100.0*covered/total if total else 0.0},{missing_cnt}\n')
        extra_files.append(csv_path)

    files.extend(extra_files)
    # Optionally generate a markdown report that assembles the figures and statistics
    if report:
        report_path = outdir / 'coverage_report.md'
        with report_path.open('w', encoding='utf-8') as rfh:
            rfh.write(f'# DOE Coverage Report for {title}\n')
            rfh.write(f'Generated: {datetime.datetime.now().isoformat()}\n\n')
            rfh.write('## Dataset summary\n')
            rfh.write(f'- Rows: {len(df) if df is not None else "n/a"}\n')
            rfh.write(f'- Unique rows: {len(df.drop_duplicates()) if df is not None else "n/a"}\n')
            rfh.write(f'- Required t-tuples: {len(required)}\n')
            rfh.write(f'- Covered t-tuples: {len(required)-len(missing)}\n')
            rfh.write(f'- Missing t-tuples: {len(missing)}\n')
            rfh.write('\n')
            rfh.write('\n### About this dataset\n')
            rfh.write('This report summarizes coverage of t-way combinations (t-tuples) in the dataset. ')
            rfh.write('The per-factor coverage shows how many levels appear in the CSV for each factor; the per-pair table shows coverage percentage for each pair of factors.\n\n')
            # include per-factor coverage table
            if df is not None and factor_names is not None and levels_by_index is not None:
                rfh.write('## Per-factor coverage\n')
                rfh.write('| Factor | Observed levels | Total levels | Percent observed |\n')
                rfh.write('|---|---:|---:|---:|\n')
                factor_cov = compute_factor_level_coverage(df, levels_by_index, factor_names)
                for fname, (obs, tot, pctf) in factor_cov.items():
                    rfh.write(f'| {fname} | {obs} | {tot} | {pctf:.1f}% |\n')
                rfh.write('\n')

            # Add per-pair coverage table
            if t == 2 and 'coverage_pct' in locals():
                rfh.write('## Per-pair coverage table\n')
                rfh.write('| Factor i | Factor j | Covered | Total | Coverage % | Missing combos |\n')
                rfh.write('|---|---|---:|---:|---:|---:|\n')
                for (i, j), total in total_by_pair.items():
                    covered = covered_by_pair[(i, j)]
                    missing_cnt = len(missing_by_pair[(i, j)])
                    rfh.write(f'| {factor_names[i]} | {factor_names[j]} | {covered} | {total} | {100.0*covered/total:.1f}% | {missing_cnt} |\n')
                rfh.write('\n')

            # Insert plots and quick references if they were generated
            rfh.write('## Plots\n')
            rfh.write('The plots below show: (1) progressive coverage vs rows added; (2) the marginal contribution of each row in terms of new tuples covered; (3) pair frequency histogram which shows how many rows each pair appears in; (4) a coverage matrix that maps factor-pairs to percent coverage; and (5) a bar chart of the top missing pairs.\n')
            for name in ['coverage_progress.png', 'coverage_gain_per_row.png', 'coverage_fraction_pie.png', 'pair_freq_hist.png', 'pair_coverage_matrix.png', 'top_missing_pairs_bar.png']:
                p = outdir / name
                if p.exists():
                    rfh.write(f'![{name}]({p.name})\n')
            # Inline heatmaps: include up to 8 by default
            heatmaps = sorted([f for f in extra_files if f.name.startswith('heatmap_')])[:8]
            if heatmaps:
                rfh.write('\n### Sample per-pair heatmaps\n')
                for h in heatmaps:
                    rfh.write(f'![{h.name}]({h.name})\n')

            # Observations & thresholds
            rfh.write('\n## Observations and thresholds\n')
            thr_rows = coverage_threshold_rows(progression, len(required))
            rfh.write('| Threshold | First row reached |\n')
            rfh.write('|---:|---:|\n')
            for thr, ridx in thr_rows.items():
                thr_pct = int(thr * 100)
                rfh.write(f'| {thr_pct}% | {ridx or "not reached"} |\n')

            # Top missing pairs list
            if t == 2 and 'missing_by_pair' in locals():
                pair_missing_counts = [(f'{factor_names[i]} | {factor_names[j]}', len(missing_set)) for (i, j), missing_set in missing_by_pair.items()]
                pair_missing_counts.sort(key=lambda x: x[1], reverse=True)
                rfh.write('\n### Top missing pairs (by missing combos)\n')
                for name, cnt in pair_missing_counts[:20]:
                    rfh.write(f'- {name}: {cnt} missing combos\n')

        files.append(report_path)
    return files


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('csv')
    p.add_argument('--config', default=None, help='TOML config file to resolve factor ordering')
    p.add_argument('--t', type=int, default=2)
    p.add_argument('--outdir', default='plots')
    p.add_argument('--report', action='store_true', help='Generate a Markdown report `coverage_report.md` in the outdir. CLI flag takes precedence over config settings.')
    p.add_argument('--max-pair-heatmaps', default=16, type=int, help='Limit the number of per-pair heatmaps to write (top missing pairs).')
    p.add_argument('--stats-only', action='store_true', help='Only compute and save statistics; skip plots')
    p.add_argument('--show', action='store_true')
    args = p.parse_args(argv)

    df = pd.read_csv(args.csv)
    # If config provided, use factor order from config; otherwise use column ordering from CSV
    if args.config:
        cfg = load_config(args.config)
        factors = load_factors_from_config(cfg)
        factor_names = list(factors.keys())
        levels_by_index = [factors[name] for name in factor_names]
    else:
        factor_names = df.columns.tolist()
        levels_by_index = [sorted(df[col].dropna().unique().tolist()) for col in factor_names]

    progression, pair_count, missing, required = compute_progression(df, levels_by_index, args.t)
    files = plot_and_save(progression, pair_count, missing, required, args.outdir, title=args.csv, stats_only=args.stats_only,
                          df=df, factor_names=factor_names, levels_by_index=levels_by_index, max_pair_heatmaps=args.max_pair_heatmaps, t=args.t, report=args.report)

    # Extract some helpful defaults for printouts
    summary_files = [f for f in files if f.name == 'coverage_summary.txt']
    p1_files = [f for f in files if f.name == 'coverage_progress.png']
    p2_files = [f for f in files if f.name == 'pair_freq_hist.png']

    if not args.stats_only and p1_files:
        print('Plotted coverage progression to', p1_files[0])
        print('Plotted pair frequency histogram to', p2_files[0])
    if summary_files:
        print('Coverage summary saved to', summary_files[0])
    report_files = [f for f in files if f.name == 'coverage_report.md']
    if report_files:
        print('Coverage report (markdown) saved to', report_files[0])
    if args.show and p1_files:
        from PIL import Image
        im = Image.open(p1_files[0])
        im.show()


if __name__ == '__main__':
    main()
