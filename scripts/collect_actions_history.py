"""Authenticated metadata-only audit. Does not rerun or re-label scientific tests."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,os,re,subprocess,urllib.request
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';D=ROOT/'docs'
REPO='annfridreksen/Forecast_Edge_Fog_Cloud';BRANCH='night/fefc-v3'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def main():
    assert git('branch','--show-current')==BRANCH
    token=os.environ.get('GH_TOKEN')
    if not token:raise RuntimeError('GH_TOKEN must be supplied by the Actions job; never print or save it')
    assert 'FINAL CHECK: PASS' in (R/'final-check.txt').read_text()
    protected={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'v2').rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    journal=D/'Журнал_проверок_Perplexity.md';jsha=sha(journal)
    source=git('rev-parse','HEAD');now=datetime.now(timezone.utc).isoformat()
    old=json.loads((R/'work-history.json').read_text());runs=[]
    for page in range(1,101):
        url=f'https://api.github.com/repos/{REPO}/actions/runs?branch=night%2Ffefc-v3&per_page=100&page={page}'
        request=urllib.request.Request(url,headers={'User-Agent':'FEFC-history-audit','Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=30) as response:data=json.load(response)
        items=data['workflow_runs']
        runs.extend({key:item.get(key) for key in ('id','name','head_sha','head_branch','status','conclusion','run_attempt','created_at','run_started_at','updated_at','html_url')} for item in items)
        if len(items)<100:break
    else:raise RuntimeError('History pagination incomplete')
    assert all(x['head_branch']==BRANCH for x in runs)
    assert len({x['id'] for x in runs})==len(runs)
    stages={str(i):{'commits':[],'actions_runs':[]} for i in range(1,10)};commits=[]
    for line in git('log','--format=%H%x09%aI%x09%s','--reverse','HEAD').splitlines():
        commit,when,title=line.split('\t',2)
        if not title.startswith('FEFC:'):continue
        files=git('diff-tree','--no-commit-id','--name-only','-r',commit).splitlines();tags=set()
        if 'начало работы' in title:tags.add('1')
        patterns={'2':('efc/model','tests/test_model'),'3':('efc/stationary','efc/sensitivity','scripts/make_notebooks','scripts/complete_notebooks'),'4':('efc/forecast','scripts/make_forecast'),'5':('efc/placement','scripts/make_placement','scripts/add_placement'),'6':('scripts/check_figures','article/figures'),'7':('article/','scripts/write_article','scripts/review_article','scripts/render_references','scripts/verify_doi'),'8':('docs/','scripts/write_report','scripts/issue4_report','scripts/collect_actions_history'),'9':('.github/workflows','scripts/build_artifacts','results/final-check','results/build-summary')}
        for stage,prefixes in patterns.items():
            if any(f.startswith(prefixes) for f in files):tags.add(stage)
        if any('views.py' in f for f in files):tags.add('6')
        commits.append({'sha':commit,'time':when,'title':title,'stages':sorted(tags),'files':files})
        for stage in tags:stages[stage]['commits'].append(commit)
    mapping={c['sha']:c for c in commits}
    for run in runs:
        for stage in set(mapping.get(run['head_sha'],{}).get('stages',[]))|{'9'}:stages[stage]['actions_runs'].append(run['id'])
    durations=[]
    for run in runs:
        if run['status']=='completed' and run['run_started_at'] and run['updated_at']:
            seconds=(datetime.fromisoformat(run['updated_at'].replace('Z','+00:00'))-datetime.fromisoformat(run['run_started_at'].replace('Z','+00:00'))).total_seconds()
            durations.append(seconds);run['elapsed_metadata_seconds']=seconds
    h={'utc':now,'audit_source_commit':source,'scientific_source_commit':json.loads((R/'build-summary.json').read_text())['source_commit'],'previous_unauthenticated_api_error':old.get('api_error'),'api_error':None,'authenticated_history_complete_at_snapshot':True,'commits':commits,'runs':runs,'stages':stages,'conclusions':dict(Counter(x['conclusion'] or x['status'] for x in runs)),'note':'Stage groups overlap and are not additive. Includes failed/cancelled runs; this audit can still be in progress at snapshot. Times are metadata intervals, not CPU or active human time.'}
    (R/'work-history.json').write_text(json.dumps(h,ensure_ascii=False,indent=2))
    text='### Расход и фактические события\nТокены неизвестны. История повторно получена авторизованным запросом; прежний403публичногоAPI устранён для этого аудита. Ни секрет, ни значение токена не сохранялись.\n\n| Этап TASK | Коммитов | Запусков Actions |\n|---|---:|---:|\n'
    for stage,item in stages.items():text+=f"| {stage} | {len(item['commits'])} | {len(set(item['actions_runs']))} |\n"
    text+=f'\nУникальных FEFC-коммитов на момент снимка: {len(commits)}. Запусков Actions: {len(runs)}. Категории перекрываются, столбцы не суммировать. Исходный коммит аудита: {source}; UTC: {now}.\n'
    text+='Статусы: '+json.dumps(h['conclusions'],ensure_ascii=False)+'. Текущий аудит может быть in_progress в снимке; это не объявление завершённых запусков.\n'
    if durations:text+=f'Длительности завершённых запусков по меткам run_started_at→updated_at: сумма {sum(durations):.1f}с; диапазон {min(durations):.1f}–{max(durations):.1f}с. Это не активное время автора и не чистое вычислительное время.\n'
    text+='Научные серии, тетради и PDF не пересчитывались этим шагом; их исходный коммит и протокол остаются прежними. Полный список: results/work-history.json.\n\n'
    report=D/'Отчёт_ночи.md';body=report.read_text();assert '### Расход и фактические события' in body and '### Issue #3' in body
    body=re.sub(r'### Расход и фактические события.*?(?=### Issue #3)',lambda _:text,body,flags=re.S);report.write_text(body)
    ir=json.loads((R/'issue4-report.json').read_text());ir.update(history_api_error=None,history_audit_commit=source,history_runs=len(runs),history_commits=len(commits));(R/'issue4-report.json').write_text(json.dumps(ir,ensure_ascii=False,indent=2))
    audit={'status':'PASS','utc':now,'source_commit':source,'scientific_source_commit':h['scientific_source_commit'],'workflow_run_id':os.environ.get('GITHUB_RUN_ID'),'history_runs':len(runs),'history_commits':len(commits),'scientific_artifacts_rerun':False,'protected_sources_unchanged':True}
    (R/'history-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    with (D/'STATUS.md').open('a') as f:f.write(f'\n\n## История Actions уточнена — {now}\nПункт15: авторизованно получены {len(runs)}запусков и {len(commits)}FEFC-коммитов с этапами/временами. Прежний403публичногоAPI записан как история, текущая проверкаPASS. Научные серии/PDF не менялись и не запускались повторно этим шагом. Исходник аудита: {source}.\n')
    with (D/'Взаимодействие_с_проверяющим.md').open('a') as f:f.write(f'\n{now}: Issue#4,п.15 — авторизованная проверка истории, исходник {source}. Статистика и времена в work-history.json; научный запуск не повторялся.\n')
    assert all(sha(ROOT/p)==v for p,v in protected.items()) and sha(journal)==jsha
    with (R/'final-check.txt').open('a') as f:f.write(f'\nAUTHENTICATED HISTORY AUDIT: PASS\naudit_source_commit={source}\naudit_utc={now}\nscientific_runs_not_repeated=True\nhistory_runs={len(runs)}\n')
    paths=[]
    for line in (ROOT/'MANIFEST.sha256').read_text().splitlines():
        if line.strip():paths.append(ROOT/line.split(maxsplit=1)[1].lstrip('*'))
    paths += [Path(__file__),ROOT/'.github/workflows/history-audit.yml',R/'history-audit.json']
    (ROOT/'MANIFEST.sha256').write_text(''.join(sha(p)+'  '+str(p.relative_to(ROOT))+'\n' for p in sorted(set(paths))))
    print(json.dumps(audit,ensure_ascii=False));print('History-only audit PASS; science outputs untouched.')
if __name__=='__main__':main()
