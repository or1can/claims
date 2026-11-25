from math import ceil

from depot.limits import CASE_SIZES


def case_size(case):
    return CASE_SIZES[case]


def whole_cases(quantity, case):
    return ceil(quantity / case_size(case))


def describe(quantity, case):
    cases, loose = divmod(quantity, case_size(case))
    if not loose:
        return f"{cases} cases"
    return f"{cases} cases and {loose} loose"
