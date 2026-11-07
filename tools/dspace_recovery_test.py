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
    # A nonempty historical core is mandatory evidence; an empty copied index
    # alone cannot demonstrate preservation of statistics.
    seed = json.dumps([{'id':'nexus-recovery-history','type':0,'time':'2026-01-01T00:00:00Z'}])
    reply = json.loads(rt.compose('exec','-T','solr','curl','-fsS','-H','Content-Type: application/json',
        '--data-binary','@-','http://127.0.0.1:8983/solr/statistics/update?commit=true',input_text=seed))
    if reply.get('responseHeader',{}).get('status') != 0: raise RuntimeError('Could not seed historical Solr data.')
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
    assert_history(rt)
    data = API(rt.state()['url']).request(fixture['content'], raw=True)
    import hashlib
    assert hashlib.sha256(data).hexdigest() == fixture['sha256'], 'Public file failed after recovery'
    with rt.lock(): recovery.restore(private)
    assert_history(rt)
    API(rt.state()['url']).request(fixture['content'], allowed=(401,403,404), raw=True)
    API(rt.state()['url']).request('/core/items/'+fixture['item'], allowed=(401,403,404), raw=True)
    admin=API(rt.state()['url']); admin.login(fixture['email'],fixture['password'])
    assert hashlib.sha256(admin.request(fixture['content'], raw=True)).hexdigest() == fixture['sha256']
    (Path(os.environ['RUNNER_TEMP'])/'dspace-recovery-acceptance.json').write_text(json.dumps({
        'public_download_after_recovery':True,'private_download_denied_after_recovery':True,
        'authorized_download_checksum':True,'logical_records_and_cold_solr_verified':True}))
    print('PASS: encrypted DSpace public/private recovery on independent volumes',flush=True)


def assert_history(rt):
    response = json.loads(rt.compose('exec','-T','solr','curl','-fsS',
        'http://127.0.0.1:8983/solr/statistics/select?q=id%3Anexus-recovery-history&wt=json'))
    if response.get('response',{}).get('numFound') != 1:
        raise RuntimeError('Historical Solr statistics were not recovered.')
