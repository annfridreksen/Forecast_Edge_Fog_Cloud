"""R1.4 clock: integer nanoseconds, nearest tick with ties to even.

Only primitive inputs are rounded. Calendar arithmetic is integer-only.
Resolution is a simulation convention, not hardware measurement accuracy.
"""
from decimal import Decimal, InvalidOperation

TICKS_PER_SECOND = 1_000_000_000
TICKS_PER_MS = 1_000_000


def _ratio(value):
    if isinstance(value, bool):
        raise ValueError('time/fraction cannot be Boolean')
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError('expected a finite nonnegative decimal') from exc
    if not d.is_finite() or d < 0:
        raise ValueError('expected a finite nonnegative decimal')
    return d.as_integer_ratio()


def _round_ratio(numerator, denominator):
    quotient, remainder = divmod(numerator, denominator)
    return quotient + int(2*remainder > denominator or
                          (2*remainder == denominator and quotient % 2 == 1))


def seconds_to_ticks(value):
    n, d = _ratio(value)
    return _round_ratio(n*TICKS_PER_SECOND, d)


def milliseconds_to_ticks(value):
    n, d = _ratio(value)
    return _round_ratio(n*TICKS_PER_MS, d)


def split_ticks(total, share):
    """Split an already rounded combined service without losing a tick."""
    if type(total) is not int or total < 0:
        raise ValueError('total must be nonnegative integer ticks')
    n, d = _ratio(share)
    if n > d:
        raise ValueError('share must be in [0,1]')
    first = _round_ratio(total*n, d)
    return first, total-first


TIME_CONTRACT = {'resolution_s': '0.000000001', 'calendar_unit': 'integer nanosecond',
                 'rounding': 'nearest, ties to even; primitive inputs only',
                 'intervals': 'half-open', 'equal_time': 'completion before arrival',
                 'edge_split': 'round processing share of combined ticks; transfer is remainder'}
