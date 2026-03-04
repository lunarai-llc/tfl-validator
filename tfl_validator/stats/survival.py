"""Survival analysis engine — Kaplan-Meier estimator and log-rank test.
Implemented from scratch using numpy (no lifelines/scipy dependency).
"""
import numpy as np
from math import sqrt, erf


def kaplan_meier(times, events, audit, tfl_id, group_label, pop_filter=None):
    """Compute Kaplan-Meier survival estimates.
    Args:
        times: array of event/censor times
        events: array of event indicators (1=event, 0=censored)
    Returns:
        dict with time points, survival probabilities, and summary stats
    """
    times = np.array(times, dtype=float)
    events = np.array(events, dtype=int)

    # Sort by time
    idx = np.argsort(times)
    times = times[idx]
    events = events[idx]

    unique_times = np.unique(times[events == 1])  # only event times
    n_at_risk = len(times)
    survival = 1.0
    km_table = []

    processed = 0
    for t in unique_times:
        # Number censored before this time
        censored_before = np.sum((times < t) & (events == 0) & (times > (km_table[-1]["time"] if km_table else 0)))
        n_at_risk -= censored_before

        d = int(np.sum((times == t) & (events == 1)))  # deaths at time t
        c = int(np.sum((times == t) & (events == 0)))   # censored at time t

        if n_at_risk > 0:
            survival *= (1 - d / n_at_risk)

        km_table.append({
            "time": float(t),
            "n_at_risk": n_at_risk,
            "n_events": d,
            "n_censored": c,
            "survival": round(survival, 4),
        })
        n_at_risk -= (d + c)

    # Median survival (time when S(t) first <= 0.5)
    median_surv = None
    for row in km_table:
        if row["survival"] <= 0.5:
            median_surv = row["time"]
            break

    n_total = len(times)
    n_events = int(events.sum())

    code = (f"Kaplan-Meier estimate for {group_label}\n"
            f"  N={n_total}, events={n_events}, censored={n_total-n_events}\n"
            f"  Unique event times: {len(unique_times)}\n"
            f"  S(t) = Π (1 - d_i/n_i) at each event time\n"
            f"  Median survival: {median_surv}")

    result = {
        "n_total": n_total,
        "n_events": n_events,
        "n_censored": n_total - n_events,
        "median_survival": median_surv,
        "km_table": km_table,
        "final_survival": km_table[-1]["survival"] if km_table else 1.0,
    }

    audit.log(tfl_id, f"KM({group_label})", code,
              f"n={n_total}, events={n_events}", result,
              variable="AVAL", population_filter=pop_filter)
    return result


def log_rank_test(times1, events1, times2, events2, audit, tfl_id,
                  label1="Group1", label2="Group2", pop_filter=None):
    """Log-rank test comparing two survival curves.
    Returns chi-square statistic and approximate p-value.
    """
    all_times = np.concatenate([times1, times2])
    all_events = np.concatenate([events1, events2])
    all_groups = np.concatenate([np.ones(len(times1)), np.zeros(len(times2))])

    # Get unique event times
    event_mask = all_events == 1
    unique_event_times = np.unique(all_times[event_mask])
    unique_event_times.sort()

    O1 = 0  # observed events in group 1
    E1 = 0.0  # expected events in group 1
    V = 0.0   # variance

    for t in unique_event_times:
        # At risk in each group at time t
        at_risk_1 = np.sum((times1 >= t))
        at_risk_2 = np.sum((times2 >= t))
        n_risk = at_risk_1 + at_risk_2

        # Events at time t
        d1 = np.sum((times1 == t) & (events1 == 1))
        d2 = np.sum((times2 == t) & (events2 == 1))
        d = d1 + d2

        if n_risk > 0:
            O1 += d1
            E1 += d * at_risk_1 / n_risk
            if n_risk > 1:
                V += d * at_risk_1 * at_risk_2 * (n_risk - d) / (n_risk * n_risk * (n_risk - 1))

    chi2 = (O1 - E1) ** 2 / V if V > 0 else 0.0
    # Approximate p-value from chi2(1)
    z = sqrt(chi2) if chi2 > 0 else 0
    p_val = 1.0 - 0.5 * (1.0 + erf(z / sqrt(2.0))) if z > 0 else 1.0
    p_val = 2 * p_val  # two-sided

    code = (f"Log-rank test: {label1} vs {label2}\n"
            f"  O1={O1}, E1={E1:.2f}, Var={V:.4f}\n"
            f"  X² = (O1-E1)²/V = {chi2:.4f}\n"
            f"  p = {p_val:.4f}")

    result = {"chi2": round(chi2, 4), "p_value": round(p_val, 4),
              "observed_1": int(O1), "expected_1": round(E1, 2)}

    audit.log(tfl_id, f"Log-rank({label1} vs {label2})", code,
              f"n1={len(times1)}, n2={len(times2)}", result,
              variable="AVAL", population_filter=pop_filter)
    return result


def compute_survival_summary(adtte, group_var, audit, tfl_id, pop_filter=None):
    """Compute KM estimates for each treatment arm and pairwise log-rank tests."""
    treatments = sorted(adtte[group_var].unique())
    km_results = {}

    for trt in treatments:
        subset = adtte[adtte[group_var] == trt]
        km_results[trt] = kaplan_meier(
            subset["AVAL"].values,
            (1 - subset["CNSR"]).values.astype(int),  # CNSR=0 means event, CNSR=1 means censored
            audit, tfl_id, trt, pop_filter
        )

    # Pairwise log-rank (first treatment vs each other)
    lr_results = {}
    ref = treatments[0]
    ref_data = adtte[adtte[group_var] == ref]
    for trt in treatments[1:]:
        comp_data = adtte[adtte[group_var] == trt]
        lr_results[f"{ref}_vs_{trt}"] = log_rank_test(
            ref_data["AVAL"].values, (1 - ref_data["CNSR"]).values.astype(int),
            comp_data["AVAL"].values, (1 - comp_data["CNSR"]).values.astype(int),
            audit, tfl_id, ref, trt, pop_filter
        )

    return {"km": km_results, "log_rank": lr_results}
