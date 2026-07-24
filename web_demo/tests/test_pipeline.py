import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from web_demo.pipeline import PipelineConfig, _heuristic_evaluate

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
