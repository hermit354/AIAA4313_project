import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
import web_demo.backend as backend

class DemoApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # SQLite handles are released by the process; Windows can retain a
        # short-lived read handle from the test client during class teardown.
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(cls.temp.name)
        backend.DATA=root/'data'; backend.UPLOADS=backend.DATA/'uploads'; backend.ARTIFACTS=backend.DATA/'artifacts'; backend.DB=backend.DATA/'demo.db'
        backend.seed(True); cls.client=TestClient(backend.app)
    def login(self,email):
        r=self.client.post('/api/auth/login',json={'email':email,'password':'demo123'});self.assertEqual(r.status_code,200);return {'Authorization':'Bearer '+r.json()['token']}
    def test_candidate_cannot_read_staff_data(self):
        h=self.login('alice@demo.local')
        self.assertEqual(self.client.get('/api/staff/applications',headers=h).status_code,403)
        response=self.client.get('/api/candidate/application',headers=h);self.assertEqual(response.status_code,200)
        payload=response.json()['application'];self.assertNotIn('score',payload);self.assertNotIn('runs',payload);self.assertNotIn('evidence',payload);self.assertNotIn('model_id',payload)
    def test_reset_removes_only_demo_records(self):
        c=backend.db(); c.execute("insert into users values(?,?,?,?,?)",('real@example.local','Real Candidate','candidate','x',0)); c.execute("insert into applications values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('app-real','real@example.local','real.pdf',None,'real','UNDER_REVIEW',1,50,50,0,0,'{}','{}',0)); c.commit(); c.close()
        self.assertEqual(self.client.post('/api/demo/reset',headers=self.login('staff@demo.local')).status_code,200)
        c=backend.db(); self.assertTrue(c.execute("select 1 from applications where id='app-real'").fetchone()); self.assertEqual(c.execute("select count(*) from applications where is_demo=1").fetchone()[0],4); c.close()
    def test_legacy_storage_column_repair_makes_pdf_rerunnable(self):
        legacy_pdf=backend.UPLOADS/'legacy.pdf'; legacy_pdf.parent.mkdir(parents=True,exist_ok=True); legacy_pdf.write_bytes(b'%PDF-1.4\nlegacy')
        c=backend.db(); c.execute("insert into applications (id,email,filename,sha256,status,created,stored_path,is_demo) values(?,?,?,?,?,?,?,?)",('app-legacy','alice@demo.local','legacy.pdf',str(legacy_pdf),'UNDER_REVIEW','PROCESSING',None,0)); c.commit(); c.close()
        c=backend.db(); repaired=c.execute("select sha256,stored_path,created from applications where id='app-legacy'").fetchone(); c.close()
        self.assertEqual(repaired['stored_path'],str(legacy_pdf)); self.assertNotEqual(repaired['sha256'],str(legacy_pdf)); self.assertIsInstance(repaired['created'],float)
    def test_upload_validation_and_real_run(self):
        h=self.login('alice@demo.local')
        self.assertEqual(self.client.post('/api/candidate/resume',headers=h,files={'file':('bad.txt',b'text','text/plain')}).status_code,415)
        fixture=Path(__file__).resolve().parents[2]/'experiments/data/resumes/clean/baseline_candidate.pdf'
        response=self.client.post('/api/candidate/resume',headers=h,files={'file':('resume.pdf',fixture.read_bytes(),'application/pdf')});self.assertEqual(response.status_code,200)
        backend.WORKER.shutdown(wait=True)
        staff=self.login('staff@demo.local');record=self.client.get('/api/staff/applications/'+response.json()['application_id'],headers=staff).json()
        self.assertEqual(record['status'],'UNDER_REVIEW');self.assertIsNotNone(record['score']);self.assertTrue(record['runs'])
        self.assertEqual(self.client.get('/api/staff/applications/'+record['id']+'/pdf',headers=staff).status_code,200)
        self.assertEqual(self.client.get('/api/staff/runs/'+record['runs'][0]['id']+'/artifact',headers=staff).status_code,200)
        reused=self.client.post('/api/staff/applications/'+record['id']+'/rerun',headers=staff,json={'model':'gemma3:4b','cache':'SAFE_REUSE'});self.assertEqual(reused.status_code,200);self.assertTrue(reused.json()['reused'])
        rejected=self.client.post('/api/staff/applications/'+record['id']+'/rerun',headers=staff,json={'model':'not-allowlisted'});self.assertEqual(rejected.status_code,400)
