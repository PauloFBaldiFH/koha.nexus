// Build-stage regression test; never included in the runtime image.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.argv[2];
const require = createRequire(join(root, 'package.json'));
const { compare, applyPatch } = require('fast-json-patch');
const ts = require('typescript');
const source = readFileSync(join(root, 'src/app/core/cookies/cookie-metadata-operations.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022,
}}).outputText;
const { cookieMetadataOperations: scoped } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));
const consent = 'dspace.agreements.end-user';
const cookies = 'dspace.agreements.cookies';
const latest = { metadata: {
  [consent]: [{value:'true'}],
  'eperson.firstname': [{value:'New name'}],
  'profile.custom': [{value:'New field'}],
}};
const stale = { metadata: {
  'eperson.firstname': [{value:'Old name'}],
  [cookies]: [{value:'{"analytics":false}'}],
}};
// Same metadata comparison used by the upstream DSOChangeAnalyzer.
const operations = compare(latest.metadata, stale.metadata).map(op => ({...op, path:'/metadata' + op.path}));
const unsafe = applyPatch(structuredClone(latest), operations, true).newDocument;
assert.equal(unsafe.metadata[consent], undefined, 'Control must reproduce the upstream consent loss');
const before = structuredClone(operations);
const safe = applyPatch(structuredClone(latest), scoped(operations), true).newDocument;
assert.deepEqual(operations, before, 'Filtering cannot mutate pending operations');
assert.deepEqual(safe.metadata[consent], latest.metadata[consent]);
assert.deepEqual(safe.metadata['eperson.firstname'], latest.metadata['eperson.firstname']);
assert.deepEqual(safe.metadata['profile.custom'], latest.metadata['profile.custom']);
assert.deepEqual(safe.metadata[cookies], stale.metadata[cookies]);

const removed = applyPatch(structuredClone(safe), scoped([{op:'remove',path:'/metadata/' + cookies}]), true).newDocument;
assert.equal(removed.metadata[cookies], undefined);
assert.deepEqual(removed.metadata[consent], latest.metadata[consent]);
const replaced = applyPatch(structuredClone(safe), scoped([{op:'replace',path:'/metadata/' + cookies + '/0/value',value:'{"analytics":true}'}]), true).newDocument;
assert.equal(replaced.metadata[cookies][0].value, '{"analytics":true}');
assert.deepEqual(replaced.metadata[consent], latest.metadata[consent]);
assert.deepEqual(scoped([
  {op:'replace',path:'/metadata',value:{}},
  {op:'remove',path:'/metadata/dspace.agreements.cookies-extra'},
  {op:'copy',from:'/metadata/' + consent,path:'/metadata/' + cookies},
  {op:'move',from:'/metadata/' + consent,path:'/metadata/' + cookies},
]), []);
console.log('PASS: cookie preference writes preserve agreements and unrelated profile metadata; unsafe control reproduced data loss');
