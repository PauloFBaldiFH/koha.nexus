"""Explicit disposable Docker save/load test; no service or registry access."""
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('nexus_docker_recovery',Path(__file__).resolve().parents[1]/'platforms/nexus/recovery.py')
full=importlib.util.module_from_spec(spec);spec.loader.exec_module(full)

@unittest.skipUnless(os.environ.get('KEI_NEXUS_DOCKER_TESTS')=='1','requires explicit disposable Docker image test')
class ImmutableImage(unittest.TestCase):
    def test_import_archived_id_after_original_image_has_been_removed(self):
        with tempfile.TemporaryDirectory(prefix='nexus-image-test-') as tmp:
            root=Path(tmp);fs=root/'fixture.tar'
            with tarfile.open(fs,'w') as archive:
                data=b'Nexus immutable image recovery fixture\n';member=tarfile.TarInfo('recovery-fixture.txt');member.size=len(data)
                archive.addfile(member,io.BytesIO(data))
            image=full.docker('image','import','--change','LABEL com.koha-nexus.test=nexus-full',str(fs)).decode().strip()
            self.assertRegex(image,r'^sha256:[0-9a-f]{64}$')
            self.addCleanup(lambda:full.docker('image','rm',image))
            home=root/'sessions';home.mkdir(mode=0o700)
            session=home/('session-'+'0'*32);session.mkdir(mode=0o700)
            tree=session/'tree';tree.mkdir(mode=0o700);(tree/'images').mkdir(mode=0o700)
            name='images/'+image[7:]+'.tar'
            full.docker('image','save','--output',str(tree/name),image)
            (tree/name).chmod(0o600)
            manifest={'images':[{'id':image,'file':name}],'files':full.inventory(tree)}
            full.atomic(tree/'manifest.json',json.dumps(manifest))
            full.atomic(session/'session.json',json.dumps({'format':1,'phase':'opened','fingerprint':'A'*40,'completed':[],
                'manifest_sha256':full.sha(tree/'manifest.json')}))
            full.docker('image','rm',image)
            recovered=full.Recovery(root/'not-executed',home).load_images(session)
            self.assertEqual(recovered['loaded'],[image])
            details=json.loads(full.docker('image','inspect',image))[0]
            self.assertEqual(details['Id'],image)
            self.assertEqual(details['Config']['Labels']['com.koha-nexus.test'],'nexus-full')
            self.assertFalse(details.get('RepoDigests'))
