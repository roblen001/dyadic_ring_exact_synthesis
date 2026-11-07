import copy
import json
from pathlib import Path
import unittest

from dyadic_viz.presentation import build_presentation
from dyadic_viz.storyboard import build_storyboard, attach_timeline
from dyadic_viz.validation import validate_trace
from test_generalization import identity_trace

ROOT=Path(__file__).resolve().parents[1]


class PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace=json.loads((ROOT/'examples/rich_dyadic_trace.json').read_text())
        validate_trace(cls.trace)

    def test_exact_coverage_and_no_source_mutation(self):
        before=copy.deepcopy(self.trace)
        plan=build_presentation(self.trace)
        self.assertEqual(self.trace,before)
        self.assertEqual([i for e in plan['events'] for i in e['source_event_ids']],
                         [e['id'] for e in self.trace['events']])
        self.assertEqual(plan['events'][-1]['applied_operation_ids'],
                         self.trace['result']['reduction_operation_ids'])
        self.assertLess(len(plan['events']),len(self.trace['events'])/2)
        for e in plan['events']:
            if e['type']=='presentation_summary':
                self.assertIn(e['payload']['before_state_id'],self.trace['states'])
                self.assertIn(e['payload']['after_state_id'],self.trace['states'])

    def test_both_residue_cases_kept_and_third_sweep_condensed(self):
        plan=build_presentation(self.trace)
        ids={e['id'] for e in plan['events']}
        self.assertIn('event_00008',ids)  # all 1 mod 4
        self.assertIn('event_00014',ids)  # correction of 3 mod 4
        self.assertIn('event_00018',ids)  # mixing after correction
        self.assertNotIn('event_00030',ids)  # same corrected case again
        self.assertTrue(any('event_00030' in e['source_event_ids'] for e in plan['events']))
        self.assertEqual(sum(e['type']=='verification' for e in plan['events']),3)

    def test_formula_pins_exact_anchor_and_preserves_trace(self):
        recipe={'version':1,'formulas':[{'after_event':'event_00030','expression':'v=w/2^k'}]}
        plan=build_presentation(self.trace,recipe=recipe)
        index=next(i for i,e in enumerate(plan['events']) if e['id']=='event_00030')
        formula=plan['events'][index+1]
        self.assertEqual(formula['type'],'presentation_formula')
        self.assertEqual(formula['source_event_ids'],[])
        self.assertEqual(formula['before_state_id'],formula['after_state_id'])

    def test_declared_new_case_is_not_lost(self):
        plan=build_presentation(self.trace,recipe={'case_tags':{'event_00030':'special boundary case'}})
        self.assertIn('event_00030',[e['id'] for e in plan['events']])

    def test_full_retains_original_events_and_holds(self):
        literal=build_storyboard(self.trace)
        full=build_presentation(self.trace,mode='full')
        for expected,actual in zip(literal['events'],full['events']):
            actual=copy.deepcopy(actual)
            actual.pop('source_event_ids')
            self.assertEqual(expected,actual)
        self.assertEqual(len(literal['events']),len(full['events']))

    def test_repeated_checks_do_not_grow_video_linearly(self):
        small=build_presentation(identity_trace(4))
        large=build_presentation(identity_trace(64))
        self.assertEqual(len(small['events']),len(large['events']))
        self.assertGreater(large['presentation']['condensed_source_events'],100)

    def test_measured_timeline_matches_render_plan(self):
        plan=build_presentation(self.trace)
        timeline={'trace_id':self.trace['trace_id'],'duration_seconds':len(plan['events']),
                  'sections':[],'events':[{'id':e['id'],'start_seconds':i,'end_seconds':i+1}
                                         for i,e in enumerate(plan['events'])]}
        timed=attach_timeline(plan,timeline)
        self.assertEqual(timed['duration_seconds'],len(plan['events']))

    def test_invalid_recipe_is_rejected(self):
        for recipe in [{'retain_events':['missing']},{'examples_per_case':False},
                       {'examples_per_case':0},{'unknown':1},{'case_tags':{'missing':'x'}},
                       {'formulas':[{'after_event':'event_00008','expression':'x','hold_seconds':float('nan')}]}]:
            with self.subTest(recipe=recipe),self.assertRaises(ValueError):
                build_presentation(self.trace,recipe=recipe)


if __name__=='__main__':
    unittest.main()
