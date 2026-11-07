"""Real encrypted recovery acceptance on the disposable DSpace runner."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys


def prepare(rt):
    path = Path(__file__).resolve().parents[1] / 'platforms/dspace'
    sys.path.insert(0, str(path))
    from backup import Recovery
    phrase = secrets.token_urlsafe(24)
    result = subprocess.run(['bash','-c','source "$1"; kei_backup_setup confirm','recovery',rt.driver],
        env=dict(os.environ,KEI_BACKUP_PHRASE=phrase),capture_output=True,text=True,timeout=300)
    if result.returncode: raise RuntimeError('Disposable recovery key setup failed.')
    recovery = Recovery(rt, phrase)
    with rt.lock():
        public = recovery.capture()['package']
    return recovery, public


def verify(rt, prepared, fixture):
    from dspace_browser_test import API
    recovery, public = prepared
    with rt.lock():
        private = recovery.capture()['package']
        recovery.test(private)
        recovery.restore(public)
    data = API(rt.state()['url']).request(fixture['content'], raw=True)
    import hashlib
    assert hashlib.sha256(data).hexdigest() == fixture['sha256'], 'Public file failed after recovery'
    with rt.lock(): recovery.restore(private)
    API(rt.state()['url']).request(fixture['content'], allowed=(401,403,404), raw=True)
    API(rt.state()['url']).request('/core/items/'+fixture['item'], allowed=(401,403,404), raw=True)
    admin=API(rt.state()['url']); admin.login(fixture['email'],fixture['password'])
    assert hashlib.sha256(admin.request(fixture['content'], raw=True)).hexdigest() == fixture['sha256']
    (Path(os.environ['RUNNER_TEMP'])/'dspace-recovery-acceptance.json').write_text(json.dumps({
        'public_download_after_recovery':True,'private_download_denied_after_recovery':True,
        'authorized_download_checksum':True,'logical_records_and_cold_solr_verified':True}))
    print('PASS: encrypted DSpace public/private recovery on independent volumes',flush=True)
