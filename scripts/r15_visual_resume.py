"""Resume artifact14971058236; keep accepted Word/vector bytes; finish PSTA links."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json,os,shutil,subprocess
from scripts import r15_visual_finish as p
from scripts import r15_full_rework as m
from scripts.r15_psta_readability import apply_saved,verify_pdf,body_links_and_captions
from scripts.build_r15_submission import download,unpack

ARTIFACT=14971058236
DIGEST='abb9c5a1ada8cb793c143a724c09d30d3b21b7d61dd37db5b62ac8249d789311'

def restore():
 if p.git('ls-remote','origin',p.REF).split()[0]!=os.environ['GITHUB_SHA']:raise RuntimeError('HEAD lease lost')
 archive=p.ROOT/'results/visual-preserved.zip'
 download(f'https://api.github.com/repos/annfridreksen/Forecast_Edge_Fog_Cloud/actions/artifacts/{ARTIFACT}/zip',archive,DIGEST,github=True)
 unpack(archive,p.OUT)
 report=json.loads((p.D/'word-render-checks.json').read_text())
 for test in report['tests']:
  if 'file' in test and p.sha(p.D/test['file'])!=test['pdf_sha256']:raise ValueError('Saved Word-PDF changed')
 preserved={f.relative_to(p.D).as_posix():p.sha(f) for f in p.D.rglob('*') if f.is_file() and (f.suffix=='.docx' or (f.suffix=='.pdf' and 'ПСТА' not in f.name and f.parent==p.D) or 'figures' in f.parts)}
 p.put(p.OUT/'preserved-rendered-files.json',preserved)
 with open(os.environ['GITHUB_ENV'],'a') as f:f.write('VISUAL_HEAD='+os.environ['GITHUB_SHA']+'\n')
 status=p.ROOT/'docs/STATUS.md';status.write_text('# STATUS — R1.5: сохранённый Word-экспорт, завершение ссылок и ZIP\n\n25.11.2026 · владелец #7145898717. Run '+os.environ['GITHUB_RUN_ID']+'. Архив14971058236 восстановлен по измеренному SHA256 '+DIGEST+'. Предыдущий run45501213211: формулы/SVG и новая PSTA-сборка выполнены, остановка на неверном ожидании имени equation.6. Проверка исправлена по реальной AUX-метке и именованным PDF-переходам; цель таблицы перенесена внутрь печатной подписи. Word/векторы не экспортируются заново. Дальше: проверка переходов, затронутый PSTA, ZIP в новой папке, сравнение и публикация; затем личный просмотр. Наука не меняется. Последний отзыв #7146021685 updated_at2026-11-24T22:16:18Z.\n\n'+status.read_text())
 p.commit(['docs/STATUS.md'],'Issue #5 п.5: сохранить точку продолжения исправленных Word и оставшихся проверок')


def finish():
 m.OUT=p.OUT;m.D=p.D;m.S=p.S;m.CHECKS=[]
 preserved=json.loads((p.OUT/'preserved-rendered-files.json').read_text())
 apply_saved(p.S)
 p.cmd(['sh','build.sh'],p.S,'psta-targets-build.log')
 log=(p.S/'main.log').read_text(errors='replace')
 if 'Overfull' in log or 'pdfTeX warning (dest)' in log:raise ValueError('PSTA guard failed')
 checks=verify_pdf(p.S/'main.pdf');p.put(p.D/'psta-readability-checks.json',checks)
 # A broken baseline must be rejected by the real checker, not a copied condition.
 try:verify_pdf(p.INPUT/'LaTeX/main.pdf')
 except (ValueError,FileNotFoundError):negative='REJECTED'
 else:raise ValueError('Old unresolved-target baseline not rejected')
 shutil.copy2(p.S/'main.pdf',p.D/'Статья_FEFC_R15_v3_ПСТА.pdf')
 shutil.copy2(p.S/'main.log',p.D/'checks/main.log')
 p.put(p.D/'tex-warnings.json',[x for x in log.splitlines() if any(w in x for w in ('Warning','warning','Overfull','Underfull'))])
 m.inspect_pdf();m.package()
 before=p.ROOT/'deliverables/r15/article.pdf'
 if p.sha(before)!='5d0424d9c8f0b0af18f009e3b1549a764aaf5f1d490cfaaee0e07348911f596f':raise ValueError('Wrong baseline for diff')
 args=['xvfb-run','-a',os.environ['DIFF_PDF_BIN'],'--output-diff='+str(p.D/'Сравнение_с_R15_390b232a.pdf'),str(before),str(p.S/'main.pdf')]
 result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
 (p.OUT/'logs/diff-pdf.log').write_bytes(result.stdout)
 if result.returncode not in (0,1) or not (p.D/'Сравнение_с_R15_390b232a.pdf').exists():raise RuntimeError('diff-pdf failed')
 p.put(p.D/'comparison-provenance.json',{'method':'diff-pdf','tool_commit':'092e6e31968cf28984c201a8c300f76f0020fbe4','baseline_delivery':'390b232a24b10d303b4f6646af8fc1414f7f182a','baseline_sha256':p.sha(before),'new_sha256':p.sha(p.S/'main.pdf'),'exit':result.returncode})
 for name,digest in preserved.items():
  if p.sha(p.D/name)!=digest:raise ValueError('Preserved rendered file changed: '+name)
 for name in ('empirical-evidence.json','conditional-evidence.json','service-reference.json'):
  if p.sha(p.D/name)!=p.sha(p.INPUT/name):raise ValueError('Scientific evidence changed')
 if (p.S/'body.tex').read_text()!=body_links_and_captions((p.INPUT/'LaTeX/body.tex').read_text()):raise ValueError('Unexpected scientific body edit')
 if p.sha(p.S/'article_body.md')!=p.sha(p.INPUT/'LaTeX/article_body.md'):raise ValueError('Article source changed')
 receipt={'source_sha':os.environ['VISUAL_HEAD'],'baseline_sha':p.BASE,'run_id':os.environ['GITHUB_RUN_ID'],'restored_artifact':ARTIFACT,'restored_artifact_sha256':DIGEST,'word_export_run':45501213211,'checks':m.CHECKS,'negative_old_pdf':negative,'preserved_rendered_file_count':len(preserved),'same_words_and_mathematical_tokens':True,'omml_objects':116,'display_equations':9,'sections':8,'references':27,'figures':3,'scientific_snapshot_requests':131,'simulation_executed':False,'bootstrap_recomputed':False,'new_neural_training':False,'visual_review':'PENDING_PERSONAL_REVIEW','ready_to_submit':False,'article_sent':False}
 for name in ('CHECK_RESULT.json','receipt.json'):
  old=p.D/name
  if old.exists():shutil.copy2(old,p.D/'checks'/('historical-'+name))
  p.put(old,receipt)
 p.put(p.D/'visual-repair-receipt.json',receipt)
 p.put(p.D/'resume-provenance.json',{'artifact':ARTIFACT,'sha256':DIGEST,'preserved_rendered_files':preserved,'word_regenerated_on_resume':False,'figure_regenerated_on_resume':False,'psta_rebuilt_reason':'real table caption destinations and class-dependent equation targets','isolated_source_zip_rebuild':json.loads((p.D/'isolated-build.json').read_text())})
 (p.D/'README.md').write_text('# FEFC R1.5 — исправленное отображение сохранённой редакции\n\nДве Word-копии с одинаковым научным текстом и редактируемыми Microsoft Equation; красная копия выделяет переработанные разделы целиком, не является посимвольным Track Changes. Неизвестные авторские поля красные. Word-PDF получены с установленным LibreOffice Math; 116 OMML/9 формул, математические токены сохранены. SVG-подписи больше не зависят от paint-order. C01 различает незавершённое сообщение и потерю.\n\nPSTA содержит согласованные двуязычные справки, работающие внутренние переходы, двуязычные подписи таблиц. Авторские вклады и личные заявления не подписаны; автоматическое утверждение о равном вкладе не добавлено.\n\nТехнические проверки — receipt.json/word-render-checks/psta-readability-checks/isolated-build. Исторические результаты находятся в checks/historical-*; их статусы не описывают новые файлы. Сравнительный PDF построен diff-pdf к точному PDF доставки390b232a; происхождение в comparison-provenance. Готовность к отправке не присвоена: новый личный просмотр и независимая приёмка учитываются отдельно. Научные серии/bootstrap/обучение не выполнялись.\n')
 p.put(p.D/'SHA256.json',{f.relative_to(p.D).as_posix():p.sha(f) for f in sorted(p.D.rglob('*')) if f.is_file() and f.name not in ('SHA256.json','FEFC_R15_v3_полный_комплект.zip') and 'review-images' not in f.parts})
 with ZipFile(p.D/'FEFC_R15_v3_полный_комплект.zip','w',ZIP_DEFLATED) as z:
  for f in sorted(p.D.rglob('*')):
   if f.is_file() and f.name!='FEFC_R15_v3_полный_комплект.zip' and 'review-images' not in f.parts and f.suffix.lower() not in p.FONT:z.write(f,f.relative_to(p.D))
 print('FINISHED_SAVED_RENDER',json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':
 import sys
 {'restore':restore,'finish':finish,'publish':p.publish}[sys.argv[1]]()
