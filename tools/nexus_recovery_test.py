#!/usr/bin/env python3
"""Full Nexus recovery acceptance inside an ALREADY disposable real-app runner.

Called by koha_set_system.bats (Koha + Tainacan) and dspace_install_test.py.
Never invoke on a workstation or production server: it deliberately removes
this throwaway server's backup keyring and changes fixture data before restore.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('nexus_full_acceptance',REPO/'platforms/nexus/recovery.py')
full=importlib.util.module_from_spec(spec);spec.loader.exec_module(full)


def exercise(driver,phrase,expected,mutate=None,assert_restored=None,output=None):
    if os.geteuid()!=0 or os.environ.get('KEI_NEXUS_DISPOSABLE')!='1':
        raise RuntimeError('Requires an explicitly disposable root test machine.')
    # Its applications must have been installed and seeded by the caller.
    home=Path('/var/lib/koha-nexus/nexus-acceptance')
    if home.exists():raise RuntimeError('The disposable full-recovery area already exists.')
    home.mkdir(mode=0o700)
    # Exercise the same standalone deployment as a user: checked code is
    # cached, and the running driver itself is root-owned, outside the checkout.
    caches='source "$1" --task info; kei_nexus_recovery cache'
    if 'dspace' in expected:caches+=' && kei_dspace_runtime cache'
    subprocess.run(['bash','-c',caches,'nexus-test',str(driver)],check=True,timeout=180)
    trusted=home/'config.sh';shutil.copyfile(driver,trusted);trusted.chmod(0o700)
    adapter=home/'recovery.py';shutil.copyfile(REPO/'platforms/nexus/recovery.py',adapter);adapter.chmod(0o600)
    local_spec=importlib.util.spec_from_file_location('nexus_private_acceptance',adapter)
    local=importlib.util.module_from_spec(local_spec);local_spec.loader.exec_module(local)
    recovery=local.Recovery(trusted,home/'sessions')
    plan=recovery.plan()
    assert plan['applications']==expected,(plan['applications'],expected)
    assert not plan.get('unknown'),plan.get('unknown')
    created=recovery.create(home/'packages','gz')
    verified=recovery.verify(created['file'],phrase)
    assert verified['isolated_keyring'] and verified['applications']==expected
    session=recovery.prepare(created['file'],phrase)['session']
    assert recovery.restore_plan(session)['compatible']
    if expected==['koha','tainacan'] and mutate is None:
        def sql(query):
            return subprocess.check_output(['koha-mysql','library','-N','-e',query],text=True).strip()
        def wp(*args):
            return subprocess.check_output(['bash','-c','source "$1" --task info; shift; _kei_tn_wp "$@"','nexus-fixture',str(trusted),*args],text=True).strip()
        surname=sql("SELECT surname FROM borrowers WHERE userid='kn-staff'")
        posts=wp('post','list','--post_type=post','--format=count')
        def mutate():
            sql("UPDATE borrowers SET surname='nexus-full-after-capture' WHERE userid='kn-staff'")
            wp('post','create','--post_title=nexus-full-after-capture','--post_status=publish','--porcelain')
            assert sql("SELECT surname FROM borrowers WHERE userid='kn-staff'")!=surname
            assert wp('post','list','--post_type=post','--format=count')!=posts
        def assert_restored():
            assert sql("SELECT surname FROM borrowers WHERE userid='kn-staff'")==surname
            assert wp('post','list','--post_type=post','--format=count')==posts
    if mutate:mutate()
    original_key=Path('/var/lib/koha-nexus/backup')
    saved=home/'original-server-key'
    # Remove all source decryption material from its active location: only the
    # capsule plus phrase may unlock the recovery now. Keep a private safety copy
    # for the test runner's own cleanup, never used by the recovery implementation.
    shutil.move(str(original_key),saved)
    try:
        second=local.Recovery(trusted,home/'independent-verifier')
        assert second.verify(created['file'],phrase)['verified']
        assert not original_key.exists(), 'verification unexpectedly restored a server key'
        result=recovery.restore(session,phrase)
        assert result['restored'] and result['phase']=='complete',result
        if assert_restored:assert_restored()
        # Local immutable IDs really resolve after import; no registry pull.
        for ident in plan['images']:
            assert json.loads(full.docker('image','inspect',ident))[0]['Id']==ident
        receipt={'applications':expected,'portable_keyring':True,'restored':True,
                 'images_imported':len(plan['images']),'schedules_activated':False}
        if output:Path(output).write_text(json.dumps(receipt,indent=2)+'\n')
        print('PASS: full Nexus recovery after loss of the active source keyring: '+(', '.join(expected) or 'Nexus configuration; no applications installed'),flush=True)
        return receipt
    finally:
        if not original_key.exists():shutil.copytree(saved,original_key)
        shutil.rmtree(saved)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable',action='store_true');parser.add_argument('--applications',required=True)
    parser.add_argument('--driver',default=str(REPO/'installer'));parser.add_argument('--output')
    args=parser.parse_args()
    if not args.disposable:parser.error('Requires --disposable on a disposable test machine.')
    phrase=os.environ.pop('KEI_NEXUS_TEST_PHRASE','')
    if not phrase:parser.error('The test recovery phrase must be supplied in the environment.')
    os.environ['KEI_NEXUS_DISPOSABLE']='1'
    exercise(args.driver,phrase,[app for app in args.applications.split(',') if app],output=args.output)

if __name__=='__main__':main()
