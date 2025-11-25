#!/usr/bin/env python3
"""
Lightweight pairwise improvements module.
- IPOG-like incremental construction for t-way arrays (simplified)
- Constraint-aware generation (is_valid row predicate and is_feasible_pair)
- Post-process pruning (redundant row removal)
- Hybrid optimization step using local search / simulated annealing-style retries
- Basic validator for t-way coverage

This module is intentionally dependency-light (only uses Python stdlib and pandas optionally) and interoperates with the existing `generate_pairwise_doe.py` script.
"""
from __future__ import annotations

import itertools
import random
import time
from typing import Dict, List, Tuple, Callable, Optional, Set

try:
    import pandas as pd
except Exception:
    pd = None

Level = object
Factors = Dict[str, List[Level]]
Row = List[Level]


def indices_from_factors(factors: Factors) -> Tuple[List[str], List[List[Level]]]:
    names = list(factors.keys())
    levels = [factors[k] for k in names]
    return names, levels


# --- Utilities ---

def all_t_tuples(levels_by_index: List[List[Level]], t: int) -> Set[Tuple[Tuple[int, Level], ...]]:
    """Return a set of all required t-way tuples of (index, level) pairs.
    For t=2 this is pairs; for t>2 it's more complex.
    """
    k = len(levels_by_index)
    all_sets = set()
    for idxs in itertools.combinations(range(k), t):
        lvl_lists = [levels_by_index[i] for i in idxs]
        for product in itertools.product(*lvl_lists):
            tup = tuple((i, product[j]) for j, i in enumerate(idxs))
            all_sets.add(tup)
    return all_sets


def row_to_t_tuples(row: Row, t: int) -> Set[Tuple[Tuple[int, Level], ...]]:
    k = len(row)
    r = []
    for idxs in itertools.combinations(range(k), t):
        tup = tuple((i, row[i]) for i in idxs)
        r.append(tup)
    return set(r)


# --- Validator ---

def validate_coverage_rows(rows: List[Row], levels_by_index: List[List[Level]], t: int = 2) -> Tuple[bool, Set[Tuple[Tuple[int, Level], ...]]]:
    """Return (is_full_coverage, missing_set)
    missing_set is the set of t-tuples that are not covered.
    """
    required = all_t_tuples(levels_by_index, t)
    present = set()
    for row in rows:
        present.update(row_to_t_tuples(row, t))
    missing = required - present
    return (len(missing) == 0, missing)


# --- Pruning ---

def prune_redundant_rows(rows: List[Row], levels_by_index: List[List[Level]], t: int = 2) -> List[Row]:
    """Iteratively remove rows that are redundant (do not change coverage).
    This is a simple O(N^2 * combos) approach; it's fine for moderate N.
    """
    changed = True
    result = rows.copy()
    while changed:
        changed = False
        is_full, _ = validate_coverage_rows(result, levels_by_index, t)
        if not is_full:
            # We cannot assume it's valid before pruning
            break
        for idx in range(len(result)):
            temp = result[:idx] + result[idx + 1 :]
            ok, _ = validate_coverage_rows(temp, levels_by_index, t)
            if ok:
                # drop the row
                result = temp
                changed = True
                break
    return result


# --- Constraint aware helpers ---

def default_is_valid(row: Row) -> bool:
    return True


def is_feasible_pair(i: int, a: Level, j: int, b: Level, is_valid_row: Callable[[Row], bool], levels_by_index: List[List[Level]], default_fill=None) -> bool:
    """Check if a pair (i,a,j,b) can ever be part of a valid row by trying default fills.

    This is not exhaustive but a heuristic: fill other positions with default or first level values and call is_valid_row.
    """
    if default_fill is None:
        default_fill = [lvls[0] for lvls in levels_by_index]
    row = default_fill.copy()
    row[i] = a
    row[j] = b
    return is_valid_row(row)


# --- IPOG-like incremental construction (t-way) ---

def ipog_like(factors: Factors, t: int = 2, is_valid_row: Optional[Callable[[Row], bool]] = None, seed_rows: Optional[List[Row]] = None, prune_infeasible: bool = True) -> List[Row]:
    """A simplified IPOG-like construction for t-way covering arrays.

    This approach is not guaranteed minimal but tends to be more compact than naive greedy for many parameter sets.
    """
    if is_valid_row is None:
        is_valid_row = default_is_valid
    names, levels_by_index = indices_from_factors(factors)
    k = len(levels_by_index)

    # Start with full factorial of first t factors
    base_indices = list(range(min(t, k)))
    design = []
    for prod in itertools.product(*(levels_by_index[i] for i in base_indices)):
        row = [lvls[0] for lvls in levels_by_index]
        for i, val in zip(base_indices, prod):
            row[i] = val
        if is_valid_row(row):
            design.append(row)

    # Add seed rows if provided
    if seed_rows:
        # Prepend seeds to design so they are prioritized
        for sr in seed_rows:
            if is_valid_row(sr) and sr not in design:
                design.insert(0, sr)

    # Maintain required t-way tuples
    required = all_t_tuples(levels_by_index, t)
    if prune_infeasible:
        # Optionally, prune infeasible t-tuples by testing a default fill
        feasible_required = set()
        default_fill = [lvls[0] for lvls in levels_by_index]
        for tup in required:
            r = default_fill.copy()
            for i, val in tup:
                r[i] = val
            if is_valid_row(r):
                feasible_required.add(tup)
            else:
                # attempt a small random sample to check feasibility
                feasible = False
                for _ in range(20):
                    r2 = r.copy()
                    for i in range(k):
                        if i not in [ii for ii, _ in tup]:
                            r2[i] = random.choice(levels_by_index[i])
                    if is_valid_row(r2):
                        feasible = True
                        break
                if feasible:
                    feasible_required.add(tup)
        required = feasible_required
    # Optionally, prune infeasible t-tuples by testing a default fill
    feasible_required = set()
    default_fill = [lvls[0] for lvls in levels_by_index]
    for tup in required:
        r = default_fill.copy()
        for i, val in tup:
            r[i] = val
        if is_valid_row(r):
            feasible_required.add(tup)
        else:
            # attempt a small random sample to check feasibility
            feasible = False
            for _ in range(20):
                r2 = r.copy()
                for i in range(k):
                    if i not in [ii for ii, _ in tup]:
                        r2[i] = random.choice(levels_by_index[i])
                if is_valid_row(r2):
                    feasible = True
                    break
            if feasible:
                feasible_required.add(tup)
    required = feasible_required
    present = set()
    for r in design:
        present.update(row_to_t_tuples(r, t))

    # For each remaining factor beyond the base, extend design
    for new_idx in range(min(t, k), k):
        # target t-tuples that include new_idx
        relevant_required = set([tup for tup in required if any(i == new_idx for i, _ in tup)])
        missing = relevant_required - present
        if not missing:
            continue
        # Extend existing rows: try to set best level per row
        for ridx, row in enumerate(design):
            best_level = None
            best_gain = 0
            for level in levels_by_index[new_idx]:
                candidate = row.copy()
                candidate[new_idx] = level
                if not is_valid_row(candidate):
                    continue
                gain = len(row_to_t_tuples(candidate, t) & missing)
                if gain > best_gain:
                    best_gain = gain
                    best_level = level
            if best_level is not None:
                design[ridx][new_idx] = best_level
                present.update(row_to_t_tuples(design[ridx], t))
                missing = relevant_required - present
                if not missing:
                    break
        # If still missing, add new rows to cover them
        while missing:
            tup = missing.pop()
            # We will try to create a row that includes this tuple; fill others with default (first) values and validate
            new_row = [lvls[0] for lvls in levels_by_index]
            for i, val in tup:
                new_row[i] = val
            # If it's invalid, try random fills for the other positions until we find a valid row
            trials = 0
            found = False
            while not is_valid_row(new_row) and trials < 1000:
                for i in range(k):
                    if i not in [ii for ii, _ in tup]:
                        new_row[i] = random.choice(levels_by_index[i])
                trials += 1
            if is_valid_row(new_row):
                design.append(new_row)
                present.update(row_to_t_tuples(new_row, t))
                missing = relevant_required - present
            else:
                # Could not find a valid row for this tuple; skip it (assume it's infeasible with our is_valid predicate)
                pass
    # Final cleaning: attempt to cover missing t-tuples across design
    full_ok, missing = validate_coverage_rows(design, levels_by_index, t)
    if not full_ok:
        # We can try further steps: greedy fill for missing t-tuples
        print(f"IPOG initial design misses {len(missing)} t-tuples; attempting greedy fillers")
        # Construct rows to cover missing
        missing = set(missing)
        while missing:
            tup = missing.pop()
            new_row = [lvls[0] for lvls in levels_by_index]
            for i, val in tup:
                new_row[i] = val
            trials = 0
            while not is_valid_row(new_row) and trials < 1000:
                for i in range(k):
                    if i not in [ii for ii, _ in tup]:
                        new_row[i] = random.choice(levels_by_index[i])
                trials += 1
            if is_valid_row(new_row):
                design.append(new_row)
                present.update(row_to_t_tuples(new_row, t))
                missing = set([m for m in missing if m not in present])
            else:
                # If we can't find a valid row for a missing tupple, skip it
                pass
    return design


# --- Greedy + Hybrid optimizer ---

def greedy_pairwise(factors: Factors, t: int = 2, is_valid_row: Optional[Callable[[Row], bool]] = None, seed: int = 42, max_tries: int = 400) -> List[Row]:
    # Simple adaptation of existing greedy algorithm to t-way
    random.seed(seed)
    if is_valid_row is None:
        is_valid_row = default_is_valid
    names, levels_by_index = indices_from_factors(factors)
    k = len(levels_by_index)
    pair_indices = list(itertools.combinations(range(k), t))
    uncovered = set(all_t_tuples(levels_by_index, t))
    design: List[Row] = []
    steps = 0
    MAX_STEPS = 50000
    while uncovered and steps < MAX_STEPS:
        steps += 1
        best_row = None
        best_cov = -1
        best_remove = None
        for _ in range(max_tries):
            candidate = [random.choice(lvls) for lvls in levels_by_index]
            if not is_valid_row(candidate):
                continue
            cov = len(row_to_t_tuples(candidate, t) & uncovered)
            if cov > best_cov:
                best_cov = cov
                best_row = candidate
                best_remove = row_to_t_tuples(candidate, t) & uncovered
                if cov > 0 and cov >= 0.95 * len(pair_indices):
                    break
        if best_row is None:
            # fallback: try to construct rows for remaining missing tuples
            tup = next(iter(uncovered))
            r = [lvls[0] for lvls in levels_by_index]
            for i, val in tup:
                r[i] = val
            # try randomizing other fields
            found = False
            trials = 0
            while not is_valid_row(r) and trials < 1000:
                r = [random.choice(lvls) if i not in [ii for ii, _ in tup] else val for i, lvls in enumerate(levels_by_index)]
                trials += 1
            if is_valid_row(r):
                best_row = r
                best_remove = row_to_t_tuples(r, t) & uncovered
            else:
                # can't find a valid candidate; break to avoid infinite loop
                break
        design.append(best_row)
        for rr in best_remove:
            uncovered.discard(rr)
    return design


def simulated_annealing_shrink(design: List[Row], levels_by_index: List[List[Level]], t: int = 2, time_limit: int = 20) -> List[Row]:
    """Basic local search to remove rows or adjust rows to try to reduce the design size.
    - Try to remove a random row; if coverage remains intact, keep removal.
    - Try to mutate rows to better cover pairs and remove other rows.
    This is a lightweight simulated annealing inspired approach (not a full implementation).
    """
    start = time.time()
    current = design.copy()
    best = current
    while time.time() - start < time_limit:
        # Try to remove a random row
        if len(current) <= 1:
            break
        idx = random.randrange(len(current))
        candidate = current[:idx] + current[idx + 1 :]
        ok, _ = validate_coverage_rows(candidate, levels_by_index, t)
        if ok:
            current = candidate
            if len(current) < len(best):
                best = current
            continue
        # Try to mutate a row by changing random levels (local perturbation)
        idx = random.randrange(len(current))
        mutated = current.copy()
        row = mutated[idx].copy()
        # pick a factor index to mutate; use the canonical factor count k
        i = random.randrange(len(levels_by_index))
        row[i] = random.choice(levels_by_index[i])
        mutated[idx] = row
        ok, _ = validate_coverage_rows(mutated, levels_by_index, t)
        if ok and len(mutated) < len(best):
            best = mutated
            current = mutated
    return best


# --- High level runner / hybrid ---

def generate_pairwise_ext(factors: Factors, t: int = 2, algorithm: str = "ipog", is_valid_row: Optional[Callable[[Row], bool]] = None, seed: int = 42, seed_rows: Optional[List[Row]] = None, prune: bool = True, hybrid_optimize: bool = True, prune_infeasible: bool = True) -> List[Row]:
    if is_valid_row is None:
        is_valid_row = default_is_valid
    if algorithm == "ipog":
        design = ipog_like(factors, t=t, is_valid_row=is_valid_row, seed_rows=seed_rows, prune_infeasible=prune_infeasible)
    elif algorithm == "greedy":
        design = greedy_pairwise(factors, t=t, is_valid_row=is_valid_row, seed=seed)
    elif algorithm == "hybrid":
        design = ipog_like(factors, t=t, is_valid_row=is_valid_row, seed_rows=seed_rows, prune_infeasible=prune_infeasible)
        # run greedy to try to fill leftover issues
        if not validate_coverage_rows(design, indices_from_factors(factors)[1], t)[0]:
            more = greedy_pairwise(factors, t=t, is_valid_row=is_valid_row, seed=seed)
            design.extend(more)
    else:
        raise ValueError("algorithm must be ipog|greedy|hybrid")

    names, levels_by_index = indices_from_factors(factors)

    if prune:
        design = prune_redundant_rows(design, levels_by_index, t)

    if hybrid_optimize:
        design = simulated_annealing_shrink(design, levels_by_index, t, time_limit=5)

    return design


# --- CLI helper for writing CSVs ---

def rows_to_dataframe(rows: List[Row], factor_names: List[str]):
    if pd is None:
        import csv
        import sys
        writer = csv.writer(sys.stdout)
        writer.writerow(factor_names)
        for r in rows:
            writer.writerow(r)
        return None
    else:
        return pd.DataFrame(rows, columns=factor_names)


# End of file
