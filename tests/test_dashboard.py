"""Small UI/oracle fixtures only; no scientific grid, fitting or Colab browser."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from efc import dashboard as d
from efc.grid import GridRunner, digest, atomic_json, config_key
from efc.primary import PrimarySampler
from efc.workload import INPUT_FIELDS, generate_workload


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.config = d.make_config(50*.5/.055, 50, 5, n_tasks=100)
    def tearDown(self): self.temp.cleanup()

    def test_configuration_is_current_environment(self):
        self.assertEqual((self.config.n_edge,self.config.n_cloud),(1000,40))
        self.assertEqual(self.config.fog_service_ms,(30,80))
    def test_invalid_controls(self):
        for values in [(float('nan'),50,5),(True,50,5),(-1,50,5),(10,31,5),(10,50,3),(10,True,5)]:
            with self.subTest(values=values),self.assertRaises(ValueError):d.make_config(*values)
        with self.assertRaises(ValueError): d.make_config(10,50,5,n_tasks=5001)
    def test_single_run_has_no_statistical_claim(self):
        r=d.run_example(self.config)
        self.assertIsNone(r['display_summary']['intervals'])
        self.assertEqual(r['display_summary']['statistical_status'],'NOT_EVALUATED_SINGLE_REPLICATION')
        self.assertEqual(r['metrics']['arrivals'],100)
    def test_same_inputs_when_controls_change(self):
        a=d.run_example(self.config);b=d.run_example(replace(self.config,n_fog=30,buffer=0))
        self.assertEqual([{k:t[k] for k in INPUT_FIELDS} for t in a['tasks']],
                         [{k:t[k] for k in INPUT_FIELDS} for t in b['tasks']])
        self.assertNotEqual([t['fog'] for t in a['tasks']],[t['fog'] for t in b['tasks']])
    def test_manual_oracle_and_six_stages(self):
        r,w,t=d.manual_case();self.assertEqual(w,[0,9,18,None,20]);self.assertEqual(t,[14,23,32,None,34])
        self.assertEqual((r['metrics']['completed'],r['metrics']['dropped']),(4,1))
        self.assertEqual(r['tasks'][4]['fog_arrival_tick'],r['tasks'][0]['fog_end_tick'])
    def test_all_arrivals_in_completion_curve(self):
        r,_,_=d.manual_case();x,y=d.completion_curve(r)
        self.assertEqual(y[-1],.8);self.assertTrue(np.all(np.diff(y)>=0))
        self.assertEqual(y[np.where(x==200)[0][0]],.8)
    def test_shutdown_preserves_preexisting_messages(self):
        s=d.shutdown_case();self.assertEqual(s['original_event_ids'],[0,1,2,4]);self.assertEqual(s['not_created_ids'],[3,5])
        r=s['result'];self.assertEqual((r['metrics']['arrivals'],r['metrics']['completed'],r['metrics']['dropped']),(4,4,0))
        self.assertTrue(all(t['end_tick']>s['cutoff_tick'] for t in r['tasks']))
        self.assertEqual(d.completion_curve(r)[1][-1],1.)
    def test_shutdown_equal_time_precedes_creation(self):
        c=replace(self.config,n_edge=1000,n_tasks=2);w=generate_workload(c,[0,.001])
        sensor=w.events[1].sensor
        cfg,after,ids,removed=d.disconnect_workload(c,w,sensor,w.events[1].release_tick)
        self.assertIn(1,removed);self.assertEqual(ids,[0]);self.assertEqual(cfg.n_tasks,1)
        self.assertEqual(after.events[0],w.events[0])
    def test_shutdown_all_events_and_invalid_request(self):
        c=d.Config(n_edge=1,n_fog=1,n_cloud=1,n_tasks=2);w=generate_workload(c,[0,.001])
        cfg,after,ids,removed=d.disconnect_workload(c,w,0,0)
        self.assertEqual((cfg.n_tasks,ids,removed),(0,[],[0,1]))
        self.assertEqual(d.simulate(cfg,workload=after)['metrics']['arrivals'],0)
        with self.assertRaises(ValueError):d.disconnect_workload(c,w,1,0)
        with self.assertRaises(ValueError):d.disconnect_workload(c,w,0,0.5)
    def test_missing_checkpoint_is_not_zero(self):
        saved=d.saved_cell(self.root,self.config)
        self.assertEqual(saved['status'],'NOT_CALCULATED');self.assertIsNone(saved['summary'])
        self.assertEqual(list(self.root.iterdir()),[])
    def fixture(self):
        runner=GridRunner(self.root,configurations=[self.config],factory=PrimarySampler)
        runner._bind();mapping=runner.map_data();atomic_json(self.root/'map.json',mapping)
        return mapping
    def test_current_manifest_read_only(self):
        mapping=self.fixture();before=(self.root/'map.json').read_bytes()
        self.assertEqual(d.saved_cell(self.root,self.config)['status'],'NOT_CALCULATED')
        self.assertEqual(before,(self.root/'map.json').read_bytes())
    def test_foreign_manifest_rejected(self):
        mapping=self.fixture();mapping['manifest_sha256']='wrong';atomic_json(self.root/'map.json',mapping)
        with self.assertRaises(ValueError):d.saved_cell(self.root,self.config)
    def test_foreign_code_rejected(self):
        self.fixture()
        with self.assertRaises(ValueError):d.saved_cell(self.root,replace(self.config,fog_service_ms=(1,2)))
    def test_no_accepted_status_without_primary(self):
        mapping=self.fixture();mapping['rows'][0]['status']='ACCEPTABLE';atomic_json(self.root/'map.json',mapping)
        with self.assertRaises(ValueError):d.saved_cell(self.root,self.config)
    def terminal_fixture(self):
        from efc.statistics import Cohort, cluster_summary
        mapping=self.fixture();row=mapping['rows'][0];key=row['key'];cid=row['config_id']
        plan=dict(config_id=cid,pilot_seeds=list(range(100,110)),main_seeds=list(range(10)),
                  confirmation_seeds=list(range(200,210)),warmup=4000,observe=4000,guard=1000)
        pilot=dict(status='READY',config_id=cid,plan=plan,plan_sha256=digest(plan))
        summary=cluster_summary([Cohort(i,1000,1,0,(100_000_000,)*999) for i in range(10)])
        main=dict(status='ACCEPTABLE',phase='main',config_id=cid,plan_sha256=digest(plan),summary=summary)
        atomic_json(self.root/'cells'/key/'pilot.json',pilot)
        atomic_json(self.root/'cells'/key/'main.json',main)
        row.update(status='ACCEPTABLE',main_sha256=digest(main),summary=summary)
        atomic_json(self.root/'map.json',mapping)
        return mapping,main
    def test_saved_intervals_are_read_not_recomputed(self):
        self.terminal_fixture()
        with patch('efc.statistics.cluster_summary',side_effect=AssertionError('recompute forbidden')):
            saved=d.saved_cell(self.root,self.config)
        self.assertEqual(saved['status'],'ACCEPTABLE')
        self.assertEqual(saved['summary']['intervals']['drop_fraction']['upper'],.001)
    def test_saved_decision_must_match_joint_rule(self):
        mapping,main=self.terminal_fixture();row=mapping['rows'][0]
        main['status']='UNACCEPTABLE';row.update(status='UNACCEPTABLE',main_sha256=digest(main))
        atomic_json(self.root/'cells'/row['key']/'main.json',main);atomic_json(self.root/'map.json',mapping)
        with self.assertRaises(ValueError):d.saved_cell(self.root,self.config)
    def test_callback_controls_do_not_run_implicitly(self):
        panel=d.Dashboard(self.root,render=False);self.assertEqual(panel.calls,0)
        panel.fog.value=30;panel.buffer.value=0;panel.rate.value=50*.95/.055
        self.assertEqual(panel.calls,0)
        panel.button.click();self.assertEqual(panel.calls,1);self.assertIsNone(panel.last_error)
        self.assertEqual(panel.last['result']['config']['n_fog'],30)
        self.assertFalse(panel.button.disabled)
    def test_callback_failure_clears_stale_result(self):
        panel=d.Dashboard(self.root,render=False);panel.button.click();self.assertIsNotNone(panel.last)
        with patch('efc.dashboard.run_example',side_effect=ValueError('injected failure')):panel.button.click()
        self.assertIsNone(panel.last);self.assertEqual(panel.last_error,'injected failure');self.assertFalse(panel.button.disabled)
    def test_callback_reentrancy_blocked(self):
        panel=d.Dashboard(self.root,render=False);panel.button.disabled=True;panel.calculate()
        self.assertEqual(panel.calls,0);panel.button.disabled=False
        panel.off_button.click();self.assertEqual(panel.shutdown['not_created_ids'],[3,5]);self.assertFalse(panel.off_button.disabled)
    def test_no_grid_writer_called_by_interface(self):
        panel=d.Dashboard(self.root,render=False)
        with patch('efc.grid.GridRunner.run',side_effect=AssertionError('grid forbidden')):
            panel.button.click();panel.off_button.click()
        self.assertIsNone(panel.last_error);self.assertEqual(panel.calls,1)

if __name__=='__main__':unittest.main()
