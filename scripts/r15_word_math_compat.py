"""Presentation-only OMML compatibility repair; never rasterize an equation.

LibreOffice Math must be installed separately from Writer on minimal runners.
The canonical visible mathematical token stream and all w:t text are retained.
The scoped edits were reproduced on saved FEFC DOCX/PDF in LibreOffice 25.2.3.
"""
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from lxml import etree as E

NS = {
    'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
}


def q(name):
    prefix, local = name.split(':')
    return '{' + NS[prefix] + '}' + local


def mathematical_tokens(element):
    """Canonical visible tokens, including OMML delimiter attributes."""
    name = E.QName(element).localname
    if name in ('rPr', 'ctrlPr', 'dPr', 'oMathParaPr', 'naryPr', 'fPr',
                'sSubPr', 'sSupPr', 'sSubSupPr'):
        return ''
    if name == 't':
        return element.text or ''
    if name == 'd':
        prop = element.find(q('m:dPr'))
        begin = prop.find(q('m:begChr'))
        end = prop.find(q('m:endChr'))
        if begin is None or end is None:
            raise ValueError('Explicit delimiter pair required')
        return (begin.get(q('m:val')) + ''.join(
            mathematical_tokens(c) for c in element
            if E.QName(c).localname != 'dPr') + end.get(q('m:val')))
    return ''.join(mathematical_tokens(c) for c in element)


def repair_math(root):
    """Repair only literal #, positive-part + and affected delimiter imports."""
    before = [mathematical_tokens(e) for e in root.xpath('//m:oMath', namespaces=NS)]
    edits = 0
    for run in root.xpath('//m:r', namespaces=NS):
        text = ''.join(run.xpath('./m:t/text()', namespaces=NS))
        if text == '#' or (text == '+' and E.QName(run.getparent()).localname == 'sub'):
            prop = run.find(q('m:rPr'))
            if prop is None:
                prop = E.Element(q('m:rPr')); run.insert(0, prop)
            if prop.find(q('m:lit')) is None:
                E.SubElement(prop, q('m:lit')); edits += 1
    for element in root.xpath('//m:d', namespaces=NS):
        prop = element.find(q('m:dPr'))
        begin = prop.find(q('m:begChr')); end = prop.find(q('m:endChr'))
        if begin is None or end is None:
            continue
        pair = (begin.get(q('m:val')), end.get(q('m:val')))
        if pair not in [('|', '|'), ('⌈', '⌉')]:
            continue
        parent = element.getparent(); index = parent.index(element)
        colors = element.xpath('.//w:rPr', namespaces=NS)

        def literal(text):
            run = E.Element(q('m:r')); pr = E.SubElement(run, q('m:rPr'))
            E.SubElement(pr, q('m:lit'))
            if colors:
                run.append(deepcopy(colors[0]))
            E.SubElement(run, q('m:t')).text = text
            return run

        replacement = [literal(pair[0])] + [
            deepcopy(c) for c in element.find(q('m:e'))] + [literal(pair[1])]
        parent.remove(element)
        for offset, child in enumerate(replacement):
            parent.insert(index + offset, child)
        edits += 1
    after = [mathematical_tokens(e) for e in root.xpath('//m:oMath', namespaces=NS)]
    if before != after:
        raise ValueError('Mathematical token stream changed')
    return edits, len(before)


def repair_docx_math(path):
    """Retain all document parts; modify only compatibility properties in OMML."""
    path = Path(path)
    with ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    root = E.fromstring(files['word/document.xml'])
    before = root.xpath('//w:t/text()', namespaces=NS)
    edits, count = repair_math(root)
    if root.xpath('//w:t/text()', namespaces=NS) != before:
        raise ValueError('Non-mathematical text changed')
    if edits:
        files['word/document.xml'] = E.tostring(
            root, xml_declaration=True, encoding='UTF-8', standalone=True)
        with ZipFile(path, 'w', ZIP_DEFLATED) as archive:
            for name, value in files.items():
                archive.writestr(name, value)
    return {'file': path.name, 'math_objects': count, 'compatibility_edits': edits,
            'mathematical_tokens_unchanged': True, 'word_text_unchanged': True,
            'equations_are_editable_omml': True}
