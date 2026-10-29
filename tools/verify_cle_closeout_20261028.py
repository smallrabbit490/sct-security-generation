from pathlib import Path
import importlib.util,re,json,zipfile
from lxml import etree
from PIL import Image,ImageDraw
R=Path.cwd();O=R/'docs/research/reports/CLE-PKG-20261022-20261028-closeout-v01'
spec=importlib.util.spec_from_file_location('render',r'C:/Users/fujunye/.codex/plugins/cache/openai-primary-runtime/documents/26.1020.11618/skills/documents/render_docx.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
for i,doc in enumerate(O.glob('*.docx')):
 pdf=O/'preview'/('atlas_final.pdf' if '思路图汇总' in doc.stem else doc.stem+'.pdf');out=O/'preview'/str(i);m.convert_to_pdf=lambda *args,**kwargs:(str(pdf),'Word native PDF');paths=list(map(Path,m.rasterize(str(doc),str(out),60,False,False)));paths.sort(key=lambda p:int(re.search(r'page-(\d+)',p.name)[1]))
 for start in range(0,len(paths),12):
  group=paths[start:start+12];sheet=Image.new('RGB',(1200,350*((len(group)+3)//4)),'#ddd');dr=ImageDraw.Draw(sheet)
  for j,p in enumerate(group):
   im=Image.open(p);im.thumbnail((290,320));x=j%4*300;y=j//4*350;sheet.paste(im,(x,y+20));dr.text((x,y),p.stem,fill='black')
  sheet.save(O/'preview'/f'contact-{i}-{start//12}.png')
 ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
 with zipfile.ZipFile(doc) as z:xml=etree.fromstring(z.read('word/document.xml'))
 marks=xml.xpath('//w:bookmarkStart/@w:name',namespaces=ns);links=xml.xpath('//w:hyperlink/@w:anchor',namespaces=ns);assert not set(links)-set(marks)
 if '结论与下一步' in doc.stem:assert len(paths)==1,len(paths)
 checks.append({'file':doc.name,'render_folder':i,'pages':len(paths),'internal_links':len(links),'missing_anchors':[]})
(O/'evidence/document_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(checks,ensure_ascii=False))
