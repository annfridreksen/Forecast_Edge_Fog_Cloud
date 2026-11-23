"""Read-only choice of a displayed series, never selection of a scientific plan."""
from .companion import curve_points


def choose_curve(snapshot, fog=None, buffer=None):
    """Both overrides are explicit; automatic order is presentation-only.

    The first (Fog, B) having a saved main point is shown. This is NOT a
    recommendation, a feasibility claim or an optimization of infrastructure.
    Without main data the explicit fallback 50/5 remains empty.
    """
    if (fog is None) != (buffer is None):
        raise ValueError('Укажите Fog и B вместе либо оставьте оба None')
    if fog is not None and (type(fog) is not int or fog <= 0
                           or type(buffer) is not int or buffer < 0):
        raise ValueError('Fog — положительное целое, B — неотрицательное целое')
    options = []
    if snapshot.get('state') == 'CHECKED_CHAINS':
        pairs = sorted({(r['n_fog'], r['buffer']) for r in snapshot['rows']
                        if r.get('main_sha256') and r.get('summary') is not None})
        for f, b in pairs:
            if any(curve_points(snapshot, m, f, b) for m in ('p95_ms', 'drop_fraction')):
                options.append((f, b))
    if fog is None:
        fog, buffer = options[0] if options else (50, 5)
        mode = 'FIRST_SAVED_MAIN' if options else 'EMPTY_FALLBACK'
    else:
        mode = 'EXPLICIT'
    counts = {m: len(curve_points(snapshot, m, fog, buffer))
              for m in ('p95_ms', 'drop_fraction')}
    return dict(fog=fog, buffer=buffer, mode=mode, available=options, counts=counts,
                note='Выбор только отображения, не рекомендация конфигурации. '
                     'Пересчёта имитации или доверительных интервалов нет.')


def curve_title(selection, metric):
    return (f"Сохранённые итоговые оценки · Fog={selection['fog']}, "
            f"B={selection['buffer']} · точек: {selection['counts'][metric]}")
