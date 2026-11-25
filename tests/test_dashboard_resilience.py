"""Real widget callbacks; a broken optional archive must not disable the kernel."""
import unittest
from unittest.mock import patch
import test_dashboard as fixtures
from efc import dashboard as d
from efc.grid import atomic_json


class ArchiveIsolationTests(unittest.TestCase):
    def setUp(self):
        self.fx=fixtures.DashboardTests();self.fx.setUp();self.root=self.fx.root
    def tearDown(self): self.fx.tearDown()
    def assert_demo_with_archive_error(self, panel):
        panel.button.click()
        self.assertIsNone(panel.last_error)
        self.assertIsNotNone(panel.last_saved_error)
        self.assertEqual(panel.last['result']['metrics']['arrivals'],600)
        self.assertEqual(panel.last['saved']['status'],'ARCHIVE_UNVERIFIED')
        self.assertIsNone(panel.last['saved']['summary'])
        self.assertEqual(panel.last['saved']['rows'],[])
        self.assertIsNone(panel.last['result']['display_summary']['intervals'])
        self.assertFalse(panel.button.disabled)
    def test_wrong_manifest_hash_does_not_disable_600_event_demo(self):
        mapping=self.fx.fixture();mapping['manifest_sha256']='wrong'
        atomic_json(self.root/'map.json',mapping)
        self.assert_demo_with_archive_error(d.Dashboard(self.root,render=False))
    def test_missing_manifest_is_a_separate_archive_error(self):
        self.fx.fixture();(self.root/'manifest.json').unlink()
        self.assert_demo_with_archive_error(d.Dashboard(self.root,render=False))
    def test_malformed_archive_does_not_disable_demo(self):
        (self.root/'map.json').write_text('{broken')
        self.assert_demo_with_archive_error(d.Dashboard(self.root,render=False))
    def test_error_does_not_keep_stale_accepted_summary_and_recovers(self):
        self.fx.terminal_fixture();panel=d.Dashboard(self.root,render=False)
        panel.button.click();self.assertEqual(panel.last['saved']['status'],'ACCEPTABLE')
        (self.root/'map.json').write_text('{broken')
        self.assert_demo_with_archive_error(panel)
        (self.root/'map.json').unlink();panel.button.click()
        self.assertIsNone(panel.last_saved_error)
        self.assertEqual(panel.last['saved']['status'],'NOT_CALCULATED')
        self.assertEqual(panel.calls,3)
    def test_real_kernel_error_is_not_relabelled_archive_error(self):
        panel=d.Dashboard(self.root,render=False)
        with patch('efc.dashboard.run_example',side_effect=ValueError('kernel failure')):
            panel.button.click()
        self.assertEqual(panel.last_error,'kernel failure')
        self.assertIsNone(panel.last_saved_error);self.assertIsNone(panel.last)
        self.assertEqual(panel.calls,0);self.assertFalse(panel.button.disabled)
    def test_invalid_snapshot_is_not_rewritten(self):
        mapping=self.fx.fixture();mapping['manifest_sha256']='wrong'
        atomic_json(self.root/'map.json',mapping)
        before={str(p):p.read_bytes() for p in self.root.rglob('*.json')}
        self.assert_demo_with_archive_error(d.Dashboard(self.root,render=False))
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*.json')})

if __name__=='__main__':unittest.main()
