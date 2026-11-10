#!/usr/bin/env python3
"""Portable encrypted Nexus recovery bundle; archived code is never executed.

The outer ZIP contains only a format header, a passphrase-protected OpenPGP
private key and an encrypted payload. Data/configuration/image inventories are
inside the payload. Opening a bundle imports its key into a temporary keyring,
never the destination keyring. Commands are supplied by the installed driver,
not by any archive field.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
import zipfile
import fcntl
import signal

KIND = 'koha-nexus-recovery'
CODECS = {'gz':'w:gz', 'bz2':'w:bz2', 'xz':'w:xz', 'none':'w'}
IMAGE = re.compile(r'sha256:[0-9a-f]{64}\Z')
HEX = re.compile(r'[0-9a-f]{64}\Z')
FPR = re.compile(r'[0-9A-F]{40,64}\Z')
OUTER = {'envelope.json', 'recovery-key.asc', 'payload.gpg'}
APPS = ('koha', 'tainacan', 'dspace')
KEY_ROLES = ('backup-secret-key-asc', 'backup-check-asc', 'backup-recovery-kit-txt')

class Error(ValueError):
    pass

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def atomic(path, value):
    path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as target:
            target.write(value);target.flush();os.fsync(target.fileno())
        os.replace(tmp,path)
        sync(path.parent)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def sync(path):
    fd=os.open(path,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

@contextlib.contextmanager
def operation(home):
    private(home,True)
    fd=os.open(home/'operation.lock',os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as lock:
        info=os.fstat(lock.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1 or info.st_mode&0o077:
            raise Error('Untrusted recovery operation lock.')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Error('Another full recovery operation is already running.') from None
        yield

def private(path, create=False):
    path=Path(path).absolute()
    if path.resolve()!=path:raise Error('Use a canonical recovery folder without symbolic links.')
    for ancestor in path.parents:
        if not ancestor.exists():continue
        st=ancestor.stat()
        sticky=st.st_uid==Path('/').stat().st_uid and st.st_mode&stat.S_ISVTX
        if st.st_uid not in (os.geteuid(),Path('/').stat().st_uid) or (st.st_mode&0o022 and not sticky):
            raise Error('The recovery folder has an untrusted writable parent.')
    if create:path.mkdir(mode=0o700,parents=True,exist_ok=True)
    st=path.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid() or st.st_mode&0o077:
        raise Error('The recovery folder must be private and owned by its operator.')
    return path

def run(args, *, env=None, input=None, timeout=21600):
    try:
        result=subprocess.run(list(map(str,args)),input=input,stdout=subprocess.PIPE,stderr=None,
                              env=env,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired):raise Error('Recovery command unavailable or timed out: '+str(args[0])) from None
    if result.returncode:raise Error('Recovery command failed (exit '+str(result.returncode)+'): '+str(args[0]))
    return result.stdout

def docker(*args, timeout=21600):
    env=dict(os.environ)
    for key in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):env.pop(key,None)
    return run(['docker','--host=unix:///var/run/docker.sock',*args],env=env,timeout=timeout)

class Crypto:
    def __init__(self, home):
        self.home=private(home,True)
        self.short_home=None
        # GnuPG otherwise places Unix sockets under GNUPGHOME. Long server
        # backup/session paths exceed sockaddr_un's limit on machines without
        # /run/user/<uid>/gnupg. Keep the temporary keyring private and short.
        if len(os.fsencode(str(self.home)))>70:
            self.short_home=Path(tempfile.mkdtemp(prefix='kn-gpg-',dir='/tmp'))
            self.home=private(self.short_home)
        self.env=dict(os.environ,GNUPGHOME=str(self.home),LC_ALL='C')
        self.env.pop('GPG_AGENT_INFO',None)
        atomic(self.home/'gpg-agent.conf','default-cache-ttl 0\nmax-cache-ttl 0\nallow-loopback-pinentry\n')
    def call(self,*args,phrase=None,input=None):
        if phrase is None:
            result=subprocess.run(['gpg','--no-options','--batch','--yes','--no-tty',*map(str,args)],
                env=self.env,input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=21600)
            if result.returncode:raise Error('The protected recovery key could not be read.')
            return result.stdout
        # An inherited descriptor, never a password in argv, logs or a disk file.
        read,write=os.pipe()
        try:
            os.write(write,phrase.encode());os.close(write);write=None
            result=subprocess.run(['gpg','--no-options','--batch','--yes','--no-tty','--pinentry-mode','loopback',
                '--passphrase-fd',str(read),*map(str,args)],input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                env=self.env,pass_fds=(read,),timeout=21600)
            if result.returncode:raise Error('The recovery key or phrase could not open this package.')
            return result.stdout
        finally:
            os.close(read)
            if write is not None:os.close(write)
    def check_key(self, key, fingerprint):
        if not isinstance(fingerprint,str) or not FPR.fullmatch(fingerprint) or len(key)>1024*1024:raise Error('Invalid recovery key envelope.')
        packets=self.call('--pinentry-mode','error','--list-packets',input=key).decode(errors='replace')
        sections=re.split(r':secret (?:sub )?key packet:',packets)[1:]
        if len(re.findall(r':secret key packet:',packets))!=1 or not sections or any('[v4 protected]' not in part.split(':signature packet:',1)[0] for part in sections):
            raise Error('Every private recovery key must remain passphrase-protected.')
        self.call('--import',input=key)
        listing=self.call('--with-colons','--list-secret-keys').decode()
        actual=[line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:')]
        if not actual or actual[0]!=fingerprint:raise Error('Recovery key fingerprint does not match.')
    def close(self):
        subprocess.run(['gpgconf','--kill','gpg-agent'],env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if self.short_home:shutil.rmtree(self.short_home)

def inventory(root):
    result={}
    for path in sorted(Path(root).rglob('*')):
        info=path.lstat()
        if stat.S_ISDIR(info.st_mode):continue
        if not stat.S_ISREG(info.st_mode):raise Error('Recovery staging contains a link or special file.')
        result[path.relative_to(root).as_posix()]={'bytes':info.st_size,'sha256':sha(path),'mode':stat.S_IMODE(info.st_mode)}
    return result

def copy_tree(source, target):
    source=Path(source)
    if source.is_symlink():raise Error('A configuration source is a symbolic link; review it first.')
    if source.is_dir():
        info=source.stat()
        if info.st_uid not in (0,os.geteuid()) or info.st_mode&0o022:
            raise Error('A configuration directory has untrusted write permissions.')
        target.mkdir(mode=0o700,parents=True,exist_ok=True)
        for item in source.iterdir():
            if item.name in ('__pycache__','.venv','.git') or item.name.endswith(('.pyc','.lock')):continue
            copy_tree(item,target/item.name)
    elif source.is_file():
        target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        info=source.stat()
        if info.st_uid not in (0,os.geteuid(),Path('/').stat().st_uid) or info.st_mode&0o022:
            raise Error('A configuration source has untrusted ownership or write permissions.')
        before=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
        with open(source,'rb') as inp,open(target,'xb') as out:
            opened=os.fstat(inp.fileno())
            if (opened.st_dev,opened.st_ino)!=(info.st_dev,info.st_ino):raise Error('A configuration source changed while opening.')
            shutil.copyfileobj(inp,out,1024*1024)
        after=source.stat()
        if before!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise Error('A configuration source changed during capture; retry the full backup.')
        target.chmod(0o600)
    else:raise Error('A required recovery source is missing or is a special file.')

def source_names(source):
    """The same exclusions as copy_tree, so additions cannot be silently lost."""
    source=Path(source)
    if source.is_symlink():raise Error('A source setting changed into a symbolic link.')
    if not source.is_dir():return {''} if source.is_file() else set()
    names=set()
    for child in source.iterdir():
        if child.name in ('__pycache__','.venv','.git') or child.name.endswith(('.pyc','.lock')):continue
        if child.is_symlink():raise Error('A source setting changed into a symbolic link.')
        if child.is_dir():names.update(child.name+'/'+name for name in source_names(child))
        elif child.is_file():names.add(child.name)
        else:raise Error('A source setting changed into a special file.')
    return names

def validate_manifest(tree, manifest, header):
    apps=manifest.get('applications')
    if (not isinstance(apps,list) or any(app not in APPS for app in apps) or len(apps)!=len(set(apps))
        or manifest.get('fingerprint')!=header['fingerprint'] or manifest.get('compression')!=header['compression']):
        raise Error('Invalid full recovery application manifest.')
    if apps and not (tree/'data/applications.tar').is_file():raise Error('Application data are missing.')
    for role in KEY_ROLES:
        if not (tree/'settings'/role).is_file():raise Error('The portable recovery kit is incomplete.')
    validate_kit({role:tree/'settings'/role for role in KEY_ROLES},header['fingerprint'])
    if hashlib.sha256((tree/'settings/backup-secret-key-asc').read_bytes()).hexdigest()!=header['key_sha256']:
        raise Error('The inner recovery key does not match its envelope.')
    images=manifest.get('images')
    if not isinstance(images,list):raise Error('Missing container image inventory.')
    seen=set()
    for row in images:
        if (not isinstance(row,dict) or not IMAGE.fullmatch(row.get('id','')) or row['id'] in seen
            or row.get('file')!='images/'+row['id'][7:]+'.tar' or not (tree/row['file']).is_file()):
            raise Error('Invalid recovered image mapping.')
        seen.add(row['id'])
    refs=manifest.get('image_references',{})
    if not isinstance(refs,dict) or any(not isinstance(ref,str) or not ref or ident not in seen for ref,ident in refs.items()):
        raise Error('Invalid recovered container reference inventory.')
    if not isinstance(manifest.get('settings'),dict) or any(not re.fullmatch(r'[a-z][a-z0-9-]{0,95}',role) for role in manifest['settings']):
        raise Error('Invalid recovered settings inventory.')

def validate_kit(paths,fingerprint):
    text=Path(paths['backup-recovery-kit-txt']).read_text()
    if re.findall(r'^fingerprint=([0-9A-F]+)$',text,re.M)!=[fingerprint]:
        raise Error('Save the current recovery kit again: its fingerprint does not match.')
    for section,role in (('secret-key','backup-secret-key-asc'),('check','backup-check-asc')):
        blocks=re.findall(r'^@@begin '+section+r'\n(.*?)^@@end$',text,re.M|re.S)
        if len(blocks)!=1 or blocks[0].strip()!=Path(paths[role]).read_text().strip():
            raise Error('Save the current recovery kit again: its protected key/check is out of date.')

def settings_changes(tree, current):
    """Only data formats understood here are applied to installed destinations.

    The remaining source files are retained in the private recovery session:
    host identities, arbitrary shell configuration, addresses and cron commands
    cannot become executable configuration just because they were archived.
    """
    targets=current.get('targets',{});changes=[];references=[]
    settings=tree/'settings'
    for role in sorted(p.name for p in settings.iterdir()):
        source=settings/role
        if role=='backup-plans' and source.is_dir() and targets.get(role):
            for item in sorted(source.glob('*.json')):
                if item.name.endswith('.history.json'):continue
                data=json.loads(item.read_text());name=data.get('id','')
                if (not re.fullmatch(r'[a-z][a-z0-9-]{0,31}',name) or item.name!=name+'.json'
                    or data.get('schema')!=1 or not isinstance(data.get('members'),list)
                    or not data['members'] or any(app not in APPS for app in data['members'])):
                    raise Error('Invalid archived backup plan; no settings were applied.')
                target=Path(targets[role])/item.name
                # Existing target plans are independent; never reschedule them.
                cron=Path(targets.get('plan-cron-directory','/etc/cron.d'))/('koha-nexus-plan-'+name)
                if target.exists() or cron.exists():references.append(role+'/'+item.name);continue
                data['time']=''
                changes.append((target,(json.dumps(data,indent=2)+'\n').encode(),role+'/'+item.name))
        elif role=='panel-settings' and source.is_dir() and targets.get(role):
            theme=source/'theme-settings.json'
            if theme.is_file():
                data=json.loads(theme.read_text())
                if not isinstance(data,dict):raise Error('Invalid theme preferences in the recovery package.')
                changes.append((Path(targets[role])/'theme-settings.json',(json.dumps(data)+'\n').encode(),role+'/theme-settings.json'))
            references.append(role)
        elif role=='panel-language' and source.is_file() and targets.get(role):
            allowed=set(current.get('panel_languages',[]));values={}
            for line in source.read_text().splitlines():
                match=re.fullmatch(r'(KOHA_PANEL_LANG(?:_FULL)?)=["\']?([a-z]{2}(?:-[A-Za-z]{2})?)["\']?',line.strip())
                if match and match[2] in allowed:values[match[1]]=match[2]
            if values:
                text=''.join(key+'="'+value+'"\n' for key,value in sorted(values.items()))
                changes.append((Path(targets[role]),text.encode(),role))
        elif role.startswith('backup-') or role.startswith('restic-'):
            references.append(role)
        else:references.append(role)
    for target,content,role in changes:
        if target.absolute()!=target or target.resolve()!=target:raise Error('A settings destination contains a symbolic link.')
        parent=target.parent
        while not parent.exists():parent=parent.parent
        info=parent.stat()
        if info.st_uid not in (0,os.geteuid()) or info.st_mode&0o022:raise Error('Untrusted settings destination.')
        if target.exists():
            info=target.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o022 or info.st_nlink!=1:
                raise Error('Untrusted settings destination file.')
    return changes,sorted(set(references))

def apply_settings(tree, session, current):
    area=session/'settings-rollback';area.mkdir(mode=0o700,exist_ok=True)
    journal=area/'journal.json'
    if journal.exists():
        # A process death between two atomic writes is rolled back before retry.
        previous=json.loads(journal.read_text())
        if previous.get('phase')!='complete':rollback_settings(area,previous)
        else:return previous['result']
    changes,references=settings_changes(tree,current)
    rows=[]
    for n,(target,content,role) in enumerate(changes):
        old=target.read_bytes() if target.exists() else None
        backup=area/str(n)
        if old is not None:backup.write_bytes(old);backup.chmod(0o600);sync(backup)
        rows.append({'target':str(target),'backup':str(n) if old is not None else None,
                     'old_sha256':hashlib.sha256(old).hexdigest() if old is not None else None,
                     'new_sha256':hashlib.sha256(content).hexdigest()})
    record={'phase':'applying','rows':rows}
    atomic(journal,json.dumps(record)+'\n')
    try:
        for target,content,role in changes:atomic(target,content.decode())
        result={'applied':[role for _,_,role in changes],'private_reference':references,
                'reference_directory':str(tree/'settings'),'source_schedules_activated':False}
        record.update(phase='complete',result=result);atomic(journal,json.dumps(record)+'\n')
        return result
    except BaseException:
        rollback_settings(area,record);raise

def rollback_settings(area,record):
    for row in reversed(record['rows']):
        target=Path(row['target'])
        # Preserve an operator's edit made after the interrupted recovery.
        if target.is_symlink():raise Error('A settings destination changed after interruption; review the recovery session.')
        actual=sha(target) if target.exists() else None
        if actual not in (row['old_sha256'],row['new_sha256']):raise Error('A settings destination was edited; review it before retrying recovery.')
        if actual==row['old_sha256']:continue
        if row['backup'] is None:target.unlink(missing_ok=True)
        else:atomic(target,(area/row['backup']).read_text())
    record['phase']='rolled-back';atomic(area/'journal.json',json.dumps(record)+'\n')

class Recovery:
    def __init__(self, driver, home='/var/lib/koha-nexus/full-recovery'):
        self.driver=str(Path(driver).absolute());self.home=Path(home)
    def task(self, action,*args,env=None):
        data=run(['bash',self.driver,'--task',action,*map(str,args)],env=env).decode(errors='replace')
        # The installer emits its machine protocol on stderr as well; use a
        # dedicated JSON driver below for inventory/capture instead of scraping logs.
        return data
    def driver_json(self,action,*args):
        return json.loads(run(['bash',self.driver,'--nexus-recovery-driver',action,*map(str,args)]))
    def plan(self,compression=None):
        compression=compression or self.settings()['compression']
        if compression not in CODECS:raise Error('Unknown recovery compression.')
        data=self.driver_json('inventory')
        if data.get('unknown'):raise Error('Some application states are unreadable; diagnose them before a full backup.')
        if not FPR.fullmatch(data.get('fingerprint','')):raise Error('Configure the existing shared backup key first.')
        if not Path(data.get('key_file','')).is_file():raise Error('The protected recovery key export is missing.')
        if any(app not in APPS for app in data.get('applications',[])):raise Error('Unknown application in full backup inventory.')
        if any(not Path(data.get('settings',{}).get(role,'')).is_file() for role in KEY_ROLES):
            raise Error('Save the current recovery kit before making a full backup.')
        return dict(data,compression=compression,kind=KIND,format=1,os_image=False,
                    previous_backups_included=False,external_publication_requires_review=True)
    def create(self,destination,compression=None):
        destination=private(destination,True);private(self.home,True)
        with operation(self.home):
            plan=self.plan(compression)
            compression=plan['compression']
            estimate=int(plan.get('estimated_source_bytes',0))
            required=max(64*1024*1024,estimate*4)
            if shutil.disk_usage(destination).free<required:
                raise Error('Insufficient backup space for staging, compression and encryption. Required estimate: '+str(required)+' bytes.')
            with tempfile.TemporaryDirectory(prefix='.nexus-capture-',dir=destination) as temp:
                stage=Path(temp);tree=stage/'tree';tree.mkdir(mode=0o700)
                key=Path(plan['key_file']).read_bytes()
                crypto=Crypto(stage/'key-check')
                try:crypto.check_key(key,plan['fingerprint'])
                finally:crypto.close()
                validate_kit(plan['settings'],plan['fingerprint'])
                # No silent data-only fallback. The existing application engines
                # capture each member consistently and check their own errors.
                if plan['applications']:
                    (tree/'data').mkdir(mode=0o700)
                    print('Capturing application data with the existing backup engines',file=__import__('sys').stderr,flush=True)
                    data=self.driver_json('capture',str(tree/'data'),','.join(plan['applications']))
                    if data.get('complete')!='yes' or data.get('recoverability')!='full':
                        raise Error('Application capture is incomplete; no full backup was published.')
                    package=Path(data['file'])
                    package.rename(tree/'data'/'applications.tar')
                for role,path in plan.get('settings',{}).items():
                    if not re.fullmatch(r'[a-z][a-z0-9-]{0,95}',role):raise Error('Invalid recovery role.')
                    print('Capturing Nexus configuration: '+role,file=__import__('sys').stderr,flush=True)
                    copy_tree(path,tree/'settings'/role)
                copy_tree(self.driver,tree/'program'/'installer')
                copy_tree(__file__,tree/'program'/'recovery.py')
                images=[]
                for image in sorted(set(plan.get('images',[]))):
                    if not IMAGE.fullmatch(image):raise Error('Invalid immutable container image ID.')
                    directory=tree/'images';directory.mkdir(mode=0o700,exist_ok=True)
                    image_file=directory/(image[7:]+'.tar')
                    print('Saving container image '+image[7:19],file=__import__('sys').stderr,flush=True)
                    docker('image','save','--output',str(image_file),image)
                    image_file.chmod(0o600);images.append({'id':image,'file':image_file.relative_to(tree).as_posix()})
                final=self.driver_json('inventory')
                for field in ('applications','images','fingerprint','settings','requirements','panel_version'):
                    if final.get(field)!=plan.get(field):raise Error('The server configuration changed during capture; retry the full backup.')
                if sha(self.driver)!=sha(tree/'program/installer'):
                    raise Error('The installed driver changed during capture; retry the full backup.')
                for role,source in plan.get('settings',{}).items():
                    captured=tree/'settings'/role
                    captured_names={item.relative_to(captured).as_posix() for item in captured.rglob('*') if item.is_file()} if captured.is_dir() else {''}
                    if source_names(source)!=captured_names:
                        raise Error('The source settings changed during capture; retry the full backup.')
                    pairs=((Path(source)/item.relative_to(captured),item) for item in captured.rglob('*') if item.is_file()) if captured.is_dir() else ((Path(source),captured),)
                    for original,copied in pairs:
                        if original.is_symlink() or not original.is_file() or sha(original)!=sha(copied):
                            raise Error('A source setting changed during capture; retry the full backup.')
                manifest=dict(kind=KIND,format=1,id=secrets.token_hex(16),created=int(time.time()),
                    panel_version=plan['panel_version'],system=plan['system'],applications=plan['applications'],
                    images=images,settings=plan.get('settings',{}),requirements=plan.get('requirements',{}),
                    files=inventory(tree),compression=compression,complete=True,
                    fingerprint=plan['fingerprint'],image_references=plan.get('image_references',{}))
                atomic(tree/'manifest.json',json.dumps(manifest,indent=2)+'\n')
                raw=stage/'payload.tar'
                print('Compressing the complete recovery payload',file=__import__('sys').stderr,flush=True)
                with tarfile.open(raw,CODECS[compression]) as archive:
                    for child in sorted(tree.iterdir()):archive.add(child,arcname=child.name,recursive=True)
                encrypted=stage/'payload.gpg'
                self.task('dspace-backup-crypto','encrypt',raw,encrypted)
                header=dict(kind=KIND,format=1,fingerprint=plan['fingerprint'],compression=compression,
                    payload_bytes=encrypted.stat().st_size,payload_sha256=sha(encrypted),key_sha256=hashlib.sha256(key).hexdigest())
                name='knx-nexus-'+time.strftime('%Y%m%d-%H%M%S')+'-'+manifest['id'][:8]+'.nexus'
                part=destination/('.'+name+'.part');target=destination/name
                try:
                    with zipfile.ZipFile(part,'x',compression=zipfile.ZIP_STORED) as archive:
                        archive.writestr('envelope.json',json.dumps(header))
                        archive.writestr('recovery-key.asc',key)
                        archive.write(encrypted,'payload.gpg')
                    part.chmod(0o600)
                    with open(part,'rb') as stream:os.fsync(stream.fileno())
                    os.replace(part,target)
                    sync(destination)
                finally:
                    if part.exists():part.unlink()
                atomic(self.home/'last.json',json.dumps({'file':str(target),'created':manifest['created'],'bytes':target.stat().st_size,'compression':compression,'applications':manifest['applications']})+'\n')
                return {'file':str(target),'bytes':target.stat().st_size,'complete':True,'compression':compression,'applications':manifest['applications']}
    @contextlib.contextmanager
    def opened(self,package,phrase):
        if not phrase or len(phrase.encode())>4096:raise Error('Provide the recovery phrase.')
        private(self.home,True)
        with tempfile.TemporaryDirectory(prefix='opened-',dir=self.home) as temp:
            area=Path(temp);budget=shutil.disk_usage(area).free//4
            fd=os.open(package,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,'rb') as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):raise Error('Select a regular recovery file.')
                with zipfile.ZipFile(source) as archive:
                    items=archive.infolist()
                    if len(items)!=3 or {i.filename for i in items}!=OUTER or any(i.compress_type!=zipfile.ZIP_STORED or i.flag_bits&1 for i in items):
                        raise Error('Unknown or unsafe full recovery envelope.')
                    if archive.getinfo('envelope.json').file_size>16384 or archive.getinfo('recovery-key.asc').file_size>1024*1024:
                        raise Error('Recovery envelope metadata is too large.')
                    header=json.loads(archive.read('envelope.json'));key=archive.read('recovery-key.asc')
                    if (not isinstance(header,dict) or header.get('kind')!=KIND or header.get('format')!=1 or header.get('compression') not in CODECS
                        or header.get('key_sha256')!=hashlib.sha256(key).hexdigest()):raise Error('Invalid recovery envelope header.')
                    payload=archive.getinfo('payload.gpg')
                    if payload.file_size>budget or payload.file_size!=header.get('payload_bytes'):raise Error('Insufficient recovery space or incorrect payload size.')
                    encrypted=area/'payload.gpg'
                    with archive.open(payload) as inp,open(encrypted,'xb') as out:shutil.copyfileobj(inp,out,1024*1024)
                    if sha(encrypted)!=header.get('payload_sha256'):raise Error('Encrypted recovery payload is damaged.')
            crypto=Crypto(area/'keyring')
            try:
                crypto.check_key(key,header['fingerprint'])
                raw=area/'payload.tar'
                crypto.call('--max-output',str(budget),'--output',raw,'--decrypt',encrypted,phrase=phrase)
                tree=area/'tree';tree.mkdir(mode=0o700)
                plain=expand(raw,budget,header['compression'])
                extract(plain,tree,budget,'none')
                if (tree/'manifest.json').stat().st_size>32*1024*1024:raise Error('Recovery manifest is too large.')
                manifest=json.loads((tree/'manifest.json').read_text())
                actual=inventory(tree);actual.pop('manifest.json',None)
                if not isinstance(manifest,dict) or manifest.get('kind')!=KIND or manifest.get('format')!=1 or manifest.get('complete') is not True or actual!=manifest.get('files'):
                    raise Error('Recovery contents do not match the complete manifest.')
                validate_manifest(tree,manifest,header)
                yield tree,manifest
            finally:crypto.close()
    def verify(self,package,phrase):
        with self.opened(package,phrase) as (tree,manifest):
            for row in manifest.get('images',[]):
                if not IMAGE.fullmatch(row.get('id','')) or row.get('file')!='images/'+row['id'][7:]+'.tar':raise Error('Invalid recovered image mapping.')
                if not (tree/row['file']).is_file():raise Error('A required container image is missing.')
            return {'verified':True,'applications':manifest['applications'],'images':len(manifest['images']),
                    'panel_version':manifest['panel_version'],'system':manifest['system'],'isolated_keyring':True}

    def prepare(self,package,phrase):
        private(self.home,True)
        session=self.home/('session-'+secrets.token_hex(16));session.mkdir(mode=0o700)
        try:
            with self.opened(package,phrase) as (tree,manifest):
                os.replace(tree,session/'tree')
                atomic(session/'session.json',json.dumps({'format':1,'fingerprint':manifest['fingerprint'],
                    'manifest_sha256':sha(session/'tree/manifest.json'),'phase':'opened','completed':[]})+'\n')
            return dict(self.restore_plan(str(session)),session=str(session))
        except BaseException:
            shutil.rmtree(session);raise
    def session(self,session):
        path=Path(session).absolute()
        if path.parent!=self.home.absolute() or not re.fullmatch(r'session-[0-9a-f]{32}',path.name):raise Error('Select an existing private recovery session.')
        private(path);tree=private(path/'tree')
        meta_path=path/'session.json'
        if meta_path.is_symlink() or not meta_path.is_file():raise Error('Invalid recovery session record.')
        meta=json.loads(meta_path.read_text())
        if (not isinstance(meta,dict) or meta.get('format')!=1 or meta.get('phase') not in ('opened','restoring','interrupted','complete')
            or not isinstance(meta.get('fingerprint'),str) or not FPR.fullmatch(meta['fingerprint'])
            or not isinstance(meta.get('completed'),list) or any(app not in (*APPS,'settings') for app in meta['completed'])):
            raise Error('Invalid recovery session record.')
        if sha(tree/'manifest.json')!=meta.get('manifest_sha256'):raise Error('The recovery manifest changed after opening.')
        manifest=json.loads((tree/'manifest.json').read_text());actual=inventory(tree);actual.pop('manifest.json',None)
        if actual!=manifest['files']:raise Error('The opened recovery contents changed; reopen the original package.')
        return path,tree,meta,manifest
    def restore_plan(self,session):
        path,tree,meta,manifest=self.session(session)
        current=self.driver_json('inventory');problems=[]
        missing=[app for app in manifest['applications'] if app not in current['applications']]
        if current.get('unknown'):problems.append('Diagnose unreadable destination applications first.')
        if missing:problems.append('Prepare compatible empty application installations first: '+', '.join(missing))
        if manifest['system']!=current['system']:problems.append('Recovery requires the same operating-system release and architecture.')
        if current.get('fingerprint') not in ('',meta['fingerprint']):problems.append('The destination has a different backup key. Its existing backups and key will not be overwritten.')
        for app in manifest['applications']:
            source=manifest.get('requirements',{}).get(app,{})
            target=current.get('requirements',{}).get(app,{})
            if app in missing:continue
            for field in ('package_version','release_sha256','url','images'):
                if field in source and source[field]!=target.get(field):problems.append(app+': destination '+field+' must match before full recovery.')
        try:
            changes,references=settings_changes(tree,current)
        except (Error,OSError,ValueError) as error:
            changes=[];references=[];problems.append(str(error))
        return {'compatible':not problems,'problems':problems,'applications':manifest['applications'],
            'images':len(manifest['images']),'settings':sorted(manifest.get('settings',{})),
            'completed':meta['completed'],'phase':meta['phase'],'source_version':manifest['panel_version'],
            'addresses_preserved':True,'schedules_restored_disabled':True,'publication_requires_review':True,
            'settings_to_apply':[role for _,_,role in changes],'settings_for_review':references,
            'reference_directory':str(tree/'settings'),
            'requires_prepared_applications':True,'cross_application_atomic':False}
    def _load_images(self,session):
        path,tree,meta,manifest=self.session(session)
        loaded=[]
        for row in manifest['images']:
            if not IMAGE.fullmatch(row.get('id','')) or row.get('file')!='images/'+row['id'][7:]+'.tar':raise Error('Invalid recovered image identity.')
            docker('image','load','--input',str(tree/row['file']))
            details=json.loads(docker('image','inspect',row['id']))
            if len(details)!=1 or details[0]['Id']!=row['id']:raise Error('A recovered image has the wrong identity.')
            loaded.append(row['id'])
        return {'loaded':loaded,'session':str(path)}
    def load_images(self,session):
        with operation(self.home):return self._load_images(session)
    def restore(self,session,phrase):
        with operation(self.home):
            plan=self.restore_plan(session)
            if not plan['compatible']:raise Error(' '.join(plan['problems']))
            path,tree,meta,manifest=self.session(session)
            if meta['phase']=='complete':return dict(plan,restored=True,session=str(path),settings=meta.get('settings_result',{}))
            # Recheck the phrase before importing a key or changing applications.
            key=tree/'settings/backup-secret-key-asc'
            check=tree/'settings/backup-check-asc'
            crypto=Crypto(path/'verification-keyring')
            try:
                crypto.check_key(key.read_bytes(),meta['fingerprint'])
                decoded=crypto.call('--decrypt',check,phrase=phrase)
                if decoded!=b'koha-nexus-recovery-kit-check':raise Error('Recovery phrase verification failed.')
            finally:
                crypto.close();shutil.rmtree(path/'verification-keyring',ignore_errors=True)
            meta['phase']='restoring';atomic(path/'session.json',json.dumps(meta)+'\n')
            try:
                self._load_images(session)
                self.driver_json_secret('import-key',phrase,str(tree/'settings/backup-recovery-kit-txt'))
                if manifest['applications'] and 'application-stage' not in meta:
                    data=self.driver_json('unpack',str(tree/'data/applications.tar'))
                    meta['application-stage']=data;atomic(path/'session.json',json.dumps(meta)+'\n')
                order=[app for app in ('dspace','koha','tainacan') if app in manifest['applications']]
                for app in order:
                    if app in meta['completed']:continue
                    stage=meta['application-stage']
                    if not stage.get(app):raise Error('The '+app+' member did not pass its recovery checks.')
                    print('Restoring '+app+' with its existing verification and safety-backup procedure',file=__import__('sys').stderr,flush=True)
                    self.driver_json_secret('restore-part',phrase,app,stage[app],stage['stage'])
                    meta['completed'].append(app);atomic(path/'session.json',json.dumps(meta)+'\n')
                if 'settings' not in meta['completed']:
                    result=apply_settings(tree,path,self.driver_json('inventory'))
                    meta['settings_result']=result;meta['completed'].append('settings')
                meta['phase']='complete';atomic(path/'session.json',json.dumps(meta)+'\n')
                return dict(self.restore_plan(session),restored=True,session=str(path),settings=meta.get('settings_result',{}))
            except BaseException:
                meta['phase']='interrupted';atomic(path/'session.json',json.dumps(meta)+'\n');raise
    def driver_json_secret(self,action,phrase,*args):
        env=dict(os.environ,KEI_BACKUP_PHRASE=phrase)
        return json.loads(run(['bash',self.driver,'--nexus-recovery-driver',action,*map(str,args)],env=env))
    def cleanup(self,session):
        with operation(self.home):
            path,tree,meta,manifest=self.session(session)
            if meta.get('phase') in ('restoring','interrupted'):raise Error('Resume the interrupted recovery before discarding its session.')
            if meta.get('application-stage'):self.driver_json('cleanup',meta['application-stage']['stage'])
            shutil.rmtree(path);return {'removed':True}
    def status(self):
        path=self.home/'last.json'
        result=json.loads(path.read_text()) if path.exists() else {'file':None}
        sessions=[]
        if self.home.exists():
            private(self.home)
            for folder in sorted(self.home.glob('session-*')):
                private(folder)
                meta=json.loads((folder/'session.json').read_text())
                sessions.append({'session':str(folder),'phase':meta['phase'],'completed':meta['completed']})
        result['sessions']=sessions
        result['compression']=self.settings()['compression']
        return result
    def settings(self,compression=None,confirm=False):
        if self.home.exists():private(self.home)
        path=self.home/'preferences.json'
        data=json.loads(path.read_text()) if path.exists() else {'compression':'gz'}
        if data.get('compression') not in CODECS:raise Error('Invalid full backup compression preference.')
        if compression is not None:
            if compression not in CODECS or not confirm:raise Error('Confirm the selected full backup compression.')
            with operation(self.home):
                data={'compression':compression};atomic(path,json.dumps(data)+'\n')
        return data

def identify(package):
    fd=os.open(package,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):raise Error('Select a regular recovery file.')
        try:
            with zipfile.ZipFile(source) as archive:
                if archive.getinfo('envelope.json').file_size>16384:return {'kind':'unknown'}
                header=json.loads(archive.read('envelope.json'))
                return {'kind':KIND if isinstance(header,dict) and header.get('kind')==KIND and header.get('format')==1 else 'unknown'}
        except (zipfile.BadZipFile,KeyError,ValueError):return {'kind':'unknown'}


def extract(path,target,budget,compression):
    with open(path,'rb') as source:magic=source.read(6)
    actual='gz' if magic.startswith(b'\x1f\x8b') else 'bz2' if magic.startswith(b'BZh') else 'xz' if magic.startswith(b'\xfd7zXZ\x00') else 'none'
    if actual!=compression:raise Error('Payload compression does not match its envelope.')
    total=0;seen=set();members=[]
    with tarfile.open(path,'r:*') as archive:
        for item in archive:
            name=PurePosixPath(item.name)
            if (not name.parts or name.is_absolute() or '..' in name.parts or '\\' in item.name or str(name)!=item.name
                or item.name in seen or len(name.parts)>80 or not(item.isfile() or item.isdir())
                or name.parts[0] not in ('manifest.json','data','settings','program','images')):
                raise Error('Unsafe or duplicate recovery archive member.')
            seen.add(item.name);total+=item.size
            if total>budget or len(seen)>1000000:raise Error('Recovery archive exceeds available space or entry limit.')
            members.append(item)
        for item in members:
            output=target/item.name
            if item.isdir():output.mkdir(mode=0o700,parents=True,exist_ok=True)
            else:
                output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                with archive.extractfile(item) as inp,open(output,'xb') as out:shutil.copyfileobj(inp,out,1024*1024)
                output.chmod(0o600)
                # Permissions are part of the inventory, but never grant access
                # outside the private staging directory or execute a file here.
                output.chmod(item.mode&0o777)

def expand(path,budget,compression):
    """Bound decompression before tar header parsing, including XZ memory use."""
    if compression=='none':return path
    import gzip,bz2,lzma
    output=path.with_name('expanded.tar');total=0
    try:
        with open(output,'xb') as out:
            if compression=='xz':
                dec=lzma.LZMADecompressor(memlimit=256*1024*1024)
                with open(path,'rb') as source:
                    while not dec.eof:
                        block=source.read(1024*1024) if dec.needs_input else b''
                        if not block and dec.needs_input:raise Error('Truncated XZ recovery payload.')
                        value=dec.decompress(block,max_length=1024*1024)
                        total+=len(value)
                        if total>budget:raise Error('Expanded recovery payload exceeds available space.')
                        out.write(value)
                    if dec.unused_data or source.read(1):raise Error('Ambiguous XZ recovery payload.')
            else:
                opener={'gz':gzip.open,'bz2':bz2.open}[compression]
                with opener(path,'rb') as source:
                    while True:
                        block=source.read(1024*1024)
                        if not block:break
                        total+=len(block)
                        if total>budget:raise Error('Expanded recovery payload exceeds available space.')
                        out.write(block)
    except (OSError,EOFError,lzma.LZMAError) as error:
        raise Error('The compressed recovery payload is damaged or exceeds the memory limit.') from error
    return output

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver',required=True);parser.add_argument('--home',default='/var/lib/koha-nexus/full-recovery')
    sub=parser.add_subparsers(dest='action',required=True)
    plan=sub.add_parser('plan');plan.add_argument('--compression',choices=CODECS)
    create=sub.add_parser('create');create.add_argument('destination');create.add_argument('--compression',choices=CODECS);create.add_argument('--confirm',action='store_true')
    verify=sub.add_parser('verify');verify.add_argument('package')
    sub.add_parser('status')
    identified=sub.add_parser('identify');identified.add_argument('package')
    settings=sub.add_parser('settings');settings.add_argument('--compression',choices=CODECS);settings.add_argument('--confirm',action='store_true')
    opened=sub.add_parser('open');opened.add_argument('package')
    for name in ('restore-plan','restore','load-images','cleanup'):
        child=sub.add_parser(name);child.add_argument('session')
        if name in ('restore','load-images'):child.add_argument('--confirm',action='store_true')
    args=parser.parse_args();recovery=Recovery(args.driver,args.home)
    phrase=os.environ.pop('KEI_BACKUP_PHRASE','')
    if args.action=='identify':result=identify(args.package)
    elif args.action=='settings':result=recovery.settings(args.compression,args.confirm)
    elif args.action=='plan':result=recovery.plan(args.compression)
    elif args.action=='create':
        if not args.confirm:raise Error('Confirm the reviewed full recovery plan first.')
        result=recovery.create(args.destination,args.compression)
    elif args.action=='verify':result=recovery.verify(args.package,phrase)
    elif args.action=='open':result=recovery.prepare(args.package,phrase)
    elif args.action=='restore-plan':result=recovery.restore_plan(args.session)
    elif args.action in ('restore','load-images'):
        if not args.confirm:raise Error('Review and confirm the recovery plan first.')
        result=recovery.restore(args.session,phrase) if args.action=='restore' else recovery.load_images(args.session)
    elif args.action=='cleanup':result=recovery.cleanup(args.session)
    else:
        result=recovery.status()
    print(json.dumps(result))

if __name__=='__main__':
    def interrupted(_signal,_frame):raise Error('Recovery interrupted. Its private session and completed components were preserved.')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGHUP,interrupted)
    try:main()
    except (KeyError,TypeError,AttributeError):
        print('Nexus recovery: invalid or incomplete recovery metadata.',file=__import__('sys').stderr);raise SystemExit(1)
    except (Error,OSError,ValueError,tarfile.TarError,zipfile.BadZipFile) as error:
        print('Nexus recovery: '+str(error),file=__import__('sys').stderr);raise SystemExit(1)
