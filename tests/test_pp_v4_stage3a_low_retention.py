from __future__ import annotations
import unittest
from research.profit_protection_v4.stage3a_low_retention_anatomy import classify_failure

class PPV4Stage3AFailureAnatomyTests(unittest.TestCase):
    def test_observation_miss_has_priority(self):
        self.assertEqual(classify_failure(.79,True,.95,True,.20),"OBSERVATION_MISS")

    def test_runner_trigger_delay(self):
        self.assertEqual(classify_failure(.95,True,.60,False,.40),"RUNNER_TRIGGER_DELAY")

    def test_execution_accounting_drag(self):
        self.assertEqual(classify_failure(.95,True,.85,False,.70),"EXECUTION_ACCOUNTING_DRAG")

    def test_partial_reduce_drag(self):
        self.assertEqual(classify_failure(.95,False,None,True,.20),"PARTIAL_REDUCE_DRAG")

if __name__=="__main__":unittest.main()
