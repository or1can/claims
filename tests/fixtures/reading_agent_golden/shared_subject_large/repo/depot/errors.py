class DepotError(Exception):
    pass


class UnknownItem(DepotError):
    pass


class UnknownBin(DepotError):
    pass


class UnknownHold(DepotError):
    pass


class NotEnoughStock(DepotError):
    pass
