from dataclasses import dataclass, field
from datetime import datetime, timedelta

from depot.errors import NotEnoughStock, UnknownBin, UnknownHold, UnknownItem
from depot.limits import HOLD_MINUTES, MAX_HOLD_MINUTES


@dataclass(frozen=True)
class Item:
    code: str
    title: str
    case: str = "medium"
    reorder_at: int = 0
    supplier: str | None = None


@dataclass
class Bin:
    code: str
    zone: str
    quantities: dict[str, int] = field(default_factory=dict)
    closed: bool = False

    def quantity(self, item_code):
        return self.quantities.get(item_code, 0)

    def is_empty(self):
        return not any(self.quantities.values())


@dataclass(frozen=True)
class Movement:
    number: int
    kind: str
    item: str
    bin: str
    quantity: int
    at: datetime
    actor: str
    reason: str = ""


@dataclass
class Hold:
    number: int
    item: str
    quantity: int
    placed_at: datetime
    expires_at: datetime
    customer: str
    priority: int = 0


class Ledger:
    def __init__(self, clock=datetime.now):
        self._clock = clock
        self._items = {}
        self._bins = {}
        self._holds = {}
        self._movements = []
        self._next_hold = 1
        self._watchers = []

    # Items and bins

    def add_item(self, item):
        if item.code in self._items:
            raise ValueError(f"item {item.code} is already listed")
        self._items[item.code] = item
        return item

    def item(self, item_code):
        try:
            return self._items[item_code]
        except KeyError:
            raise UnknownItem(item_code) from None

    def items(self):
        return sorted(self._items.values(), key=lambda item: item.code)

    def add_bin(self, code, zone):
        if code in self._bins:
            raise ValueError(f"bin {code} is already listed")
        self._bins[code] = Bin(code, zone)
        return self._bins[code]

    def bin(self, bin_code):
        try:
            return self._bins[bin_code]
        except KeyError:
            raise UnknownBin(bin_code) from None

    def bins(self, zone=None):
        found = [b for b in self._bins.values() if zone is None or b.zone == zone]
        return sorted(found, key=lambda b: b.code)

    def open_bins(self, zone=None):
        return [b for b in self.bins(zone) if not b.closed]

    def close_bin(self, bin_code):
        found = self.bin(bin_code)
        if not found.is_empty():
            raise ValueError(f"bin {bin_code} still holds stock")
        found.closed = True

    def reopen_bin(self, bin_code):
        self.bin(bin_code).closed = False

    # Counting

    def on_hand(self, item_code):
        self.item(item_code)
        return sum(b.quantity(item_code) for b in self._bins.values())

    def held(self, item_code):
        self.item(item_code)
        now = self._clock()
        return sum(
            hold.quantity
            for hold in self._holds.values()
            if hold.item == item_code and hold.expires_at > now
        )

    def available(self, item_code):
        return self.on_hand(item_code) - self.held(item_code)

    def bins_holding(self, item_code):
        self.item(item_code)
        return [b for b in self.bins() if b.quantity(item_code)]

    def zone_totals(self, zone):
        totals = {}
        for found in self.bins(zone):
            for item_code, quantity in found.quantities.items():
                totals[item_code] = totals.get(item_code, 0) + quantity
        return totals

    # Watchers

    def watch(self, watcher):
        self._watchers.append(watcher)

    def unwatch(self, watcher):
        self._watchers.remove(watcher)

    def _record(self, kind, item_code, bin_code, quantity, actor, reason=""):
        movement = Movement(
            number=len(self._movements) + 1,
            kind=kind,
            item=item_code,
            bin=bin_code,
            quantity=quantity,
            at=self._clock(),
            actor=actor,
            reason=reason,
        )
        self._movements.append(movement)
        for watcher in self._watchers:
            watcher(movement)
        return movement

    # Stock coming in and going out

    def receive(self, item_code, bin_code, quantity, actor):
        if quantity <= 0:
            raise ValueError("a receipt has to be of at least one")
        self.item(item_code)
        target = self.bin(bin_code)
        if target.closed:
            raise ValueError(f"bin {bin_code} is closed")
        target.quantities[item_code] = target.quantity(item_code) + quantity
        return self._record("receive", item_code, bin_code, quantity, actor)

    def dispatch(self, item_code, quantity, actor):
        if quantity <= 0:
            raise ValueError("a dispatch has to be of at least one")
        if self.available(item_code) < quantity:
            raise NotEnoughStock(item_code)
        taken = []
        wanted = quantity
        for source in self.bins_holding(item_code):
            portion = min(wanted, source.quantity(item_code))
            source.quantities[item_code] -= portion
            taken.append(self._record("dispatch", item_code, source.code, -portion, actor))
            wanted -= portion
            if not wanted:
                break
        return taken

    def transfer(self, item_code, from_code, to_code, quantity, actor):
        source = self.bin(from_code)
        target = self.bin(to_code)
        if target.closed:
            raise ValueError(f"bin {to_code} is closed")
        if source.quantity(item_code) < quantity:
            raise NotEnoughStock(item_code)
        source.quantities[item_code] -= quantity
        target.quantities[item_code] = target.quantity(item_code) + quantity
        self._record("transfer", item_code, from_code, -quantity, actor)
        return self._record("transfer", item_code, to_code, quantity, actor)

    def count(self, item_code, bin_code, counted, actor):
        if counted < 0:
            raise ValueError("a count can't be negative")
        found = self.bin(bin_code)
        difference = counted - found.quantity(item_code)
        found.quantities[item_code] = counted
        return self._record("count", item_code, bin_code, difference, actor, "counted")

    # Movements

    def movements(self, item_code=None, kind=None, since=None):
        found = []
        for movement in self._movements:
            if item_code is not None and movement.item != item_code:
                continue
            if kind is not None and movement.kind != kind:
                continue
            if since is not None and movement.at < since:
                continue
            found.append(movement)
        return found

    def last_movement(self, item_code):
        for movement in reversed(self._movements):
            if movement.item == item_code:
                return movement
        return None

    def net_change(self, item_code, since):
        return sum(m.quantity for m in self.movements(item_code, since=since))

    def busiest_bins(self, since, limit=5):
        counts = {}
        for movement in self.movements(since=since):
            counts[movement.bin] = counts.get(movement.bin, 0) + 1
        ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
        return ranked[:limit]

    def rebuild(self):
        rebuilt = {code: {} for code in self._bins}
        for movement in self._movements:
            quantities = rebuilt[movement.bin]
            quantities[movement.item] = quantities.get(movement.item, 0) + movement.quantity
        for code, quantities in rebuilt.items():
            self._bins[code].quantities = quantities

    # Reports

    def low_stock(self, ratio):
        low = []
        for item in self.items():
            if not item.reorder_at:
                continue
            if self.available(item.code) <= item.reorder_at * (1 + ratio):
                low.append(item)
        return low

    def idle_items(self, since):
        moved = {movement.item for movement in self.movements(since=since)}
        return [item for item in self.items() if item.code not in moved]

    def zone_report(self):
        zones = sorted({b.zone for b in self._bins.values()})
        return {zone: self.zone_totals(zone) for zone in zones}

    def snapshot(self):
        return {
            b.code: dict(sorted(b.quantities.items()))
            for b in self.bins()
            if not b.is_empty()
        }

    # Holds

    def place_hold(self, item_code, quantity, customer, minutes=None, priority=0):
        if quantity <= 0:
            raise ValueError("a hold has to be of at least one")
        if self.available(item_code) < quantity:
            raise NotEnoughStock(item_code)
        length = HOLD_MINUTES if minutes is None else min(minutes, MAX_HOLD_MINUTES)
        now = self._clock()
        hold = Hold(
            number=self._next_hold,
            item=item_code,
            quantity=quantity,
            placed_at=now,
            expires_at=now + timedelta(minutes=length),
            customer=customer,
            priority=priority,
        )
        self._next_hold += 1
        self._holds[hold.number] = hold
        return hold

    def hold(self, number):
        try:
            return self._holds[number]
        except KeyError:
            raise UnknownHold(number) from None

    def holds(self, item_code=None):
        found = [h for h in self._holds.values() if item_code is None or h.item == item_code]
        return sorted(found, key=lambda h: h.number)

    def cancel_hold(self, number):
        self.hold(number)
        del self._holds[number]

    def extend_hold(self, number, minutes):
        hold = self.hold(number)
        latest = hold.placed_at + timedelta(minutes=MAX_HOLD_MINUTES)
        hold.expires_at = min(hold.expires_at + timedelta(minutes=minutes), latest)
        return hold

    def expire_holds(self):
        now = self._clock()
        expired = [h for h in self.holds() if h.expires_at <= now]
        for hold in expired:
            del self._holds[hold.number]
        return expired

    def next_hold(self, item_code):
        waiting = self.holds(item_code)
        if not waiting:
            return None
        return min(waiting, key=lambda h: (-h.priority, h.placed_at, h.number))

    def fulfil_next(self, item_code, actor):
        hold = self.next_hold(item_code)
        if hold is None:
            return []
        del self._holds[hold.number]
        return self.dispatch(hold.item, hold.quantity, actor)

    # Corrections

    def write_off(self, item_code, bin_code, quantity, actor, reason):
        found = self.bin(bin_code)
        if found.quantity(item_code) < quantity:
            raise NotEnoughStock(item_code)
        found.quantities[item_code] -= quantity
        return self._record("write-off", item_code, bin_code, -quantity, actor, reason)

    def merge_bins(self, from_code, to_code, actor):
        source = self.bin(from_code)
        target = self.bin(to_code)
        if target.closed:
            raise ValueError(f"bin {to_code} is closed")
        for item_code in sorted(source.quantities):
            quantity = source.quantity(item_code)
            if quantity:
                self.transfer(item_code, from_code, to_code, quantity, actor)
        source.closed = True

    def empty_zone(self, zone):
        for found in self.bins(zone):
            found.quantities.clear()
