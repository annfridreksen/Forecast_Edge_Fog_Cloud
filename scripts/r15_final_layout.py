"""Final presentation-only patch: availability, section-six height and diff type.
No raw data, analysis, bibliography content or accepted notebook is changed.
"""
from pathlib import Path
import os,subprocess,json,difflib
ROOT=Path(__file__).resolve().parents[1]
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Unexpected final-patch anchor: '+repr(old[:80]))
    return text.replace(old,new,1)
def main():
    expected=os.environ['GITHUB_SHA'];ref='refs/heads/night/fefc-v3'
    if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('HEAD lease lost')
    p=ROOT/'article/main.tex';old=p.read_text();text=old
    a=text.index(r'\paragraph{Доступность материалов.}');b=text.index(r'\raggedbottom',a)
    availability=r'''\paragraph{Доступность материалов.}
Исходники расчётной версии зафиксированы в репозитории:
\url{https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/tree/1801dd37898e2d53eb2ab22a8dee532fd1083f5d}.
Первичные данные, контрольные суммы и воспроизводящие материалы доступны без авторизации:
\url{https://github.com/annfridreksen/Forecast_Edge_Fog_Cloud/tree/4a8bc330e49adfaea7259586ca632b3b3250fc5f/deliverables/r15}.
Набор содержит именно зафиксированный срез из131 запроса и отдельную условную оценку. Обновление оформления не изменяет эти наблюдения. Полные выходные сведения авторских тезисов НСКФ требуют уточнения.

'''
    text=text[:a]+availability+text[b:]
    text=once(text,'text width=88mm,minimum height=6mm','text width=88mm,minimum height=5mm')
    p.write_text(text)
    build=ROOT/'scripts/r15_build_author.py';code=build.read_text()
    code=once(code,"cmd=['latexdiff','--encoding=utf8'","cmd=['latexdiff','--type=CFONT','--encoding=utf8'")
    before="rows=bibliography_report(ROOT/'article',delivery);shutil.copy2(delivery/'bibliography-report.json',package/'bibliography-report.json')"
    after="""previous=ROOT/'deliverables/r15/bibliography-report.json'
    bib_unchanged=not subprocess.check_output(['git','diff','1801dd37898e2d53eb2ab22a8dee532fd1083f5d','HEAD','--','article/r15-references.tex','article/r15-sources.json'],cwd=ROOT)
    if previous.exists() and bib_unchanged:
        shutil.copy2(previous,delivery/'bibliography-report.json')
        rows=json.loads(previous.read_text())['rows']
        receipt['bibliography_registry_reused_from']='45286829771; unchanged reference text and source matrix'
    else:
        rows=bibliography_report(ROOT/'article',delivery)
    shutil.copy2(delivery/'bibliography-report.json',package/'bibliography-report.json')"""
    code=once(code,before,after);build.write_text(code)
    # Keep a readable exact diff, not an unrecorded author rewrite.
    delta=''.join(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='1801dd3-main.tex',tofile='final-availability-main.tex'))
    (ROOT/'docs/R15_Финальная_верстка.diff').write_text(delta)
    (ROOT/'docs/R15_Финальная_верстка.md').write_text('# Финальная техническая редакция\n\nИсточникданных/анализа1801dd3 неизменён. Публичнаядоставка4a8bc33 реальноскачана безавторизации вActions45286829771, поэтому встатье убрана устаревшая оговорка онепровереннойдоступности и приведены закреплённыессылки. Высотаузлов схемы6 уменьшена с6до5мм безизменения текста/шрифта; цель —около2страниц раздела6.\n\nLatexdiffпереведён на штатныйCFONT: предыдущаяошибка требовала отсутствующийulem.sty; новыйцветовойрежимне зависит отнего. При отказеC9остаётсяоткрытым. Неизменённаясверкабиблиографии повторно несетеваязапускается; источникреестра указывается. DOIWei поDROPS подтверждён ранее; сетевойCrossrefотказне назван отрицаниемDOI. C7визуальныйосмотрв этомконтейнере остаётсянедоступен.\n')
    allowed=['article/main.tex','scripts/r15_build_author.py','docs/R15_Финальная_верстка.diff','docs/R15_Финальная_верстка.md']
    git('config','user.name','FEFC final-layout executor');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');git('add','--',*allowed)
    staged=[s for s in subprocess.check_output(['git','-c','core.quotepath=false','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0') if s]
    if set(staged)!=set(allowed):raise ValueError('Unexpected source write scope')
    if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('HEAD lease lost before source commit')
    git('commit','-m','Issue #4 п.10–12 / R1.5 C: закрепить публичные источники и исправить сравнительную верстку')
    head=git('rev-parse','HEAD');git('push','origin','HEAD:'+ref)
    if git('ls-remote','origin',ref).split()[0]!=head:raise RuntimeError('remote source mismatch')
    with open(os.environ['GITHUB_ENV'],'a') as f:f.write('R15_SOURCE_SHA='+head+'\n')
    print('FINAL_SOURCE_SHA',head,flush=True)
if __name__=='__main__':main()
