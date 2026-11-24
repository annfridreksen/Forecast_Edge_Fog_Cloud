"""Scoped PSTA presentation fixes for review #7146021685; no scientific changes."""
import re
from pathlib import Path


def body_links_and_captions(text):
    if r'\label{tab:3}' in text:
        return text
    pattern = re.compile(r'\\textbf\{Таблица ([1-3])\. (.*?)\}\n\n\\emph\{(.*?)\}\n\n(\{\\small\\setlength\{\\tabcolsep\}\{3pt\}\n)(\\begin\{longtable\}.*?)(?=\\toprule)', re.S)

    def caption(m):
        return (m[4] + r'\setlength{\LTcapwidth}{\linewidth}' + '\n' + m[5]
                + r'\caption{' + m[2] + r'\engcap{' + m[3] + '}}'
                + r'\label{tab:' + m[1] + r'}\\' + '\n')

    text, count = pattern.subn(caption, text)
    if count != 3:
        raise ValueError('Exactly three existing bilingual table captions required')
    text = re.sub(r'([Фф]ормул[а-я]* )\(([1-9])\)',
                  lambda m: m[1] + r'\eqref{eq:' + m[2] + '}', text)
    text = re.sub(r'([Рр]исун(?:ок|ка|ке|ку|ком) )([1-3])(?![0-9])',
                  lambda m: m[1] + r'\ref{fig:' + m[2] + '}', text)
    text = re.sub(r'([Тт]аблиц[а-я]* )([1-3])(?![0-9])',
                  lambda m: m[1] + r'\ref{tab:' + m[2] + '}', text)
    return text


def author_blocks(text):
    if r'\clearpage\English\makeauthorsinfo' in text:
        return text
    # Do not allow the journal class's default equal-contribution declaration
    # to become an unsupported statement on behalf of the authors.
    credit = r'\renewcommand{\PSTAnoCRediTstext}{\RussianEnglish{\textcolor{red}{[ДЛЯ АВТОРА: распределение вклада соавторов не подтверждено.]}}{\textcolor{red}{[AUTHOR: individual contributions have not been confirmed.]}}}'
    text = text.replace(r'\begin{document}', credit + '\n' + r'\begin{document}')
    old = r'\renewcommand{\PSTAconflictsofinterests}{\textcolor{red}{[ДЛЯ АВТОРА / AUTHOR: личное заявление о конфликте интересов; не подтверждено исполнителем.]}}'
    new = r'\renewcommand{\PSTAconflictsofinterests}{\RussianEnglish{\textcolor{red}{[ДЛЯ АВТОРА: личное заявление о конфликте интересов; не подтверждено исполнителем.]}}{\textcolor{red}{[AUTHOR: personal conflict-of-interest declaration; not confirmed by the executor.]}}}'
    if old not in text:
        raise ValueError('Expected unresolved declaration not found')
    text = text.replace(old, new)
    text = text.replace(r'\raggedbottom\input{references.bbl}',
                        r'\raggedbottom\input{references.bbl}' + '\n' + r'\clearpage\Russian\makeauthorsinfo')
    text = text.replace(r'\end{document}', r'\clearpage\English\makeauthorsinfo' + '\n' + r'\end{document}')
    return text


def apply_saved(folder):
    folder = Path(folder)
    body = folder / 'body.tex'; main = folder / 'main.tex'
    body.write_text(body_links_and_captions(body.read_text()))
    main.write_text(author_blocks(main.read_text()))
    build = folder / 'build.sh'; script = build.read_text()
    guard = "if grep -F 'pdfTeX warning (dest)' main.log; then exit 1; fi"
    if guard not in script:
        script += '\n' + guard + "\nif grep -F 'Overfull' main.log; then exit 1; fi\n"
        build.write_text(script)


def verify_pdf(path):
    import fitz
    with fitz.open(path) as doc:
        names = doc.resolve_names()
        expected = ['russian--authorsinfo', 'english--authorsinfo']
        expected += [lang + '--author.' + str(i) for lang in ('russian', 'english') for i in (1, 2, 3)]
        expected += ['equation.6', 'figure.russian---3', 'table.russian---3']
        if any(n not in names for n in expected):
            raise ValueError('Missing PDF destination: ' + repr([n for n in expected if n not in names]))
        links = [l for page in doc for l in page.get_links()]
        if any(l.get('kind') == 1 and not 0 <= l.get('page', -1) < len(doc) for l in links):
            raise ValueError('Unresolved internal PDF link')
        transitions = {}
        for name in ('equation.6', 'figure.russian---3', 'table.russian---3'):
            dest = names[name]
            matched = [l for l in links if l.get('kind') == 1 and l.get('page') == dest['page']
                       and abs(l['to'].y - dest['to'][1]) < 2]
            if not matched:
                raise ValueError('No actual link to ' + name)
            transitions[name] = {'page': dest['page'] + 1, 'link_count': len(matched)}
        text = '\n'.join(p.get_text() for p in doc)
        if 'contributed equally' in text or 'равный вклад' in text:
            raise ValueError('Unconfirmed equal-contribution declaration')
        if 'Учёный-исследователь' not in text or 'Researcher in distributed' not in text:
            raise ValueError('Author biographies not visible')
        page = doc[names['table.russian---3']['page']].get_text()
        if not all(x in page for x in ('Итоговая серия', 'Main series', 'Поступления')):
            raise ValueError('Bilingual table caption separated from first data row')
        return {'destinations_checked': expected, 'actual_transitions': transitions,
                'bilingual_table3_on_one_page': True, 'authors_visible': True,
                'unsupported_contribution_declaration': False}
