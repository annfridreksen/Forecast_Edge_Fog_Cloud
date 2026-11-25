"""Close C9 using the requested diff-pdf utility; address actual TeX overflow.
Numerical evidence and scientific interpretation remain unchanged.
"""
from pathlib import Path
import difflib,os,subprocess
ROOT=Path(__file__).resolve().parents[1]
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def once(s,a,b):
    if s.count(a)!=1:raise ValueError('Unexpected patch anchor '+repr(a[:80]))
    return s.replace(a,b,1)
def main():
    expected=os.environ['GITHUB_SHA'];ref='refs/heads/night/fefc-v3'
    if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('HEAD lease lost')
    path=ROOT/'article/main.tex';old=path.read_text();text=old
    a=r'Полный каталог содержит шесть нагрузок $\rho_{50}\in\{0{,}10;0{,}30;0{,}50;0{,}70;0{,}85;0{,}95\}$. Число Fog принимает значения $30,40,50,60,70$, буфер --- $0,2,5,10,20,50,100,200,400$.'
    b=r'Полный каталог содержит шесть нагрузок $\rho_{50}$: 0,10; 0,30; 0,50; 0,70; 0,85; 0,95. Число Fog принимает значения 30, 40, 50, 60, 70. Буфер равен 0, 2, 5, 10, 20, 50, 100, 200 или 400.'
    text=once(text,a,b)
    text=text.replace(r'\mathrm{стац}',r'\text{стац}').replace(r'\mathrm{моб}',r'\text{моб}')
    text=once(text,'text width=88mm,minimum height=5mm','text width=88mm,minimum height=4mm')
    path.write_text(text)
    build=ROOT/'scripts/r15_build_author.py';code=build.read_text()
    start=code.index("    try:\n        cmd=['latexdiff'")
    end=code.index("    put(delivery/'difference-provenance.json'",start)
    block='''    # diff-pdf compares the two actual PDFs and avoids TeX bibliography/table macros.
    tool=Path(os.environ['DIFF_PDF_BIN']).resolve()
    cmd=['xvfb-run','-a',str(tool),'--output-diff='+str(delivery/'difference.pdf'),str(basepdf),str(pdf)]
    r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240)
    (out/'diff-pdf.log').write_bytes(r.stdout)
    if r.returncode not in (0,1) or not (delivery/'difference.pdf').exists():
        raise RuntimeError('diff-pdf failed, code '+str(r.returncode))
    with fitz.open(delivery/'difference.pdf') as compared:
        if not len(compared):raise ValueError('Empty utility comparison PDF')
    ds.update(method='diff-pdf',requested_utility_success=True,utility_exit=r.returncode,
              tool_commit='092e6e31968cf28984c201a8c300f76f0020fbe4',
              command=cmd,interpretation='Exit1 means actual PDF differences, not a tool error.')
'''
    code=code[:start]+block+code[end:];build.write_text(code)
    diff=''.join(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='before-layout-only',tofile='after-layout-only'))
    (ROOT/'docs/R15_C9_и_переполнение.md').write_text('# C9 и переполнение строки\n\nВ фактическом run45289905581 чистыйPDF и ZIPповторнаясборкаPASS; latexdiffCFONT завершился ошибкой Misplaced noalign на booktabs-таблице. Содержимое статьи ради latexdiff не удаляется. Применяется прямо разрешённая заданием утилита diff-pdf, commit092e6e31968cf28984c201a8c300f76f0020fbe4, официальныйисходник vslavik/diff-pdf. Exit1означает обнаруженные различия, не отказутилиты; проверяется существующий непустойPDF.\n\nВчистомPDF найдены2 реальных overfullhbox из непереносимых числовых mathсписков; значения не меняются, только математические обёртки заменены обычным перечислением. Кириллическиеиндексы выведены через text, ане mathromanfont. Высотаузловсхемы6 на1ммменьше, текст/шрифтнеуменьшаются. Сохраняетсяточный diff. C7остаётся независимым визуальнымтребованием, машинныйPASSего незаменяет.\n\n```diff\n'+diff+'```\n')
    names=['article/main.tex','scripts/r15_build_author.py','docs/R15_C9_и_переполнение.md']
    git('config','user.name','FEFC comparison executor');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com');git('add','--',*names)
    staged=[p for p in subprocess.check_output(['git','-c','core.quotepath=false','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0') if p]
    if set(staged)!=set(names):raise ValueError('Source write scope violated')
    if git('ls-remote','origin',ref).split()[0]!=expected:raise RuntimeError('HEAD changed')
    git('commit','-m','Issue #4 п.10 / R1.5 C9: сравнить реальные PDF и устранить переполнение списков')
    head=git('rev-parse','HEAD');git('push','origin','HEAD:'+ref)
    if git('ls-remote','origin',ref).split()[0]!=head:raise RuntimeError('Source push mismatch')
    with open(os.environ['GITHUB_ENV'],'a') as f:f.write('R15_SOURCE_SHA='+head+'\n')
    print('C9_SOURCE_SHA',head,flush=True)
if __name__=='__main__':main()
