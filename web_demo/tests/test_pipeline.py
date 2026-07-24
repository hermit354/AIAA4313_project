import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from web_demo.pipeline import PipelineConfig, _heuristic_evaluate, _parse

class PipelineTests(unittest.TestCase):
    def test_config_fingerprint_is_stable_and_request_scoped(self):
        one=PipelineConfig(model_id='gemma3:4b'); two=PipelineConfig(model_id='gemma3:4b'); other=PipelineConfig(model_id='deepseek',provider='deepseek')
        self.assertEqual(one.fingerprint(),two.fingerprint());self.assertNotEqual(one.fingerprint(),other.fingerprint())
    def test_score_is_capped_and_deductions_apply(self):
        text=('production deployed scale kubernetes customer project github open source built ' * 300)
        score,base,bonus,deduction,_=_heuristic_evaluate(text,{'skills':['Python']*50,'github':'github.com/example'})
        self.assertLessEqual(score,100);self.assertGreaterEqual(score,0);self.assertEqual(score,base+bonus-deduction)
    def test_short_resume_gets_deduction(self):
        score,base,bonus,deduction,_=_heuristic_evaluate('Python',{'skills':['Python'],'github':None})
        self.assertGreater(deduction,0);self.assertEqual(score,base+bonus-deduction)

    def test_section_parser_does_not_turn_contact_or_education_into_work(self):
        resume=_parse('''Chenrui Tie
Email: chenrui@example.edu | https://example.edu
EDUCATION
National University of Singapore
PhD Student in Computer Science
EXPERIENCE
Research Assistant — Robotics Lab
Built evaluation tooling for embodied agents.
PROJECTS
Resume Injection Benchmark
SKILLS
Python, PyTorch
''')
        self.assertEqual(resume['basics']['name'],'Chenrui Tie')
        self.assertEqual(resume['education'],['National University of Singapore','PhD Student in Computer Science'])
        self.assertEqual(resume['work'],['Research Assistant — Robotics Lab','Built evaluation tooling for embodied agents.'])
        self.assertNotIn('Email: chenrui@example.edu | https://example.edu',resume['work'])
