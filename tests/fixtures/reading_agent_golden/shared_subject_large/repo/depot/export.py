import csv
import json


def movements_csv(ledger, out, since=None):
    writer = csv.writer(out)
    writer.writerow(["number", "kind", "item", "bin", "quantity", "at", "reason"])
    for m in ledger.movements(since=since):
        writer.writerow([m.number, m.kind, m.item, m.bin, m.quantity, m.at.isoformat(), m.reason])


def snapshot_json(ledger, out):
    json.dump(ledger.snapshot(), out, indent=2, sort_keys=True)


def daily_summary(ledger, since):
    rows = {}
    for m in ledger.movements(since=since):
        row = rows.setdefault(m.actor, {"movements": 0, "units": 0})
        row["movements"] += 1
        row["units"] += abs(m.quantity)
    return rows
