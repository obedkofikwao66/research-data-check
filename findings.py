import pandas as pd
from stat_tests import show_p, LEVEL


def num(x):
    if pd.isna(x):
        return "n/a"
    x = float(x)
    if x.is_integer():
        return str(int(x))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def pct(part, whole):
    if not whole:
        return "0.0"
    return f"{part / whole * 100:.1f}"


def people(n):
    n = int(n)
    return "1 person" if n == 1 else f"{n} people"


def small_note(n):
    if n < 30:
        return f"With only {n} answers, treat this with caution."
    return ""


def describe_cleaning(rows, columns_used, decisions, open_count):
    parts = [f"The file has {rows} rows, and {columns_used} columns are being analysed."]
    if decisions:
        fixed = sum(1 for d in decisions if d["action"] == "fix")
        excluded = sum(1 for d in decisions if d["action"] == "exclude")
        kept = sum(1 for d in decisions if d["action"] == "keep")
        parts.append(f"{len(decisions)} problems have been reviewed: {fixed} fixed, {excluded} excluded and {kept} kept as they were. Every change is listed in the cleaning log.")
    if open_count:
        parts.append(f"{open_count} problems are still open, so the results below may change once they are reviewed.")
    if not decisions and not open_count:
        parts.append("No problems were found, so the data is analysed as uploaded.")
    return " ".join(parts)


def describe_number(name, total, row):
    n = int(row["answered"])
    if n == 0:
        return f"No one answered {name}, so there is nothing to summarise."
    parts = [f"{n} of {total} respondents answered {name}."]
    missing = int(row["missing"])
    if missing:
        parts.append(f"{missing} blank or excluded answers are left out of every figure for this column.")
    parts.append(f"The average is {num(row['mean'])} and the median, the middle value, is {num(row['median'])}. Answers run from {num(row['min'])} to {num(row['max'])}.")
    std = row["std dev"]
    if not pd.isna(std):
        parts.append(f"The standard deviation is {num(std)}, which means answers typically vary by about {num(std)} around the average.")
        if std > 0 and abs(row["mean"] - row["median"]) > 0.25 * std:
            if row["mean"] > row["median"]:
                parts.append("The average sits above the median, which suggests that a few high values pull it upward.")
            else:
                parts.append("The average sits below the median, which suggests that a few low values pull it downward.")
    note = small_note(n)
    if note:
        parts.append(note)
    return " ".join(parts)


def describe_distribution(name, counts):
    total = int(counts.sum())
    if total == 0:
        return ""
    filled = counts[counts > 0].sort_values(ascending=False, kind="stable")
    top = filled.iloc[0]
    tied = filled[filled == top]
    if len(tied) > 1:
        names = ", ".join(str(i) for i in tied.index)
        parts = [f"The groups {names} tie for the most respondents, with {int(top)} each ({pct(top, total)} percent each)."]
    else:
        parts = [f"Most respondents for {name} fall in the {tied.index[0]} group: {int(top)} of {total}, or {pct(top, total)} percent."]
        if len(filled) > 1:
            parts.append(f"The next largest is {filled.index[1]} with {people(filled.iloc[1])} ({pct(filled.iloc[1], total)} percent).")
    if len(filled) > 2 and filled.iloc[-1] != top:
        low = filled[filled == filled.iloc[-1]]
        if len(low) == 1:
            parts.append(f"The smallest group with anyone in it is {low.index[0]}, with {people(low.iloc[0])}.")
        else:
            names = ", ".join(str(i) for i in low.index)
            parts.append(f"The smallest groups with anyone in them are {names}, with {people(low.iloc[0])} each.")
    empty = [str(i) for i in counts.index[counts == 0]]
    if empty:
        shown = ", ".join(empty[:5])
        more = " and others" if len(empty) > 5 else ""
        parts.append(f"No one falls in: {shown}{more}.")
    note = small_note(total)
    if note:
        parts.append(note)
    return " ".join(parts)


def describe_categories(name, counts, answered):
    if len(counts) == 0 or answered == 0:
        return ""
    names = [str(i) for i in counts.index]
    vals = [int(v) for v in counts.values]
    if len(names) == 1:
        text = f"Everyone who answered {name} gave the same answer: {names[0]} ({people(vals[0])})."
    elif len(names) == 2:
        text = f"For {name}, {names[0]} accounts for {vals[0]} respondents ({pct(vals[0], answered)} percent) and {names[1]} for {vals[1]} ({pct(vals[1], answered)} percent)."
        if abs(vals[0] - vals[1]) / answered * 100 < 10:
            text += " The two answers are close to evenly split."
    else:
        text = (
            f"The most common answer for {name} is {names[0]} ({people(vals[0])}, {pct(vals[0], answered)} percent), "
            f"followed by {names[1]} ({people(vals[1])}, {pct(vals[1], answered)} percent). "
            f"The top two together make up {pct(vals[0] + vals[1], answered)} percent of the {answered} answers."
        )
    note = small_note(answered)
    if note:
        text += " " + note
    return text


def describe_cross(first, split, table):
    total = int(table.values.sum())
    if total == 0:
        return ""
    stack = table.stack()
    top = stack.max()
    ties = stack[stack == top]
    if len(ties) > 1:
        first_tie = ties.index[0]
        parts = [
            f"{total} respondents answered both {first} and {split}. Several combinations tie for the largest count, "
            f"{people(top)} each, for example {first_tie[0]} with {first_tie[1]}."
        ]
    else:
        best = ties.index[0]
        parts = [
            f"{total} respondents answered both {first} and {split}. The biggest combination is {best[0]} with {best[1]}: "
            f"{people(top)}, or {pct(top, total)} percent of those who answered both."
        ]
    if table.shape[1] == 2:
        c1 = table.columns[0]
        sizes = table.sum(axis=1)
        enough = sizes[sizes >= 5].index
        if len(enough) >= 2:
            share = table.loc[enough, c1] / sizes[enough] * 100
            hi, lo = share.idxmax(), share.idxmin()
            if share[hi] != share[lo]:
                parts.append(f"Within each {first} group, {c1} makes up the largest share in {hi} ({share[hi]:.1f} percent) and the smallest in {lo} ({share[lo]:.1f} percent).")
    tiny = [str(i) for i in table.index[table.sum(axis=1) < 5]]
    if tiny:
        parts.append(f"Some {first} groups have fewer than 5 respondents ({', '.join(tiny[:5])}), so their percentages are unstable.")
    parts.append(f"The second table shows how each {first} group divides across {split}, so groups of different sizes can be compared fairly.")
    return " ".join(parts)


def describe_pyramid(first, table):
    names = [str(c) for c in table.columns]
    left = table.iloc[:, 0]
    right = table.iloc[:, 1]
    parts = [f"In the pyramid, {names[0]} extends to the left and {names[1]} to the right. Each bar shows how many people fall in that {first} group."]
    if left.max() > 0:
        parts.append(f"The widest bar on the left is {left.idxmax()} ({people(left.max())}).")
    if right.max() > 0:
        parts.append(f"The widest bar on the right is {right.idxmax()} ({people(right.max())}).")
    return " ".join(parts)


def describe_group_stats(outcome, grouping, stats_table):
    t = stats_table[stats_table["count"] > 0]
    if len(t) < 2:
        return ""
    hi = t["mean"].idxmax()
    lo = t["mean"].idxmin()
    diff = t.loc[hi, "mean"] - t.loc[lo, "mean"]
    if diff == 0:
        return f"The average {outcome} is the same in every {grouping} group ({num(t.loc[hi, 'mean'])})."
    return (
        f"The average {outcome} is highest for {hi} ({num(t.loc[hi, 'mean'])}, from {people(t.loc[hi, 'count'])}) "
        f"and lowest for {lo} ({num(t.loc[lo, 'mean'])}, from {people(t.loc[lo, 'count'])}), a difference of {num(diff)}. "
        f"The table also gives each group's median and standard deviation."
    )


def describe_test(r):
    p = r["p"]
    significant = p < LEVEL
    kind = r["kind"]
    n = r.get("n", 0)
    parts = []
    if kind == "ttest":
        out, grp = r["outcome"], r["grouping"]
        parts.append(f"A Welch t-test asks whether the average {out} differs between the two {grp} groups by more than chance would explain. It does not assume the two groups have equal spread.")
        parts.append(f"The result is t = {abs(r['statistic']):.2f} with about {r['df']:.1f} degrees of freedom, {show_p(p)}.")
        if significant:
            parts.append("Because p is below 0.05, the difference between the two averages is statistically significant in this sample.")
        else:
            parts.append("Because p is 0.05 or higher, this sample does not give enough evidence of a real difference. The gap seen could be due to chance.")
    elif kind == "anova":
        out, grp = r["outcome"], r["grouping"]
        parts.append(f"A one-way ANOVA asks whether the average {out} differs across the {r['groups']} {grp} groups. It shows whether at least one group differs, not which one.")
        parts.append(f"The result is F = {r['statistic']:.2f} with {r['df'][0]} and {r['df'][1]} degrees of freedom, {show_p(p)}.")
        if significant:
            parts.append("Because p is below 0.05, at least one group average differs from the others in this sample.")
        else:
            parts.append("Because p is 0.05 or higher, this sample does not give enough evidence that the group averages differ. The gaps seen could be due to chance.")
    elif kind == "correlation":
        a, b = r["first"], r["split"]
        direction = "positive" if r["statistic"] > 0 else "negative"
        parts.append(f"A correlation asks whether {a} and {b} move together. The value r runs from -1 to +1, and 0 means no straight-line relationship.")
        parts.append(f"Here r = {r['statistic']:.2f}, a {r['effect_label']} {direction} relationship based on {n} respondents who answered both, {show_p(p)}.")
        if r["statistic"] > 0:
            parts.append(f"Higher {a} tends to go with higher {b}.")
        else:
            parts.append(f"Higher {a} tends to go with lower {b}.")
        if significant:
            parts.append("Because p is below 0.05, the relationship is statistically significant in this sample.")
        else:
            parts.append("Because p is 0.05 or higher, this sample does not give enough evidence of a real relationship. The pattern seen could be due to chance.")
        parts.append(f"The Spearman rank correlation, which suits ratings and data with extreme values, is rho = {r['rho']:.2f} ({show_p(r['p_rho'])}).")
        parts.append(f"About {r['statistic'] ** 2 * 100:.0f} percent of the variation is shared, in a straight-line sense.")
    else:
        a, b = r["first"], r["split"]
        parts.append(f"A chi-square test asks whether {a} and {b} are associated, meaning whether the pattern across one column changes depending on the other.")
        dof = "1 degree of freedom" if r["df"] == 1 else f"{r['df']} degrees of freedom"
        parts.append(f"The result is chi-square = {r['statistic']:.2f} with {dof}, {show_p(p)}.")
        if significant:
            parts.append("Because p is below 0.05, the association is statistically significant in this sample.")
        else:
            parts.append("Because p is 0.05 or higher, this sample does not give enough evidence of an association. The pattern seen could be due to chance.")
        cell = r["cell"]
        parts.append(f"The combination that departs most from what chance alone would give is {cell['row']} with {cell['column']}: {people(cell['observed'])} observed against about {cell['expected']:.1f} expected.")
    if kind != "correlation" and r.get("effect_label") not in (None, "unknown"):
        parts.append(f"The effect size ({r['effect_name']}) is {abs(r['effect']):.2f}, which is {r['effect_label']}. The p-value shows whether a pattern would be surprising under chance, while the effect size shows how big it is.")
    if not significant and n and n < 30:
        parts.append("With so few respondents, a real pattern could easily go undetected.")
    parts.append("A pattern in a sample does not show that one column causes the other.")
    return " ".join(parts)


def build_ai_prompt(topic, report_text, log):
    lines = [
        "You are helping a student write the findings of a research study.",
        "Use ONLY the findings and numbers given below. Do not use outside facts, do not invent numbers, and do not cite any sources.",
        "If a sample is small (fewer than 30 answers), say that the result is uncertain.",
        "Do not claim that one thing causes another. A pattern in a sample is not proof of cause.",
        "Write three parts: (1) the main findings in plain language, quoting the numbers, (2) what the findings might mean for the research topic, (3) the limitations of this data.",
        "Where the numbers do not support a statement, say that the data does not show it.",
        "",
        f"Research topic: {topic}" if topic else "Research topic: not given.",
        "",
        "Findings computed from the data:",
        report_text,
        "",
        "Data cleaning decisions made by the researcher:",
    ]
    lines.extend(log if log else ["No changes were made."])
    return "\n".join(lines)
