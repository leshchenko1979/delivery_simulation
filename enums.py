from enum import Enum


class OperationTypes(Enum):
    DROPOFF = 1
    PICKUP = 2


class ParcelMoverTimer(Enum):
    AWAIT_DISPATCH_EMPTY = 1
    AWAIT_DISPATCH_LOADED = 2
    LOADING = 3
    UNLOADING = 4
    MOVE_LOADED = 5
    MOVE_EMPTY = 6


class ParcelTimer(Enum):
    AWAIT_COURIER = 0
    AWAIT_TRUCK = 1
    MOVE_COURIER = 2
    MOVE_TRUCK = 3