def find_blank(table, column):
    return table[table[column].isna()]


def find_out_of_range(table, column, low, high):
    return table[(table[column] < low) | (table[column] > high)]


def find_problems(table, ranges):
    problems = []
    for column in table.columns:
        for index in find_blank(table, column).index:
            problems.append({"row": index, "column": column, "kind": "blank", "value": None})
        if column in ranges:
            low, high = ranges[column]
            for index in find_out_of_range(table, column, low, high).index:
                problems.append({"row": index, "column": column, "kind": "range", "value": table.loc[index, column]})
    return problems


def describe(p, ranges):
    if p["kind"] == "blank":
        return "blank answer"
    low, high = ranges[p["column"]]
    return f"value {p['value']} outside {low} to {high}"


def apply_decisions(table, decisions):
    working = table.copy()
    log = []
    for d in decisions:
        where = f"Row {d['row'] + 1}, {d['column']}: {d['issue']}"
        if d["action"] == "fix":
            working.loc[d["row"], d["column"]] = d["value"]
            log.append(f"{where}, fixed to {d['value']}")
        elif d["action"] == "exclude":
            working.loc[d["row"], d["column"]] = float("nan")
            log.append(f"{where}, excluded")
        else:
            log.append(f"{where}, kept")
    return working, log