// Real local Worker/D1/Durable Object + fake Cloudflare. No external publication.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {startBroker,BROKER_DIR} from './harness.mjs';
const temp=mkdtempSync(join(tmpdir(),'nexus-dspace-broker-'));
const signer=join(BROKER_DIR,'scripts/kei-sign.sh');
const broker=await startBroker({vars:{DSPACE_ENABLED:'true'}});
let checks=0;
async function call(method,path,body,headers={}){
  const r=await fetch(broker.url+path,{method,headers:{...(body===undefined?{}:{'Content-Type':'application/json'}),...headers},body:body===undefined?undefined:typeof body==='string'?body:JSON.stringify(body)});
  return {status:r.status,data:await r.json()};
}
function signed(lib,method,path,body){
  const args=[signer,'headers',lib.key,lib.id,method,path],raw=body===undefined?undefined:JSON.stringify(body);
  if(raw!==undefined){const file=join(temp,'body.json');writeFileSync(file,raw,{mode:0o600});args.push(file);}
  const headers=Object.fromEntries(execFileSync('bash',args,{encoding:'utf8',timeout:30000}).trim().split('\n').filter(Boolean).map(line=>{const i=line.indexOf(':');return [line.slice(0,i),line.slice(i+1).trim()];}));
  return call(method,path,raw,headers);
}
async function enroll(name,services){
  const key=join(temp,name+'.key');execFileSync('bash',[signer,'keygen',key]);
  const pub=execFileSync('bash',[signer,'pubkey',key],{encoding:'utf8'}).trim();
  const start=await call('POST','/v1/device/start',{institution_name:'Repository institution '+name,contact_email:'repository@example.org',requested_name:name,services});
  assert.equal(start.status,200,'Repository enrollment request refused');
  const result=await call('POST','/v1/enroll',{device_code:start.data.device_code,public_key:pub});
  assert.equal(result.status,202);assert.ok(await broker.settle());
  return {id:result.data.library_id,key};
}
try{
  const caps=await call('GET','/v1/capabilities');assert.ok(caps.data.services.includes('dspace'));assert.equal(caps.data.repository_origin_port,18102);checks++;
  const shared=await enroll('repository-shared',['koha','tainacan']);
  const before=broker.fake.snapshot(),tunnel=before.tunnels[0].id;
  const attached=await signed(shared,'PUT','/v1/services',{dspace:true});assert.equal(attached.status,200);assert.ok(attached.data.hostnames.repository.endsWith('-repositorio.example.org'));checks++;
  const detached=await signed(shared,'DELETE','/v1/services/dspace');assert.equal(detached.status,200);assert.equal(detached.data.services,'koha,tainacan');
  const after=broker.fake.snapshot();assert.equal(after.tunnels[0].id,tunnel);assert.deepEqual(after.dns_records.map(x=>x.name).sort(),before.dns_records.map(x=>x.name).sort());checks++;
  const alone=await enroll('repository-alone',['dspace']);
  const info=await signed(alone,'GET','/v1/library');assert.deepEqual(info.data.services,['dspace']);assert.deepEqual(Object.keys(info.data.hostnames),['repository']);checks++;
  const removed=await signed(alone,'DELETE','/v1/services/dspace');assert.equal(removed.status,202);assert.ok(await broker.settle());
  assert.equal((await signed(shared,'GET','/v1/library')).data.status,'active');assert.equal(broker.fake.snapshot().tunnels.length,1);checks++;
  await broker.db.prepare("DELETE FROM broker_features WHERE name='dspace'").run();
  const old=await call('GET','/v1/capabilities');assert.ok(!old.data.services.includes('dspace'));
  const unavailable=await call('POST','/v1/device/start',{institution_name:'Unavailable repository',contact_email:'repository@example.org',requested_name:'repository-unavailable',services:['dspace']});assert.equal(unavailable.status,409);checks++;
  console.log(`DSpace broker e2e: ${checks} checks passed (local Worker and fake Cloudflare)`);
}finally{await broker.close();rmSync(temp,{recursive:true,force:true});}
