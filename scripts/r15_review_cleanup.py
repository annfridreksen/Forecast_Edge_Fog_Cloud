"""Address read-only review #7116776800 without changing numerical evidence.
Requires the last verified published package; source and delivery are committed
separately by the sole executor under a HEAD lease. No simulation/bootstrap.
"""
from pathlib import Path
import difflib,json,os,subprocess
ROOT=Path(__file__).resolve().parents[1]
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def main():
    expected=os.environ['GITHUB_SHA'];ref='refs/heads/night/fefc-v3'
    if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('HEAD lease lost')
    path=ROOT/'article/main.tex';before=path.read_text();after=before
    old='Материалы НСКФ в R1.4'
    if after.count(old)!=4:raise ValueError('Unexpected provenance table; do not silently patch another revision')
    after=after.replace(old,r'Материалы НСКФ~\cite{nskf}')
    old='The study concerns infrastructure configuration rather than runtime task migration.'
    new='The study addresses infrastructure configuration and outlines a conceptual architecture for forecast-aware reassignment of connected tasks. The reported experiments concern configuration only.'
    if after.count(old)!=1:raise ValueError('Extended-summary anchor missing')
    after=after.replace(old,new,1);path.write_text(after)
    letter=ROOT/'submission/cover_letter.md';old_letter=letter.read_text()
    marker='\n\nРешения автора #7115069628/#7115236266 применены:'
    if old_letter.count(marker)!=1:raise ValueError('Expected one administrative letter appendix')
    new_letter=old_letter.split(marker)[0].rstrip()+'\n'
    letter.write_text(new_letter)
    names=['article/main.tex','submission/cover_letter.md','docs/R15_Ответ_RO_7116776800.md']
    diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='before-main',tofile='after-main'))
    (ROOT/names[-1]).write_text('# Адресная правка по #7116776800\n\n1. Принято: внутренняя редакция R1.4 удалена из таблицы параметров; ссылка на неизменённый авторский материалНСКФ. Это не подтверждает его публикационные реквизиты.\n2. Принято: первое предложение английского резюме согласовано с заголовком; эксперимент относится только к конфигурации, переразмещение концептуально.\n3. Принято: из письма убран служебный хвост с IDGitHub. Факт созданного комплекта уже подтверждён успешной сборкой/публичными загрузками. Письмо остаётся неподписанным проектом.\n4. Принято ранее: закреплённые ссылки на уже доступный код/данные внесены предыдущим финальным шагом.\n\nНи исходные числа, ниусловныйанализ, ниbootstrap, нинейтросеть не изменяются. НезависимыеJSвычисленияRO-хода не приписаны исполнителю. Готовностьотправки не присвоена.\n\n```diff\n'+diff+'```\n')
    git('config','user.name','FEFC read-only-review executor');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','--',*names)
    staged=[p for p in subprocess.check_output(['git','-c','core.quotepath=false','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0') if p]
    if set(staged)!=set(names):raise ValueError('Unexpected staged files')
    if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('HEAD changed before source commit')
    git('commit','-m','Issue #4 п.10 / R1.5 B: устранить служебные ссылки и согласовать английское резюме')
    head=git('rev-parse','HEAD');git('push','origin','HEAD:'+ref)
    if git('ls-remote','origin',ref).split()[0]!=head:raise RuntimeError('Published source mismatch')
    with open(os.environ['GITHUB_ENV'],'a') as f:f.write('R15_SOURCE_SHA='+head+'\n')
    print('EDITORIAL_SOURCE_SHA',head,flush=True)
if __name__=='__main__':main()
