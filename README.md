# DOEAnalysis

A Python-based Design of Experiments (DOE) analysis tool for generating and analyzing **t-way covering arrays** (pairwise and higher-order combinatorial test designs). Supports constraint-aware generation, multiple algorithms (IPOG, greedy, hybrid), coverage visualization, and flexible TOML-based configuration.

---

## Features

- **t-way Covering Array Generation**: Generate pairwise (t=2) or higher-order (t=3+) combinatorial test designs
- **Multiple Algorithms**:
  - `ipog` — IPOG-like incremental construction (default, generally compact)
  - `greedy` — Randomized greedy algorithm
  - `hybrid` — IPOG + greedy fill + simulated annealing optimization
- **Constraint Support**: Define valid/invalid factor combinations via Python predicates or inline TOML rules
- **Seed Rows**: Pre-specify must-have test cases that will be included in the design
- **Pruning**: Automatically remove redundant rows that don't contribute to coverage
- **Coverage Analysis & Visualization**:
  - Coverage progression plots
  - Pair frequency histograms
  - Pairwise coverage heatmaps
  - Missing tuple reports
  - Markdown summary reports
- **Flexible Configuration**: TOML-based config files for factors, levels, constraints, and settings

---

## Installation

### Clone the repository

```bash
git clone git@github.com:josh-fowler-hub/DOEAnalysis.git
cd DOEAnalysis
```

### Install dependencies

Requires Python 3.8+ (Python 3.11+ recommended for built-in `tomllib` support).

```bash
pip install -r requirements.txt
```

Or install dependencies manually:

```bash
pip install pandas numpy matplotlib Pillow toml
```

> **Note**: On Python 3.11+, the `toml` package is optional since `tomllib` is included in the standard library.

---

## Quick Start

1. **Create a configuration file** (`doe_config.toml`):

```toml
[factors]
"Input Rate" = ["32k", "34k", "36k", "38k", "40k"]
"Gas Valve Location" = [2, 3, 4, 5, 6]
"Fan Speed" = ["Low", "Medium", "High"]
"Temperature" = [100, 120, 140, 160]

[settings]
algorithm = "ipog"      # ipog | greedy | hybrid
t = 2                   # t-way coverage (2 = pairwise)
out = "Pairwise_DOE.csv"
prune = true            # Remove redundant rows
seed = 42               # Random seed for reproducibility
plots = true            # Generate coverage plots
statistics = false      # Generate stats only (no plots)
report = true           # Generate Markdown report
```

2. **Generate the DOE**:

```bash
python generate_doe.py --config doe_config.toml
```

3. **Output**: The tool writes `Pairwise_DOE.csv` and (if enabled) a `Pairwise_DOE.csv.plots/` directory with coverage visualizations.

---

## Usage

### Command-Line Interface

```bash
python generate_doe.py --config <path-to-config.toml>
```

| Option | Description |
|--------|-------------|
| `--config` | Path to the TOML configuration file (default: `doe_config.toml`) |

### Configuration Options

All settings go in your TOML config file:

#### `[factors]` Section

Define your factors and their levels:

```toml
[factors]
"Factor A" = ["level1", "level2", "level3"]
"Factor B" = [1, 2, 3, 4]
"Factor C" = [true, false]
```

#### `[settings]` Section

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `algorithm` | string | `"ipog"` | Algorithm: `ipog`, `greedy`, or `hybrid` |
| `t` | int | `2` | t-way coverage level (2 = pairwise, 3 = 3-way, etc.) |
| `out` | string | `"Pairwise_DOE.csv"` | Output CSV filename |
| `prune` | bool | `true` | Remove redundant rows after generation |
| `prune_infeasible` | bool | `true` | Skip infeasible t-tuples during generation |
| `seed` | int | `42` | Random seed for reproducibility |
| `plots` | bool | `false` | Generate coverage plots |
| `statistics` | bool | `false` | Generate statistics only (no plots) |
| `report` | bool | `false` | Generate Markdown coverage report |
| `max_pair_heatmaps` | int | `16` | Max number of per-pair heatmaps to generate |
| `constraints` | string/table | `null` | Path to constraints.py or inline constraint rules |
| `seed_rows` | string/list | `null` | Path to seed_rows.json or inline list of seed rows |

---

## Constraints

### Option 1: Python Constraint File

Create a `constraints.py` file with an `is_valid(row)` function:

```python
def is_valid(row):
    """Return True if the row is valid, False otherwise.
    row is a list of values in factor order.
    """
    input_rate, gas_valve, fan_speed, temp = row
    # Example: High fan speed not allowed with low input rate
    if fan_speed == "High" and input_rate == "32k":
        return False
    return True
```

Reference it in your config:

```toml
[settings]
constraints = "constraints.py"
```

### Option 2: Inline TOML Constraints

```toml
[[constraints]]
if = { "Jacket Thickness" = 2, "Water Outlet" = 125 }
then_not = { "Damper" = ["Top"] }

[[constraints]]
if = { "Tank Volume" = "36g" }
then_not = { "Water Outlet" = 125 }
```

---

## Seed Rows

Pre-specify test cases that **must** appear in the final design:

### Option 1: JSON File

Create `seed_rows.json`:

```json
[
    ["32k", 2, "Low", 100],
    ["40k", 6, "High", 160]
]
```

Reference in config:

```toml
[settings]
seed_rows = "seed_rows.json"
```

### Option 2: Inline in TOML

```toml
[settings]
seed_rows = [
    ["32k", 2, "Low", 100],
    ["40k", 6, "High", 160]
]
```

---

## Coverage Analysis

Run standalone coverage analysis on an existing DOE CSV:

```bash
python plot_coverage.py Pairwise_DOE.csv --config doe_config.toml --t 2 --outdir ./plots --report
```

| Option | Description |
|--------|-------------|
| `csv` | Input CSV file with DOE design |
| `--config` | TOML config for factor ordering |
| `--t` | t-way coverage level |
| `--outdir` | Output directory for plots/stats |
| `--report` | Generate Markdown report |
| `--stats-only` | Compute statistics without generating plots |
| `--max-pair-heatmaps` | Limit number of per-pair heatmaps |
| `--show` | Display plots interactively |

### Generated Outputs

| File | Description |
|------|-------------|
| `coverage_progress.png` | Coverage fraction vs. cumulative rows |
| `coverage_gain_per_row.png` | New tuples covered by each row |
| `pair_freq_hist.png` | Histogram of pair frequencies |
| `coverage_fraction_pie.png` | Pie chart of covered vs. missing tuples |
| `pair_coverage_matrix.png` | Heatmap of coverage % per factor pair |
| `heatmap_*.png` | Per-pair level×level count heatmaps |
| `top_missing_pairs_bar.png` | Bar chart of top missing pairs |
| `coverage_summary.txt` | Text summary of coverage statistics |
| `coverage_report.md` | Markdown report with all figures |

---

## Validation

Validate that a DOE CSV achieves full t-way coverage:

```bash
python validate_pairwise_doe.py Pairwise_DOE.csv --config doe_config.toml --t 2
```

---

## Project Structure

```text
DOEAnalysis/
├── generate_doe.py           # Main entry point
├── pairwise_improvements.py  # Core algorithms (IPOG, greedy, hybrid, pruning)
├── doe_helpers.py            # Constraints, Seed Rows, Read/Write
├── plot_coverage.py          # Coverage analysis and visualization
├── config_loader.py          # TOML configuration loader
├── requirements.txt          # Python dependencies
├── README.md
│
├── templates/                # Example configurations
│   └── doe_config.toml       # Example TOML configuration
│
└── docs/                     # Documentation
    ├── Pairwise_DOE_Guide.md # Complete theory & usage guide
    │
    └── diagrams/                 # Documentation diagrams
        ├── algorithm_flowchart.png
        ├── full_vs_pairwise.png
        └── pairwise_concept.png
```

---

## Examples

### Example 1: Basic Pairwise DOE

```toml
# doe_config.toml
[factors]
Browser = ["Chrome", "Firefox", "Safari", "Edge"]
OS = ["Windows", "macOS", "Linux"]
Resolution = ["1080p", "1440p", "4K"]

[settings]
t = 2
out = "browser_tests.csv"
```

```bash
python generate_doe.py --config doe_config.toml
```

### Example 2: 3-Way Coverage with Constraints

```toml
[factors]
API = ["REST", "GraphQL", "gRPC"]
Auth = ["None", "Basic", "OAuth", "JWT"]
Cache = ["Disabled", "Memory", "Redis"]
DB = ["PostgreSQL", "MySQL", "MongoDB"]

[settings]
algorithm = "hybrid"
t = 3
out = "api_tests.csv"
prune = true
plots = true
report = true

[constraints]
rules = [
    "Auth != 'None' or API != 'gRPC'",
    "Cache != 'Redis' or DB != 'MongoDB'"
]
```

### Example 3: Using Seed Rows

```toml
[factors]
Environment = ["Dev", "Staging", "Prod"]
Feature = ["Login", "Checkout", "Search"]
User = ["Guest", "Member", "Admin"]

[settings]
t = 2
out = "feature_tests.csv"
seed_rows = [
    ["Prod", "Login", "Admin"],
    ["Prod", "Checkout", "Member"]
]
```

---

## Algorithm Comparison

| Algorithm | Speed | Compactness | Best For |
|-----------|-------|-------------|----------|
| `ipog` | Fast | Good | Most use cases, balanced performance |
| `greedy` | Medium | Variable | Simple problems, when IPOG struggles |
| `hybrid` | Slower | Best | Minimizing test count, final optimization |

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
git clone git@github.com:josh-fowler-hub/DOEAnalysis.git
cd DOEAnalysis
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## License

This project is provided as-is for internal and educational use. See the repository for licensing details.

---

## References

- [IPOG Algorithm](https://csrc.nist.gov/publications/detail/journal-article/2008/ipog-a-general-strategy-for-t-way-software-testing) — NIST publication on IPOG
- [Pairwise Testing](https://www.pairwise.org/) — Introduction to pairwise/combinatorial testing
- [Covering Arrays](https://math.nist.gov/coveringarrays/) — NIST covering array resources
