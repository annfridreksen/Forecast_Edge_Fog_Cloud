from pathlib import Path
import tempfile
import unittest
import zipfile
from scripts.verify_r14_archive import verify_archive,file_hash

class ArchiveTests(unittest.TestCase):
    def fixture(self,tmp):
        z=Path(tmp)/'x.zip';root=Path(tmp)/'tree';root.mkdir()
        with zipfile.ZipFile(z,'w') as f:f.writestr('a.txt','one')
        with zipfile.ZipFile(z) as f:f.extractall(root)
        return z,root
    def test_measured_provenance_and_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            z,r=self.fixture(d);h=file_hash(z)
            a=verify_archive(z,r,expected_sha256=h,artifact_id=123)
            self.assertEqual(a,verify_archive(z,r,expected_sha256=h,artifact_id=123))
            self.assertEqual(a['measured_zip_sha256'],h)
            self.assertEqual(a['extracted_members_verified'],1)
    def test_wrong_zip(self):
        with tempfile.TemporaryDirectory() as d:
            z,r=self.fixture(d)
            with self.assertRaises(ValueError):verify_archive(z,r,expected_sha256='0'*64)
    def test_changed_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            z,r=self.fixture(d);(r/'a.txt').write_text('two')
            with self.assertRaises(ValueError):verify_archive(z,r,expected_sha256=file_hash(z))
    def test_missing_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            z,r=self.fixture(d);(r/'a.txt').unlink()
            with self.assertRaises(ValueError):verify_archive(z,r,expected_sha256=file_hash(z))
    def test_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            z,r=self.fixture(d)
            with zipfile.ZipFile(z,'a') as f:f.writestr('../outside','x')
            with self.assertRaises(ValueError):verify_archive(z,r,expected_sha256=file_hash(z))
