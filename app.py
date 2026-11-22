import math
import altair as alt
import pandas as pd
import streamlit as st
from checks import find_problems, describe, apply_decisions
from stat_tests import run_test
from word_export import build_docx
from charts import bar_png, grouped_bar_png, pyramid_png, pie_png
from findings import (
    describe_cleaning,
    describe_number,
    describe_distribution,
    describe_categories,
    describe_cross,
    describe_pyramid,
    describe_group_stats,
    describe_test,
    build_ai_prompt,
)

st.title("Research Data Check")

uploaded = st.file_uploader("Upload your responses (CSV file)", type="csv")

if "decisions" not in st.session_state:
    st.session_state.decisions = []


def tidy(x):
    return int(x) if float(x).is_integer() else x


def guess_type(df, column):
    name = column.lower()
    if name in ("id", "no", "serial", "index") or name.endswith("_id"):
        return "Ignore"
    if column not in df.select_dtypes("number").columns:
        return "Category"
    if df[column].nunique() <= 2:
        return "Category"
    return "Number"


def make_groups(values, width, start):
    if start is None:
        start = (values.min() // width) * width
    count = int((values.max() - start) // width) + 1
    if count < 1:
        return None
    edges = [start + i * width for i in range(count + 1)]
    whole = all(float(e).is_integer() for e in edges) and bool((values % 1 == 0).all())
    labels = []
    for i in range(count):
        low_edge = edges[i]
        high_edge = edges[i + 1]
        if whole:
            last = int(high_edge) - 1
            if last == int(low_edge):
                labels.append(str(int(low_edge)))
            else:
                labels.append(f"{int(low_edge)}-{last}")
        else:
            labels.append(f"{low_edge:g} to under {high_edge:g}")
    return pd.cut(values, bins=edges, right=False, labels=labels)


def auto_width(values):
    spread = values.max() - values.min()
    raw = spread / 8 if spread > 0 else 1
    magnitude = 10 ** math.floor(math.log10(raw))
    whole = bool((values % 1 == 0).all())
    for step in (1, 2, 2.5, 5, 10):
        width = step * magnitude
        if width >= raw and (not whole or float(width).is_integer()):
            break
    return width


def show_bar(counts):
    data = pd.DataFrame({"group": counts.index.astype(str), "count": counts.values})
    chart = alt.Chart(data).mark_bar().encode(
        x=alt.X("group:N", sort=list(data["group"])),
        y="count:Q",
    )
    st.altair_chart(chart)


def show_pie(counts):
    data = pd.DataFrame({"answer": counts.index.astype(str), "count": counts.values})
    chart = alt.Chart(data).mark_arc().encode(theta="count:Q", color="answer:N")
    st.altair_chart(chart)


def labelled(clean, column, number_columns, group_settings):
    if column not in number_columns:
        return clean[column]
    values = clean[column].dropna()
    if len(values) == 0:
        return None
    width, start = group_settings.get(column, (auto_width(values), None))
    return make_groups(values, width, start)


def show_grouped_bar(table):
    order = list(table.index)
    long = table.reset_index().melt(id_vars="group", var_name="split", value_name="count")
    chart = alt.Chart(long).mark_bar().encode(
        x=alt.X("group:N", sort=order),
        y="count:Q",
        color="split:N",
        xOffset="split:N",
    )
    st.altair_chart(chart)


def show_pyramid(table):
    order = list(table.index)
    biggest = max(int(table.values.max()), 1)
    names = list(table.columns)
    left = pd.DataFrame({"group": order, "count": table[names[0]].values})
    right = pd.DataFrame({"group": order, "count": table[names[1]].values})
    left_chart = alt.Chart(left).mark_bar(color="#4c78a8").encode(
        y=alt.Y("group:N", sort=order[::-1], title=None),
        x=alt.X("count:Q", scale=alt.Scale(domain=[0, biggest], reverse=True), title=names[0]),
    ).properties(width=250)
    right_chart = alt.Chart(right).mark_bar(color="#f58518").encode(
        y=alt.Y("group:N", sort=order[::-1], axis=None),
        x=alt.X("count:Q", scale=alt.Scale(domain=[0, biggest]), title=names[1]),
    ).properties(width=250)
    st.altair_chart(alt.hconcat(left_chart, right_chart))


if uploaded is not None:
    if st.session_state.get("file_name") != uploaded.name:
        st.session_state.decisions = []
        st.session_state.file_name = uploaded.name

    df = pd.read_csv(uploaded)
    decisions = st.session_state.decisions
    numeric_dtype = df.select_dtypes("number").columns.tolist()
    report = []
    blocks = []

    def say(text, title=None):
        if not text:
            return
        st.info(text.replace("$", "\\$"))
        report.append(f"{title}: {text}" if title else text)
        if title:
            blocks.append(("h3", title))
        blocks.append(("text", text))

    st.subheader("Column types")
    st.write("Check how each column should be treated, and change any that are wrong.")
    types = {}
    with st.expander("Show column types", expanded=True):
        for column in df.columns:
            if column in numeric_dtype:
                options = ["Number", "Category", "Ignore"]
            else:
                options = ["Category", "Ignore"]
            default = guess_type(df, column)
            types[column] = st.selectbox(column, options, index=options.index(default), key="type_" + column)

    number_columns = [c for c in df.columns if types[c] == "Number"]
    category_columns = [c for c in df.columns if types[c] == "Category"]
    checked = df[[c for c in df.columns if types[c] != "Ignore"]]

    st.subheader("Allowed ranges (optional)")
    st.write("For any number column, type the lowest and highest allowed value to check it.")
    rules = {}
    for column in number_columns:
        left, right = st.columns(2)
        low = left.number_input(f"{column}: lowest allowed", value=None, key="low_" + column)
        high = right.number_input(f"{column}: highest allowed", value=None, key="high_" + column)
        if low is not None and high is not None:
            rules[column] = (tidy(low), tidy(high))

    st.subheader("Groups for number columns (optional)")
    st.write("To group a number column, type the group width, such as 10 for 0-9, 10-19. Leave empty for automatic whole-number groups.")
    group_settings = {}
    for column in number_columns:
        left, right = st.columns(2)
        width = left.number_input(f"{column}: group width", value=None, min_value=0.0, key="width_" + column)
        start = right.number_input(f"{column}: first group starts at", value=None, key="start_" + column)
        if width:
            group_settings[column] = (width, start)

    problems = find_problems(checked, rules)
    decided = [(d["row"], d["column"]) for d in decisions]
    open_problems = [p for p in problems if (p["row"], p["column"]) not in decided]

    st.subheader("Problems to review")
    if not open_problems:
        st.success("All problems have been reviewed.")
    else:
        st.write(f"{len(open_problems)} problems open. Showing the first 20.")

    for p in open_problems[:20]:
        issue = describe(p, rules)
        key = f"{p['row']}_{p['column']}"
        with st.container(border=True):
            st.write(f"Row {p['row'] + 1}, {p['column']}: {issue}")
            bounds = rules.get(p["column"])
            min_v = float(bounds[0]) if bounds else None
            max_v = float(bounds[1]) if bounds else None
            if p["column"] in numeric_dtype:
                value = st.number_input("Correct value", value=None, min_value=min_v, max_value=max_v, key="value_" + key)
            else:
                value = st.text_input("Correct value", key="value_" + key) or None
            fix, exclude, keep = st.columns(3)
            if fix.button("Fix", key="fix_" + key):
                if value is None:
                    st.error("Type the correct value first.")
                else:
                    decisions.append({"row": p["row"], "column": p["column"], "issue": issue, "action": "fix", "value": value})
                    st.rerun()
            if exclude.button("Exclude", key="exclude_" + key):
                decisions.append({"row": p["row"], "column": p["column"], "issue": issue, "action": "exclude"})
                st.rerun()
            if keep.button("Keep", key="keep_" + key):
                decisions.append({"row": p["row"], "column": p["column"], "issue": issue, "action": "keep"})
                st.rerun()

    clean, log = apply_decisions(df, decisions)

    st.subheader("Cleaning log")
    if not log:
        st.write("No decisions yet.")
    for entry in log:
        st.write(entry)
    if decisions and st.button("Undo last decision"):
        decisions.pop()
        st.rerun()

    st.subheader("Results")
    st.metric("Total responses in file", len(clean))
    blocks.append(("h1", "Data and cleaning"))
    say(describe_cleaning(len(clean), len(number_columns) + len(category_columns), decisions, len(open_problems)), "Data overview")
    blocks.append(("h2", "Cleaning log"))
    if log:
        for entry in log:
            blocks.append(("text", entry))
    else:
        blocks.append(("text", "No changes were made to the data."))

    if number_columns:
        st.write("Number columns")
        numbers = clean[number_columns]
        summary = pd.DataFrame({
            "answered": numbers.count(),
            "missing": numbers.isna().sum(),
            "mean": numbers.mean().round(2),
            "median": numbers.median().round(2),
            "std dev": numbers.std().round(2),
            "min": numbers.min(),
            "max": numbers.max(),
        })
        summary.index.name = "column"
        st.dataframe(summary)
        blocks.append(("h1", "Number columns"))
        blocks.append(("table", "Summary of number columns", summary))
        for column in number_columns:
            say(describe_number(column, len(clean), summary.loc[column]), f"Summary of {column}")

        for column in number_columns:
            values = clean[column].dropna()
            if len(values) == 0:
                continue
            st.write(f"Distribution of {column}")
            width, start = group_settings.get(column, (auto_width(values), None))
            groups = make_groups(values, width, start)
            if groups is None:
                st.warning(f"The first group for {column} starts above every value. Lower the start.")
                continue
            outside = int(groups.isna().sum())
            if outside:
                st.warning(f"{outside} values fall below the first group and are not shown.")
            counts = groups.value_counts(sort=False)
            counts.index = counts.index.astype(str)
            percent = (counts / counts.sum() * 100).round(1)
            dist = pd.DataFrame({"count": counts, "percent": percent})
            dist.index.name = "group"
            st.dataframe(dist)
            show_bar(counts)
            blocks.append(("table", f"Distribution of {column}", dist))
            blocks.append(("image", f"Chart: distribution of {column}", bar_png(list(counts.index), list(counts.values), f"Distribution of {column}")))
            say(describe_distribution(column, counts), f"Distribution of {column}")

    if category_columns:
        blocks.append(("h1", "Category columns"))
    for column in category_columns:
        counts = clean[column].value_counts()
        if len(counts) == 0:
            continue
        st.write(f"Answers for {column}")
        total = clean[column].count()
        if len(counts) > 10:
            st.write(f"Showing the 10 most common of {len(counts)} values.")
            counts = counts.head(10)
        percent = (counts / total * 100).round(1)
        table = pd.DataFrame({"count": counts, "percent": percent})
        table.index = table.index.astype(str)
        table.index.name = column
        st.dataframe(table)
        if len(counts) == 2:
            show_pie(counts)
        else:
            show_bar(counts)
        blocks.append(("table", f"Answers for {column}", table))
        if len(counts) == 2:
            blocks.append(("image", f"Chart: answers for {column}", pie_png(list(counts.index), list(counts.values), f"Answers for {column}")))
        else:
            blocks.append(("image", f"Chart: answers for {column}", bar_png(list(counts.index), list(counts.values), f"Answers for {column}")))
        say(describe_categories(column, counts, int(total)), f"Answers for {column}")

    st.subheader("Compare columns")
    st.write("Pick two columns to compare, such as age by gender. Any number or category column can be used for either.")
    compare_options = number_columns + category_columns
    if len(compare_options) >= 2:
        first = st.selectbox("Column to analyse", compare_options, key="cmp_first")
        split_options = [c for c in compare_options if c != first]
        split = st.selectbox("Split by", split_options, key="cmp_split")
        a = labelled(clean, first, number_columns, group_settings)
        b = labelled(clean, split, number_columns, group_settings)
        if a is None or b is None:
            st.warning("One of the chosen columns has no answers, or its groups start above every value.")
        else:
            data = pd.DataFrame({"a": a, "b": b}).dropna()
            for name, column in (("a", first), ("b", split)):
                if column not in number_columns:
                    top = data[name].value_counts().head(10).index
                    data = data[data[name].isin(top)]
            if data.empty:
                st.warning("No rows have answers for both columns.")
            else:
                table = pd.crosstab(data["a"], data["b"])
                if isinstance(data["a"].dtype, pd.CategoricalDtype):
                    table = table.reindex(list(data["a"].cat.categories), fill_value=0)
                if isinstance(data["b"].dtype, pd.CategoricalDtype):
                    table = table.reindex(columns=list(data["b"].cat.categories), fill_value=0)
                table.index = table.index.astype(str)
                table.columns = table.columns.astype(str)
                table.index.name = "group"
                blocks.append(("h1", f"Comparison: {first} by {split}"))
                st.write(f"{first} by {split}: counts")
                st.dataframe(table)
                blocks.append(("table", f"{first} by {split}: counts", table))
                totals = table.sum(axis=1).replace(0, float("nan"))
                percent = table.div(totals, axis=0).mul(100).round(1).fillna(0)
                st.write(f"{first} by {split}: percent within each row")
                st.dataframe(percent)
                blocks.append(("table", f"{first} by {split}: percent within each row", percent))
                say(describe_cross(first, split, table), f"{first} by {split}")
                if first in number_columns and len(table.columns) == 2:
                    show_pyramid(table)
                    blocks.append(("image", f"Chart: {first} by {split}", pyramid_png(table, f"Pyramid of {first} by {split}")))
                    say(describe_pyramid(first, table), f"Pyramid of {first} by {split}")
                else:
                    show_grouped_bar(table)
                    blocks.append(("image", f"Chart: {first} by {split}", grouped_bar_png(table, f"{first} by {split}")))
                if first in number_columns:
                    outcome, grouping_name, grouping = first, split, data["b"]
                elif split in number_columns:
                    outcome, grouping_name, grouping = split, first, data["a"]
                else:
                    outcome = None
                if outcome is not None:
                    stats = clean.loc[data.index].groupby(grouping, observed=True)[outcome].agg(["count", "mean", "median", "std"]).round(2)
                    stats.index = stats.index.astype(str)
                    stats.index.name = grouping_name
                    st.write(f"Summary of {outcome} for each {grouping_name} group")
                    st.dataframe(stats)
                    blocks.append(("table", f"Summary of {outcome} for each {grouping_name} group", stats))
                    say(describe_group_stats(outcome, grouping_name, stats), f"Average {outcome} by {grouping_name}")
                result = run_test(clean, data, first, split, number_columns)
                st.write("Statistical test")
                if result is None:
                    st.info("There is not enough data or variation in these groups to run a test.")
                else:
                    st.write(result["text"])
                    say(describe_test(result), f"{result['test']}: {first} by {split}")
                    for note in result["notes"]:
                        st.warning(note)
                    st.caption("The p-value is the chance of seeing a pattern at least this strong if there were no real difference. Below 0.05 is the usual cut-off for significance. A significant result shows a pattern in this sample. It does not show that one column causes the other.")

    st.subheader("Findings summary")
    report_text = "\n\n".join(report)
    st.text_area("Copy these findings into your report", report_text, height=300)

    st.subheader("Prepare for AI")
    topic = st.text_input("Research topic (optional)", key="topic")
    st.write("Copy the text below into an AI chat to get findings and implications based only on your numbers.")
    st.code(build_ai_prompt(topic, report_text, log), language=None)

    st.subheader("Word report")
    st.write("Download your findings, tables and cleaning log as an editable Word document.")
    blocks.append(("h1", "How to read this report"))
    blocks.append(("text", "The findings are written from the numbers in the tables. A p-value below 0.05 is the usual cut-off for statistical significance, and the effect size shows how large a pattern is. Groups with fewer than 30 answers give uncertain results. A pattern in a sample does not show that one column causes another. Every change made to the data is listed in the cleaning log above."))
    st.download_button(
        "Download Word report",
        build_docx("Research Data Report", topic, blocks),
        file_name="research_report.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    st.subheader("Cleaned data")
    st.dataframe(clean)
    st.download_button("Download cleaning log", "\n".join(log), file_name="cleaning_log.txt")
