import math
import numpy as np
import pandas as pd
from scipy import stats

LEVEL = 0.05


def show_p(p):
    if p < 0.001:
        return "p < 0.001"
    return f"p = {p:.3f}"


def verdict(p, what):
    if p < LEVEL:
        return f"{what} is statistically significant at the 5 percent level."
    return f"{what} is not statistically significant at the 5 percent level."


def small_groups(sizes):
    small = [name for name, size in sizes.items() if size < 30]
    if small:
        return ["Fewer than 30 answers in: " + ", ".join(small) + ". Treat this result with caution."]
    return []


def label_effect(value, small, medium, large):
    value = abs(value)
    if value < small:
        return "negligible"
    if value < medium:
        return "small"
    if value < large:
        return "medium"
    return "large"


def compare_number_by_group(values, groups):
    data = pd.DataFrame({"value": values, "group": groups}).dropna()
    parts = {}
    for name, part in data.groupby("group", observed=True):
        if len(part) >= 2:
            parts[str(name)] = part["value"]
    if len(parts) < 2:
        return None
    notes = small_groups({name: len(part) for name, part in parts.items()})
    everyone = pd.concat(parts.values())
    if len(parts) == 2:
        first, second = list(parts.values())
        result = stats.ttest_ind(first, second, equal_var=False)
        n1, n2 = len(first), len(second)
        pooled = math.sqrt(((n1 - 1) * first.var(ddof=1) + (n2 - 1) * second.var(ddof=1)) / (n1 + n2 - 2))
        effect = (first.mean() - second.mean()) / pooled if pooled > 0 else float("nan")
        out = {
            "kind": "ttest",
            "test": "Welch t-test",
            "effect_name": "Cohen's d",
            "df": float(result.df),
        }
        effect_cuts = (0.2, 0.5, 0.8)
    else:
        result = stats.f_oneway(*parts.values())
        grand = everyone.mean()
        between = sum(len(p) * (p.mean() - grand) ** 2 for p in parts.values())
        total = ((everyone - grand) ** 2).sum()
        effect = between / total if total > 0 else float("nan")
        out = {
            "kind": "anova",
            "test": "One-way ANOVA",
            "effect_name": "eta squared",
            "df": (len(parts) - 1, len(everyone) - len(parts)),
            "groups": len(parts),
        }
        effect_cuts = (0.01, 0.06, 0.14)
    statistic = float(result.statistic)
    p = float(result.pvalue)
    if pd.isna(p):
        return None
    out["statistic"] = statistic
    out["p"] = p
    out["effect"] = float(effect)
    out["effect_label"] = label_effect(effect, *effect_cuts) if not pd.isna(effect) else "unknown"
    out["n"] = len(everyone)
    out["notes"] = notes
    out["text"] = f"{out['test']}: statistic = {abs(statistic):.2f}, {show_p(p)}. " + verdict(p, "The difference between the groups")
    return out


def correlate(x, y):
    data = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(data) < 3 or data["x"].nunique() < 2 or data["y"].nunique() < 2:
        return None
    r, p = stats.pearsonr(data["x"], data["y"])
    rho, p_rho = stats.spearmanr(data["x"], data["y"])
    strength = label_effect(r, 0.1, 0.3, 0.5)
    direction = "positive" if r > 0 else "negative"
    notes = []
    if len(data) < 30:
        notes.append(f"Only {len(data)} rows have both answers. Treat this result with caution.")
    text = (
        f"Pearson correlation: r = {r:.2f} ({strength} {direction}), {show_p(p)}. "
        f"Spearman rank correlation: rho = {rho:.2f}, {show_p(p_rho)}. "
        + verdict(p, "The relationship")
    )
    return {
        "kind": "correlation",
        "test": "Correlation",
        "statistic": float(r),
        "p": float(p),
        "rho": float(rho),
        "p_rho": float(p_rho),
        "effect": float(r),
        "effect_name": "r",
        "effect_label": strength,
        "n": len(data),
        "text": text,
        "notes": notes,
    }


def compare_categories(table):
    table = table.loc[table.sum(axis=1) > 0, table.sum(axis=0) > 0]
    if table.shape[0] < 2 or table.shape[1] < 2:
        return None
    chi2, p, dof, expected = stats.chi2_contingency(table)
    n = table.values.sum()
    k = min(table.shape[0] - 1, table.shape[1] - 1)
    v = math.sqrt(chi2 / (n * k)) if n > 0 and k > 0 else float("nan")
    notes = []
    if (expected < 5).mean() > 0.2:
        notes.append("More than 20 percent of the cells expect fewer than 5 people, so this test may be unreliable.")
    residuals = (table.values - expected) / np.sqrt(expected)
    row, col = np.unravel_index(np.abs(residuals).argmax(), residuals.shape)
    cell = {
        "row": str(table.index[row]),
        "column": str(table.columns[col]),
        "observed": int(table.values[row, col]),
        "expected": float(expected[row, col]),
    }
    text = f"Chi-square test: chi2 = {chi2:.2f}, {show_p(p)}. " + verdict(p, "The association between the two columns")
    return {
        "kind": "chisquare",
        "test": "Chi-square",
        "statistic": float(chi2),
        "p": float(p),
        "df": int(dof),
        "effect": float(v),
        "effect_name": "Cramer's V",
        "effect_label": label_effect(v, 0.1, 0.3, 0.5) if not pd.isna(v) else "unknown",
        "n": int(n),
        "cell": cell,
        "text": text,
        "notes": notes,
    }


def run_test(clean, data, first, split, number_columns):
    rows = data.index
    first_is_number = first in number_columns
    split_is_number = split in number_columns
    result = None
    if first_is_number and split_is_number:
        result = correlate(clean.loc[rows, first], clean.loc[rows, split])
    elif first_is_number:
        result = compare_number_by_group(clean.loc[rows, first], data["b"])
        if result:
            result["outcome"], result["grouping"] = first, split
    elif split_is_number:
        result = compare_number_by_group(clean.loc[rows, split], data["a"])
        if result:
            result["outcome"], result["grouping"] = split, first
    else:
        result = compare_categories(pd.crosstab(data["a"], data["b"]))
    if result:
        result["first"], result["split"] = first, split
    return result
