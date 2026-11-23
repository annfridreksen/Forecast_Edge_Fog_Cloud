"""Presentation of saved intervals; never changes estimates or classification."""

ZERO_NOTE = ('нулевые наблюдённые потери; вырожденный bootstrap; '
             'риск ≤0,1% не подтверждён')


def interval_display(metric, value, lower, upper, reasons=()):
    zero = metric == 'drop_fraction' and value == lower == upper == 0
    flagged = metric == 'drop_fraction' and 'zero_loss_degenerate_bootstrap' in reasons
    if zero or flagged:
        return dict(interval_drawn=False, interval_note=ZERO_NOTE,
                    interval_state='ZERO_LOSS_DEGENERATE_BOOTSTRAP')
    if lower == upper:
        return dict(interval_drawn=False,
                    interval_note='Вырожденный сохранённый интервал; не изображается как проверенный ДИ.',
                    interval_state='DEGENERATE_SAVED_INTERVAL')
    return dict(interval_drawn=True,
                interval_note='Сохранённый номинальный 95%-й ДИ; не гарантия покрытия всей карты.',
                interval_state='SAVED_NOMINAL_INTERVAL')


def figure_from_points(points, metric, fog, buffer):
    import matplotlib.pyplot as plt
    factor = 100 if metric == 'drop_fraction' else 1
    warnings = [p for p in points if not p['interval_drawn']]
    fig, ax = plt.subplots(figsize=(8, 4.3 if warnings else 3.2))
    labelled = set()
    for p in points:
        if p['interval_drawn']:
            label = 'Сохранённый номинальный 95%-й ДИ'
            line, = ax.plot([p['rho50']] * 2, [factor*p['lower'], factor*p['upper']], '-',
                           label=label if label not in labelled else '_nolegend_')
            line.set_gid('saved-interval'); labelled.add(label)
        label = 'Наблюдённая оценка †, без интервала риска' if not p['interval_drawn'] else 'Итоговая оценка'
        line, = ax.plot(p['rho50'], factor*p['value'], 'x' if not p['interval_drawn'] else 'o',
                       label=label if label not in labelled else '_nolegend_')
        line.set_gid('saved-estimate'); labelled.add(label)
        if not p['interval_drawn']:
            ax.annotate('†', (p['rho50'], factor*p['value']), xytext=(5, 7), textcoords='offset points')
    if not points:
        ax.text(.5, .5, 'Нет итоговых оценок с ДИ; нули не подставляются', transform=ax.transAxes, ha='center')
    else:
        ax.legend(fontsize=8, loc='best')
    ax.set(xlabel='Предложенная нагрузка ρ50', ylabel='Потери, %' if factor == 100 else 'p95, мс',
           title=f'Сохранённые итоговые оценки · Fog={fog}, B={buffer} · точек: {len(points)}', xlim=(.05, 1))
    if metric == 'drop_fraction': ax.set_ylim(bottom=0)
    if warnings:
        groups = {}
        for p in warnings:
            groups.setdefault(p['interval_note'], []).append(f"{p['rho50']:.3g}")
        lines = []
        for note, rhos in groups.items():
            lines.append('† ρ50=' + ', '.join(rhos) + ':')
            if note == ZERO_NOTE:
                lines.extend(['нулевые наблюдённые потери; вырожденный bootstrap;',
                              'риск ≤0,1% не подтверждён. [0;0] не показан как интервал риска.'])
            else:
                lines.append(note)
        fig.text(.02, .02, '\n'.join(lines), ha='left', va='bottom', fontsize=8)
        fig.tight_layout(rect=(0, min(.42, .045*len(lines)+.03), 1, 1))
    else:
        fig.tight_layout()
    return fig
