"""Obtain the official class unchanged; fail rather than silently substitute."""
from pathlib import Path,PurePosixPath
import hashlib,io,urllib.request,zipfile
ROOT=Path(__file__).resolve().parents[1]
URL='https://psta.psiras.ru/publ-conditions/psta.zip'
EXPECTED='f0fdb7c786dd54fb5f066a58630a7b67235a01871457f5dcd26c48b6d476ea1b'

def ensure():
    p=ROOT/'article/psta.cls'
    if p.exists():
        if hashlib.sha256(p.read_bytes()).hexdigest()!=EXPECTED:raise RuntimeError('unexpected psta.cls version; review before accepting')
        return
    req=urllib.request.Request(URL,headers={'User-Agent':'FEFC-reproducible-build/1.0'})
    data=urllib.request.urlopen(req,timeout=90).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if hashlib.sha256(z.read('psta.cls')).hexdigest()!=EXPECTED:raise RuntimeError('official class changed; manual review required')
        for name in z.namelist():
            q=PurePosixPath(name)
            if q.is_absolute() or '..' in q.parts:raise RuntimeError('unsafe template archive')
            if name=='psta.cls' or name.startswith('psta/'):
                if name.endswith('/') or q.suffix.lower() in ('.ttf','.otf','.pfb','.woff','.woff2'):continue
                dest=ROOT/'article'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
    (ROOT/'article/STYLE_SOURCE.txt').write_text(URL+'\nVersion: 2026/10/16\nSHA256 psta.cls: '+EXPECTED+'\nClass unchanged. No font files distributed.\n')
if __name__=='__main__':ensure()
