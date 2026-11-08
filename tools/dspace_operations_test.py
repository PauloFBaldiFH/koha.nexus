"""Real operations on the disposable installation runner, never a user server."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def exercise(rt, prepared, output):
    from operations import Operations
    from runtime import Refused, read_json
    from dspace_recovery_test import assert_history
    recovery,_=prepared
    op=Operations(rt,recovery.phrase)
    before=rt.state()['url'];matrix={k:v['image'] for k,v in read_json(rt.root/'compose.json')['services'].items()}
    custom='\n# institution test property\nnexus.custom.preserved = yes\n'
    with open(rt.root/'local.cfg','a') as stream:stream.write(custom)
    op.commit_config()
    destination=output/'encrypted-plans';destination.mkdir(mode=0o700)
    # An rclone local backend is a real configured connection; no cloud account or internet is used.
    subprocess.run(['rclone','config','create','nexus-ci','local'],check=True,capture_output=True,timeout=30)
    remote=output/'cloud-copy';remote.mkdir(mode=0o700)
    data=dict(id='ci-repository',members=['dspace'],time='02:30',keep=1,destination=str(destination),remote='nexus-ci:'+str(remote))
    op.save_plan(data,True)
    from operations import fields
    set_dir=output/'real-dspace-set';set_dir.mkdir(mode=0o700)
    actual=fields(op.driver('set-backup',set_dir,'dspace'))
    assert actual['complete']=='yes' and actual['recoverability']=='full'
    inspected=fields(op.driver('set-inspect',actual['file']))
    assert inspected['platforms']=='dspace' and inspected['integrity']=='ok'
    opened=fields(op.driver('set-unpack',actual['file']))
    try:
        with rt.lock():recovery.test(opened['dspace'])
    finally:op.driver('set-cleanup',opened['stage'])
    cron=Path('/etc/cron.d/koha-nexus-plan-ci-repository').read_text()
    assert '30 2 * * * root' in cron and '# Members=dspace' in cron
    # Execute exactly the command cron would execute (not a fake capture).
    job=next(line for line in cron.splitlines() if line.startswith('30 2 '))
    subprocess.run(['bash','-ec',job.split(' root ',1)[1]],check=True,timeout=1800)
    history=op.history(data['id']);assert history[-1]['capture']=='ok' and history[-1]['copy']=='ok'
    artifact=Path(history[-1]['file']);assert artifact.exists() and (remote/artifact.name).exists()
    with rt.lock():recovery.test(artifact)
    # Real invalid remote proves failure leaves the previous recoverable package intact.
    failure=dict(data,remote='nexus-ci:/proc/nexus-not-writable')
    op.save_plan(failure,True)
    try:op.run_plan(data['id'])
    except Refused:pass
    else:raise AssertionError('Upload to unwritable /proc unexpectedly succeeded')
    assert artifact.exists() and op.history(data['id'])[-1]['copy']=='failed'
    op.save_plan(dict(data,time=''),True)
    assert not Path('/etc/cron.d/koha-nexus-plan-ci-repository').exists()
    # URL change preserves institution configuration and exact data volumes/images.
    with rt.lock():op.address({'url':'http://repository.kei.test:8101','mode':'apache'},True)
    assert 'nexus.custom.preserved = yes' in (rt.root/'local.cfg').read_text()
    assert_history(rt)
    assert {k:v['image'] for k,v in read_json(rt.root/'compose.json')['services'].items()}==matrix
    # A real HTTPS vhost using a disposable test certificate; not an ACME issuance.
    cert=output/'repository.pem';key=output/'repository.key'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN=repository.kei.test',
        '-addext','subjectAltName=DNS:repository.kei.test','-keyout',str(key),'-out',str(cert)],check=True,capture_output=True,timeout=30)
    key.chmod(0o600)
    with rt.lock():op.address({'url':'https://repository.kei.test:8443','mode':'tls','certificate':str(cert),'key':str(key)},True)
    subprocess.run(['curl','--noproxy','repository.kei.test','--cacert',str(cert),'--resolve','repository.kei.test:8443:127.0.0.1',
        '-fsS','--max-time','60','https://repository.kei.test:8443/server/api'],check=True,capture_output=True,timeout=70)
    assert_history(rt)
    with rt.lock():op.address({'url':before,'mode':'apache'},True)
    # Removal keeps all active owned volumes by default and can resume through Start.
    compose=read_json(rt.root/'compose.json');owned=[v['name'] for v in compose['volumes'].values()]
    with rt.lock():result=op.remove({'purge':False},True)
    assert result['keep_data'] and all(json.loads(rt.docker('volume','inspect',name))[0]['Name']==name for name in owned)
    rt.control(True);assert_history(rt)
    (output/'dspace-operations-acceptance.json').write_text(json.dumps(dict(
        real_format2_encrypted_member_recovery=True,real_scheduled_capture=True,real_encrypted_local_cloud_copy=True,upload_failure_preserves_good_backup=True,
        canonical_url_change=True,custom_configuration_preserved=True,real_tls_with_test_ca=True,
        keep_data_removal_and_restart=True,vm_reboot=False)))
    print('PASS: real DSpace schedule, encrypted cloud copy, URL/TLS and keep-data removal',flush=True)
