"""Recovery package validation: real files, no Docker or root required."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'platforms/dspace'
sys.path.insert(0, str(MODULE))
import backup as b


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.dest = self.root / 'out'; self.dest.mkdir()

    def archive(self, names):
        path = self.root / 'data.tar'
        with tarfile.open(path, 'w') as out:
            for name, kind in names:
                info = tarfile.TarInfo(name); info.type = kind
                if kind == tarfile.REGTYPE:
                    info.size = 4; out.addfile(info, io.BytesIO(b'data'))
                else: info.linkname = '/etc/passwd'; out.addfile(info)
        return path

    def test_regular_file_roundtrip(self):
        path = self.archive([('volumes/assetstore/document', tarfile.REGTYPE)])
        self.assertEqual(b.extract(path, self.dest, 4), 4)
        self.assertEqual((self.dest/'volumes/assetstore/document').read_bytes(), b'data')

    def test_unsafe_paths_and_types_never_extract(self):
        for name, kind in [('/etc/test',tarfile.REGTYPE),('../escape',tarfile.REGTYPE),
                           ('x/../escape',tarfile.REGTYPE),('x\\y',tarfile.REGTYPE),
                           ('x',tarfile.SYMTYPE),('x',tarfile.LNKTYPE),('x',tarfile.CHRTYPE),
                           ('a//b',tarfile.REGTYPE),('./file',tarfile.REGTYPE)]:
            with self.subTest(name=name,kind=kind):
                with self.assertRaises(b.Error): b.extract(self.archive([(name,kind)]), self.dest, 100)
                self.assertEqual(list(self.dest.iterdir()), [])

    def test_duplicate_names_rejected_before_first_write(self):
        path = self.archive([('x',tarfile.REGTYPE),('x',tarfile.REGTYPE)])
        with self.assertRaises(b.Error): b.extract(path,self.dest,100)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_expansion_limited_before_writing(self):
        path = self.archive([('x',tarfile.REGTYPE)])
        with self.assertRaises(b.Error): b.extract(path,self.dest,3)
        self.assertEqual(list(self.dest.iterdir()), [])

    def test_inventory_rejects_symlinks(self):
        (self.dest/'link').symlink_to('/etc/passwd')
        with self.assertRaises(b.Error): b.entries(self.dest)

    def test_inventory_detects_same_size_corruption(self):
        p=self.dest/'doc'; p.write_text('abcd'); first=b.entries(self.dest)
        p.write_text('abce'); self.assertNotEqual(first,b.entries(self.dest))

    def test_dump_fingerprint_ignores_only_random_session_markers(self):
        p=self.root/'a'; q=self.root/'b'
        p.write_text('-- time A\n\\restrict randomA\nINSERT INTO t VALUES (1);\n\\unrestrict randomA\n')
        q.write_text('-- time B\n\\restrict randomB\nINSERT INTO t VALUES (1);\n\\unrestrict randomB\n')
        self.assertEqual(b.normalized_dump(p),b.normalized_dump(q))
        q.write_text('INSERT INTO t VALUES (2);\n'); self.assertNotEqual(b.normalized_dump(p),b.normalized_dump(q))

    def test_corrupt_ciphertext_refused_before_decryption(self):
        class RT: root=self.root
        recovery=b.Recovery(RT()); package=self.root/'pack.gpg'; package.write_bytes(b'x')
        package.with_suffix('.sha256').write_text('0'*64)
        with self.assertRaises(b.Error):
            with recovery.opened(package): self.fail('must not open')

if __name__ == '__main__': unittest.main()
