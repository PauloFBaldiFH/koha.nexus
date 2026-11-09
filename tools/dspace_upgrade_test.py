#!/usr/bin/env python3
"""Review historical recipes -> current recipe against actual historical images, in an EMPTY disposable runner.

No historical image is relabelled as a different release. Builds come from the
pinned original repository export. This tests a same-DSpace-version image update,
not a schema upgrade or migration from arbitrary upstream installations.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'platforms/dspace'))
from runtime import Runtime, Refused, SERVICES, atomic, digest, read_json, redact
from operations import Operations


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--disposable',action='store_true');parser.add_argument('--from-recipe',type=int,choices=(3,4),default=4)
    args=parser.parse_args()
    root=Path('/var/lib/koha-nexus/platforms/dspace')
    if not args.disposable or os.geteuid()!=0 or root.exists():parser.error('Requires root, --disposable and an empty dedicated runner.')
    output=Path(os.environ['RUNNER_TEMP'])
    old_catalog=output/'legacy-catalog.json';new_catalog=output/'current-catalog.json'
    previous=digest(REPO/('platforms/dspace/release-r'+str(args.from_recipe)+'.json'))
    images={}
    for name in ('backend','ui','solr'):
        image=json.loads(subprocess.check_output(['docker','--host=unix:///var/run/docker.sock','image','inspect','nexus-dspace-'+name+':10.1-r'+str(args.from_recipe)],text=True))[0]
        assert image['Config']['Labels']['org.koha-nexus.dspace.release-lock']==previous
        images[name]=image['Id']
    old_catalog.write_text(json.dumps({'schema':1,'release_sha256':previous,'images':images}))
    new_catalog.write_text(subprocess.check_output([sys.executable,str(REPO/'tools/dspace_catalog.py')],text=True))
    rt=Runtime(root,old_catalog,lab=True,driver=str(REPO/'installer'),release_lock=previous)
    def assert_matrix():
        current=read_json(root/'compose.json')
        for name,service in current['services'].items():
            cid=rt.compose('ps','-q',name).strip()
            actual=json.loads(rt.docker('inspect',cid))[0]['Image']
            expected=json.loads(rt.docker('image','inspect',service['image']))[0]['Id']
            assert actual==expected, 'Running image matrix differs for '+name
    rt.install('http://repository.kei.test:8100')
    try:
        email='upgrade@example.org';password=secrets.token_urlsafe(24)
        rt.admin('create',dict(email=email,first='Nexus',last='Upgrade',language='en',password=password))
        from dspace_browser_test import API
        api=API(rt.state()['url']);api.login(email,password)
        community=api.request('/core/communities','POST',{'metadata':{'dc.title':[{'value':'Nexus historical upgrade community'}]}})
        collection=api.request('/core/collections?parent='+community['uuid'],'POST',{'metadata':{'dc.title':[{'value':'Nexus historical upgrade collection'}]}})
        # The official import CLI creates an archived item and bitstream in recipe 3.
        rt.compose('exec','-T','backend','sh','-ec','mkdir -p /dspace/imports/upgrade-fixture/item')
        files={'dublin_core.xml':'<dublin_core><dcvalue element="title" qualifier="none">Historical upgrade document</dcvalue></dublin_core>',
               'contents':'document.txt\n','document.txt':'historical document must survive the update\n'}
        for name,text in files.items():rt.compose('exec','-T','backend','sh','-ec','cat > "$1"','fixture','/dspace/imports/upgrade-fixture/item/'+name,input_text=text)
        rt.compose('run','--rm','--no-deps','-T','backend','cli','import','--add','--eperson',email,'--collection',collection['uuid'],
            '--source','/dspace/imports/upgrade-fixture','--mapfile','/dspace/imports/upgrade-map',timeout=300)
        rt.compose('run','--rm','--no-deps','-T','backend','cli','index-discovery','-b',timeout=300)
        schema=rt.compose('exec','-T','postgres','psql','-U','dspace','-d','dspace','-Atc','SELECT installed_rank,version,checksum,success FROM schema_version ORDER BY installed_rank')
        owned={k:v['name'] for k,v in read_json(root/'compose.json')['volumes'].items()}
        from languages import edit, configuration
        old_compose=read_json(root/'compose.json')
        old_language=edit(old_compose,{'active':['en','kk','pt-PT','sr-lat'],'fallback':'pt-PT'},args.from_recipe)
        (root/'compose.json').write_text(json.dumps(old_compose)+'\n')
        Operations(rt).commit_config()
        rt.compose('up','-d','--pull','never','--no-deps','--force-recreate','ui',timeout=240)
        rt.health()
        from dspace_recovery_test import prepare, assert_history
        recovery,_=prepare(rt)
        op=Operations(rt,recovery.phrase)
        # Exercise a real failed validation after changing images; rollback may not rewind repository data.
        original_health=rt.health;calls=[0]
        def fail_once():
            calls[0]+=1
            if calls[0]==2:raise Refused('Disposable injected post-update health failure')
            return original_health()
        # capture resumes invokes health, isolated clone uses its own probes, then update validates.
        rt.health=fail_once
        with rt.lock():
            try:op.upgrade({'catalog':str(new_catalog)},True)
            except Refused:pass
            else:raise AssertionError('Injected failed update unexpectedly succeeded')
        rt.health=original_health
        assert rt.state()['release_sha256']==previous
        assert_matrix()
        assert op.journal.exists() and read_json(op.journal)['phase']=='rolled-back'
        with rt.lock():result=op.upgrade({'catalog':str(new_catalog)},True)
        assert result['updated'] and rt.state()['release_sha256']==digest(REPO/'platforms/dspace/release.json')
        assert_matrix()
        assert owned=={k:v['name'] for k,v in read_json(root/'compose.json')['volumes'].items()}
        updated_language=configuration(read_json(root/'compose.json'),5)
        assert updated_language['active']==old_language['active'] and updated_language['fallback']==old_language['fallback']
        assert schema==rt.compose('exec','-T','postgres','psql','-U','dspace','-d','dspace','-Atc','SELECT installed_rank,version,checksum,success FROM schema_version ORDER BY installed_rank')
        assert_history(rt)
        current=API(rt.state()['url']);current.login(email,password)
        assert current.request('/core/collections/'+collection['uuid'])['uuid']==collection['uuid']
        # Official export proves the old bitstream contents, not just volume names.
        rt.compose('exec','-T','backend','sh','-ec','find /dspace/assetstore -type f -print0 | xargs -0 sha256sum > /dspace/reports/upgrade-files.sha256')
        expected=hashlib.sha256(files['document.txt'].encode()).hexdigest()
        assert expected in rt.compose('exec','-T','backend','cat','/dspace/reports/upgrade-files.sha256')
        (output/'dspace-upgrade-acceptance.json').write_text(json.dumps(dict(actual_historical_recipe=args.from_recipe,same_version_update=True,
            failed_validation_rollback=True,administrator_and_collection_preserved=True,document_checksum_preserved=True,
            schema_history_unchanged=True,old_volumes_preserved=True,major_version_migration=False)))
        print('PASS: actual historical recipes -> current recipe, injected failure rollback and historical document',flush=True)
    except BaseException:
        # Disposable lab only: service logs with this lab's generated database
        # password redacted, so a refused start (e.g. the schema guard) is visible.
        password=(root/'db-password').read_text().strip() if (root/'db-password').exists() else ''
        for service in SERVICES:
            try:print('Disposable CI logs: '+service+'\n'+redact(rt.compose('logs','--no-color','--tail','60',service,log_failure=False),password),flush=True)
            except Refused:pass
        raise
    finally:
        rt.compose('down','--timeout','90',timeout=420)  # no volume pruning; disposable runner owns final cleanup
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:
        # Public frames identify the failed acceptance step without leaking
        # CLI arguments, account passwords or raw service logs.
        import traceback
        frames=' > '.join(Path(frame.filename).name+':'+str(frame.lineno)+' '+frame.name
                          for frame in traceback.extract_tb(error.__traceback__))
        detail=type(error).__name__+' at '+frames
        print('::error title=DSpace historical upgrade::'+detail.replace('%','%25').replace('\n','%0A'),flush=True)
        raise
