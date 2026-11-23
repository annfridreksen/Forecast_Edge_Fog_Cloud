"""Four-state map rendering, only after whole-snapshot evidence-chain checks."""
import numpy as np

# Colour is redundant: every cell and legend also carry explicit text.
STYLES = {
    'NOT_CALCULATED': ('#eeeeee', 'Не\nрассчитано', 'Не рассчитано'),
    'ACCEPTABLE': ('#d1e5f0', 'Допустима\nпо оценке', 'Допустима по оценке'),
    'UNACCEPTABLE': ('#fddbc7', 'Недопустима\nпо оценке', 'Недопустима по оценке'),
    'INSUFFICIENT_DATA': ('#e7d4e8', 'Недостаточно\nданных', 'Недостаточно данных'),
}


def configuration_map_figure(saved, rate):
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from matplotlib.patches import Patch
    if (saved.get('verification') != 'ALL_DISPLAY_CHAINS_CHECKED'
            or not saved.get('rows')
            or any(r.get('display_chain_checked') is not True for r in saved['rows'])):
        raise ValueError('Нельзя рисовать непроверенные статусы карты')
    if any(r['status'] not in STYLES for r in saved['rows']):
        raise ValueError('Неизвестный научный статус')
    rows = [r for r in saved['rows'] if r['arrival_rate_s'] == rate]
    if not rows:
        raise ValueError('Нет выбранного потока в карте')
    fogs, buffers = sorted({r['n_fog'] for r in rows}), sorted({r['buffer'] for r in rows})
    cells = {(r['n_fog'], r['buffer']): r for r in rows}
    if len(cells) != len(rows):
        raise ValueError('Повторные координаты карты')
    codes = {name: i for i, name in enumerate(STYLES)}
    matrix = np.full((len(fogs), len(buffers)), np.nan)
    for i, fog in enumerate(fogs):
        for j, buffer in enumerate(buffers):
            row = cells.get((fog, buffer))
            if row is not None:
                matrix[i, j] = codes[row['status']]
    cmap = ListedColormap([x[0] for x in STYLES.values()]); cmap.set_bad('white')
    fig, ax = plt.subplots(figsize=(max(8, 1.25*len(buffers)), max(4, .65*len(fogs)+1.8)))
    ax.imshow(np.ma.masked_invalid(matrix), cmap=cmap,
              norm=BoundaryNorm(np.arange(-.5, len(STYLES)+.5), len(STYLES)), aspect='auto')
    for i, fog in enumerate(fogs):
        for j, buffer in enumerate(buffers):
            row = cells.get((fog, buffer))
            text = STYLES[row['status']][1] if row else 'Вне\nкаталога'
            ax.text(j, i, text, ha='center', va='center', fontsize=8)
    ax.set(xticks=range(len(buffers)), xticklabels=buffers,
           yticks=range(len(fogs)), yticklabels=fogs, xlabel='B — мест ожидания на Fog',
           ylabel='Число Fog', title=f'Сохранённая карта · λ = {rate:.3f} событий/с')
    fig.legend(handles=[Patch(facecolor=color, label=label) for color, _, label in STYLES.values()],
               loc='lower center', ncol=2, fontsize=9, frameon=False)
    fig.tight_layout(rect=(0, .13, 1, 1))
    return fig
