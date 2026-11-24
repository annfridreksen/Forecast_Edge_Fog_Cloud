"""Scoped PSTA presentation fixes for review #7146021685; no scientific changes."""
import re
from pathlib import Path


def table_targets(text):
    """Put a stable target inside the printed caption, not before a page break."""
    for n in range(1, 4):
        target = 'fefc-tab:' + str(n)
        if '\\hypertarget{' + target + '}' not in text:
            pattern = re.compile(r'\\caption\{([^\n]*?)\}\\label\{tab:' + str(n) + r'\}\\\\')
            text, count = pattern.subn(lambda m: r'\caption{\hypertarget{' + target + '}{}' + m[1] + r'}\label{tab:' + str(n) + r'}\\', text)
            if count != 1:
                raise ValueError('One caption required for table ' + str(n))
        text = text.replace(r'\ref*{tab:' + str(n) + '}', r'\getrefnumber{russian--tab:' + str(n) + '}')
        text = text.replace(r'\ref{tab:' + str(n) + '}',
                            r'\hyperlink{' + target + r'}{\getrefnumber{russian--tab:' + str(n) + '}}')
    return text


def body_links_and_captions(text):
    if r'\label{tab:3}' in text:
        return table_targets(text)
    pattern = re.compile(r'\\textbf\{Таблица ([1-3])\. (.*?)\}\n\n\\emph\{(.*?)\}\n\n(\{\\small\\setlength\{\\tabcolsep\}\{3pt\}\n)(\\begin\{longtable\}.*?)(?=\\toprule)', re.S)
    def caption(m):
        return (m[4] + r'\setlength{\LTcapwidth}{\linewidth}' + '\n' + m[5]
                + r'\caption{' + m[2] + r'\engcap{' + m[3] + '}}'
                + r'\label{tab:' + m[1] + r'}\\' + '\n')
    text, count = pattern.subn(caption, text)
    if count != 3:
        raise ValueError('Exactly three existing bilingual table captions required')
    text = re.sub(r'([Фф]ормул[а-я]* )\(([1-9])\)', lambda m: m[1] + r'\eqref{eq:' + m[2] + '}', text)
    text = re.sub(r'([Рр]исун(?:ок|ка|ке|ку|ком) )([1-3])(?![0-9])', lambda m: m[1] + r'\ref{fig:' + m[2] + '}', text)
    text = re.sub(r'([Тт]аблиц[а-я]* )([1-3])(?![0-9])', lambda m: m[1] + r'\ref{tab:' + m[2] + '}', text)
    return table_targets(text)


def author_blocks(text):
    if r'\clearpage\English\makeauthorsinfo' in text:
        return text
    credit = r'\renewcommand{\PSTAnoCRediTstext}{\RussianEnglish{\textcolor{red}{[ДЛЯ АВТОРА: распределение вклада соавторов не подтверждено.]}}{\textcolor{red}{[AUTHOR: individual contributions have not been confirmed.]}}}'
    text = text.replace(r'\begin{document}', credit + '\n' + r'\begin{document}')
    old = r'\renewcommand{\PSTAconflictsofinterests}{\textcolor{red}{[ДЛЯ АВТОРА / AUTHOR: личное заявление о конфликте интересов; не подтверждено исполнителем.]}}'
    new = r'\renewcommand{\PSTAconflictsofinterests}{\RussianEnglish{\textcolor{red}{[ДЛЯ АВТОРА: личное заявление о конфликте интересов; не подтверждено исполнителем.]}}{\textcolor{red}{[AUTHOR: personal conflict-of-interest declaration; not confirmed by the executor.]}}}'
    if old not in text:
        raise ValueError('Expected unresolved declaration not found')
    text = text.replace(old, new)
    text = text.replace(r'\raggedbottom\input{references.bbl}', r'\raggedbottom\input{references.bbl}' + '\n' + r'\clearpage\Russian\makeauthorsinfo')
    return text.replace(r'\end{document}', r'\clearpage\English\makeauthorsinfo' + '\n' + r'\end{document}')


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
    path = Path(path)
    aux = path.with_suffix('.aux').read_text()
    match = re.search(r'\\newlabel\{eq:6\}.*?\{(equation\.[^{}]+)\}', aux)
    if not match:
        raise ValueError('Equation 6 has no resolved source label')
    equation = match[1]
    with fitz.open(path) as doc:
        names = doc.resolve_names()
        expected = ['russian--authorsinfo', 'english--authorsinfo']
        expected += [lang + '--author.' + str(i) for lang in ('russian', 'english') for i in (1, 2, 3)]
        expected += [equation, 'figure.russian---3', 'fefc-tab:3']
        if any(n not in names for n in expected):
            raise ValueError('Missing PDF destination: ' + repr([n for n in expected if n not in names]))
        links = [l for page in doc for l in page.get_links()]
        for link in links:
            if link.get('kind') in (fitz.LINK_GOTO, fitz.LINK_NAMED):
                if not 0 <= link.get('page', -1) < len(doc):
                    raise ValueError('Unresolved internal PDF link')
        transitions = {}
        for name in (equation, 'figure.russian---3', 'fefc-tab:3'):
            dest = names[name]
            matched = [l for l in links if l.get('page') == dest['page'] and (
                l.get('nameddest') == name or
                (l.get('kind') == fitz.LINK_GOTO and
                 min(abs(l['to'].y - dest['to'][1]),
                     abs(l['to'].y - (doc[dest['page']].rect.height - dest['to'][1]))) < 2))]
            if not matched:
                raise ValueError('No actual link to ' + name)
            transitions[name] = {'page': dest['page'] + 1, 'link_count': len(matched)}
        text = '\n'.join(p.get_text() for p in doc)
        if 'contributed equally' in text or 'равный вклад' in text:
            raise ValueError('Unconfirmed equal-contribution declaration')
        if 'Учёный-исследователь' not in text or 'Researcher in distributed' not in text:
            raise ValueError('Author biographies not visible')
        page = doc[names['fefc-tab:3']['page']].get_text()
        if not all(x in page for x in ('Итоговая серия', 'Main series', 'Поступления')):
            raise ValueError('Bilingual table caption separated from first data row')
        return {'destinations_checked': expected, 'equation6_destination_from_aux': equation,
                'actual_transitions': transitions, 'bilingual_table3_on_one_page': True,
                'authors_visible': True, 'unsupported_contribution_declaration': False}
