#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate the full factorial run matrix in chunked CSV files.
Each chunk contains up to 1,000,000 rows to respect Excel limits.
"""
import itertools
import csv

factors = [
    ("Input Rate", ["32k","34k","36k","38k","40k"]),
    ("Gas Valve Location", [2,3,4,5,6]),
    ("Gas Valve Differential", [5,8,11,14,16]),
    ("Dip Tube Length", ["1/2 Tank Height","1/2 Tank Height +2","1/2 Tank Height +4","1/2 Tank Height +6","Tank Bottom"]),
    ("Tank Volume", ["36g","38g","40g","42g"]),
    ("Flue Tube", [3,4]),
    ("Tank Diameter", [16,18]),
    ("Jacket Thickness", [1,1.5,2]),
    ("Damper", ["Top","Bottom"]),
    ("Water Outlet", [115,117.5,120,122.5,125]),
    ("Water Inlet", [64,65,66,67,68,69,70]),
    ("Foam R-Value", ["nominal - 20%","nominal - 15%","nominal - 10%","nominal - 5%","nominal","nominal + 5%","nominal + 10%","nominal + 15%","nominal + 20%"]),
]

headers = [name for name, _ in factors]
levels_by_index = [lvls for _, lvls in factors]

CHUNK_SIZE = 1_000_000
chunk_idx = 1
count = 0
rows_in_chunk = 0
f = open(f"Full_Factorial_chunk_{chunk_idx}.csv", "w", newline="")
writer = csv.writer(f)
writer.writerow(headers)

try:
    for combo in itertools.product(*levels_by_index):
        writer.writerow(combo)
        count += 1
        rows_in_chunk += 1
        if rows_in_chunk >= CHUNK_SIZE:
            f.close()
            chunk_idx += 1
            rows_in_chunk = 0
            f = open(f"Full_Factorial_chunk_{chunk_idx}.csv", "w", newline="")
            writer = csv.writer(f)
            writer.writerow(headers)
finally:
    f.close()

print(f"Total rows written: {count}")
