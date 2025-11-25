#!/usr/bin/env python3
"""
Validate a CSV DOE (t-way) to ensure all t-way tuples are present.

Usage:
    python3 validate_pairwise_doe.py Pairwise_DOE.csv --t 2
"""
from __future__ import annotations

import argparse
import pandas as pd
from itertools import combinations


def validate(df, t: int = 2):
    factor_names = df.columns.tolist()
    levels_by_factor = {i: df[factor].unique().tolist() for i, factor in enumerate(factor_names)}
    target_pairs = set()
    for idxs in combinations(range(len(factor_names)), t):
        for product in __import__('itertools').product(*(levels_by_factor[i] for i in idxs)):
            tup = tuple((i, str(product[j])) for j, i in enumerate(idxs))
            target_pairs.add(tup)
    present_pairs = set()
    for _, row in df.iterrows():
        for idxs in combinations(range(len(factor_names)), t):
            tup = tuple((i, str(row[i])) for i in idxs)
            present_pairs.add(tup)
    missing = target_pairs - present_pairs
    return missing


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('csv')
    p.add_argument('--t', type=int, default=2)
    args = p.parse_args(argv)
    df = pd.read_csv(args.csv)
    miss = validate(df, args.t)
    if miss:
        print(f"Missing {len(miss)} t-tuples. Examples:")
        for m in list(miss)[:10]:
            print(m)
    else:
        print("All t-tuples covered!")


if __name__ == '__main__':
    main()
