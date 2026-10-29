from pathlib import Path
import importlib.util,re,json,zipfile,csv
from lxml import etree
from PIL import Image,ImageDraw
R=Path.cwd();base=R/'docs/research/manuals/CLE-MAN-20261028-current';out=base/'preview'
spec=importlib.util.spec_from_file_location('render',r'C:/Users/fujunye/.codex/plugins/cache/openai-primary-runtime/documents/26.1020.11618/skills/documents/render_docx.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.convert_to_pdf=lambda *args,**kwargs:(str(out/'qa_final.pdf'),'Word native PDF')
md=R/'docs/CLE项目全景手册_零基础完整版_20261028.md';doc=md.with_suffix('.docx')
paths=m.rasterize(str(doc),str(out),90,False,False)
paths=sorted(map(Path,paths),key=lambda p:int(re.search(r'page-(\d+)',p.name)[1]))
for start in range(0,len(paths),12):
 group=paths[start:start+12];sheet=Image.new('RGB',(1000,370*((len(group)+3)//4)),'#ddd');dr=ImageDraw.Draw(sheet)
 for i,p in enumerate(group):
  im=Image.open(p);im.thumbnail((240,340));x=(i%4)*250;y=(i//4)*370;sheet.paste(im,(x,y+20));dr.text((x+5,y+3),p.stem,fill='black')
 sheet.save(out/f'contact-{start//12+1}.png')
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
with zipfile.ZipFile(doc) as z:xml=etree.fromstring(z.read('word/document.xml'))
marks=xml.xpath('//w:bookmarkStart/@w:name',namespaces=ns);links=xml.xpath('//w:hyperlink/@w:anchor',namespaces=ns)
missing=sorted(set(links)-set(marks));assert not missing,missing
local=[]
for target in re.findall(r'\]\(([^)]+)\)',md.read_text(encoding='utf-8')):
 if target.startswith(('#','http:','https:')):continue
 p=(md.parent/target.split('#')[0]);
 if not p.exists():local.append(target)
print(json.dumps({'pages':len(paths),'bookmarks':len(marks),'internal_links':len(links),'missing_anchors':missing,'missing_local_links':local},ensure_ascii=False))
(base/'evidence/document_checks.json').write_text(json.dumps({'pages':len(paths),'bookmarks':len(marks),'internal_links':len(links),'missing_anchors':missing,'missing_local_links':local},indent=2,ensure_ascii=False),encoding='utf-8')



