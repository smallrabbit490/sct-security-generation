"""验证本次文档链接与字体；使用原生Word导出的PDF进行官方渲染器分页检查。"""
from pathlib import Path
import argparse
import importlib.util
import json
import re
import sys
from urllib.parse import unquote,urlparse
from zipfile import ZipFile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.build_cle_weekly_package_20261028 import OUT,SUMMARY,MAP,REPORT,build_word
TEMPLATES=ROOT/'docs/research/templates'
TEMPLATE_NAMES=['CLE-TPL-weekly-summary-v02','CLE-TPL-weekly-idea-map-v01','CLE-TPL-weekly-experiment-report-v04']
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def build_templates():
    for name,kind in zip(TEMPLATE_NAMES,['summary','map','report']):
        build_word(TEMPLATES/(name+'.md'),kind)


def docs():
    return [OUT/(s+'.docx') for s in [SUMMARY,MAP,REPORT]]+[TEMPLATES/(s+'.docx') for s in TEMPLATE_NAMES]


def preview(doc):
    return (OUT/'preview'/doc.stem) if doc.parent==OUT else (OUT/'preview/templates'/doc.stem)


def render():
    path=Path('C:/Users/fujunye/.codex/plugins/cache/openai-primary-runtime/documents/26.1020.11618/skills/documents/render_docx.py')
    spec=importlib.util.spec_from_file_location('docx_render',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    counts={}
    for doc in docs():
        folder=preview(doc);pdf=folder/'render.pdf'
        # PDF由本次隐藏Word实例导出；分页栅格化仍使用文档技能的render_docx。
        mod.convert_to_pdf=lambda *args, pdf=pdf,**kwargs:(str(pdf),'Microsoft Word native export')
        pages=mod.rasterize(str(doc),str(folder),120,False,False)
        counts[doc.stem]=len(pages)
    print(json.dumps(counts,ensure_ascii=False))
    return counts


def verify():
    result={};errors=[]
    all_docs=docs()
    for doc in all_docs:
        with ZipFile(doc) as z:
            xml=ET.fromstring(z.read('word/document.xml'))
            rel=ET.fromstring(z.read('word/_rels/document.xml.rels'))
            bookmarks={e.get(W+'name') for e in xml.iter(W+'bookmarkStart')}
            rels={e.get('Id'):e.get('Target') for e in rel}
            hyperlinks=list(xml.iter(W+'hyperlink'))
            for h in hyperlinks:
                anchor=h.get(W+'anchor');rid=h.get(R+'id')
                if not rid:
                    if anchor not in bookmarks:errors.append(f'{doc.name}:missing_anchor:{anchor}')
                    continue
                target=rels[rid]
                if target.startswith('file:'):
                    local=unquote(urlparse(target).path).lstrip('/')
                    p=Path(local)
                    if not p.exists():errors.append(f'{doc.name}:missing_target:{p}')
                    if anchor and p.suffix=='.docx' and p.exists():
                        with ZipFile(p) as other:
                            anchors={e.get(W+'name') for e in ET.fromstring(other.read('word/document.xml')).iter(W+'bookmarkStart')}
                        if anchor not in anchors:errors.append(f'{doc.name}:external_anchor:{p.name}#{anchor}')
            styles=ET.fromstring(z.read('word/styles.xml'))
            for name in ['Normal','Title','Heading1','Heading2','Heading3','Heading1Char','Heading2Char','Heading3Char']:
                st=next((s for s in styles.iter(W+'style') if s.get(W+'styleId')==name),None)
                if st is not None:
                    f=st.find(W+'rPr/'+W+'rFonts')
                    if f is None or f.get(W+'eastAsia')!='宋体' or f.get(W+'ascii')!='Times New Roman':errors.append(f'{doc.name}:font:{name}')
            count=len(list(preview(doc).glob('page-*.png')))
            result[doc.name]={'bookmarks':len(bookmarks),'hyperlinks':len(hyperlinks),'rendered_pages':count}
    if result[SUMMARY+'.docx']['rendered_pages']!=1:errors.append('summary_not_one_page')
    for md in OUT.glob('*.md'):
        text=md.read_text(encoding='utf-8');anchors=set(re.findall(r'<a id="([^"]+)"',text))
        for target in re.findall(r'\]\(([^)]+)\)',text):
            path,_,anchor=target.partition('#')
            if urlparse(path).scheme in ('https','http'):continue
            p=(md.parent/path).resolve() if path else md
            if not p.exists():errors.append(f'{md.name}:missing_md_target:{target}');continue
            if anchor and p.suffix=='.md' and f'<a id="{anchor}">' not in p.read_text(encoding='utf-8-sig'):
                errors.append(f'{md.name}:missing_md_anchor:{target}')
    data={'status':'passed' if not errors else 'failed','documents':result,'errors':errors}
    (OUT/'verification.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(data,ensure_ascii=False))
    if errors:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['templates','render','verify']);a=p.parse_args()
    {'templates':build_templates,'render':render,'verify':verify}[a.mode]()
