"""Explicit DSpace operations. Reuses platform recovery and shared resource ownership.

Schedules store a fixed member list; old Koha/Tainacan plans are never rewritten.
No archived programs, shell fragments or floating image tags are executed.
"""
import contextlib
import copy
import fcntl
import json
import hashlib
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
import time
from urllib.parse import urlsplit

from runtime import BASE, LABELS, Refused, atomic, canonical_url, command, digest, local_docker_env, read_json
from backup import Recovery, Error, sha as file_sha

MEMBERS = ('koha', 'tainacan', 'dspace')
SCHEMA_RECEIPT = '/dspace/var/nexus-schema.sha256'
IDENTIFIER = re.compile(r'[a-z][a-z0-9-]{0,31}')
REMOTE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}:[A-Za-z0-9_./-]{1,180}')


def private(path, create=False, allow_read=False):
    path = Path(path).absolute()
    try:
        if path.resolve() != path:raise Refused('Use a canonical path without symbolic links.')
    except (OSError,RuntimeError):raise Refused('Use a canonical path without symbolic links.') from None
    operator=os.geteuid()
    # Public-readable backup parents are fine; writable untrusted ancestors are not.
    # Root's sticky /tmp is permitted, since other users cannot rename our root-owned child.
    for ancestor in (path,*path.parents):
        if not ancestor.exists():continue
        info=ancestor.stat()
        sticky=ancestor!=path and info.st_uid==0 and info.st_mode & stat.S_ISVTX
        if info.st_uid not in (0,operator) or (info.st_mode & 0o022 and not sticky):
            raise Refused('A backup path has an untrusted or writable parent; choose a server backup directory.')
    if create:path.mkdir(mode=0o700,parents=True,exist_ok=True)
    info=path.stat()
    forbidden=0o022 if allow_read else 0o077
    if not path.is_dir() or info.st_uid!=operator or info.st_mode & forbidden:
        raise Refused('Choose a trusted backup folder; each plan uses its own private subfolder.')
    return path


def cloud_env():
    env=local_docker_env()
    env.setdefault('RCLONE_CONFIG','/root/.config/rclone/rclone.conf')
    return env


def trusted_json(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_nlink != 1:
        raise Refused('An operation record has untrusted ownership or permissions.')
    return read_json(path)


def members(value):
    if not isinstance(value, list) or not value or any(not isinstance(p,str) or p not in MEMBERS for p in value) or len(value) != len(set(value)):
        raise Refused('Select each known platform at most once.')
    if 'dspace' not in value:
        raise Refused('Use the existing Koha/Tainacan plan editor for plans without DSpace.')
    return [p for p in MEMBERS if p in value]


def fields(text):
    """Existing installer task protocol; values are data, never commands."""
    result = {}
    for line in text.splitlines():
        if line.startswith('@@result '):
            key, sep, value = line[9:].partition('=')
            if sep: result[key] = value
    return result


class Operations:
    def __init__(self, rt, phrase=None):
        self.rt, self.phrase = rt, phrase
        self.home = rt.root.parent.parent / 'backup-plans'
        self.journal = rt.root / 'operations.json'

    def driver(self, task, *args, timeout=21600):
        if not self.rt.driver: raise Refused('Use the local installer resource driver.')
        return command(['bash', self.rt.driver, '--task', task, *map(str, args)], timeout=timeout, env=dict(local_docker_env(), KEI_DSPACE_DIR=str(self.rt.root)))

    def results(self, task, *args, partial=False, timeout=21600):
        """Results of an installer --task: kei_emit writes '@@result' lines to
        stderr (the panel reads both streams), so stdout alone is always empty.
        partial=True also returns the results of a task that exited non-zero."""
        from runtime import OperationFailed
        if not self.rt.driver: raise Refused('Use the local installer resource driver.')
        env=dict(local_docker_env(), KEI_DSPACE_DIR=str(self.rt.root))
        try:
            proc=subprocess.run(['bash', self.rt.driver, '--task', task, *map(str, args)], text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env)
        except (OSError, subprocess.TimeoutExpired):
            raise Refused('Operation unavailable or timed out: ' + task)
        if proc.returncode and not partial: raise OperationFailed(task, proc)
        return fields(proc.stdout + '\n' + proc.stderr)

    def plan_path(self, name):
        if not isinstance(name, str) or not IDENTIFIER.fullmatch(name): raise Refused('Invalid backup plan identifier.')
        return self.home / (name + '.json')

    def check_plan(self, data):
        if not isinstance(data, dict): raise Refused('The plan must be an object.')
        name = data.get('id'); self.plan_path(name)
        selected = members(data.get('members'))
        hour = data.get('time', '')
        if hour and not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', hour): raise Refused('Use HH:MM or an empty time to disable the schedule.')
        keep = data.get('keep', 7)
        if isinstance(keep, bool) or not isinstance(keep, int) or not 1 <= keep <= 365: raise Refused('Keep 1 to 365 successful packages.')
        dest = private(data.get('destination', ''), allow_read=True)
        if dest == self.rt.root or self.rt.root in dest.parents or dest in self.rt.root.parents:
            raise Refused('Backups must be outside the platform configuration directory.')
        remote = data.get('remote', '')
        if not isinstance(remote, str) or (remote and (not REMOTE.fullmatch(remote) or '..' in remote.split('/') or any(x in remote for x in ('Backup_SQL_Koha', 'Backup_MARC_Koha')))):
            raise Refused('Choose an existing rclone connection and a separate backup folder.')
        if remote:
            available = command(['rclone', 'listremotes'], timeout=30, env=cloud_env()).splitlines()
            if remote.split(':')[0] + ':' not in available: raise Refused('The chosen cloud connection does not exist.')
        return dict(schema=1, id=name, members=selected, time=hour, keep=keep, destination=str(dest), remote=remote)

    @contextlib.contextmanager
    def plan_lock(self, name):
        self.plan_path(name)
        private(self.home, create=True)
        fd = os.open(self.home / (name + '.lock'), os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as out:
            info = os.fstat(out.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1 or info.st_mode & 0o077:
                raise Refused('Untrusted plan lock.')
            try: fcntl.flock(out, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise Refused('This backup plan is already running or being edited.')
            yield

    def plans(self):
        rows = []
        if not self.home.exists(): return {'plans': rows}
        private(self.home)
        for path in sorted(self.home.glob('*.json')):
            if path.name.endswith('.history.json'): continue
            data = trusted_json(path)
            if data.get('schema') != 1 or self.plan_path(data.get('id')) != path: raise Refused('Unknown plan record.')
            history = self.history(data['id'])
            rows.append(dict(data, last=history[-1] if history else None))
        return {'plans': rows}

    def save_plan(self, request, confirm=False):
        data = self.check_plan(request)
        # A schedule cannot silently create a data-only backup.
        Recovery(self.rt).crypto('check')
        if not confirm: return dict(plan=data, writes='private plan, owned cron; no backup runs now', encrypted=True)
        if os.geteuid() != 0: raise Refused('Save scheduled plans locally as root.')
        self.driver('dspace-cache')
        with self.plan_lock(data['id']):
            path = self.plan_path(data['id'])
            old = trusted_json(path) if path.exists() else None
            self.expected_plan(request, old)
            atomic(path, json.dumps(data) + '\n')
            try:
                self.rt.core('plan-cron', data['id'], data['time'], ','.join(data['members']))
            except BaseException:
                if old is None: path.unlink()
                else: atomic(path, json.dumps(old) + '\n')
                raise
        return {'saved': data, 'encrypted': True}

    def expected_plan(self, request, current):
        if 'expected_plan' in request and request['expected_plan'] != current:
            raise Refused('This backup plan changed since it was displayed. Refresh before saving.')

    def disable_plan(self, name, confirm=False, expected=None):
        private(self.home)
        data=trusted_json(self.plan_path(name))
        if data.get('schema')!=1 or data.get('id')!=name:raise Refused('Unknown backup plan.')
        selected=members(data.get('members'))
        data['time']=''
        if not confirm:return {'plan':data,'writes':'owned cron removal only; no backup, key or cloud access'}
        if os.geteuid()!=0:raise Refused('Disable scheduled plans locally as root.')
        with self.plan_lock(name):
            # Disabling remains possible when the destination, credentials or key are lost.
            data=trusted_json(self.plan_path(name))
            if data.get('schema')!=1 or data.get('id')!=name:raise Refused('Unknown backup plan.')
            if expected is not None:
                self.expected_plan({'expected_plan': expected}, data)
            selected=members(data.get('members'));data['time']=''
            self.rt.core('plan-cron',name,'',','.join(selected))
            atomic(self.plan_path(name),json.dumps(data)+'\n')
        return {'disabled':name,'plan':data}

    def history(self, name):
        path = self.home / (name + '.history.json')
        return trusted_json(path) if path.exists() else []

    def run_plan(self, name):
        if os.geteuid() != 0: raise Refused('Run scheduled backups locally as root.')
        with self.plan_lock(name):
            plan = self.check_plan(trusted_json(self.plan_path(name)))
            recovery = Recovery(self.rt); recovery.crypto('check')
            directory = private(Path(plan['destination']) / ('nexus-' + name), create=True)
            history = self.history(name)
            record = dict(started=time.time(), members=plan['members'], capture='failed', copy='not-requested', retention='not-run')
            try:
                with __import__('tempfile').TemporaryDirectory(prefix='.capture-', dir=directory) as temp:
                    temp = Path(temp)
                    if plan['members'] == ['dspace']:
                        result = json.loads(self.driver('dspace', 'backup-create', '--confirm'))
                        source = Path(result['package'])
                        if source.is_symlink() or not source.is_file(): raise Refused('The DSpace backup was not published.')
                        target = directory / source.name
                        with open(source, 'rb') as src, open(temp / 'capture.part', 'xb') as dst: shutil.copyfileobj(src, dst)
                    else:
                        # The format-2 set contains existing platform packages, not references.
                        # A partial capture exits non-zero but still reports its file.
                        result=self.results('set-backup',temp,','.join(plan['members']),partial=True)
                        if not result.get('file'): raise Refused('No platform could be captured; no package was published.')
                        record['partial']=result.get('complete')!='yes' or result.get('recoverability')!='full'
                        source = Path(result['file'])
                        if source.parent != temp or source.is_symlink(): raise Refused('Invalid capture destination.')
                        target = directory / (source.name + '.gpg')
                        recovery.crypto('encrypt', source, temp / 'capture.part')
                    from backup import sync_path
                    sync_path(temp / 'capture.part')
                    if target.exists(): raise Refused('A backup with this name already exists.')
                    os.replace(temp / 'capture.part', target); target.chmod(0o600); sync_path(directory)
                    record.update(capture='partial' if record.get('partial') else 'ok', file=str(target), sha256=file_sha(target))
                    atomic(target.with_suffix('.sha256'), record['sha256'] + '\n')
                if record.get('partial'): raise Refused('A partial encrypted package was preserved; no upload or retention ran.')
                if plan['remote']:
                    record['copy'] = 'failed'
                    remote = plan['remote'].rstrip('/') + '/' + target.name
                    command(['rclone', 'copyto', str(target), remote], timeout=21600, env=cloud_env())
                    verified = json.loads(command(['rclone', 'lsjson', '--stat', remote], timeout=120, env=cloud_env()))
                    if verified.get('Size') != target.stat().st_size: raise Refused('The cloud copy size was not verified.')
                    record.update(copy='ok', remote=remote)
                history.append(record)
                self.retention(plan, history)
                record['retention'] = 'ok'
                return dict(record, complete=True)
            except BaseException:
                record['complete'] = False
                if not history or history[-1] is not record: history.append(record)
                raise
            finally:
                record['finished'] = time.time()
                atomic(self.home / (name + '.history.json'), json.dumps(history[-2000:]) + '\n')

    def retention(self, plan, history):
        """Only this plan's recorded immutable outputs; never prune unrelated directories."""
        good = [r for r in history if r.get('capture') == 'ok' and r.get('copy') != 'failed' and not r.get('deleted')]
        for row in good[:-plan['keep']]:
            path = Path(row['file'])
            expected = Path(plan['destination']) / ('nexus-' + plan['id'])
            if path.parent != expected or not re.fullmatch(r'knx-(?:dspace|set)-[a-z0-9-]+\.tar\.gpg', path.name):
                continue
            if path.is_symlink() or (path.exists() and file_sha(path) != row['sha256']):
                raise Refused('An old backup changed; automatic retention refused.')
            # Remote deletion is intentionally exact and only after a newer copy succeeded.
            if row.get('remote') and plan['remote'] and row['remote'] == plan['remote'].rstrip('/') + '/' + path.name:
                command(['rclone', 'deletefile', row['remote']], timeout=300, env=cloud_env())
            path.unlink(missing_ok=True); path.with_suffix('.sha256').unlink(missing_ok=True)
            row['deleted'] = True

    def pending(self):
        if self.journal.exists() and trusted_json(self.journal).get('phase') not in ('complete', 'rolled-back'):
            raise Refused('Interrupted DSpace operation. Resume the same removal, or use config.sh --task dspace operations rollback --confirm for an address/update rollback.')

    def snapshot(self, operation):
        self.pending()
        data = dict(schema=1, operation=operation, phase='prepared', files={}, state=self.rt.state())
        for name in ('local.cfg', 'compose.json'):
            data['files'][name] = (self.rt.root / name).read_text()
        catalog=self.rt.catalog_path
        if catalog.exists():
            if catalog.is_symlink():raise Refused('The image catalog must not be a symbolic link.')
            data['catalog']={'path':str(catalog),'text':catalog.read_text()}
        atomic(self.journal, json.dumps(data) + '\n')
        return data

    def commit_config(self):
        self.rt.mark(files={n:digest(self.rt.root/n) for n in ('local.cfg','compose.json','db-password')})

    def schema_receipt(self):
        """Prove the running history matches the installed image's guard, then read its receipt.

        The receipt binds the database history to the release lock baked into
        the backend image, so a reviewed image update must re-bind it and a
        rollback must put back the exact previous receipt.
        """
        self.rt.compose('run','--rm','--no-deps','-T','--entrypoint','java','backend',
                        '-cp','/usr/local/lib/nexus-dspace:/dspace/lib/*','NexusSchemaGuard','check',timeout=180)
        text=self.rt.compose('run','--rm','--no-deps','-T','--entrypoint','cat','backend',SCHEMA_RECEIPT,timeout=120).strip()
        if not re.fullmatch(r'[a-f0-9]{64}',text): raise Refused('Unexpected DSpace schema receipt; nothing was changed.')
        return text

    def restart(self, dependencies=False, schema=None):
        """schema: 'record' re-binds the unchanged history to the new image's
        release lock; a 64-hex value puts back that exact previous receipt."""
        if schema is not None and (not dependencies or not (schema=='record' or re.fullmatch(r'[a-f0-9]{64}',schema))):
            raise Refused('A schema receipt is only changed with the backend stopped, from a valid saved value.')
        if dependencies:
            # The reviewed update replaces the Solr image too. Drain its writers
            # before recreating it; otherwise Compose could leave recipe 3 running
            # while the declared matrix already says recipe 4.
            self.rt.compose('stop','--timeout','90','ui','backend','solr',timeout=420)
            self.rt.compose('up','-d','--pull','never','--force-recreate','solr',timeout=420)
        self.rt.dependencies()
        if schema=='record':
            self.rt.compose('run','--rm','--no-deps','-T','backend','schema-record',timeout=180)
        elif schema is not None:
            self.rt.compose('run','--rm','--no-deps','-T','--entrypoint','sh','backend','-ec',
                            'umask 077; cat > "$1.restore"; mv -f "$1.restore" "$1"','receipt',SCHEMA_RECEIPT,
                            input_text=schema+'\n',timeout=120)
        self.rt.compose('up','-d','--pull','never','--force-recreate','backend','ui',timeout=420)
        self.rt.health(); self.rt.core('audit')

    def rollback(self):
        if not self.journal.exists(): raise Refused('There is no saved operation to roll back.')
        data = trusted_json(self.journal)
        if data.get('operation')=='remove':raise Refused('Removal is resumed with the same explicit removal request; erased volumes are recovered from its safety backup, not by configuration rollback.')
        if data.get('phase') == 'complete': raise Refused('Completed operations are not automatically reversed.')
        language_change = data.get('operation') == 'languages'
        for name in (('compose.json',) if language_change else ('local.cfg', 'compose.json')):
            atomic(self.rt.root/name, data['files'][name], gid=10001 if name=='local.cfg' else None, mode=0o440 if name=='local.cfg' else 0o600)
        atomic(self.rt.root/'state.json', json.dumps(data['state'])+'\n')
        if data.get('catalog'):
            if data['catalog']['path']!=str(self.rt.catalog_path):raise Refused('Catalog rollback destination changed; inspect the journal.')
            atomic(self.rt.catalog_path,data['catalog']['text'])
        upgrade=data.get('operation')=='upgrade'
        if language_change:
            if data['state'].get('intended') != 'stopped':
                self.rt.compose('up','-d','--pull','never','--no-deps','--force-recreate','ui',timeout=240)
                self.rt.health(); self.rt.public_health()
        else:
            self.restart(dependencies=upgrade,schema=data.get('schema_receipt') if upgrade else None)
            self.rt.core('proxy')
        data['phase']='rolled-back'; atomic(self.journal,json.dumps(data)+'\n')
        return {'rolled_back':True, 'data_volumes_preserved':True}

    def address_plan(self, request):
        self.pending()
        Recovery(self.rt).checked()
        url = canonical_url(request['url']); u=urlsplit(url)
        self.rt.core('address-check',url)
        mode=request.get('mode','apache')
        if mode not in ('apache','external','tunnel','tls'): raise Refused('Unknown publication mode.')
        port=request.get('origin_port',8100)
        if isinstance(port,bool) or not isinstance(port,int) or not 1024<=port<=65535 or port in (8080,8090,18100,18101): raise Refused('Choose a separate unprivileged origin port.')
        if mode in ('tunnel','tls','external') and u.scheme!='https': raise Refused('This publication mode requires a canonical HTTPS address.')
        if mode=='apache' and u.scheme!='http': raise Refused('Select TLS, tunnel or an external HTTPS proxy.')
        proxy_mode=self.rt.core('publication-plan').strip()
        if proxy_mode=='external' and mode!='external':raise Refused('An external web server is active. Use its own HTTPS configuration; no Apache site was changed.')
        cert=request.get('certificate',''); key=request.get('key','')
        if mode=='tls':
            for path in (cert,key):
                if not isinstance(path,str) or not re.fullmatch(r'/[A-Za-z0-9_./-]+',path) or not Path(path).is_file(): raise Refused('Choose existing PEM certificate and private key files.')
            command(['openssl','x509','-in',cert,'-noout','-checkhost',u.hostname],timeout=10)
            command(['openssl','x509','-in',cert,'-noout','-checkend','86400'],timeout=10)
            public=command(['openssl','x509','-in',cert,'-noout','-pubkey'],timeout=10)
            actual=command(['openssl','pkey','-in',key,'-passin','pass:','-pubout'],timeout=10)
            if public!=actual: raise Refused('Certificate and private key do not match.')
        plan=dict(previous_url=self.rt.state()['url'],url=url,mode=mode,origin_port=port,certificate=cert,key=key,
                    safety_backup=True,external_proxy_manual=mode=='external',identifier_changes=False,
                    oai_publication='disabled pending live permission/index reconciliation acceptance')
        if mode=='external':
            proxy=request.get('proxy','nginx')
            if proxy not in ('nginx','caddy'):raise Refused('Choose nginx or caddy for the external proxy instructions.')
            ports=self.rt.state()['ports']
            headers='proxy_set_header Host '+u.netloc+'; proxy_set_header X-Forwarded-Proto https; proxy_set_header Forwarded \"\"; proxy_set_header X-Forwarded-Host '+u.netloc+'; proxy_set_header X-Forwarded-Port '+str(u.port or 443)+'; proxy_set_header X-Forwarded-For $remote_addr;'
            nginx=('location ~ ^/server/(actuator|config|oai)(/|$) { deny all; }\n'
                'location /server { proxy_pass http://127.0.0.1:'+str(ports['backend'])+'; '+headers+' proxy_read_timeout 300s; }\n'
                'location / { proxy_pass http://127.0.0.1:'+str(ports['ui'])+'; '+headers+' proxy_read_timeout 300s; }\n')
            caddy=('@internal path /server/actuator* /server/config* /server/oai*\nrespond @internal 403\n'
                'handle /server* {\n reverse_proxy 127.0.0.1:'+str(ports['backend'])+' {\n header_up Host '+u.netloc+'\n header_up X-Forwarded-Proto https\n }\n}\n'
                'handle {\n reverse_proxy 127.0.0.1:'+str(ports['ui'])+' {\n header_up Host '+u.netloc+'\n header_up X-Forwarded-Proto https\n }\n}\n')
            plan['external_proxy_snippet']=nginx if proxy=='nginx' else caddy
        return plan

    def address(self, request, confirm=False):
        plan=self.address_plan(request)
        if not confirm: return plan
        if not self.phrase:raise Refused('The recovery phrase is required to verify the safety backup.')
        recovery=Recovery(self.rt,self.phrase);recovery.recover_capture()
        if self.rt.state().get('url')==plan['url'] and self.rt.state().get('publication',{}).get('mode')==plan['mode']:
            if plan['mode']!='external':self.rt.core('proxy');self.rt.health();self.rt.public_health()
            return dict(plan,changed=False,managed_proxy_checked=plan['mode']!='external')
        package=recovery.capture()['package']
        # Recoverability is proven before any canonical URL or configuration changes.
        recovery.test(package)
        saved=self.snapshot('address'); saved['safety_backup']=package
        atomic(self.journal,json.dumps(saved)+'\n')
        try:
            cfg=(self.rt.root/'local.cfg').read_text()
            values={'dspace.ui.url':plan['url'],'dspace.server.url':plan['url']+'/server','rest.cors.allowed-origins':plan['url']}
            for key,value in values.items():
                cfg,n=re.subn(r'(?m)^\s*'+re.escape(key)+r'\s*=.*$',key+' = '+value,cfg)
                if n!=1: raise Refused('The canonical URL configuration needs manual review: '+key)
            compose=read_json(self.rt.root/'compose.json'); env=compose['services']['ui']['environment']; u=urlsplit(plan['url'])
            env.update(DSPACE_UI_BASEURL=plan['url'],DSPACE_REST_HOST=u.hostname,DSPACE_REST_PORT=str(u.port or (443 if u.scheme=='https' else 80)),DSPACE_REST_SSL=str(u.scheme=='https').lower())
            atomic(self.rt.root/'local.cfg',cfg,0o440,gid=10001)
            atomic(self.rt.root/'compose.json',json.dumps(compose,indent=2)+'\n')
            self.rt.mark(url=plan['url'],publication={k:plan[k] for k in ('mode','origin_port','certificate','key')})
            self.commit_config(); self.restart()
            if plan['mode']!='external': self.rt.core('proxy')
            self.rt.mark(proxy_status='external-proxy-required' if plan['mode']=='external' else 'apache-configured')
            self.rt.public_health()
            saved['phase']='complete'; atomic(self.journal,json.dumps(saved)+'\n')
            return dict(plan,changed=True,safety_backup=package,verified='local API and SSR; external DNS/TLS still requires end-to-end verification')
        except BaseException:
            self.rollback(); raise

    def repair_web(self, request, confirm=False):
        """Repair the managed web configuration, optionally for this PC only.

        No database/assetstore operation and no image build/migration. Keep a
        private configuration journal and roll it back if the web checks fail.
        Public address/publication changes still use the normal address flow.
        """
        self.pending()
        state, compose = Recovery(self.rt).checked(web_repair=True)
        if state.get('migration') != 'done' or state.get('publication', {}).get('mode', 'apache') != 'apache':
            raise Refused('Local web repair requires a completed installation with the managed HTTP proxy.')
        if self.rt.core('publication-plan').strip() == 'external':
            raise Refused('The web server is external; its configuration was preserved.')
        local = request.get('local_only', False)
        if type(local) is not bool:
            raise Refused('Choose whether access is local to this computer.')
        old = urlsplit(canonical_url(state['url']))
        if old.scheme != 'http' or (local and (old.port or 80) in (80,443)):
            raise Refused('Local repair needs a separate HTTP port; use the address assistant for another publication mode.')
        url = canonical_url(request.get('url') or ('http://localhost:' + str(old.port) if local else old.geturl()))
        target = urlsplit(url)
        if target.scheme != 'http' or target.port != old.port or not (url == old.geturl() or target.hostname == 'localhost' or re.fullmatch(r'[0-9.]+',target.hostname)):
            raise Refused('Web repair accepts the actual local IPv4 address or localhost on the existing HTTP port. Use the address assistant for domains, TLS or port changes.')
        self.rt.core('address-check',url)
        local = target.hostname == 'localhost' or target.hostname.startswith('127.')
        plan = dict(url=url, previous_url=state['url'], local_only=local,
                    changes='DSpace UI/API address and owned Apache site; private configuration rollback copy',
                    data_volumes_preserved=True, database_migration=False,
                    note='localhost works only on this computer. Other computers require the network/address assistant.' if local else 'The configured public address is preserved.')
        if not confirm:
            return plan
        saved = self.snapshot('repair-web')
        try:
            cfg = saved['files']['local.cfg']
            for key, value in {'dspace.ui.url':url, 'dspace.server.url':url+'/server', 'rest.cors.allowed-origins':url}.items():
                cfg, count = re.subn(r'(?m)^\s*'+re.escape(key)+r'\s*=.*$', key+' = '+value, cfg)
                if count != 1:
                    raise Refused('The web configuration needs manual review: '+key)
            env = compose['services']['ui']['environment']
            env.update(DSPACE_UI_BASEURL=url, DSPACE_REST_HOST=urlsplit(url).hostname,
                       DSPACE_REST_PORT=str(old.port or 80), DSPACE_REST_SSL='false')
            atomic(self.rt.root/'local.cfg',cfg,0o440,gid=10001)
            atomic(self.rt.root/'compose.json',json.dumps(compose,indent=2)+'\n')
            self.rt.mark(url=url)
            self.commit_config()
            self.restart()
            self.rt.core('proxy')
            self.rt.mark(proxy_status='apache-configured')
            self.rt.public_health()
            self.rt.mark(status='installed', phase='ready', intended='running')
            saved['phase']='complete'; atomic(self.journal,json.dumps(saved)+'\n')
            return dict(plan, repaired=True)
        except BaseException:
            # The original configuration may already be broken. Restore its
            # bytes/listener even when its health check cannot succeed.
            for name in ('local.cfg','compose.json'):
                atomic(self.rt.root/name,saved['files'][name],mode=0o440 if name=='local.cfg' else 0o600,gid=10001 if name=='local.cfg' else None)
            atomic(self.rt.root/'state.json',json.dumps(saved['state'])+'\n')
            try:
                self.rt.compose('up','-d','--pull','never','--force-recreate','backend','ui',timeout=420)
                self.rt.core('proxy')
                saved['phase']='rolled-back'; atomic(self.journal,json.dumps(saved)+'\n')
            except BaseException:
                raise Refused('Web repair failed and automatic configuration recovery is incomplete. Data volumes were preserved; inspect the private operation journal and resume rollback.') from None
            raise

    def languages(self, request):
        from languages import configuration, suggest
        state,compose=Recovery(self.rt).checked()
        result=configuration(compose,self.rt.release['recipe'])
        result.update(suggested=suggest(request.get('panel_language'),self.rt.release['recipe']),
                      bundled=True, downloads_required=False,
                      account_upgrade_required=self.rt.release['recipe']<5)
        return result

    def language_save(self, request, confirm=False):
        from languages import edit
        self.pending()
        state,compose=Recovery(self.rt).checked()
        stopped=state.get('intended')=='stopped'
        revision=hashlib.sha256((digest(self.rt.root/'compose.json')+'\0'+str(stopped)).encode()).hexdigest()
        if 'expected_revision' in request and request['expected_revision']!=revision:
            raise Refused('The DSpace configuration changed since this plan was displayed. Refresh before applying languages.')
        try:result=edit(compose,request,self.rt.release['recipe'])
        except ValueError as error:raise Refused(str(error)) from None
        if not confirm:
            changes = 'UI languages and fallback; applied on next start.' if stopped else 'UI languages and fallback; UI container restart only.'
            return dict(result,revision=revision,pending_start=stopped,changes=changes+' Existing account preferences are kept.')
        saved=self.snapshot('languages')
        try:
            atomic(self.rt.root/'compose.json',json.dumps(compose,indent=2)+'\n')
            self.commit_config()
            if not stopped:
                self.rt.compose('up','-d','--pull','never','--no-deps','--force-recreate','ui',timeout=240)
                self.rt.health();self.rt.public_health()
            saved['phase']='complete';atomic(self.journal,json.dumps(saved)+'\n')
            return dict(result,saved=True,pending_start=stopped)
        except BaseException:
            atomic(self.rt.root/'compose.json',saved['files']['compose.json'])
            atomic(self.rt.root/'state.json',json.dumps(saved['state'])+'\n')
            if not stopped:
                self.rt.compose('up','-d','--pull','never','--no-deps','--force-recreate','ui',timeout=240)
            saved['phase']='rolled-back';atomic(self.journal,json.dumps(saved)+'\n')
            raise

    def upgrade(self, request, confirm=False):
        self.pending()
        state,compose=Recovery(self.rt).checked()
        target=read_json(BASE/'release.json'); target_hash=digest(BASE/'release.json')
        from runtime import reviewed_releases
        reviewed=reviewed_releases()
        if self.rt.release_hash not in reviewed or self.rt.release_hash==target_hash or self.rt.release.get('recipe') not in (3,4) or target.get('recipe')!=5:
            raise Refused('Only reviewed recipe 3 or 4 to 5 updates of DSpace 10.1 are supported.')
        if target['sources']!=self.rt.release['sources'] or target['bases']!=self.rt.release['bases']:
            raise Refused('Schema, runtime or database migrations require a separately reviewed procedure.')
        catalog=Path(request['catalog']).absolute()
        # Validate using an empty target directory, never silently select new images for an installed old release.
        from runtime import Runtime
        candidate=Runtime(self.rt.root.parent/'upgrade-candidate'/'dspace',catalog,self.rt.lab,self.rt.driver,release_lock=target_hash)
        images=candidate.images()
        from languages import migrate_environment
        try:migrate_environment(compose,self.rt.release['recipe'])
        except ValueError as error:raise Refused(str(error)) from None
        plan=dict(from_recipe=self.rt.release['recipe'],to_recipe=target['recipe'],release_sha256=target_hash,images=images,database_migration=False,safety_backup_required=True,language_configuration_preserved=True,
                  # Recovery requires the exact installed image matrix (PR4); recipe 3 packages,
                  # including this safety backup, are refused once recipe 4 is confirmed.
                  earlier_backups_restorable_after_update=False)
        if not confirm:return plan
        if not self.phrase:raise Refused('The recovery phrase is required to verify the safety backup.')
        recovery=Recovery(self.rt,self.phrase);recovery.recover_capture()
        candidate.check_images(images)  # before stopping a running service
        package=recovery.capture()['package']; recovery.test(package)
        # Checked by the installed image's own guard before anything changes.
        receipt=self.schema_receipt()
        saved=self.snapshot('upgrade'); saved['safety_backup']=package; saved['schema_receipt']=receipt
        atomic(self.journal,json.dumps(saved)+'\n')
        try:
            for name,image in images.items(): compose['services'][name]['image']=image
            atomic(self.rt.root/'compose.json',json.dumps(compose,indent=2)+'\n')
            atomic(self.rt.catalog_path,catalog.read_text())
            self.rt.mark(release_sha256=target_hash,recipe=target['recipe'])
            self.commit_config(); self.restart(dependencies=True,schema='record')
            saved['phase']='complete'; atomic(self.journal,json.dumps(saved)+'\n')
            return dict(plan,updated=True,safety_backup=package)
        except BaseException:
            self.rollback();raise

    def remove(self, request, confirm=False):
        purge=request.get('purge',False)
        if not isinstance(purge,bool):raise Refused('Choose explicitly whether to erase data.')
        pending=trusted_json(self.journal) if self.journal.exists() else {}
        resumed=pending.get('operation')=='remove' and pending.get('phase')!='complete'
        if resumed:
            if purge!=pending['purge']:raise Refused('Resume the same removal choice recorded in the journal.')
            state,compose=Recovery(self.rt,self.phrase).checked()
            names=pending['volumes']
        else:
            self.pending()
            recovery=Recovery(self.rt,self.phrase);state,compose=recovery.checked()
            volumes=recovery.volumes(compose)
            names={k:compose['volumes'][k]['name'] for k in volumes}
        plan=dict(keep_data=not purge,volumes=list(names),shared_services_removed=False,backup_before_purge=purge,resume=resumed)
        if not confirm:return plan
        if purge and request.get('erase')!='DSpace':raise Refused('Type DSpace to confirm permanent removal of its owned data.')
        if state.get('publication',{}).get('mode')=='tunnel':raise Refused('Detach the DSpace tunnel address first; shared tunnel is preserved.')
        Recovery(self.rt,self.phrase).recover_capture()
        if purge and not resumed:
            if not self.phrase:raise Refused('The recovery phrase is required to verify the safety backup.')
            package=recovery.capture()['package'];recovery.test(package);plan['safety_backup']=package
        if not resumed:
            pending=dict(schema=1,operation='remove',phase='stopping',purge=purge,volumes=names,deleted=[],safety_backup=plan.get('safety_backup'))
            atomic(self.journal,json.dumps(pending)+'\n')
        for item in self.plans()['plans']:
            if 'dspace' in item['members'] and item['time']:
                self.disable_plan(item['id'],True)
        self.rt.compose('stop','--timeout','90','ui','backend','solr','postgres',timeout=420)
        self.rt.core('release-web')
        self.rt.compose('down','--timeout','90',timeout=420) # no volumes or shared network removed implicitly
        if purge:
            pending['phase']='erasing';atomic(self.journal,json.dumps(pending)+'\n')
            for name in names.values():
                if not re.fullmatch(r'kn-dspace(?:-rt-[0-9a-f]{20})?-[a-z-]+',name):raise Refused('Unexpected volume name in removal journal.')
                if name in pending['deleted']:continue
                present=set(self.rt.docker('volume','ls','--format','{{.Name}}').splitlines())
                if name in present:
                    obj=json.loads(self.rt.docker('volume','inspect',name))[0]
                    if any((obj.get('Labels') or {}).get(k)!=v for k,v in LABELS.items()):raise Refused('A remaining volume has changed ownership.')
                    self.rt.docker('volume','rm',name)
                self.rt.core('forget-volume',name)
                pending['deleted'].append(name);atomic(self.journal,json.dumps(pending)+'\n')
        self.rt.mark(status='data-removed' if purge else 'data-kept',intended='stopped')
        pending['phase']='complete';atomic(self.journal,json.dumps(pending)+'\n')
        if purge:
            # Retain the private configuration/journal for audit and explicit disaster recovery,
            # outside the active installation path. No backup or old recovered volume is erased.
            archive=self.rt.root.parent/('dspace-removed-'+secrets.token_hex(10))
            os.rename(self.rt.root,archive)
            plan['configuration_archive']=str(archive)
        return dict(plan,removed=True)

    def dispatch(self, action, request, confirm=False):
        if action=='plans':return self.plans()
        if action=='languages':return self.languages(request)
        if action=='plan-save':return self.save_plan(request,confirm)
        if action=='plan-disable':return self.disable_plan(request['id'],confirm,request.get('expected_plan'))
        if action=='plan-run':
            if not confirm:raise Refused('Explicit --confirm is required to run a backup.')
            return self.run_plan(request['id'])
        if action in ('address','upgrade','remove','rollback','repair-web','language-save'):
            with self.rt.lock(allow_pending=action in ('rollback','remove')):
                if action=='rollback':
                    if not confirm:raise Refused('Explicit confirmation is required for rollback.')
                    return self.rollback()
                return getattr(self,action.replace('-','_'))(request,confirm)
        raise Refused('Unknown DSpace operation.')
