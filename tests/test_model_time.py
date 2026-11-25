"""Independent literal oracles for TASK R1.4 section 5.1-2. Synthetic only."""
from dataclasses import replace
from decimal import Decimal
import unittest
from efc.model import Config, simulate, COMPONENTS
from efc.timebase import seconds_to_ticks, milliseconds_to_ticks, split_ticks


def boundary_config():
    return Config(n_edge=1,n_fog=1,n_cloud=1,buffer=0,n_tasks=2,
                  mobile_fraction=0,edge_fixed_ms=(3,3),edge_processing_share=1/3,
                  fog_service_ms=(9,9),fog_cloud_ms=(0,0),cloud_service_ms=(0,0))


class ClockTests(unittest.TestCase):
    def test_half_even_without_binary_intermediate(self):
        self.assertEqual([seconds_to_ticks(x) for x in
                          ('0.0000000005','0.0000000015','0.0000000025')],[0,2,2])
        self.assertEqual(milliseconds_to_ticks('0.0000015'),2)

    def test_decimal_and_float_paths(self):
        self.assertEqual(seconds_to_ticks(Decimal('.012')),12_000_000)
        self.assertEqual(seconds_to_ticks(.009+.001+.002),12_000_000)

    def test_invalid_time(self):
        for value in (-1, True, 'nan', 'Infinity', 'not a time'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                seconds_to_ticks(value)

    def test_split_conserves_ticks(self):
        self.assertEqual(split_ticks(3_000_000,1/3),(1_000_000,2_000_000))
        self.assertEqual(split_ticks(5,'.5'),(2,3))
        self.assertEqual(split_ticks(7,'.5'),(4,3))
        for ticks in range(10):
            self.assertEqual(sum(split_ticks(ticks,'.3')),ticks)

    def test_invalid_split(self):
        for ticks,share in ((-1,.5),(1,2),(1,True),(1.5,.5)):
            with self.subTest(ticks=ticks,share=share), self.assertRaises(ValueError):
                split_ticks(ticks,share)

    def test_equal_arrival_after_release_is_admitted(self):
        r=simulate(boundary_config(),['0','0.009'])
        self.assertEqual((r['metrics']['completed'],r['metrics']['dropped']),(2,0))
        self.assertEqual(r['tasks'][0]['fog_end_tick'],12_000_000)
        self.assertEqual(r['tasks'][1]['fog_arrival_tick'],12_000_000)
        self.assertEqual(r['tasks'][1]['fog_wait_tick'],0)

    def test_one_tick_early_is_lost(self):
        r=simulate(boundary_config(),['0','0.008999999'])
        self.assertEqual((r['metrics']['completed'],r['metrics']['dropped']),(1,1))
        self.assertEqual(r['tasks'][1]['fog_arrival_tick'],11_999_999)
        self.assertNotIn('latency_ms',r['tasks'][1])

    def test_one_tick_late_is_admitted(self):
        r=simulate(boundary_config(),['0','0.009000001'])
        self.assertEqual((r['metrics']['completed'],r['metrics']['dropped']),(2,0))
        self.assertEqual(r['tasks'][1]['fog_arrival_tick'],12_000_001)
        self.assertEqual(r['tasks'][1]['fog_wait_tick'],0)

    def test_same_float_counterexample(self):
        self.assertEqual(simulate(boundary_config(),[0,.009])['metrics']['dropped'],0)

    def test_five_manual_tasks_and_full_buffer(self):
        c=replace(boundary_config(),buffer=2,n_tasks=5,edge_fixed_ms=(2,2),
                  edge_processing_share=.5,fog_service_ms=(10,10),fog_cloud_ms=(1,1),cloud_service_ms=(1,1))
        r=simulate(c,['0','.001','.002','.003','.010'])
        self.assertEqual([x['status'] for x in r['tasks']],['completed','completed','completed','dropped','completed'])
        self.assertEqual([x.get('fog_wait_ms') for x in r['tasks']],[0,9,18,None,20])
        self.assertEqual([x.get('latency_ms') for x in r['tasks']],[14,23,32,None,34])
        self.assertEqual([x.get('end_tick') for x in r['tasks']],
                         [14_000_000,24_000_000,34_000_000,None,44_000_000])
        self.assertEqual([x['task_id'] for x in sorted(
            [x for x in r['tasks'] if x['status']=='completed'],key=lambda x:x['fog_start_tick'])],[0,1,2,4])
        self.assertEqual((r['metrics']['arrivals'],r['metrics']['completed'],r['metrics']['dropped']),(5,4,1))
        for row in r['tasks']:
            if row['status']=='completed':
                self.assertEqual(sum(row[k] for k in COMPONENTS),row['latency_ms'])

    def test_calendar_integer_and_exact_six_component_identity(self):
        result=simulate(Config(n_tasks=200,arrival_rate_s=500,buffer=2))
        components=('edge_delay_tick','edge_fog_tick','fog_wait_tick','fog_service_tick','fog_cloud_tick','cloud_tick')
        for row in result['tasks']:
            self.assertTrue(all(type(v) is int for k,v in row.items() if k.endswith('_tick')))
            if row['status']=='completed':
                self.assertEqual(sum(row[k] for k in components),row['end_tick']-row['release_tick'])
        self.assertTrue(all(type(x['time_tick']) is int for x in result['queue_trace']))
        self.assertEqual(result['timing']['resolution_s'],'0.000000001')

    def test_zero_service_and_simultaneous_events(self):
        c=replace(boundary_config(),n_tasks=4,edge_fixed_ms=(0,0),fog_service_ms=(0,0))
        self.assertEqual(simulate(c,[0,0,0,0])['metrics']['completed'],4)

    def test_negative_and_nonfinite_trace_rejected(self):
        for value in ('-1','nan','inf'):
            with self.assertRaises(ValueError):simulate(boundary_config(),['0',value])

    def test_repeatability(self):
        self.assertEqual(simulate(boundary_config(),['0','.009']),simulate(boundary_config(),['0','.009']))
