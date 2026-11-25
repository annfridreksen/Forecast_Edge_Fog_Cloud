"""Columnar storage adapter, not a second scheduler.

Nonnegative integer primitives are exact int64; -1 denotes an absent field.
Exported seconds/milliseconds are computed views of the same integer ticks.
Only storage changes: the event loop in model.simulate is shared by both paths.
"""
from collections.abc import MutableMapping, Sequence
import numpy as np

FLOAT_FIELDS = frozenset(('observed_rate_s', 'rho_feature'))
STATUS = ('pending', 'completed', 'dropped')


class TaskColumns(Sequence):
    """Fixed capacity; allocation is O(number_of_fields * number_of_events)."""
    def __init__(self, capacity):
        if type(capacity) is not int or capacity < 0:
            raise ValueError('nonnegative capacity required')
        self.capacity = capacity
        self.size = 0
        self.columns = {}
        self.views = {}

    def __len__(self):
        return self.size

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [TaskRow(self, i) for i in range(*index.indices(self.size))]
        if index < 0:
            index += self.size
        if not 0 <= index < self.size:
            raise IndexError(index)
        return TaskRow(self, index)

    def append(self, values):
        if self.size >= self.capacity:
            raise ValueError('task store capacity exceeded')
        row = TaskRow(self, self.size)
        self.size += 1
        row.update(values)

    @property
    def allocated_bytes(self):
        return sum(a.nbytes for a in self.columns.values())


class TaskRow(MutableMapping):
    __slots__ = ('table', 'index')

    def __init__(self, table, index):
        self.table, self.index = table, index

    def __getitem__(self, key):
        if key in self.table.views:
            source, divisor = self.table.views[key]
            return self[source] / divisor
        column = self.table.columns.get(key)
        if column is None:
            raise KeyError(key)
        value = column[self.index].item()
        if key in FLOAT_FIELDS:
            if np.isnan(value):
                raise KeyError(key)
        elif value == -1:
            raise KeyError(key)
        if key == 'status':
            return STATUS[value]
        if key == 'mobile':
            return bool(value)
        return value

    def __setitem__(self, key, value):
        if key in self.table.views:
            raise ValueError('exported times are read-only views')
        if key == 'status':
            value = STATUS.index(value)
        elif key == 'mobile':
            if type(value) is not bool:
                raise ValueError('mobile must be Boolean')
            value = int(value)
        elif key in FLOAT_FIELDS:
            if isinstance(value, bool) or not np.isfinite(value):
                raise ValueError('finite feature required')
        elif type(value) is not int or not 0 <= value < 2**63:
            raise ValueError('compact store needs nonnegative int64 primitives')
        if key not in self.table.columns:
            floating = key in FLOAT_FIELDS
            self.table.columns[key] = np.full(self.table.capacity,
                np.nan if floating else -1, dtype=np.float64 if floating else np.int64)
        self.table.columns[key][self.index] = value

    def __delitem__(self, key):
        self[key]  # preserve KeyError for absent fields
        if key in self.table.views:
            raise ValueError('cannot delete a derived view')
        self.table.columns[key][self.index] = np.nan if key in FLOAT_FIELDS else -1

    def __iter__(self):
        for key in self.table.columns:
            if key in self:
                yield key
        for key, (source, _) in self.table.views.items():
            if source in self:
                yield key

    def __contains__(self, key):
        if key in self.table.views:
            return self.table.views[key][0] in self
        column = self.table.columns.get(key)
        if column is None:
            return False
        value = column[self.index]
        return not np.isnan(value) if key in FLOAT_FIELDS else value != -1

    def __len__(self):
        return sum(1 for _ in self)


def materialize_result(result):
    """Explicit small-test/JSON export. Do not materialize large scientific runs."""
    return {**result, 'tasks': [dict(row) for row in result['tasks']]}
