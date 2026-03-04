"""Inferential statistics engine — numpy-based implementations.
Implements t-test, chi-square, and Fisher exact test without scipy.
"""
import numpy as np
import pandas as pd
from math import lgamma, exp, sqrt, pi


def _t_cdf_approx(t, df):
    """Approximate two-tailed p-value for Student's t distribution.
    Uses the regularized incomplete beta function approximation.
    """
    x = df / (df + t * t)
    if df <= 0:
        return 1.0
    # Use series approximation for the regularized incomplete beta function
    # For large df, use normal approximation
    if df > 100:
        from math import erf
        z = t
        p = 1.0 - 0.5 * (1.0 + erf(z / sqrt(2.0)))
        return 2.0 * min(p, 1.0 - p)

    # Beta function approximation via Lentz's continued fraction
    a = df / 2.0
    b = 0.5
    if x >= (a + 1) / (a + b + 2):
        ibeta = 1.0 - _incomplete_beta(b, a, 1 - x)
    else:
        ibeta = _incomplete_beta(a, b, x)
    p_two_tail = ibeta
    return min(max(p_two_tail, 0.0), 1.0)


def _incomplete_beta(a, b, x, max_iter=200):
    """Regularized incomplete beta function via continued fraction."""
    if x < 0 or x > 1:
        return 0.0
    if x == 0 or x == 1:
        return x
    lbeta = lgamma(a) + lgamma(b) - lgamma(a + b)
    front = exp(a * np.log(x) + b * np.log(1 - x) - lbeta) / a
    # Lentz's algorithm
    f = 1.0
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1)
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    f = d

    for m in range(1, max_iter + 1):
        # even step
        num = m * (b - m) * x / ((a + 2*m - 1) * (a + 2*m))
        d = 1.0 + num * d
        if abs(d) < 1e-30: d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30: c = 1e-30
        f *= c * d
        # odd step
        num = -(a + m) * (a + b + m) * x / ((a + 2*m) * (a + 2*m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30: d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30: c = 1e-30
        delta = c * d
        f *= delta
        if abs(delta - 1.0) < 1e-8:
            break

    return front * f


def _chi2_cdf_approx(chi2, df):
    """Approximate p-value for chi-square distribution using Wilson-Hilferty."""
    if df <= 0 or chi2 <= 0:
        return 1.0
    z = ((chi2 / df) ** (1/3) - (1 - 2 / (9 * df))) / sqrt(2 / (9 * df))
    from math import erf
    p = 0.5 * (1 + erf(z / sqrt(2)))
    return 1.0 - p


def welch_ttest(group1, group2, audit, tfl_id, variable, pop_filter=None):
    """Welch's two-sample t-test (unequal variances)."""
    n1, n2 = len(group1), len(group2)
    m1, m2 = np.mean(group1), np.mean(group2)
    v1, v2 = np.var(group1, ddof=1), np.var(group2, ddof=1)

    se = sqrt(v1/n1 + v2/n2) if (v1/n1 + v2/n2) > 0 else 1e-10
    t_stat = (m1 - m2) / se
    df = (v1/n1 + v2/n2)**2 / ((v1/n1)**2/(n1-1) + (v2/n2)**2/(n2-1)) if n1 > 1 and n2 > 1 else 1
    p_val = _t_cdf_approx(t_stat, df)

    code = (f"Welch t-test: t = (mean1 - mean2) / sqrt(var1/n1 + var2/n2)\n"
            f"  n1={n1}, n2={n2}, mean1={m1:.4f}, mean2={m2:.4f}\n"
            f"  var1={v1:.4f}, var2={v2:.4f}, t={t_stat:.4f}, df={df:.2f}")

    result = {"t_stat": round(t_stat, 4), "df": round(df, 2), "p_value": round(p_val, 4)}
    audit.log(tfl_id, f"Welch_t-test({variable})", code,
              f"n1={n1}, n2={n2}, means=({m1:.2f}, {m2:.2f})", result,
              variable=variable, population_filter=pop_filter)
    return result


def chi_square_test(df, row_var, col_var, audit, tfl_id, pop_filter=None):
    """Chi-square test of independence on a contingency table."""
    ct = pd.crosstab(df[row_var], df[col_var])
    observed = ct.values.astype(float)
    row_sums = observed.sum(axis=1, keepdims=True)
    col_sums = observed.sum(axis=0, keepdims=True)
    grand_total = observed.sum()

    expected = (row_sums * col_sums) / grand_total
    dof = (observed.shape[0] - 1) * (observed.shape[1] - 1)

    chi2 = np.sum((observed - expected) ** 2 / np.where(expected > 0, expected, 1e-10))
    p_val = _chi2_cdf_approx(chi2, dof)

    code = (f"Chi-square test: X² = Σ (O-E)²/E\n"
            f"  Contingency table: {row_var} × {col_var}\n"
            f"  Shape: {observed.shape}, DoF: {dof}\n"
            f"  X²={chi2:.4f}, p={p_val:.4f}")

    result = {"chi2": round(chi2, 4), "df": dof, "p_value": round(p_val, 4)}
    audit.log(tfl_id, f"Chi-square({row_var}×{col_var})", code,
              f"table_shape={observed.shape}, grand_total={grand_total}", result,
              variable=f"{row_var}×{col_var}", population_filter=pop_filter)
    return result


def fisher_exact_2x2(table, audit, tfl_id, label, pop_filter=None):
    """Fisher exact test for 2×2 contingency table.
    table = [[a, b], [c, d]]
    """
    a, b, c, d = table[0][0], table[0][1], table[1][0], table[1][1]
    n = a + b + c + d

    def _log_hyper(a, b, c, d):
        n = a + b + c + d
        return (lgamma(a+b+1) + lgamma(c+d+1) + lgamma(a+c+1) + lgamma(b+d+1)
                - lgamma(n+1) - lgamma(a+1) - lgamma(b+1) - lgamma(c+1) - lgamma(d+1))

    log_p_obs = _log_hyper(a, b, c, d)
    p_value = 0.0
    r1 = a + b
    r2 = c + d
    c1 = a + c

    for i in range(min(r1, c1) + 1):
        j = r1 - i
        k = c1 - i
        l = r2 - k
        if j >= 0 and k >= 0 and l >= 0:
            log_p = _log_hyper(i, j, k, l)
            if log_p <= log_p_obs + 1e-10:
                p_value += exp(log_p)

    p_value = min(p_value, 1.0)
    code = (f"Fisher exact test (2×2): [[{a},{b}],[{c},{d}]]\n"
            f"  Sum over hypergeometric probabilities ≤ P(observed)\n"
            f"  p={p_value:.4f}")
    result = {"p_value": round(p_value, 4)}
    audit.log(tfl_id, f"Fisher_exact({label})", code,
              f"table=[[{a},{b}],[{c},{d}]], n={n}", result, population_filter=pop_filter)
    return result
