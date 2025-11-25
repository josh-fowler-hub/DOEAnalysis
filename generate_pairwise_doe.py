
#!/usr/bin/env python3
"""
This script generates a Pairwise Design of Experiments (DOE) using a greedy all-pairs coverage algorithm.

Why Pairwise DOE?
-----------------
A full factorial design tests every possible combination of factor levels. While comprehensive, it can be
impractical when the number of factors and levels is large. For example, with 12 factors and multiple levels,
the full factorial can easily exceed millions of runs.

Pairwise DOE drastically reduces the number of runs by ensuring that every *pair* of factor levels appears
at least once across the design. This approach is widely used in software testing and engineering because
most defects or significant effects arise from interactions between two factors rather than three or more.

Algorithm Overview:
-------------------
1. Define all factors and their levels.
2. Generate all possible pairs of factor levels that need coverage.
3. Use a greedy algorithm:
   - Randomly sample candidate rows.
   - Select the row that covers the most uncovered pairs.
   - Repeat until all pairs are covered.

Result:
-------
This script produces a CSV file with ~73 runs (vs. millions in full factorial), covering all pairs.
"""

import random
import pandas as pd
import argparse
from config_loader import load_config

parser = argparse.ArgumentParser()
parser.add_argument('--config', type=str, default='doe_config.toml', help='Path to TOML config file for factors')
parser.add_argument('--out', type=str, default='Pairwise_DOE.csv')
args = parser.parse_args()

# Step 1: Define factors and levels based on the provided run matrix
factors = load_config(args.config)

# Extract factor names and levels
factor_names = list(factors.keys())
levels_by_index = [factors[name] for name in factor_names]

# Step 2: Identify all pairs of factor levels that need coverage
# For each pair of factors, create all possible level combinations and mark them as uncovered initially.
pair_indices = [(i, j) for i in range(len(factor_names)) for j in range(i + 1, len(factor_names))]
uncovered_pairs = set()
for (i, j) in pair_indices:
    for li in levels_by_index[i]:
        for lj in levels_by_index[j]:
            uncovered_pairs.add((i, str(li), j, str(lj)))

# Step 3: Define a helper function to count how many uncovered pairs a candidate row would cover
def covered_pairs_by_row(row):
    count = 0
    remove_list = []
    for (i, j) in pair_indices:
        t = (i, str(row[i]), j, str(row[j]))
        if t in uncovered_pairs:
            count += 1
            remove_list.append(t)
    return count, remove_list

# Step 4: Greedy algorithm to select rows
# At each step, randomly sample candidates and pick the one that covers the most uncovered pairs.
pairwise_rows = []
random.seed(42)  # For reproducibility
MAX_TRIES_PER_STEP = 400  # Number of random candidates to evaluate per step
MAX_STEPS = 5000  # Safety limit to avoid infinite loops
steps = 0

while uncovered_pairs and steps < MAX_STEPS:
    steps += 1
    best_row = None
    best_cov = -1
    best_remove = None
    for _ in range(MAX_TRIES_PER_STEP):
        candidate = [random.choice(levels_by_index[i]) for i in range(len(levels_by_index))]
        cov, to_remove = covered_pairs_by_row(candidate)
        if cov > best_cov:
            best_cov = cov
            best_row = candidate
            best_remove = to_remove
            # Early stop if candidate covers a large chunk of pairs
            if cov >= 0.9 * len(pair_indices):
                break
    # Accept best candidate and remove covered pairs from uncovered set
    pairwise_rows.append(best_row)
    for t in best_remove:
        uncovered_pairs.discard(t)

# Convert the selected rows into a DataFrame
doe_df = pd.DataFrame(pairwise_rows, columns=factor_names)
doe_df.to_csv(args.out, index=False)



# Save the DOE to a CSV file
doe_df = doe_df.transpose()
doe_df.to_csv(args.out.replace('.csv','_transpose.csv'), index=True)

# Print summary
print(f"Pairwise DOE generated with {len(pairwise_rows)} runs (vs. millions in full factorial).")
print(f"Files saved: {args.out} and {args.out.replace('.csv','_transpose.csv')}")