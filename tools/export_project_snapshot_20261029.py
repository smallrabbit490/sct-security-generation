"""Export a deduplicated project snapshot without credentials or installed runtimes."""
from pathlib import Path
import os,subprocess,hashlib,json,zipfile,re,time,sqlite3

ROOT=Path(__file__).resolve().parents[1]
OUT=Path('E:/ResearchExports/CLE/20261029');OUT.mkdir(parents=True,exist_ok=True)
DB=sqlite3.connect(OUT/'export.sqlite3')
DB.execute('create table if not exists files(path text primary key,size integer,mtime integer,digest text)')
blocked={'.git','__pycache__','node_modules','.venv','venv','cle_memory_q_env','local_secrets','服务器连接','.workbuddy-ai'}
secret=re.compile(rb'(?<![A-Za-z0-9_-])(?:sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{25,})|Bearer\s+[A-Za-z0-9_.-]{30,}')
text_ext={'.py','.md','.json','.jsonl','.txt','.toml','.yaml','.yml','.csv','.js','.ts','.html','.xml','.svg','.ps1','.log','.ini','.cfg','.sh','.bat'}
def allowed(p):
 n=p.name.lower()
 return not (n.startswith(('.env','~$')) or any(x in n for x in ('apikey','api_key','credentials','password','cookie','密码')) or p.suffix.lower() in {'.pem','.key','.pyc','.pyo','.vhdx','.lock'} or n in {'id_rsa','id_ed25519'})
def walk(base,prefix):
 for a,ds,fs in os.walk(base):
  ds[:]=sorted(x for x in ds if x not in blocked)
  for f in sorted(fs):
   p=Path(a)/f
   if allowed(p):yield p,str(Path(prefix)/p.relative_to(base)).replace('\\','/')
def stream(p):
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024):yield b

files=[]
tracked=subprocess.check_output(['git','ls-files','-co','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
for name in sorted(set(tracked)):
 p=ROOT/name
 if name and p.is_file() and allowed(p) and not any(x in blocked for x in p.parts):files.append((p,'project/'+name.replace('\\','/')))
for sub in ['baseline_runs','diagnostics','sct_runs','cache']:
 files.extend(walk(ROOT/'translation_work'/sub,'project/translation_work/'+sub))
files.extend(walk(Path('E:/ResearchRuns/CLE/20261027_full_requirements'),'external_runs/20261027_full_requirements'))
print('inventory',len(files),flush=True)
manifest=[];unique={};redacted=[];started=time.time()
for i,(p,name) in enumerate(files):
 st=p.stat();old=DB.execute('select size,mtime,digest from files where path=?',(str(p),)).fetchone()
 if old and old[:2]==(st.st_size,st.st_mtime_ns):digest=old[2]
 else:
  h=hashlib.sha256()
  for b in stream(p):h.update(b)
  digest=h.hexdigest();DB.execute('insert or replace into files values(?,?,?,?)',(str(p),st.st_size,st.st_mtime_ns,digest))
 manifest.append({'path':name,'size':st.st_size,'blob':digest,'mtime_ns':st.st_mtime_ns})
 unique.setdefault(digest,p)
 if i%2000==0:DB.commit();print('hashed',i,'unique',len(unique),'seconds',round(time.time()-started),flush=True)
DB.commit()
(OUT/'manifest.json').write_text(json.dumps({'format':'content-addressed-zip-v1','created':'2026-10-29','branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),'excludes':'credentials, installed runtimes, bytecode, locks; older 20261022 release remains available','files':manifest},ensure_ascii=False),encoding='utf8')
part=0;budget=0;z=None
for i,(digest,p) in enumerate(unique.items()):
 if z is None or budget>700_000_000:
  if z:z.close()
  part+=1;budget=0;z=zipfile.ZipFile(OUT/f'CLE-snapshot-20261029-blobs-{part:03}.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=1)
 data=None
 if p.suffix.lower() in text_ext and p.stat().st_size<100_000_000:
  data=p.read_bytes();clean,n=secret.subn(b'[REDACTED_CREDENTIAL]',data)
  if n:redacted.append({'blob':digest,'occurrences':n});data=clean
 if data is None:z.write(p,'blobs/'+digest)
 else:z.writestr('blobs/'+digest,data)
 budget=z.fp.tell()
 if i%2000==0:print('packed',i,'part',part,flush=True)
if z:z.close()
shipped={x['blob'] for x in redacted}
for row in manifest:
 if row['blob'] in shipped:row['export_redacted']=True
(OUT/'manifest.json').write_text(json.dumps({'format':'content-addressed-zip-v1','created':'2026-10-29','files':manifest,'redactions':redacted,'exclusions':'credentials, installed runtimes, bytecode, locks'},ensure_ascii=False),encoding='utf8')
(OUT/'restore.py').write_text('''from pathlib import Path
import json,zipfile,shutil
base=Path(__file__).resolve().parent; out=base/'restored'; blobs=base/'blobs'
for p in sorted(base.glob('*blobs-*.zip')):
 with zipfile.ZipFile(p) as z:z.extractall(base)
for row in json.loads((base/'manifest.json').read_text(encoding='utf8'))['files']:
 p=out/row['path'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(blobs/row['blob'],p)
print('Restored to',out)
''',encoding='utf8')
receipt={'files':len(manifest),'unique_blobs':len(unique),'original_bytes':sum(x['size'] for x in manifest),'parts':part,'redacted_blobs':len(redacted),'archives_bytes':sum(p.stat().st_size for p in OUT.glob('*blobs-*.zip'))}
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print('DONE',receipt,flush=True)
