"""R1.4 author interface. No training, grid execution or source-file writes.

A short drained example is NOT a stationary estimate. Saved estimates are read
from a version-matched checkpoint; missing confidence intervals stay missing.
"""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import html
import math
import numpy as np
from .model import Config, simulate, COMPONENTS
from .workload import generate_workload, Workload
from .grid import config_key, read_json, digest
from .primary import PrimarySampler

RHO = (.10, .30, .50, .70, .85, .95)
FOG = (30, 40, 50, 60, 70)
BUFFERS = (0, 2, 5, 10, 20, 50, 100, 200, 400)
LABELS = ('Edge', 'Edge→Fog', 'Ожидание Fog', 'Обработка Fog', 'Fog→Cloud', 'Cloud')
STATUS = {'NOT_CALCULATED': 'Не рассчитано', 'ACCEPTABLE': 'Допустима по оценке',
          'UNACCEPTABLE': 'Недопустима по оценке', 'INSUFFICIENT_DATA': 'Недостаточно данных',
          'ARCHIVE_UNVERIFIED': 'Архив не проверен; статистика недоступна'}
TICKS = ('edge_delay_tick', 'edge_fog_tick', 'fog_wait_tick', 'fog_service_tick', 'fog_cloud_tick', 'cloud_tick')
DEMO = 'Единичный синтетический опыт; статистическая допустимость НЕ оценена.'


def make_config(rate, fog, buffer, *, seed=42, n_tasks=600):
    if isinstance(rate, bool) or not math.isfinite(rate) or rate <= 0:
        raise ValueError('λ должна быть положительной конечной величиной')
    if type(fog) is not int or fog not in FOG or type(buffer) is not int or buffer not in BUFFERS:
        raise ValueError('Fog и буфер должны принадлежать утверждённой сетке')
    if type(n_tasks) is not int or not 1 <= n_tasks <= 5000:
        raise ValueError('Для короткой демонстрации разрешено 1–5000 сообщений')
    return Config(n_cloud=40, arrival_rate_s=rate, n_fog=fog, buffer=buffer,
                  seed=seed, n_tasks=n_tasks)


def run_example(config):
    """Same kernel as scientific runs, no pilot or inference hidden here."""
    result = simulate(config, compact=True, record_queue=True)
    result['tasks'] = [dict(t) for t in result['tasks']]
    ticks = tuple(int(t['latency_tick']) for t in result['tasks'] if t['status'] == 'completed')
    for t in result['tasks']:
        if t['status'] == 'completed':
            assert sum(t[k] for k in TICKS) == t['latency_tick']
    n = len(result['tasks'])
    result['display_summary'] = dict(scope=DEMO, p95_ms=result['metrics']['p95_ms'],
        drop_fraction=result['metrics']['drop_fraction'],
        H200=sum(t <= 200_000_000 for t in ticks)/n if n else None,
        intervals=None, statistical_status='NOT_EVALUATED_SINGLE_REPLICATION')
    return result


def completion_curve(result):
    delays = np.sort([t['latency_tick']/1e6 for t in result['tasks'] if t['status'] == 'completed'])
    x = np.unique(np.r_[0., 200., delays])
    n = len(result['tasks'])
    y = np.searchsorted(delays, x, side='right')/n if n else np.zeros(len(x))
    return x, y


def manual_case():
    c = Config(n_edge=1, n_fog=1, n_cloud=1, buffer=2, n_tasks=5,
        mobile_fraction=0, edge_fixed_ms=(2, 2), edge_processing_share=.5,
        fog_service_ms=(10, 10), fog_cloud_ms=(1, 1), cloud_service_ms=(1, 1))
    r = simulate(c, [0, .001, .002, .003, .010])
    waits, delays = [0, 9, 18, None, 20], [14, 23, 32, None, 34]
    for i, t in enumerate(r['tasks']):
        if delays[i] is None:
            assert t['status'] == 'dropped' and 'latency_tick' not in t
        else:
            assert t['fog_wait_tick'] == waits[i]*1_000_000
            assert t['latency_tick'] == delays[i]*1_000_000
            assert sum(t[k] for k in TICKS) == t['latency_tick']
    return r, waits, delays


def disconnect_workload(config, workload, sensor, at_tick):
    """Filter only NOT-YET-CREATED messages. Preserve original IDs separately.

    At equality manual disconnection precedes generation. Kernel IDs are dense;
    original IDs remain in the explicit mapping, never silently renumbered.
    """
    workload.validate_for(config)
    if type(sensor) is not int or not 0 <= sensor < config.n_edge:
        raise ValueError('Неизвестный датчик')
    if type(at_tick) is not int or at_tick < 0:
        raise ValueError('Момент отключения задаётся неотрицательным целым тиком')
    kept = [e for e in workload.events if not (e.sensor == sensor and e.release_tick >= at_tick)]
    removed = [e.event_id for e in workload.events if e.sensor == sensor and e.release_tick >= at_tick]
    origins = [e.event_id for e in kept]
    adapted = Workload(tuple(replace(e, event_id=i) for i, e in enumerate(kept)),
                       workload.source_signature, workload.horizon_tick)
    return replace(config, n_tasks=len(kept)), adapted, origins, removed


def shutdown_case():
    c = Config(n_edge=2, n_fog=1, n_cloud=1, buffer=5, n_tasks=6,
        mobile_fraction=0, edge_fixed_ms=(2, 2), fog_service_ms=(10, 10),
        fog_cloud_ms=(1, 1), cloud_service_ms=(1, 1))
    w = generate_workload(c, [0, .001, .002, .003, .004, .005])
    w = replace(w, events=tuple(replace(e, sensor=s) for e, s in zip(w.events, (0, 1, 0, 0, 1, 0))))
    cfg, after, origins, suppressed = disconnect_workload(c, w, 0, 3_000_000)
    r = simulate(cfg, workload=after)
    return dict(result=r, original_event_ids=origins, not_created_ids=suppressed,
                cutoff_tick=3_000_000, statistical_status='MANUAL_ILLUSTRATION_ONLY')


def saved_cell(root, config):
    """Validate the entire displayed snapshot, not just the selected cell."""
    from .saved_map import saved_cell as read_checked
    return read_checked(root, config)


def architecture_figure():
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 2.7)); ax.axis('off')
    labels = ['1000 датчиков\nEdge', 'Канал\nEdge→Fog', 'Fog\nочередь B + сервис', 'Канал\nFog→Cloud', '40 серверов\nCloud']
    for i, label in enumerate(labels):
        ax.text(i, 0, label, ha='center', va='center', fontsize=10)
        if i < 4: ax.annotate('', xy=(i+.68, 0), xytext=(i+.32, 0), arrowprops=dict(arrowstyle='->'))
    ax.annotate('Буфер заполнен → потеря;\nфиктивного завершения нет', xy=(2, -.15), xytext=(2, -.65),
                ha='center', fontsize=9, arrowprops=dict(arrowstyle='->'))
    ax.set(xlim=(-.5, 4.5), ylim=(-.95, .45))
    fig.tight_layout(); return fig


def manual_figure(result):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 3.8))
    rows = [t for t in result['tasks'] if t['status'] == 'completed']
    left = np.array([t['release_tick']/1e6 for t in rows])
    for k, label in zip(COMPONENTS, LABELS):
        widths = np.array([t[k] for t in rows])
        ax.barh([t['task_id']+1 for t in rows], widths, left=left, label=label)
        left += widths
    for t in result['tasks']:
        if t['status'] == 'dropped': ax.scatter([t['drop_tick']/1e6], [t['task_id']+1], marker='x', label='Потеря Fog')
    ax.set(xlabel='Время, мс', ylabel='Сообщение', yticks=range(1, len(result['tasks'])+1))
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1)); fig.tight_layout(); return fig


def show_result(result, saved):
    import matplotlib.pyplot as plt
    from IPython.display import display, HTML
    s = result['display_summary']
    q = 'нет завершений' if s['p95_ms'] is None else f"{s['p95_ms']:.3f} мс"
    display(HTML(f'<h3>Сейчас выполнен короткий опыт</h3><p>{DEMO}</p>'
        f'<p>p95: <b>{q}</b>; потери: <b>{100*s["drop_fraction"]:.3f}%</b>; '
        f'H(200 мс): <b>{s["H200"]:.5f}</b>. ДИ: <b>не оценивались</b>.</p>'
        '<p>Требование к статистической карте: p95 ≤ 200 мс <b>И</b> потери ≤ 0,1%.</p>'))
    display(HTML('<h3>Отдельно: сохранённая статистическая оценка</h3><p>'+
        html.escape(STATUS[saved['status']])+'. '+html.escape(saved['note'])+'</p><p>Источник: '+html.escape(saved['source'])+'</p>'))
    if saved['summary'] is not None:
        summary = saved['summary']; table = []
        for name, unit, factor in [('p95_ms', 'мс', 1), ('drop_fraction', '%', 100)]:
            v = summary['point'].get(name); ci = summary['intervals'].get(name)
            value = 'не определено' if v is None else f'{v*factor:.6g} {unit}'
            interval = 'не оценивался' if ci is None else f"[{ci['lower']*factor:.6g}; {ci['upper']*factor:.6g}] {unit}"
            table.append(f'<tr><td>{name}</td><td>{value}</td><td>{interval}</td></tr>')
        display(HTML('<table><tr><th>Метрика</th><th>Оценка</th><th>95% ДИ</th></tr>'+''.join(table)+'</table>'))
        display(HTML('<p>H(200 мс): '+html.escape(str(summary['point'].get('H200')))+
            '; причины ограничения: '+html.escape(', '.join(summary['reasons']) or 'нет')+'</p>'))
    x, y = completion_curve(result)
    fig, ax = plt.subplots(figsize=(7, 3)); ax.step(x, y, where='post'); ax.axvline(200, linestyle='--')
    ax.set(xlabel='Задержка t после собственного поступления, мс', ylabel='H(t), доля всех поступивших', ylim=(0, 1.02), title='Короткий опыт: потери остаются в знаменателе')
    display(fig); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 3))
    if result['metrics']['completed']: ax.bar(LABELS, [result['metrics']['components_ms'][k] for k in COMPONENTS])
    ax.set(ylabel='Среднее, мс', title='Шесть составляющих — только по завершённым'); ax.tick_params(axis='x', rotation=20)
    if not result['metrics']['completed']: ax.text(.5, .5, 'Нет завершённых: средние не определены', transform=ax.transAxes, ha='center')
    fig.tight_layout(); display(fig); plt.close(fig)
    if result['queue_trace']:
        node = max(result['queue_trace'], key=lambda r:r['waiting'])['fog']
        trace = [r for r in result['queue_trace'] if r['fog'] == node]
        fig, ax = plt.subplots(figsize=(7, 3)); ax.step([r['time_s'] for r in trace], [r['waiting'] for r in trace], where='post')
        ax.set(xlabel='Время, с', ylabel='Ожидающих', title=f'Короткий опыт: очередь Fog {node}, не стационарная оценка')
        display(fig); plt.close(fig)
    if saved['rows']:
        from .map_view import configuration_map_figure
        rate = result['config']['arrival_rate_s']
        fig = configuration_map_figure(saved, rate)
        display(fig); plt.close(fig)
        for metric, factor, label in [('p95_ms', 1, 'p95, мс'), ('drop_fraction', 100, 'Потери, %')]:
            fig, ax = plt.subplots(figsize=(7, 3)); points = 0
            for row in saved['rows']:
                if (row['n_fog'], row['buffer']) != (result['config']['n_fog'], result['config']['buffer']): continue
                ss = row.get('summary') or {}; ci = ss.get('intervals', {}).get(metric)
                value = ss.get('point', {}).get(metric)
                if ci is None or value is None: continue
                rho = row['arrival_rate_s']*.055/50
                ax.plot([rho, rho], [factor*ci['lower'], factor*ci['upper']], '-')
                ax.plot(rho, factor*value, 'o'); points += 1
            if not points: ax.text(.5, .5, 'Нет рассчитанных точек с ДИ', transform=ax.transAxes, ha='center')
            ax.set(xlabel='Предложенная нагрузка ρ50', ylabel=label, xticks=RHO, xlim=(.05, 1), title='Только сохранённые оценки; пропуски не соединены')
            fig.tight_layout(); display(fig); plt.close(fig)
    else:
        display(HTML('<p>Карта не загружена. Короткий опыт не заполняет её клетки.</p>'))


class Dashboard:
    """Widget values change configuration only; only explicit buttons compute."""
    def __init__(self, checkpoint='results/r14/night-map', *, render=True):
        import ipywidgets as w
        self.checkpoint, self.render = Path(checkpoint), render
        self.rate = w.Dropdown(options=[(f'{50*r/.055:.3f} (ρ50={r:g})', 50*r/.055) for r in RHO], value=50*.5/.055, description='λ, событий/с', style={'description_width':'initial'})
        self.fog = w.Dropdown(options=FOG, value=50, description='Узлов Fog')
        self.buffer = w.Dropdown(options=BUFFERS, value=5, description='Буфер B')
        self.button = w.Button(description='Рассчитать и проверить', layout=w.Layout(width='230px'))
        self.off_button = w.Button(description='Отключить датчик 0 в 3 мс', layout=w.Layout(width='250px'))
        self.output, self.off_output = w.Output(), w.Output()
        self.calls = 0; self.last = None; self.last_error = None; self.shutdown = None
        self.last_saved_error = None
        self.button.on_click(self.calculate); self.off_button.on_click(self.disable_sensor)
        details = w.Accordion(children=[w.HTML('<p>Демонстрация: 600 событий, seed=42, без прогрева и ДИ. '
            'Научная карта использует отдельные пилотные/итоговые/подтверждающие seed. '
            'Перемещение настроек не запускает полный расчёт. Нейросеть не подключена.</p>')])
        details.set_title(0, 'Что именно считается; seed и ограничения')
        shutdown = w.Accordion(children=[w.VBox([w.HTML('<p>Отдельная ручная иллюстрация: два датчика, один Fog. '
            'Не созданные после команды сообщения не являются потерями Fog. Основная карта не изменяется.</p>'), self.off_button, self.off_output])])
        shutdown.set_title(0, 'Условная демонстрация отключения датчика')
        self.widget = w.VBox([w.HTML('<h2>Среда Edge–Fog–Cloud</h2><p>Выберите поток, число Fog и буфер. '
            'Кнопка запускает короткий пример, а не полную статистическую сетку.</p>'), self.rate, self.fog,
            self.buffer, self.button, self.output, details, shutdown])

    def calculate(self, _=None):
        if self.button.disabled: return
        self.button.disabled = True; self.last = None; self.last_error = None
        self.last_saved_error = None
        try:
            c = make_config(self.rate.value, self.fog.value, self.buffer.value)
            result = run_example(c); self.calls += 1
            # The demonstration is independent of the external scientific archive.
            try:
                saved = saved_cell(self.checkpoint, c)
            except Exception as exc:
                self.last_saved_error = str(exc)
                saved = dict(status='ARCHIVE_UNVERIFIED', summary=None, rows=[],
                             source=str(self.checkpoint), checked_rows=0,
                             verification='FAILED', note='Короткий опыт выполнен отдельно. '
                             'Статусы карты и доверительные интервалы не показаны: '+str(exc))
            self.last = dict(result=result, saved=saved)
            if self.render:
                with self.output:
                    self.output.clear_output(wait=True); show_result(result, saved)
        except Exception as exc:
            self.last_error = str(exc)
            if self.render:
                with self.output:
                    self.output.clear_output(wait=True); print('Ошибка короткого опыта/вывода:', self.last_error)
        finally:
            self.button.disabled = False

    def disable_sensor(self, _=None):
        if self.off_button.disabled: return
        self.off_button.disabled = True
        try:
            self.shutdown = shutdown_case()
            if self.render:
                from IPython.display import display
                with self.off_output:
                    self.off_output.clear_output(wait=True)
                    print('Сохранены исходные ID:', self.shutdown['original_event_ids'],
                          '; не созданы после отключения:', self.shutdown['not_created_ids'])
                    print('Ранее созданные сообщения дообслужены; потери Fog:', self.shutdown['result']['metrics']['dropped'])
                    fig = manual_figure(self.shutdown['result']); display(fig)
                    import matplotlib.pyplot as plt
                    plt.close(fig)
        except Exception as exc:
            self.shutdown = None
            with self.off_output: print('Ошибка демонстрации:', str(exc))
        finally:
            self.off_button.disabled = False
