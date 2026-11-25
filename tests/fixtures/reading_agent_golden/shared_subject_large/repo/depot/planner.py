from dataclasses import dataclass
from math import ceil

from depot.limits import LOW_STOCK_RATIO, MAX_PLAN_LINES
from depot.units import case_size, whole_cases


@dataclass(frozen=True)
class Line:
    item: str
    title: str
    quantity: int
    cases: int
    supplier: str | None
    urgent: bool = False


@dataclass(frozen=True)
class Plan:
    lines: tuple[Line, ...]
    left_out: tuple[str, ...] = ()

    def total(self):
        return sum(line.quantity for line in self.lines)

    def suppliers(self):
        return sorted({line.supplier for line in self.lines if line.supplier})

    def for_supplier(self, supplier):
        return [line for line in self.lines if line.supplier == supplier]

    def urgent_lines(self):
        return [line for line in self.lines if line.urgent]


class Planner:
    def __init__(self, ledger, ratio=LOW_STOCK_RATIO):
        self._ledger = ledger
        self._ratio = ratio
        self._skipped = set()
        self._targets = {}

    # Choosing items

    def skip(self, item_code):
        self._ledger.item(item_code)
        self._skipped.add(item_code)

    def unskip(self, item_code):
        self._skipped.discard(item_code)

    def skipped(self):
        return sorted(self._skipped)

    def set_target(self, item_code, quantity):
        if quantity < 0:
            raise ValueError("a target can't be negative")
        self._ledger.item(item_code)
        self._targets[item_code] = quantity

    def clear_target(self, item_code):
        self._targets.pop(item_code, None)

    def target(self, item):
        return self._targets.get(item.code, 2 * item.reorder_at)

    def candidates(self):
        return [item for item in self._ledger.low_stock(self._ratio) if item.code not in self._skipped]

    # Working out quantities

    def shortfall(self, item):
        return max(0, self.target(item) - self._ledger.available(item.code))

    def is_urgent(self, item):
        return self._ledger.available(item.code) <= 0

    def days_left(self, item, since, now):
        days = max(1, (now - since).days)
        used = -sum(
            movement.quantity
            for movement in self._ledger.movements(item.code, kind="dispatch", since=since)
        )
        if not used:
            return None
        return self._ledger.available(item.code) / (used / days)

    def slow_movers(self, since, now, threshold=90):
        slow = []
        for item in self._ledger.items():
            left = self.days_left(item, since, now)
            if left is None or left > threshold:
                slow.append(item)
        return slow

    def fast_movers(self, since, now, threshold=7):
        fast = []
        for item in self._ledger.items():
            left = self.days_left(item, since, now)
            if left is not None and left < threshold:
                fast.append(item)
        return fast

    # Reading a plan back

    def describe(self, plan):
        rows = []
        for line in plan.lines:
            mark = "!" if line.urgent else " "
            supplier = line.supplier or "-"
            rows.append(f"{mark} {line.item:<12} {line.quantity:>6} {line.cases:>4} {supplier}")
        for item_code in plan.left_out:
            rows.append(f"  {item_code:<12} left out")
        return "\n".join(rows)

    def compare(self, earlier, later):
        before = {line.item: line.quantity for line in earlier.lines}
        after = {line.item: line.quantity for line in later.lines}
        changes = {}
        for item_code in sorted(before | after):
            difference = after.get(item_code, 0) - before.get(item_code, 0)
            if difference:
                changes[item_code] = difference
        return changes

    def share(self, plan):
        total = plan.total()
        if not total:
            return {}
        return {line.item: line.quantity / total for line in plan.lines}

    def by_zone(self, plan):
        zones = {}
        for line in plan.lines:
            for found in self._ledger.bins_holding(line.item):
                zones.setdefault(found.zone, []).append(line.item)
        return {zone: sorted(set(items)) for zone, items in sorted(zones.items())}

    def room_for(self, plan, per_bin):
        bins = len(self._ledger.open_bins())
        return plan.total() <= bins * per_bin

    def missing(self, plan):
        planned = {line.item for line in plan.lines}
        return [item.code for item in self.candidates() if item.code not in planned]

    # Checking a delivery against a plan

    def check_delivery(self, plan, delivered):
        wanted = {line.item: line.quantity for line in plan.lines}
        problems = []
        for item_code, quantity in sorted(delivered.items()):
            if item_code not in wanted:
                problems.append(f"{item_code} was not ordered")
            elif quantity < wanted[item_code]:
                problems.append(f"{item_code} is {wanted[item_code] - quantity} short")
            elif quantity > wanted[item_code]:
                problems.append(f"{item_code} is {quantity - wanted[item_code]} over")
        for item_code in sorted(wanted.keys() - delivered.keys()):
            problems.append(f"{item_code} did not arrive")
        return problems

    def accept_delivery(self, plan, delivered, bin_code, actor):
        problems = self.check_delivery(plan, delivered)
        for item_code, quantity in sorted(delivered.items()):
            if quantity:
                self._ledger.receive(item_code, bin_code, quantity, actor)
        return problems

    # Making a plan

    def _line(self, item):
        cases = whole_cases(self.shortfall(item), item.case)
        return Line(
            item=item.code,
            title=item.title,
            quantity=cases * case_size(item.case),
            cases=cases,
            supplier=item.supplier,
            urgent=self.is_urgent(item),
        )

    def _order(self, lines):
        return sorted(lines, key=lambda line: (not line.urgent, -line.quantity, line.item))

    def plan(self):
        lines = [self._line(item) for item in self.candidates()]
        lines = self._order([line for line in lines if line.cases])
        kept = lines[:MAX_PLAN_LINES]
        return Plan(tuple(kept), tuple(line.item for line in lines[MAX_PLAN_LINES:]))

    def split(self, plan, parts):
        size = ceil(len(plan.lines) / parts)
        return [Plan(plan.lines[i : i + size]) for i in range(0, len(plan.lines), size)] if size else []

    def merge(self, plans):
        merged = {}
        for plan in plans:
            for line in plan.lines:
                merged[line.item] = line
        return Plan(tuple(self._order(merged.values())))

    def top_up(self, plan):
        planned = {line.item for line in plan.lines}
        room = MAX_PLAN_LINES - len(plan.lines)
        extra = []
        for item in self._ledger.items():
            if item.code in planned or item.code in self._skipped:
                continue
            line = self._line(item)
            if line.cases:
                extra.append(line)
        return Plan(plan.lines + tuple(self._order(extra)[:room]), plan.left_out)
