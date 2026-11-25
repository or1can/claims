from depot.limits import LOW_STOCK_RATIO


class LowStockAlert:
    def __init__(self, ledger, send):
        self._ledger = ledger
        self._send = send
        self._sent = set()

    def __call__(self, movement):
        low = {item.code for item in self._ledger.low_stock(LOW_STOCK_RATIO)}
        if movement.item in low and movement.item not in self._sent:
            self._sent.add(movement.item)
            self._send(f"{movement.item} is running low")
        self._sent &= low
