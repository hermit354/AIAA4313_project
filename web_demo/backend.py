"""FastAPI + SQLite local Hiring Agent demo; no Docker or external worker."""
from __future__ import annotations
import hashlib, json, secrets, sqlite3, time, uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from web_demo.pipeline import PipelineConfig, provider_registry, run_resume_pipeline

ROOT=Path(__file__).resolve().parent; DATA=ROOT/'data'; UPLOADS=DATA/'uploads'; ARTIFACTS=DATA/'artifacts'; DB=DATA/'hiring_agent.db'; TOKENS={}; WORKER=ThreadPoolExecutor(max_workers=1)
app=FastAPI(title='Hiring Agent Local Demo',version='1.0.0')
def db():
 DATA.mkdir(exist_ok=True);UPLOADS.mkdir(exist_ok=True);ARTIFACTS.mkdir(exist_ok=True); c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 c.executescript('''create table if not exists users(email text primary key,name text,role text,password text,is_demo integer);
 create table if not exists applications(id text primary key,email text,filename text,stored_path text,sha256 text,status text,created real,score real,base real,bonus real,deduction real,resume_json text,evidence_json text,is_demo integer);
 create table if not exists evaluation_runs(id text primary key,application_id text,provider text,model_id text,status text,created real,completed real,score real,config_json text,config_fingerprint text,reused_from text,error text);
 create table if not exists stage_runs(id text primary key,run_id text,name text,status text,duration_ms integer,note text,artifact_path text);
 create table if not exists app_settings(key text primary key,value text);''')
 # Upgrade the first local prototype without deleting user data.
 for col,typ in [('stored_path','text'),('base','real'),('bonus','real'),('deduction','real'),('resume_json','text'),('evidence_json','text'),('is_demo','integer')]:
  try:c.execute(f'alter table applications add column {col} {typ}')
  except sqlite3.OperationalError:pass
 try:c.execute('alter table users add column is_demo integer')
 except sqlite3.OperationalError:pass
 # The initial prototype inserted applications positionally before
 # ``stored_path`` existed. Repair those records without touching valid data.
 for legacy in c.execute("select id,sha256,created from applications where stored_path is null and sha256 like '%.pdf'").fetchall():
  source=Path(legacy['sha256'])
  if source.is_file():
   created=legacy['created']
   if not isinstance(created,(int,float)):
    run=c.execute('select created from evaluation_runs where application_id=? order by created limit 1',(legacy['id'],)).fetchone()
    created=float(run['created']) if run else stamp()
   c.execute('update applications set stored_path=?,sha256=?,created=? where id=?',(str(source),hashlib.sha256(source.read_bytes()).hexdigest(),created,legacy['id']))
 c.execute("update evaluation_runs set status='FAILED_STALE',error='Recovered at server startup' where status='RUNNING'");c.commit();return c
def rowdict(r): return dict(r) if r else None
def stamp(): return time.time()
def provider_for(model_id):
 return next((m['provider'].lower() for m in provider_registry() if m['id']==model_id),'ollama')
def queue_stages(c,rid):
 for name in ['PDF_TEXT_EXTRACTION','RESUME_SECTION_PARSE','EVALUATION','RANK_AND_PERSIST']:
  c.execute('insert into stage_runs values(?,?,?,?,?,?,?)',(uuid.uuid4().hex,rid,name,'QUEUED',0,'Waiting for local worker',None))
def seed(reset=False):
 c=db()
 if reset:
  paths=[r[0] for r in c.execute("select stored_path from applications where is_demo=1 and stored_path is not null")]
  c.execute("delete from stage_runs where run_id in (select id from evaluation_runs where application_id in (select id from applications where is_demo=1))")
  c.execute("delete from evaluation_runs where application_id in (select id from applications where is_demo=1)")
  c.execute("delete from applications where is_demo=1");c.execute("delete from users where is_demo=1");c.execute("delete from app_settings")
  for p in paths:
   try:Path(p).unlink()
   except OSError:pass
 if not c.execute("select 1 from users where email='staff@demo.local'").fetchone():
  c.executemany('insert into users values(?,?,?,?,?)',[('staff@demo.local','Research Staff','staff','demo123',1),('alice@demo.local','Alice Chen','candidate','demo123',1)])
  demo=[('app-alice','alice@demo.local','Alice Chen',91.5,87,6,1.5),('app-david','david@demo.local','David Lee',86,84,3,1),('app-maya','maya@demo.local','Maya Singh',82.5,81,2.5,1),('app-evan','alice@demo.local','Evan Liu',18.5,21,0,2.5)]
  for aid,email,name,score,base,bonus,ded in demo:
   resume={'basics':{'name':name,'email':email},'skills':['Python','FastAPI','SQL'],'work':['Seeded demonstration resume']};evidence={'strengths':['Fixed demo record with evidence.'],'improvements':['Human review remains required.']}
   c.execute('insert into applications (id,email,filename,stored_path,sha256,status,created,score,base,bonus,deduction,resume_json,evidence_json,is_demo) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,email,name.lower().replace(' ','_')+'.pdf',None,'seed-'+aid,'UNDER_REVIEW',stamp(),score,base,bonus,ded,json.dumps(resume),json.dumps(evidence),1))
   rid='run-'+aid[4:];cfg=PipelineConfig();c.execute('insert into evaluation_runs values(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,aid,'ollama','gemma3:4b','COMPLETED',stamp(),stamp(),score,json.dumps(cfg.__dict__),cfg.fingerprint(),None,None))
   for n in ['PDF_TEXT_EXTRACTION','RESUME_SECTION_PARSE','EVALUATION','RANK_AND_PERSIST']:c.execute('insert into stage_runs values(?,?,?,?,?,?,?)',(uuid.uuid4().hex,rid,n,'COMPLETED',100,'Seeded demo stage',None))
  c.execute("insert into app_settings values('default_model','gemma3:4b')")
 c.commit();c.close()
def user(authorization:Annotated[str|None,Header()]=None):
 token=(authorization or '').removeprefix('Bearer ')
 if token not in TOKENS:raise HTTPException(401,'Sign in required')
 return TOKENS[token]
def staff(u=Depends(user)):
 if u['role']!='staff':raise HTTPException(403,'Staff access required')
 return u
class Login(BaseModel):email:str;password:str
class RunRequest(BaseModel):model:str='gemma3:4b';temperature:float=.1;topP:float=.9;prompt:str='web-v1';cache:str='SAFE_REUSE';github:bool=True
class Setting(BaseModel):model_id:str
@app.on_event('startup')
def start():seed()
@app.get('/')
def page():return FileResponse(ROOT/'templates'/'hiring_agent_glass_editorial_template.html')
@app.get('/health')
def health():return {'ok':True,'db_writable':DATA.exists(),'models':provider_registry()}
@app.post('/api/auth/login')
def login(x:Login):
 r=db().execute('select email,name,role,password from users where email=?',(x.email.lower(),)).fetchone()
 if not r or r['password']!=x.password:raise HTTPException(401,'Invalid email or password')
 token=secrets.token_urlsafe(32);TOKENS[token]={'email':r['email'],'name':r['name'],'role':r['role']};return {'token':token,'user':TOKENS[token]}
@app.get('/api/me')
def me(u=Depends(user)):return u
def app_view(r,c):
 d=rowdict(r);d['resume']=json.loads(d.pop('resume_json') or '{}');d['evidence']=json.loads(d.pop('evidence_json') or '{}');d['runs']=[rowdict(x) for x in c.execute('select * from evaluation_runs where application_id=? order by created desc',(d['id'],))];return d
@app.get('/api/candidate/application')
def candidate_application(u=Depends(user)):
 if u['role']!='candidate':raise HTTPException(403,'Candidate access required')
 c=db();r=c.execute('select id,filename,status,created from applications where email=? order by created desc limit 1',(u['email'],)).fetchone()
 # Candidate responses are deliberately a separate projection.  Do not reuse
 # app_view here: it contains staff-only score, model, evidence, artifact and
 # pipeline data.
 return {'application':rowdict(r)}
@app.get('/api/staff/applications')
def applications(u=Depends(staff)):
 c=db();return [app_view(r,c) for r in c.execute('select * from applications order by score desc nulls last,created desc')]
@app.get('/api/staff/applications/{aid}')
def detail(aid:str,u=Depends(staff)):
 c=db();r=c.execute('select * from applications where id=?',(aid,)).fetchone()
 if not r:raise HTTPException(404,'Application not found')
 return app_view(r,c)
@app.get('/api/staff/runs/{rid}/stages')
def stages(rid:str,u=Depends(staff)):return [rowdict(x) for x in db().execute('select * from stage_runs where run_id=?',(rid,))]
@app.get('/api/staff/runs/{rid}/artifact')
def run_artifact(rid:str,u=Depends(staff)):
 r=db().execute("select artifact_path from stage_runs where run_id=? and artifact_path is not null limit 1",(rid,)).fetchone()
 if not r or not Path(r['artifact_path']).exists():raise HTTPException(404,'Run artifact unavailable')
 return FileResponse(r['artifact_path'],media_type='application/json',filename=rid+'.json')
@app.get('/api/staff/models')
def models(u=Depends(staff)):
 c=db();r=c.execute("select value from app_settings where key='default_model'").fetchone();return {'default_model':r['value'] if r else 'gemma3:4b','models':provider_registry()}
def enqueue(aid,rid,path,config):WORKER.submit(execute_run,aid,rid,path,config)
def execute_run(aid,rid,path,config):
 c=db();c.execute("update evaluation_runs set status='RUNNING' where id=?",(rid,));c.execute("update stage_runs set status='RUNNING',note='Local worker started' where run_id=? and name='PDF_TEXT_EXTRACTION'",(rid,));c.commit()
 try:
  result=run_resume_pipeline(path,config);artifact=ARTIFACTS/(rid+'.json');artifact.write_text(json.dumps(result.to_json(),indent=2),encoding='utf-8')
  c.execute('update evaluation_runs set status=?,completed=?,score=? where id=?',(result.status,stamp(),result.score,rid));c.execute('update applications set status=?,score=?,base=?,bonus=?,deduction=?,resume_json=?,evidence_json=? where id=?',('UNDER_REVIEW',result.score,result.base,result.bonus,result.deduction,json.dumps(result.resume),json.dumps(result.evidence),aid))
  for s in result.stages:c.execute('update stage_runs set status=?,duration_ms=?,note=?,artifact_path=? where run_id=? and name=?',(s.status,s.duration_ms,s.note,str(artifact),rid,s.name))
 except Exception as exc:c.execute("update evaluation_runs set status='FAILED',completed=?,error=? where id=?",(stamp(),str(exc),rid));c.execute("update stage_runs set status='FAILED',note=? where run_id=? and status='RUNNING'",(str(exc),rid));c.execute("update applications set status='FAILED' where id=?",(aid,))
 c.commit();c.close()
@app.post('/api/candidate/resume')
async def upload(file:UploadFile=File(...),u=Depends(user)):
 if u['role']!='candidate':raise HTTPException(403,'Candidate access required')
 if file.content_type not in {'application/pdf','application/x-pdf'} or not (file.filename or '').lower().endswith('.pdf'):raise HTTPException(415,'Only PDF resumes are accepted')
 raw=await file.read()
 if not raw or len(raw)>10*1024*1024 or not raw.startswith(b'%PDF'):raise HTTPException(400,'Invalid, empty, or oversized PDF')
 sha=hashlib.sha256(raw).hexdigest();stored=UPLOADS/(uuid.uuid4().hex+'.pdf');stored.write_bytes(raw);aid='app-'+uuid.uuid4().hex[:10];rid='run-'+uuid.uuid4().hex[:10];c=db();model=(c.execute("select value from app_settings where key='default_model'").fetchone() or ['gemma3:4b'])[0];config=PipelineConfig(model_id=model)
 config=PipelineConfig(provider=provider_for(model),model_id=model);c.execute('insert into applications (id,email,filename,stored_path,sha256,status,created,score,base,bonus,deduction,resume_json,evidence_json,is_demo) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,u['email'],file.filename,str(stored),sha,'PROCESSING',stamp(),None,None,None,None,None,None,0));c.execute('insert into evaluation_runs values(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,aid,config.provider,model,'QUEUED',stamp(),None,None,json.dumps(config.__dict__),config.fingerprint(),None,None));queue_stages(c,rid);c.commit();c.close();enqueue(aid,rid,stored,config);return {'application_id':aid,'run_id':rid,'name':file.filename,'size':len(raw),'sha256':sha}
@app.post('/api/staff/applications/{aid}/rerun')
def rerun(aid:str,x:RunRequest,u=Depends(staff)):
 c=db();a=c.execute('select * from applications where id=?',(aid,)).fetchone()
 if not a:raise HTTPException(404,'Application not found')
 if x.model not in [m['id'] for m in provider_registry()]:raise HTTPException(400,'Model is not allowlisted')
 config=PipelineConfig(provider=provider_for(x.model),model_id=x.model,temperature=x.temperature,top_p=x.topP,prompt_version=x.prompt,github_enrichment=x.github,force_fresh=x.cache=='FORCE_FRESH');fp=config.fingerprint()
 if not config.force_fresh:
  old=c.execute("select id from evaluation_runs where application_id=? and config_fingerprint=? and status='COMPLETED'",(aid,fp)).fetchone()
  if old:return {'id':old['id'],'status':'COMPLETED','reused':True}
 if not a['stored_path']:raise HTTPException(409,'Seed records have no source PDF; upload a PDF to run a real evaluation')
 rid='run-'+uuid.uuid4().hex[:10];c.execute('insert into evaluation_runs values(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,aid,config.provider,x.model,'QUEUED',stamp(),None,None,json.dumps(config.__dict__),fp,None,None));queue_stages(c,rid);c.commit();c.close();enqueue(aid,rid,a['stored_path'],config);return {'id':rid,'status':'QUEUED','reused':False}
@app.patch('/api/staff/settings/default-model')
def model(x:Setting,u=Depends(staff)):
 if x.model_id not in [m['id'] for m in provider_registry()]:raise HTTPException(400,'Model is not allowlisted')
 c=db();c.execute("insert or replace into app_settings values('default_model',?)",(x.model_id,));c.commit();return x
@app.get('/api/staff/applications/{aid}/pdf')
def pdf(aid:str,u=Depends(staff)):
 r=db().execute('select stored_path,filename from applications where id=?',(aid,)).fetchone()
 if not r or not r['stored_path'] or not Path(r['stored_path']).exists():raise HTTPException(404,'PDF artifact unavailable')
 return FileResponse(r['stored_path'],media_type='application/pdf',filename=r['filename'])
@app.post('/api/demo/reset')
def reset(u=Depends(staff)):seed(True);return {'ok':True}
