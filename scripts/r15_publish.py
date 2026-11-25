"""Publish the sole executor's generated R1.5 delivery with a HEAD lease.
The stage guard reads NUL-delimited UTF-8 paths, not Git's quoted display text.
No visibility change, force push, signature, merge, or journal submission.
"""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,urllib.request
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_r15_submission import package_zip,sha,put
REPO='annfridreksen/Forecast_Edge_Fog_Cloud';BRANCH='night/fefc-v3'


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def stage_paths():
    return [p for p in subprocess.check_output(['git','-c','core.quotepath=false','diff','--cached','--name-only','-z'],cwd=ROOT).decode('utf-8').split('\0') if p]


def finalize(out):
    delivery=out/'delivery';repro=out/'work/reproducibility'
    shutil.copytree(out/'work/submission',repro/'article',dirs_exist_ok=True)
    for f in (ROOT/'v2/code/bt26').glob('*.py'):
        target=repro/'v2/code/bt26'/f.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
    shutil.copytree(ROOT/'tests',repro/'tests',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(ROOT/'article/tests',repro/'article/tests',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('r14-values.tex','r14-references.tex','r15-sources.json'):
        shutil.copy2(ROOT/'article'/name,repro/'article'/name)
    package_zip(repro,delivery/'reproducibility.zip')
    put(delivery/'SHA256.json',{p.relative_to(delivery).as_posix():sha(p) for p in sorted(delivery.rglob('*')) if p.is_file() and p.name!='SHA256.json'})


def publish(out):
    expected=os.environ.get('R15_EXPECTED_HEAD',os.environ.get('R15_SOURCE_SHA',os.environ['GITHUB_SHA']));ref='refs/heads/'+BRANCH
    def remote():return git('ls-remote','origin',ref).split()[0]
    if remote()!=expected:raise RuntimeError('HEAD lease lost; preserve artifact, do not overwrite another executor')
    request=urllib.request.Request(f'https://api.github.com/repos/{REPO}',headers={'User-Agent':'FEFC-R15-public-check'})
    with urllib.request.urlopen(request,timeout=30) as f:meta=json.load(f)
    if meta.get('private') or meta.get('visibility')!='public':raise RuntimeError('Repository is not already public; visibility change prohibited')
    target=ROOT/'deliverables/r15';target.mkdir(parents=True,exist_ok=True)
    for p in sorted((out/'delivery').rglob('*')):
        if not p.is_file():continue
        if p.stat().st_size>=100*1024*1024:raise ValueError('Delivery exceeds file-size limit')
        dest=target/p.relative_to(out/'delivery');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    git('config','user.name','FEFC build executor');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
    git('add','--','deliverables/r15');staged=stage_paths()
    if not staged or any(not p.startswith('deliverables/r15/') for p in staged):
        print('STAGED_PATHS',json.dumps(staged,ensure_ascii=False));raise RuntimeError('Only the generated delivery directory may be staged')
    if remote()!=expected:raise RuntimeError('HEAD lease lost before publication')
    git('commit','-m','Issue #4 п.10–12 / R1.5 C: опубликовать проверенный комплект и точные синтетические данные')
    published=git('rev-parse','HEAD');git('push','origin','HEAD:'+ref)
    if remote()!=published:raise RuntimeError('Published remote SHA differs')
    required=['article.pdf','submission.zip','reproducibility.zip','difference.pdf','data-parts.json']
    required += [p['name'] for p in json.loads((target/'data-parts.json').read_text())['parts']]
    checks=[]
    for name in required:
        url=f'https://raw.githubusercontent.com/{REPO}/{published}/deliverables/r15/{name}';h=hashlib.sha256();size=0
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'FEFC-R15-anonymous-download'}),timeout=180) as f:
            while b:=f.read(1<<20):h.update(b);size+=len(b)
        if h.hexdigest()!=sha(target/name):raise ValueError('Anonymous download differs: '+name)
        checks.append(dict(file=name,url=url,sha256=h.hexdigest(),bytes=size,authenticated=False))
    result=dict(status='PUBLIC_DOWNLOAD_VERIFIED',source_sha=json.loads((out/'delivery/build-receipt.json').read_text())['source_sha'],verification_sha=expected,delivery_sha=published,branch=BRANCH,checks=checks,
                visibility_changed=False,article_sent=False,ready_to_submit=False,
                reason='Author metadata, permissions, page inspection and independent acceptance remain open.')
    put(out/'publication.json',result);print('PUBLICATION_RECEIPT',json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();finalize(a.out.resolve());publish(a.out.resolve())
