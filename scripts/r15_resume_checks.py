"""Resume only unfinished v3 checks from the published header-fixed delivery."""
from pathlib import Path
import hashlib, json, os, shutil, subprocess, tempfile, zipfile
import fitz
from scripts import r15_full_rework as r

ROOT=r.ROOT
OLD=ROOT/'deliverables/r15-header-fix-pending'
OUT=ROOT/'results/r15-resume-checks'
D=OUT/'delivery'
SOURCE='2048573b64840417f4e471cf5c1b3ebe28779743'
TARGET=ROOT/'deliverables/r15-rework-v3'
LETTER='Сопроводительное_письмо_ПСТА_v3.pdf'
ARTICLE='Статья_FEFC_R15_v3_ПСТА.pdf'
RUN=os.environ.get('GITHUB_RUN_ID','local')
HEAD=os.environ.get('GITHUB_SHA','')
def git(*args):
 return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def check_manifest():
 manifest=json.loads((OLD/'SHA256.json').read_text())
 assert len(manifest)==64
 for name,digest in manifest.items():
  assert r.sha(OLD/name)==digest,name
 for name in ('article_body.md','metadata.json','change_register.md'):
  assert r.sha(OLD/'LaTeX'/name)==r.sha(ROOT/'article/rework'/name),name
 assert r.sha(OLD/ARTICLE)==r.sha(OLD/'LaTeX/main.pdf')
 assert 'Overfull' not in (OLD/'checks/main.log').read_text(errors='replace')
 return manifest
def negative_cases():
 results=[]
 original=(r.D,r.OUT,r.CHECKS)
 for kind,expected in [('empty','confirmed contact rendered'),('incomplete','required complete letter content'),('one_page_article','bounded complete page count')]:
  with tempfile.TemporaryDirectory(prefix='fefc-inspect-test-') as tmp:
   p=Path(tmp)
   for n in r.EXPECTED_PDFS:shutil.copy2(OLD/n,p/n)
   if kind=='one_page_article':
    with fitz.open(OLD/ARTICLE) as a,fitz.open() as b:
     b.insert_pdf(a,from_page=0,to_page=0)
     b.save(p/'short.pdf')
    (p/'short.pdf').replace(p/ARTICLE)
   else:
    with fitz.open() as d:
     page=d.new_page()
     if kind=='incomplete':page.insert_text((40,40),'jigulina@mail.ru')
     d.save(p/'bad.pdf')
    (p/'bad.pdf').replace(p/LETTER)
   r.D,r.OUT,r.CHECKS=p,p,[]
   try:
    r.inspect_pdf()
   except AssertionError as e:
    assert expected in str(e),(kind,str(e))
    results.append({'case':kind,'passed':True,'rejection':str(e)})
   else:raise AssertionError('invalid document accepted: '+kind)
   finally:r.D,r.OUT,r.CHECKS=original
 return results
def main():
 assert HEAD and git('rev-parse','HEAD')==HEAD
 assert not D.exists() and not TARGET.exists()
 manifest=check_manifest()
 shutil.copytree(OLD,D,ignore=shutil.ignore_patterns('FEFC_R15_v3_сохранённые_файлы.zip','SHA256.json'))
 r.OUT,r.D,r.S,r.CHECKS=OUT,D,D/'LaTeX',[]
 tests=negative_cases()
 r.put(OUT/'address-tests.json',tests)
 ledger=r.inspect_pdf()
 tests.insert(0,{'case':'complete_saved_one_page_letter_and_three_articles','passed':True,'pages':{n:sum(x['file']==n for x in ledger) for n in r.EXPECTED_PDFS}})
 r.put(D/'address-tests.json',tests)
 r.put(OUT/'address-tests.json',tests)
 mandatory=['main.tex','body.tex','psta.cls','psta/psta-utf8.sty','references.bib','references.bbl','psta-source-preserve.bst','build.sh']
 assert all((r.S/n).is_file() for n in mandatory)
 for stem in ('01_environment','02_verification','03_reassignment'):
  assert all((r.S/'figures'/(stem+ext)).is_file() for ext in ('.pdf','.svg','.tikz'))
 zipper=r.package()
 # Existing binary manuscript and evidence must not change.
 for n,h in manifest.items():
  if n.startswith('LaTeX/') or Path(n).suffix in ('.pdf','.docx') or n.endswith('evidence.json') or n=='service-reference.json':
   assert r.sha(D/n)==h,n
 shutil.copy2(OUT/'logs/isolated-source-build.log',D/'checks/isolated-source-build.log')
 r.put(D/'receipt.json',{'status':'TECHNICAL_CHECKS_COMPLETED_VISUAL_REVIEW_OPEN',
  'saved_source_sha':SOURCE,'checking_code_sha':HEAD,'run_id':RUN,
  'original_manifest_entries':len(manifest),'checks':r.CHECKS,'address_tests':tests,
  'isolated_build':json.loads((D/'isolated-build.json').read_text()),
  'saved_pdf_sha256':r.sha(D/ARTICLE),'source_zip_sha256':r.sha(D/'Исходники_ПСТА_v3.zip'),
  'word_figures_science_regenerated':False,'personal_visual_review_complete':False,
  'ready_to_submit':False,'article_sent':False})
 (D/'README.md').write_text('# FEFC R1.5 v3 — техническая проверка сохранённой редакции завершена\n\nИсходные Word/PDF, векторы, научные данные сохранены побайтово. Старый CHECK_RESULT.json описывает историческую остановку; текущие проверки — receipt.json, address-tests.json, isolated-build.json, page-review.json. Полная личная научная и визуальная приёмка открыта. Письмо не подписано, статья не отправлена.\n',encoding='utf-8')
 # Renderings are review artifacts, not part of the submission.
 r.put(D/'SHA256.json',{p.relative_to(D).as_posix():r.sha(p) for p in sorted(D.rglob('*')) if p.is_file() and p.name!='SHA256.json' and 'review-images' not in p.parts})
 zipper(D,D/'FEFC_R15_v3_полный_комплект.zip')
 ref='refs/heads/night/fefc-v3'
 assert git('ls-remote','origin',ref).split()[0]==HEAD
 shutil.copytree(D,TARGET,ignore=shutil.ignore_patterns('review-images'))
 s=ROOT/'docs/STATUS.md';history=s.read_text()
 s.write_text('# STATUS — R1.5 v3: сохранённая редакция, техническая проверка завершена\n\n25.11.2026 · BT26-R15-EXEC-20261125-01. Код проверки '+HEAD+'; Actions '+RUN+'. Проверены 64 записи исходного реестра, фактическая inspect_pdf: полное письмо и статьи проходят; пустое/неполное письмо и одностраничная статья отклонены. Изолированная сборка исходного ZIP выполнена; тексты страниц и BBL совпали, Overfull отсутствует. Word/PDF/схемы и данные не регенерировались. Файлы: deliverables/r15-rework-v3/; receipt.json, SHA256.json, address-tests.json, isolated-build.json, page-review.json. PDF SHA256 '+r.sha(D/ARTICLE)+'; ZIP SHA256 '+r.sha(D/'Исходники_ПСТА_v3.zip')+'.\n\nПоследнее обработанное поручение #7145605957 updated_at 2026-11-24T21:57:08Z; #7145471705/#7145192083/#7144375826. Следующий шаг: содержательная сверка article/rework/article_body.md, metadata.json, change_register.md и реестров; личный просмотр непринятых страниц и 3 схем обычный масштаб/7×. Рендер не равен просмотру. Diff-PDF и личные поля проверить отдельно. Готовность к отправке не заявлена. После успешного push владелец освобождает запись. Не повторять завершённые тесты/сборку без влияющих правок. Только night/fefc-v3, PR#2 без слияния.\n\n---\nИстория:\n\n'+history,encoding='utf-8')
 git('config','user.name','FEFC saved-checks executor')
 git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
 git('add','--',str(TARGET.relative_to(ROOT)),'docs/STATUS.md')
 names=git('diff','--cached','--name-only').splitlines()
 # git may quote non-ASCII paths; use NUL raw paths for scope check.
 names=subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0')
 assert all(not n or n=='docs/STATUS.md' or n.startswith('deliverables/r15-rework-v3/') for n in names)
 assert git('ls-remote','origin',ref).split()[0]==HEAD
 git('commit','-m','Issue #5: complete saved v3 PDF checks and isolated source ZIP build')
 git('push','origin','HEAD:'+ref)
 final=git('rev-parse','HEAD');assert git('ls-remote','origin',ref).split()[0]==final
 r.put(OUT/'publication.json',{'delivery_sha':final,'checking_code_sha':HEAD,'run_id':RUN,'writer_released':True})
 print('FEFC_RESUME_RESULT',final,flush=True)

if __name__=='__main__':main()
