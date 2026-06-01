import warnings
warnings.filterwarnings('ignore')
import json
import os
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# Statistical Tests
from scipy import stats
from scipy.stats import chi2_contingency, fisher_exact

# Proportion Inference & Confidence Intervals
from statsmodels.stats.proportion import proportions_ztest, proportion_confint, confint_proportions_2indep, proportion_effectsize

# Power Analysis
from statsmodels.stats.power import NormalIndPower

# Set random seed for reproducibility
RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

# Configure page
st.set_page_config(page_title="A/B Test Analyzer", page_icon="📊", layout="wide")

power_analysis = NormalIndPower()
PAYLOAD_PATH = "outputs/experiment_payload.json"


# Core inference routine shared by both tabs
def analyze_proportions(x_control, n_control, x_treatment, n_treatment, alpha):
    """Run the full inference suite for a two-arm proportion test."""
    p_control = x_control / n_control
    p_treatment = x_treatment / n_treatment

    z_stat, z_p = proportions_ztest([x_treatment, x_control], [n_treatment, n_control])
    table = np.array([[x_treatment, n_treatment - x_treatment], [x_control, n_control - x_control]])
    chi2_stat, chi2_p, dof, expected = chi2_contingency(table, correction=False)
    odds_ratio, fisher_p = fisher_exact(table)
    ci_low, ci_high = confint_proportions_2indep(x_treatment, n_treatment, x_control, n_control, method='wald')

    effect_size = proportion_effectsize(p_treatment, p_control)
    achieved_power = power_analysis.power(effect_size=abs(effect_size), nobs1=n_control,
                                         ratio=n_treatment / n_control, alpha=alpha)

    rng = np.random.default_rng(RANDOM_STATE)
    post_control = rng.beta(1 + x_control, 1 + n_control - x_control, 100000)
    post_treatment = rng.beta(1 + x_treatment, 1 + n_treatment - x_treatment, 100000)
    prob_better = (post_treatment > post_control).mean()
    expected_loss = np.maximum(post_control - post_treatment, 0).mean()

    return {
        'p_control': p_control, 'p_treatment': p_treatment,
        'absolute_lift': p_treatment - p_control,
        'relative_lift': p_treatment / p_control - 1 if p_control > 0 else np.nan,
        'z_statistic': z_stat, 'z_pvalue': z_p,
        'chi2_statistic': chi2_stat, 'chi2_pvalue': chi2_p,
        'odds_ratio': odds_ratio, 'fisher_pvalue': fisher_p,
        'ci_low': ci_low, 'ci_high': ci_high,
        'cohens_h': effect_size, 'achieved_power': achieved_power,
        'prob_treatment_better': prob_better, 'expected_loss': expected_loss,
        'posterior_control': post_control, 'posterior_treatment': post_treatment,
    }


# Sample ratio mismatch check
def check_srm(n_control, n_treatment, expected_ratio=0.5):
    """Test the observed allocation against the intended split."""
    total = n_control + n_treatment
    chi2_stat, p_value = stats.chisquare(
        f_obs=[n_control, n_treatment],
        f_exp=[total * expected_ratio, total * (1 - expected_ratio)])
    return chi2_stat, p_value


# Minimum detectable effect at a given sample size
def compute_mde(baseline, n1, n2, alpha, power):
    """Return the smallest absolute lift detectable at the given sample sizes."""
    target = power_analysis.solve_power(effect_size=None, nobs1=n1, ratio=n2 / n1,
                                       alpha=alpha, power=power)
    lo, hi = 0.0, 1.0 - baseline
    for _ in range(200):
        mid = (lo + hi) / 2
        if proportion_effectsize(baseline + mid, baseline) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# Sidebar configuration
st.sidebar.header("Configuration")
ALPHA = st.sidebar.slider("Significance level (alpha)", 0.01, 0.10, 0.05, 0.01)
POWER_TARGET = st.sidebar.slider("Target power", 0.50, 0.99, 0.80, 0.01)

st.title("A/B Test Analyzer")
st.caption("Two-arm proportion testing with frequentist, Bayesian and power diagnostics")

tab1, tab2, tab3 = st.tabs(["Cookie Cats Experiment", "Analyze Your Own Test", "Sample Size Planner"])

# ------------------------------------------------------------------ tab 1
with tab1:
    st.subheader("Mobile Game Gate Placement Experiment")

    if not os.path.exists(PAYLOAD_PATH):
        st.warning(f"Run the analysis notebook first to generate {PAYLOAD_PATH}")
    else:
        with open(PAYLOAD_PATH) as f:
            payload = json.load(f)

        st.write(f"Control group: **{payload['control']}** | Treatment group: **{payload['treatment']}**")

        col1, col2, col3 = st.columns(3)
        col1.metric("Control players", f"{payload['n_control']:,}")
        col2.metric("Treatment players", f"{payload['n_treatment']:,}")
        col3.metric("SRM p-value", f"{payload['srm_pvalue']:.4f}",
                    "PASS" if payload['srm_pvalue'] >= 0.0005 else "ALERT")

        st.markdown("---")

        for metric_name, metric in payload['metrics'].items():
            st.markdown(f"#### {metric_name}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Control rate", f"{metric['rate_control']*100:.4f}%")
            c2.metric("Treatment rate", f"{metric['rate_treatment']*100:.4f}%",
                      f"{metric['absolute_lift']*100:+.4f}pp")
            c3.metric("P-value", f"{metric['pvalue']:.6f}",
                      "significant" if metric['pvalue'] < ALPHA else "not significant")
            c4.metric("Achieved power", f"{metric['achieved_power']:.4f}")

            st.write(f"95% CI on absolute lift: "
                     f"[{metric['ci_low']*100:+.4f}pp, {metric['ci_high']*100:+.4f}pp] "
                     f"| Relative lift: {metric['relative_lift']*100:+.4f}%")
            st.markdown("---")

        st.markdown("#### Decision")
        primary = payload['metrics']['retention_7']
        st.error(f"Do not ship {payload['treatment']}. Day-7 retention falls "
                 f"{abs(primary['absolute_lift'])*100:.4f}pp "
                 f"({abs(primary['relative_lift'])*100:.2f}% relative), p = {primary['pvalue']:.6f}.")

# ------------------------------------------------------------------ tab 2
with tab2:
    st.subheader("Analyze Your Own Test")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Control arm**")
        n_control_input = st.number_input("Control sample size", min_value=1, value=44700, step=100)
        x_control_input = st.number_input("Control conversions", min_value=0, value=8502, step=10)
    with col2:
        st.markdown("**Treatment arm**")
        n_treatment_input = st.number_input("Treatment sample size", min_value=1, value=45489, step=100)
        x_treatment_input = st.number_input("Treatment conversions", min_value=0, value=8279, step=10)

    if x_control_input > n_control_input or x_treatment_input > n_treatment_input:
        st.error("Conversions cannot exceed sample size")
    else:
        result = analyze_proportions(x_control_input, n_control_input,
                                     x_treatment_input, n_treatment_input, ALPHA)
        srm_chi2, srm_p = check_srm(n_control_input, n_treatment_input)

        st.markdown("---")
        st.markdown("#### Validity check")
        if srm_p < 0.0005:
            st.error(f"Sample ratio mismatch detected: p = {srm_p:.6f}. "
                     f"Investigate the assignment pipeline before trusting these results.")
        else:
            st.success(f"No sample ratio mismatch: p = {srm_p:.6f} (alert threshold 0.0005)")

        st.markdown("#### Results")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Control rate", f"{result['p_control']*100:.4f}%")
        c2.metric("Treatment rate", f"{result['p_treatment']*100:.4f}%",
                  f"{result['absolute_lift']*100:+.4f}pp")
        c3.metric("Relative lift", f"{result['relative_lift']*100:+.4f}%")
        c4.metric("Achieved power", f"{result['achieved_power']:.4f}")

        test_table = pd.DataFrame([
            {'test': 'Two-proportion z-test', 'statistic': round(result['z_statistic'], 4),
             'pvalue': round(result['z_pvalue'], 6), 'significant': result['z_pvalue'] < ALPHA},
            {'test': 'Chi-square test', 'statistic': round(result['chi2_statistic'], 4),
             'pvalue': round(result['chi2_pvalue'], 6), 'significant': result['chi2_pvalue'] < ALPHA},
            {'test': 'Fisher exact test', 'statistic': round(result['odds_ratio'], 4),
             'pvalue': round(result['fisher_pvalue'], 6), 'significant': result['fisher_pvalue'] < ALPHA},
        ])
        st.dataframe(test_table, hide_index=True, width='stretch')

        st.write(f"95% CI on absolute lift: "
                 f"[{result['ci_low']*100:+.4f}pp, {result['ci_high']*100:+.4f}pp]")
        st.write(f"Bayesian P(treatment > control): **{result['prob_treatment_better']:.5f}** "
                 f"| Expected loss from shipping treatment: {result['expected_loss']*100:.6f}pp")

        if result['z_pvalue'] < ALPHA and result['absolute_lift'] > 0:
            st.success("Treatment is significantly better. Ship it.")
        elif result['z_pvalue'] < ALPHA and result['absolute_lift'] < 0:
            st.error("Treatment is significantly worse. Do not ship it.")
        elif result['achieved_power'] < POWER_TARGET:
            st.warning(f"Inconclusive and underpowered. Achieved power "
                       f"{result['achieved_power']:.4f} is below the {POWER_TARGET:.0%} target, "
                       f"so this test cannot rule out an effect of the observed size.")
        else:
            st.info("No significant difference detected at adequate power.")

        st.markdown("#### Posterior distributions")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.hist(result['posterior_control']*100, bins=80, alpha=0.6, label='Control',
                color='blue', density=True)
        ax.hist(result['posterior_treatment']*100, bins=80, alpha=0.6, label='Treatment',
                color='red', density=True)
        ax.set_xlabel('Conversion Rate (%)', fontweight='bold')
        ax.set_ylabel('Density', fontweight='bold')
        ax.set_title('Beta-Binomial Posteriors', fontweight='bold')
        ax.legend()
        ax.grid(alpha=0.3)
        st.pyplot(fig)

# ------------------------------------------------------------------ tab 3
with tab3:
    st.subheader("Sample Size Planner")

    baseline_input = st.number_input("Baseline conversion rate (%)", min_value=0.01,
                                    max_value=99.0, value=19.02, step=0.1) / 100
    n_available = st.number_input("Sample size available per arm", min_value=100,
                                 value=45000, step=1000)

    mde = compute_mde(baseline_input, n_available, n_available, ALPHA, POWER_TARGET)
    c1, c2 = st.columns(2)
    c1.metric("Minimum detectable effect", f"{mde*100:.4f}pp")
    c2.metric("As relative lift", f"{mde/baseline_input*100:.3f}%")

    st.markdown("#### Sample size required by target lift")
    planner_rows = []
    for rel_lift in [0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20]:
        effect_size = proportion_effectsize(baseline_input * (1 + rel_lift), baseline_input)
        n_required = power_analysis.solve_power(effect_size=effect_size, nobs1=None,
                                               ratio=1.0, alpha=ALPHA, power=POWER_TARGET)
        planner_rows.append({'relative_lift': f"{rel_lift*100:.1f}%",
                             'absolute_lift_pp': round(baseline_input * rel_lift * 100, 4),
                             'n_per_arm': int(np.ceil(n_required)),
                             'within_budget': int(np.ceil(n_required)) <= n_available})

    st.dataframe(pd.DataFrame(planner_rows), hide_index=True, width='stretch')

    fig, ax = plt.subplots(figsize=(10, 4))
    planner_df = pd.DataFrame(planner_rows)
    ax.plot(planner_df['relative_lift'], planner_df['n_per_arm'], marker='o', lw=2, color='teal')
    ax.axhline(n_available, color='red', lw=2, linestyle='--', label='Available per arm')
    ax.set_xlabel('Relative Lift Target', fontweight='bold')
    ax.set_ylabel('n per Arm', fontweight='bold')
    ax.set_title('Required Sample Size by Effect Size', fontweight='bold')
    ax.set_yscale('log')
    ax.legend()
    ax.grid(alpha=0.3)
    st.pyplot(fig)
