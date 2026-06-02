# Mobile Game A/B Test: Gate Placement and Player Retention

Analysis of a randomized controlled experiment on 90,189 mobile game players, testing whether
moving the game's first progression gate from level 30 to level 40 improves retention.

The headline result is a clear negative: moving the gate to level 40 **reduces** day-7 retention by
0.82 percentage points (a 4.31% relative drop, p = 0.0016). The recommendation is to keep the gate
at level 30. Five independent inference methods agree, and the result survives both a Bonferroni
correction across all three tested metrics and a Pocock-adjusted boundary for repeated looks.

## Experiment design

| | |
|---|---|
| Control | `gate_30` — first gate at level 30 (44,700 players) |
| Treatment | `gate_40` — first gate at level 40 (45,489 players) |
| Primary metric | Day-7 retention |
| Secondary metric | Day-1 retention |
| Guardrail metric | Game rounds played in first 14 days |
| Significance level | 0.05 |
| Target power | 0.80 |

## Results

| Metric | Control | Treatment | Absolute lift | 95% CI | p-value | Power | Verdict |
|---|---|---|---|---|---|---|---|
| Day-7 retention | 19.0201% | 18.2000% | **−0.8201pp** | [−1.3282, −0.3121] | **0.001554** | 0.886 | Significant decrease |
| Day-1 retention | 44.8188% | 44.2283% | −0.5905pp | [−1.2392, +0.0582] | 0.074410 | 0.430 | Inconclusive |
| Game rounds | 51.34 | 51.30 | −0.04 rounds | — | 0.949469 | — | No degradation |

Day-7 retention was tested five ways and every method returns the same answer:

| Method | Result |
|---|---|
| Two-proportion z-test | z = −3.1644, p = 0.001554 |
| Chi-square test | χ² = 10.0132, p = 0.001554 |
| Fisher exact test | OR = 0.9473, p = 0.001591 |
| Permutation test (10,000 draws from the exact hypergeometric null) | p = 0.001300 |
| Bootstrap (10,000 resamples) | 95% CI [−1.3356pp, −0.3111pp], P(worse) = 0.9992 |
| Bayesian Beta-Binomial | P(gate_40 better) = 0.00076 |

Projected impact of shipping the treatment: **820 fewer day-7 retained players per 100,000 installs**
(95% interval: 312 to 1,328).

## Validity checks

**Sample ratio mismatch.** Observed allocation was 49.56% / 50.44% against an intended 50/50 split,
a 789-player imbalance (χ² = 6.9024, p = 0.008608). This passes the 0.0005 and 0.001 alerting
thresholds standard for SRM checks, which are set far below 0.05 because the test runs on every
experiment and the family-wise error rate matters.

**Outlier handling on the guardrail metric.** One player recorded 49,854 game rounds, 82× the 99th
percentile. Including that single record, the treatment arm shows 1.16 fewer rounds on average; that
record alone accounts for 1.11 rounds of the gap. With it excluded the difference is 0.04 rounds
(p = 0.949), so the guardrail conclusion is driven entirely by one observation and the excluded-outlier
result is the one reported.

**Power on the secondary metric.** Day-1 retention has an achieved power of 0.430 at the observed
effect size. Detecting an effect that small at 80% power needs 111,190 players per arm, 2.49× the
sample available, so this metric is reported as inconclusive rather than null.

**Peeking.** Simulating 1,000 null experiments evaluated at 20 checkpoints each, the false positive
rate rises from 4.4% (testing only at the end, matching the nominal 5%) to 25.8% — a 5.86× inflation.
Holding family-wise error at 0.05 across 20 looks requires a per-look threshold of 0.002561; the
primary metric's p-value of 0.001554 clears it.

## Repository layout

```
mobile-game-ab-test/
├── Mobile Game AB Test Analysis.ipynb   Full analysis, 132 cells
├── app.py                               Streamlit experiment analyzer
├── data/
│   └── cookie_cats.csv                  Downloaded on first run
├── outputs/
│   ├── eda_comprehensive_analysis.png
│   ├── experiment_results_comprehensive.png
│   ├── experiment_results.csv
│   ├── sequential_analysis.csv
│   ├── sample_size_requirements.csv
│   ├── experiment_summary.txt
│   └── experiment_payload.json
├── requirements.txt
└── README.md
```

## Running it

```bash
pip install -r requirements.txt
```

Run the notebook top to bottom; it downloads the dataset into `data/` on first execution and writes
every figure and table into `outputs/`. Then launch the analyzer:

```bash
streamlit run app.py
```

The Streamlit app has three tabs: the Cookie Cats results, a general two-arm test analyzer that takes
your own conversion counts and returns the full inference suite plus an SRM check, and a sample size
planner that computes minimum detectable effect and required sample size by target lift.

## Analysis contents

The notebook covers group allocation and data quality checks, exploratory analysis of the retention
funnel and engagement distribution, SRM and outlier validity checks, power analysis with MDE and
sample size planning, the primary and secondary metric inference suites, guardrail metric testing
with an outlier sensitivity check, an exact permutation test, bootstrap confidence intervals,
Bayesian posterior comparison with expected-loss decision framing, Bonferroni and Benjamini-Hochberg
corrections, and a sequential analysis quantifying the cost of peeking.

## Data

Cookie Cats A/B test dataset, 90,189 players who installed during the experiment window. Columns:
`userid`, `version` (assignment), `sum_gamerounds`, `retention_1`, `retention_7`. The dataset
contains no pre-treatment covariates, so no covariate-adjusted or segmented estimates are computed —
`sum_gamerounds` is measured after assignment and conditioning on it would introduce post-treatment
bias.
