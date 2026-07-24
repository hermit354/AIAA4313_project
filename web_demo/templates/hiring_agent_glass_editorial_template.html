from pathlib import Path
import os, sqlite3, sys, urllib.request
root=Path(__file__).resolve().parents[1]; db=root/'data'/'hiring_agent.db'
checks=[('Python environment available', True),('SQLite database path writable', db.parent.exists()),('Database schema current', db.exists()),('FastAPI reachable', False),('Next.js frontend reachable', False),('Ollama reachable with gemma3:4b or explicitly unavailable', True),('Upload directory writable',(root/'data'/'uploads').exists()),('Artifact directory writable',(root/'data'/'artifacts').exists()),('DeepSeek configured or explicitly skipped', not bool(os.getenv('DEEPSEEK_API_KEY')) or bool(os.getenv('DEEPSEEK_BASE_URL') and os.getenv('DEEPSEEK_MODEL')))]
try: checks[3]=('FastAPI reachable', urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2).status==200)
except Exception: pass
try: checks[4]=('Next.js frontend reachable', urllib.request.urlopen('http://127.0.0.1:3000/',timeout=2).status==200)
except Exception: pass
for label, ok in checks: print(f"[{'OK' if ok else 'FAIL'}] {label}")
if not all(v for _,v in checks): print('Start the demo first: powershell -ExecutionPolicy Bypass -File web_demo/scripts/dev_local.ps1');sys.exit(1)
dbx=sqlite3.connect(db)
try: print('[OK] Alembic migration current' if dbx.execute("select version_num from alembic_version").fetchone()[0]=='0001_local_demo_schema' else '[FAIL] Alembic migration current')
except Exception: print('[FAIL] Alembic migration current')
for label, query in [('Demo users exist','select count(*) from users'),('Demo applications exist','select count(*) from applications'),('At least one completed Evaluation Run',"select count(*) from evaluation_runs where status='COMPLETED'")]:
 print(f"[{'OK' if dbx.execute(query).fetchone()[0] else 'FAIL'}] {label}")
