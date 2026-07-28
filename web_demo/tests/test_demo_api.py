import sys
import tempfile
import unittest
from pathlib import Path

import fitz

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

    def test_modal_actions_are_not_rebound_after_every_document_click(self):
        """A second binding makes one Rerun click enqueue multiple executions."""
        template=(Path(__file__).resolve().parents[1]/'templates'/'hiring_agent_glass_editorial_template.html').read_text(encoding='utf-8')
        self.assertNotIn('setTimeout(bindModalActions, 0);',template)

    def test_system_run_open_preserves_run_context_and_detail_can_switch_runs(self):
        template=(Path(__file__).resolve().parents[1]/'templates'/'hiring_agent_glass_editorial_template.html').read_text(encoding='utf-8')
        self.assertIn('runId: params.get(\'run\')',template)
        self.assertIn('data-detail-run-select',template)
        self.assertIn('data-run-id="${item.id}"',template)
        self.assertIn('?run=${encodeURIComponent(button.dataset.runId)}',template)
        self.assertNotIn('const run = candidate.runs[0];',template)

    def test_review_cutoff_is_consistently_set_to_sixty(self):
        template=(Path(__file__).resolve().parents[1]/'templates'/'hiring_agent_glass_editorial_template.html').read_text(encoding='utf-8')
        self.assertIn('const REVIEW_CUTOFF = 60;',template)
        self.assertEqual(template.count('score < REVIEW_CUTOFF'),2)
        self.assertNotIn('score < 40',template)

    def test_staff_can_select_a_default_defense_profile(self):
        h=self.login('staff@demo.local')
        profiles=self.client.get('/api/staff/defense-profiles',headers=h)
        self.assertEqual(profiles.status_code,200)
        self.assertEqual({item['id'] for item in profiles.json()['profiles']},{'v0_weak','baseline','v1_5_semantic','v2_structured','v3_vlm'})
        self.assertIn('20734_patch',{item['id'] for item in profiles.json()['github_fixtures']})
        fixture={item['id']:item for item in profiles.json()['github_fixtures']}['20734_patch']
        self.assertEqual(fixture['demo_url'],'https://github.com/YrpSponge/ipi-20734-evaluation-patch-demo')
        updated=self.client.patch('/api/staff/settings/default-defense-profile',headers=h,json={'profile_id':'v2_structured'})
        self.assertEqual(updated.status_code,200)
        self.assertEqual(updated.json()['profile_id'],'v2_structured')

    def test_system_runs_are_sorted_newest_first(self):
        template=(Path(__file__).resolve().parents[1]/'templates'/'hiring_agent_glass_editorial_template.html').read_text(encoding='utf-8')
        self.assertIn('createdAt:Number(run.created || 0)',template)
        self.assertIn('.sort((left, right) => right.createdAt - left.createdAt)',template)

    def test_run_delete_ui_calls_run_endpoint_not_candidate_endpoint(self):
        template=(Path(__file__).resolve().parents[1]/'templates'/'hiring_agent_glass_editorial_template.html').read_text(encoding='utf-8')
        self.assertIn('async deleteRun(runId)',template)
        self.assertIn('/api/staff/runs/${runId}',template)
        self.assertIn('data-confirm-delete-run',template)
        self.assertIn('The candidate, PDF and other Runs were preserved.',template)

    def test_staff_run_payload_includes_immutable_config_and_stage_duration(self):
        artifact=backend.ARTIFACTS/'trace.json';artifact.parent.mkdir(parents=True,exist_ok=True);artifact.write_text('{"base": 51, "bonus": 6, "deduction": 2, "evidence": {"breakdown": [{"key": "relevant_experience", "label": "Relevant Experience", "score": 18, "max": 30, "evidence": "work"}]}}',encoding='utf-8')
        c=backend.db()
        c.execute("insert into applications (id,email,filename,stored_path,sha256,status,created,is_demo) values(?,?,?,?,?,?,?,?)", ('app-trace','alice@demo.local','trace.pdf',None,'trace','UNDER_REVIEW',1,0))
        config={'defense_profile':'v2_structured','github_fixture_id':'20734_patch','github_evidence_mode':'structured','github_sanitize_mode':'adaptive'}
        c.execute("insert into evaluation_runs values(?,?,?,?,?,?,?,?,?,?,?,?)", ('run-trace','app-trace','ollama','gemma3:4b','COMPLETED',1,2,55,__import__('json').dumps(config),'trace-fingerprint',None,None))
        c.execute("insert into stage_runs values(?,?,?,?,?,?,?)", ('trace-extract','run-trace','PDF_TEXT_EXTRACTION','COMPLETED',120,'done',None))
        c.execute("insert into stage_runs values(?,?,?,?,?,?,?)", ('trace-github','run-trace','GITHUB_EVIDENCE_GATE','COMPLETED',230,'blocked injected text',str(artifact)))
        c.commit();c.close()
        records=self.client.get('/api/staff/applications',headers=self.login('staff@demo.local')).json()
        run=next(item for item in records if item['id']=='app-trace')['runs'][0]
        self.assertEqual(run['duration_ms'],350)
        self.assertEqual([stage['name'] for stage in run['stage_summary']],['PDF_TEXT_EXTRACTION','GITHUB_EVIDENCE_GATE'])
        self.assertEqual(__import__('json').loads(run['config_json'])['github_fixture_id'],'20734_patch')
        self.assertEqual((run['base'],run['bonus'],run['deduction']),(51,6,2))
        self.assertEqual(run['breakdown'][0]['max'],30)
        self.assertEqual(run['evidence']['breakdown'][0]['score'],18)

    def test_database_reads_do_not_mark_active_runs_stale(self):
        c=backend.db()
        c.execute("insert into applications (id,email,filename,stored_path,sha256,status,created,is_demo) values(?,?,?,?,?,?,?,?)", ('app-active','alice@demo.local','active.pdf',None,'active','PROCESSING',1,0))
        c.execute("insert into evaluation_runs values(?,?,?,?,?,?,?,?,?,?,?,?)", ('run-active','app-active','ollama','gemma3:4b','RUNNING',1,None,None,'{}','active-fingerprint',None,None))
        c.commit();c.close()
        read=backend.db(); status=read.execute("select status,error from evaluation_runs where id='run-active'").fetchone();read.close()
        self.assertEqual(status['status'],'RUNNING')
        self.assertIsNone(status['error'])

    def test_startup_recovery_marks_active_runs_once(self):
        c=backend.db()
        c.execute("insert into applications (id,email,filename,stored_path,sha256,status,created,is_demo) values(?,?,?,?,?,?,?,?)", ('app-recovery','alice@demo.local','recovery.pdf',None,'recovery','PROCESSING',1,0))
        c.execute("insert into evaluation_runs values(?,?,?,?,?,?,?,?,?,?,?,?)", ('run-recovery','app-recovery','ollama','gemma3:4b','RUNNING',1,None,None,'{}','recovery-fingerprint',None,None))
        c.commit();c.close()
        backend.recover_stale_runs()
        c=backend.db(); status=c.execute("select status,error from evaluation_runs where id='run-recovery'").fetchone();c.close()
        self.assertEqual(status['status'],'FAILED_STALE')
        self.assertEqual(status['error'],'Recovered once at server startup')

    def test_staff_can_read_pdf_preview_metadata(self):
        pdf_path = backend.UPLOADS / 'one_page_resume.pdf'
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        document = fitz.open()
        document.new_page(width=595, height=842)
        document.save(pdf_path)
        document.close()
        c = backend.db()
        c.execute("insert into applications (id,email,filename,stored_path,sha256,status,created,is_demo) values(?,?,?,?,?,?,?,?)", ('app-preview','alice@demo.local','one_page_resume.pdf',str(pdf_path),'preview','UNDER_REVIEW',1,0))
        c.commit(); c.close()
        response = self.client.get('/api/staff/applications/app-preview/pdf-meta', headers=self.login('staff@demo.local'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'page_count': 1, 'page_width': 595, 'page_height': 842})

    def test_staff_can_delete_a_completed_application_and_its_artifacts(self):
        pdf_path = backend.UPLOADS / 'delete_me.pdf'
        artifact_path = backend.ARTIFACTS / 'delete-run.json'
        pdf_path.parent.mkdir(parents=True, exist_ok=True); artifact_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b'%PDF-1.4\n'); artifact_path.write_text('{}', encoding='utf-8')
        c = backend.db()
        c.execute("insert into applications (id,email,filename,stored_path,sha256,status,created,is_demo) values(?,?,?,?,?,?,?,?)", ('app-delete','alice@demo.local','delete_me.pdf',str(pdf_path),'delete','UNDER_REVIEW',1,0))
        c.execute("insert into evaluation_runs values(?,?,?,?,?,?,?,?,?,?,?,?)", ('run-delete','app-delete','ollama','gemma3:4b','COMPLETED',1,1,50,'{}','fingerprint',None,None))
        c.execute("insert into stage_runs values(?,?,?,?,?,?,?)", ('stage-delete','run-delete','EVALUATION','COMPLETED',1,'done',str(artifact_path)))
        c.commit(); c.close()
        response = self.client.delete('/api/staff/applications/app-delete', headers=self.login('staff@demo.local'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], 'app-delete')
        c = backend.db()
        self.assertIsNone(c.execute("select 1 from applications where id='app-delete'").fetchone())
        self.assertIsNone(c.execute("select 1 from evaluation_runs where id='run-delete'").fetchone())
        self.assertIsNone(c.execute("select 1 from stage_runs where id='stage-delete'").fetchone())
        c.close()
        self.assertFalse(pdf_path.exists()); self.assertFalse(artifact_path.exists())

    def test_staff_can_delete_one_run_without_deleting_candidate_or_pdf(self):
        pdf_path=backend.UPLOADS/'keep_candidate.pdf';artifact_old=backend.ARTIFACTS/'old-run.json';artifact_new=backend.ARTIFACTS/'new-run.json'
        pdf_path.parent.mkdir(parents=True,exist_ok=True);artifact_old.parent.mkdir(parents=True,exist_ok=True)
        pdf_path.write_bytes(b'%PDF-1.4\n');artifact_old.write_text('{"score": 45, "base": 45, "bonus": 0, "deduction": 0, "resume": {"basics": {"name": "Old"}}, "evidence": {"strengths": ["old"]}}',encoding='utf-8');artifact_new.write_text('{"score": 88, "base": 84, "bonus": 4, "deduction": 0, "resume": {"basics": {"name": "New"}}, "evidence": {"strengths": ["new"]}}',encoding='utf-8')
        c=backend.db();c.execute("insert into applications (id,email,filename,stored_path,sha256,status,created,score,base,bonus,deduction,resume_json,evidence_json,is_demo) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('app-keep','alice@demo.local','keep_candidate.pdf',str(pdf_path),'keep','UNDER_REVIEW',1,88,84,4,0,'{}','{}',0))
        for rid,created,score,artifact in [('run-old',1,45,artifact_old),('run-new',2,88,artifact_new)]:
            c.execute("insert into evaluation_runs values(?,?,?,?,?,?,?,?,?,?,?,?)",(rid,'app-keep','ollama','gemma3:4b','COMPLETED',created,created,score,'{}',rid,None,None));c.execute("insert into stage_runs values(?,?,?,?,?,?,?)",('stage-'+rid,rid,'EVALUATION','COMPLETED',1,'done',str(artifact)))
        c.commit();c.close();h=self.login('staff@demo.local')
        response=self.client.delete('/api/staff/runs/run-new',headers=h);self.assertEqual(response.status_code,200)
        c=backend.db();app=c.execute("select score,base,bonus,status from applications where id='app-keep'").fetchone()
        self.assertIsNotNone(app);self.assertEqual(tuple(app),(45,45,0,'UNDER_REVIEW'));self.assertIsNotNone(c.execute("select 1 from evaluation_runs where id='run-old'").fetchone());self.assertIsNone(c.execute("select 1 from evaluation_runs where id='run-new'").fetchone());c.close()
        self.assertTrue(pdf_path.exists());self.assertTrue(artifact_old.exists());self.assertFalse(artifact_new.exists())

    def test_deleting_last_run_keeps_candidate_and_clears_ghost_score(self):
        c=backend.db();c.execute("insert into applications (id,email,filename,stored_path,sha256,status,created,score,base,bonus,deduction,resume_json,evidence_json,is_demo) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('app-last','alice@demo.local','last.pdf',None,'last','UNDER_REVIEW',1,77,70,7,0,'{}','{}',0));c.execute("insert into evaluation_runs values(?,?,?,?,?,?,?,?,?,?,?,?)",('run-last','app-last','ollama','gemma3:4b','COMPLETED',1,1,77,'{}','last',None,None));c.commit();c.close()
        response=self.client.delete('/api/staff/runs/run-last',headers=self.login('staff@demo.local'));self.assertEqual(response.status_code,200)
        c=backend.db();app=c.execute("select score,base,bonus,deduction,status from applications where id='app-last'").fetchone();c.close()
        self.assertEqual(tuple(app),(None,None,None,None,'SUBMITTED'))
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
        fixture=Path(__file__).resolve().parents[2]/'test_data/demo_handoff_samples/pdf/clean_weak_20734.pdf'
        response=self.client.post('/api/candidate/resume',headers=h,files={'file':('resume.pdf',fixture.read_bytes(),'application/pdf')});self.assertEqual(response.status_code,200)
        backend.WORKER.shutdown(wait=True)
        staff=self.login('staff@demo.local');record=self.client.get('/api/staff/applications/'+response.json()['application_id'],headers=staff).json()
        self.assertEqual(record['status'],'UNDER_REVIEW');self.assertIsNotNone(record['score']);self.assertTrue(record['runs'])
        self.assertEqual(self.client.get('/api/staff/applications/'+record['id']+'/pdf',headers=staff).status_code,200)
        self.assertEqual(self.client.get('/api/staff/runs/'+record['runs'][0]['id']+'/artifact',headers=staff).status_code,200)
        reused=self.client.post('/api/staff/applications/'+record['id']+'/rerun',headers=staff,json={'model':'gemma3:4b','cache':'SAFE_REUSE'});self.assertEqual(reused.status_code,200);self.assertTrue(reused.json()['reused'])
        rejected=self.client.post('/api/staff/applications/'+record['id']+'/rerun',headers=staff,json={'model':'not-allowlisted'});self.assertEqual(rejected.status_code,400)
