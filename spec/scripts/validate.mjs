#!/usr/bin/env node
// UTCS conformance validator.
//
// Checks, in order:
//   1. Positive examples validate against their JSON Schemas.
//   2. Negative examples fail those schemas (a pass is a failure).
//   3. Redocly lints the OpenAPI document: structure, $ref resolution,
//      and embedded examples.
//   4. The bundled OpenAPI document's embedded examples validate with Ajv.
//   5. Each MCP tool inputSchema compiles, and a known-bad tool does not.
//   6. Manifest, OpenAPI, MCP, registries, and SPECIFICATION.md agree.
//
// Exit 0 = all checks passed, 1 = one or more checks failed.

import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { parse as parseYaml } from 'yaml';
import { bundle, createConfig, lint } from '@redocly/openapi-core';

const here = dirname(fileURLToPath(import.meta.url));
const specRoot = resolve(here, '..');
const schemasDir = join(specRoot, 'schemas');
const examplesDir = join(specRoot, 'examples');
const negativeDir = join(specRoot, 'conformance', 'negative');
const openapiFile = join(specRoot, 'openapi', 'utcs-v1.yaml');
const mcpFile = join(specRoot, 'mcp', 'utcs-mcp-tools.json');
const redoclyFile = join(specRoot, 'redocly.yaml');
const specificationFile = join(specRoot, 'SPECIFICATION.md');
const errorRegistryFile = join(specRoot, 'registries', 'error-codes.json');
const operationsFile = join(specRoot, 'registries', 'rest-operations.json');
const manifestFile = join(examplesDir, 'discovery-manifest.example.json');
const ucpBindingFile = join(specRoot, 'bindings', 'ucp.md');
const a2aBindingFile = join(specRoot, 'bindings', 'a2a.md');

const SCHEMA_BASE = 'https://utcs.tax/schemas/';
const HTTP_METHODS = new Set(['get', 'post', 'put', 'delete', 'patch', 'head', 'options', 'trace']);

let failures = 0;
const pass = (m) => console.log(`  \u2713 ${m}`);
const fail = (m) => { failures += 1; console.error(`  \u2717 ${m}`); };

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (name.endsWith('.schema.json')) out.push(full);
  }
  return out;
}

function readJson(file) {
  return JSON.parse(readFileSync(file, 'utf8'));
}

function operationKey(method, path) {
  return `${String(method).toUpperCase()} ${path}`;
}

function openApiOperations(doc) {
  const found = new Map();
  for (const [path, item] of Object.entries(doc.paths || {})) {
    if (!item || typeof item !== 'object') continue;
    for (const [method, op] of Object.entries(item)) {
      if (!HTTP_METHODS.has(method)) continue;
      found.set(operationKey(method, path), op);
    }
  }
  return found;
}

function manifestProblems(manifest, registryKeys, openApiKeys) {
  const problems = [];
  for (const cap of manifest.capabilities || []) {
    const allowed = registryKeys.get(cap.name) || new Set();
    for (const [name, ep] of Object.entries(cap.endpoints || {})) {
      const key = operationKey(ep.method, ep.path);
      if (!openApiKeys.has(key)) {
        problems.push(`${cap.name}.${name} ${key} is not an OpenAPI operation`);
      } else if (!allowed.has(key)) {
        problems.push(`${cap.name}.${name} ${key} is not a registered operation for ${cap.name}`);
      }
    }
  }
  for (const transport of manifest.transports || []) {
    if (transport.type === 'a2a' && !existsSync(a2aBindingFile)) {
      problems.push('transport a2a is advertised but spec/bindings/a2a.md is not published');
    }
    if (transport.type === 'webhook') {
      problems.push('transport webhook is reserved and must not be advertised in this version');
    }
  }
  return problems;
}

function checkTools(tools, knownCapabilities) {
  const problems = [];
  if (!Array.isArray(tools) || tools.length === 0) {
    return ['tools array missing or empty'];
  }
  const names = new Set();
  const schemaAjv = new Ajv2020({ strict: false, allErrors: true, validateSchema: true });
  for (const tool of tools) {
    const label = tool && tool.name ? tool.name : '(unnamed)';
    if (!tool || typeof tool.name !== 'string' || !tool.name.startsWith('utcs_')) {
      problems.push(`${label}: name must be a utcs_ string`);
    } else if (names.has(tool.name)) {
      problems.push(`${label}: duplicate tool name`);
    }
    names.add(tool.name);
    if (typeof tool.description !== 'string' || tool.description.length === 0) {
      problems.push(`${label}: description missing`);
    }
    if (typeof tool.inputSchema !== 'object' || tool.inputSchema === null) {
      problems.push(`${label}: inputSchema missing`);
      continue;
    }
    const capability = typeof tool.capability === 'string' ? tool.capability.split('@')[0] : '';
    const experimental = tool.status === 'experimental';
    if (experimental && knownCapabilities.has(capability)) {
      problems.push(`${label}: an experimental tool must stay outside the v1 registry`);
    } else if (!experimental && !knownCapabilities.has(capability)) {
      problems.push(`${label}: capability ${tool.capability || '(missing)'} is not in the REST registry`);
    }
    try {
      schemaAjv.compile(tool.inputSchema);
    } catch (err) {
      problems.push(`${label}: inputSchema does not compile (${err.message})`);
    }
  }
  return problems;
}

function collectMediaExamples(media, where, out) {
  if (!media || !media.schema) return;
  if (media.example !== undefined) out.push({ where: `${where} example`, schema: media.schema, value: media.example });
  if (media.examples && typeof media.examples === 'object') {
    for (const [name, ex] of Object.entries(media.examples)) {
      if (ex && Object.prototype.hasOwnProperty.call(ex, 'value')) {
        out.push({ where: `${where} ${name}`, schema: media.schema, value: ex.value });
      }
    }
  }
}

function collectEmbeddedExamples(doc) {
  const out = [];
  const consider = (op, label) => {
    if (!op || typeof op !== 'object') return;
    const request = op.requestBody && op.requestBody.content;
    if (request) {
      for (const [mime, media] of Object.entries(request)) {
        collectMediaExamples(media, `${label} request ${mime}`, out);
      }
    }
    for (const [code, response] of Object.entries(op.responses || {})) {
      if (!response || !response.content) continue;
      for (const [mime, media] of Object.entries(response.content)) {
        collectMediaExamples(media, `${label} ${code} ${mime}`, out);
      }
    }
  };
  for (const [path, item] of Object.entries(doc.paths || {})) {
    for (const [method, op] of Object.entries(item || {})) {
      if (HTTP_METHODS.has(method)) consider(op, `${method.toUpperCase()} ${path}`);
    }
  }
  return out;
}

function stripSchemaKeywords(node) {
  if (!node || typeof node !== 'object') return;
  if (Array.isArray(node)) {
    for (const item of node) stripSchemaKeywords(item);
    return;
  }
  delete node.$schema;
  delete node.$id;
  for (const value of Object.values(node)) stripSchemaKeywords(value);
}

const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
for (const file of walk(schemasDir)) {
  const schema = readJson(file);
  const rel = relative(schemasDir, file).split('\\').join('/');
  if (!schema.$id) schema.$id = SCHEMA_BASE + rel;
  ajv.addSchema(schema);
}

const positive = [
  ['determine-basic.request.json', 'transaction-context.schema.json'],
  ['determine-basic.response.json', 'tax-result.schema.json'],
  ['determine-multijurisdiction.request.json', 'transaction-context.schema.json'],
  ['determine-multijurisdiction.response.json', 'tax-result.schema.json'],
  ['determine-exempt.request.json', 'transaction-context.schema.json'],
  ['determine-exempt.response.json', 'tax-result.schema.json'],
  ['determine-discount.request.json', 'transaction-context.schema.json'],
  ['determine-discount.response.json', 'tax-result.schema.json'],
  ['determine-retail-delivery-fee.request.json', 'transaction-context.schema.json'],
  ['determine-retail-delivery-fee.response.json', 'tax-result.schema.json'],
  ['determine-return.request.json', 'transaction-context.schema.json'],
  ['error-insufficient-address.response.json', 'common/error-response.schema.json'],
  ['discovery-manifest.example.json', 'discovery-manifest.schema.json'],
  ['resolve-seattle.request.json', 'jurisdiction-resolution-request.schema.json'],
  ['resolve-seattle.response.json', 'jurisdiction-resolution-result.schema.json'],
  ['classify-products.request.json', 'classification-request.schema.json'],
  ['classify-products.response.json', 'classification-result.schema.json'],
  ['exemption-resale.request.json', 'exemption-validation-request.schema.json'],
  ['exemption-resale.response.json', 'exemption-validation-result.schema.json'],
  ['webhook-tax-committed.json', 'webhooks/tax-committed.schema.json'],
  ['webhook-document-generated.json', 'webhooks/document-generated.schema.json'],
  ['webhook-obligation-warning.json', 'webhooks/obligation-threshold-warning.schema.json'],
  ['webhook-obligation-crossed.json', 'webhooks/obligation-threshold-crossed.schema.json']
];

const negativeSchemas = [
  ['empty-lines.request.json', 'transaction-context.schema.json'],
  ['return-nonnegative-amount.request.json', 'transaction-context.schema.json'],
  ['sale-negative-quantity.request.json', 'transaction-context.schema.json'],
  ['unknown-error-code.json', 'common/error-response.schema.json'],
  ['classify-no-products.json', 'classification-request.schema.json'],
  ['webhook-missing-signature.json', 'webhooks/tax-committed.schema.json']
];

function validateFile(dir, file, schemaId) {
  const full = join(dir, file);
  if (!existsSync(full)) return { missing: true };
  const validate = ajv.getSchema(SCHEMA_BASE + schemaId);
  if (!validate) return { missingSchema: true };
  const data = readJson(full);
  const ok = validate(data);
  return { ok, errors: validate.errors || [], data };
}

console.log('Schema validation of examples:');
for (const [file, schemaId] of positive) {
  const result = validateFile(examplesDir, file, schemaId);
  if (result.missing) { fail(`${file} (file missing)`); continue; }
  if (result.missingSchema) { fail(`${file} (schema not registered: ${schemaId})`); continue; }
  if (result.ok) pass(`${file}  ->  ${schemaId}`);
  else {
    fail(`${file}  ->  ${schemaId}`);
    for (const e of result.errors) console.error(`        ${e.instancePath || '/'} ${e.message}`);
  }
}

console.log('\nNegative examples (these must fail):');
for (const [file, schemaId] of negativeSchemas) {
  const result = validateFile(negativeDir, file, schemaId);
  if (result.missing) { fail(`${file} (file missing)`); continue; }
  if (result.missingSchema) { fail(`${file} (schema not registered: ${schemaId})`); continue; }
  if (!result.ok) pass(`${file} rejected by ${schemaId}`);
  else fail(`${file} was accepted by ${schemaId}; a negative fixture must fail`);
}

const stale = validateFile(negativeDir, 'manifest-stale-paths.json', 'discovery-manifest.schema.json');
if (stale.missing || stale.missingSchema || !stale.ok) {
  fail('manifest-stale-paths.json must be schema-valid so the cross-artifact check is what rejects it');
  if (stale.errors) for (const e of stale.errors) console.error(`        ${e.instancePath || '/'} ${e.message}`);
} else {
  pass('manifest-stale-paths.json is schema-valid (the schema allows unknown paths)');
}

console.log('\nOpenAPI lint and $ref resolution:');
const openApiText = readFileSync(openapiFile, 'utf8');
let bundledDoc = null;
try {
  const rawConfig = parseYaml(readFileSync(redoclyFile, 'utf8'));
  const config = await createConfig(rawConfig, { configPath: redoclyFile });
  const problems = await lint({ ref: openapiFile, config });
  const errors = problems.filter((p) => p.severity === 'error');
  const warnings = problems.filter((p) => p.severity === 'warn');
  if (errors.length === 0) pass(`Redocly lint (${problems.length === 0 ? 'clean' : `${warnings.length} warning(s)`})`);
  else {
    fail(`Redocly lint reported ${errors.length} error(s)`);
    for (const p of errors) console.error(`        ${p.location && p.location.pointer ? p.location.pointer.join('/') : ''} ${p.message}`);
  }
  for (const p of warnings) console.log(`        warn: ${p.message}`);

  const bundled = await bundle({ ref: openapiFile, config, dereference: true });
  const bundleErrors = (bundled.problems || []).filter((p) => p.severity === 'error');
  if (bundleErrors.length === 0) pass(`$refs resolved (${bundled.fileDependencies.size} file(s))`);
  else {
    fail(`OpenAPI bundle reported ${bundleErrors.length} error(s)`);
    for (const p of bundleErrors) console.error(`        ${p.message}`);
  }
  bundledDoc = bundled.bundle.parsed;
} catch (err) {
  fail(`OpenAPI lint/bundle error: ${err.message}`);
}

if (bundledDoc) {
  console.log('\nEmbedded OpenAPI examples:');
  const exampleAjv = new Ajv2020({ strict: false, allErrors: true });
  addFormats(exampleAjv);
  const embedded = collectEmbeddedExamples(bundledDoc);
  if (embedded.length === 0) fail('no embedded examples found');
  else pass(`${embedded.length} embedded example(s) found`);
  for (const item of embedded) {
    try {
      const schema = structuredClone(item.schema);
      stripSchemaKeywords(schema);
      const validate = exampleAjv.compile(schema);
      if (validate(item.value)) pass(item.where);
      else {
        fail(item.where);
        for (const e of validate.errors) console.error(`        ${e.instancePath || '/'} ${e.message}`);
      }
    } catch (err) {
      fail(`${item.where} (schema did not compile: ${err.message})`);
    }
  }
}

console.log('\nMCP tool schemas:');
const operations = readJson(operationsFile);
const knownCapabilities = new Set(operations.operations.map((op) => op.capability).filter(Boolean));
try {
  const mcp = readJson(mcpFile);
  const tools = Array.isArray(mcp) ? mcp : mcp.tools;
  const problems = checkTools(tools, knownCapabilities);
  if (problems.length === 0) pass(`${tools.length} MCP tool inputSchema(s) compiled`);
  else {
    fail('MCP tool schemas');
    for (const p of problems) console.error(`        ${p}`);
  }
} catch (err) {
  fail(`MCP parse error: ${err.message}`);
}

const badTools = readJson(join(negativeDir, 'mcp-bad-tool.json'));
const badProblems = checkTools(badTools.tools, knownCapabilities);
if (badProblems.length > 0) pass('mcp-bad-tool.json rejected');
else fail('mcp-bad-tool.json was accepted; a negative tool must fail');

console.log('\nCross-artifact consistency:');
const specification = readFileSync(specificationFile, 'utf8');
const errorRegistry = readJson(errorRegistryFile);
const errorSchema = readJson(join(schemasDir, 'common', 'error-response.schema.json'));
const schemaCodes = errorSchema.properties.error.properties.code.enum;
const registryCodes = errorRegistry.codes.map((c) => c.code);
if (JSON.stringify(schemaCodes) === JSON.stringify(registryCodes)) {
  pass(`error-code enum matches registries/error-codes.json (${registryCodes.length} codes)`);
} else {
  fail('error-response.schema.json code enum does not match registries/error-codes.json');
}
const schemaCategories = new Set(errorSchema.properties.error.properties.category.enum);
let codesNamed = true;
for (const entry of errorRegistry.codes) {
  if (!schemaCategories.has(entry.category)) {
    fail(`${entry.code} category ${entry.category} is not in the error schema`);
  }
  if (!specification.includes(entry.code)) {
    codesNamed = false;
    fail(`SPECIFICATION.md does not name ${entry.code}`);
  }
}
if (codesNamed) pass('SPECIFICATION.md names every registry code');

let doc = null;
try {
  doc = parseYaml(openApiText);
} catch (err) {
  fail(`OpenAPI parse error: ${err.message}`);
}

if (doc) {
  const found = openApiOperations(doc);
  const registryKeys = new Set(operations.operations.map((op) => operationKey(op.method, op.path)));
  const byCapability = new Map();
  for (const op of operations.operations) {
    if (!op.capability) continue;
    if (!byCapability.has(op.capability)) byCapability.set(op.capability, new Set());
    byCapability.get(op.capability).add(operationKey(op.method, op.path));
  }
  let registryOk = true;
  for (const key of registryKeys) {
    if (!found.has(key)) { registryOk = false; fail(`registry operation missing from OpenAPI: ${key}`); }
    const path = key.slice(key.indexOf(' ') + 1);
    if (!specification.includes('`' + path + '`')) {
      registryOk = false;
      fail(`SPECIFICATION.md does not name \`${path}\``);
    }
  }
  const experimentalKeys = [];
  for (const [key, op] of found) {
    const experimental = op && op['x-utcs-status'] === 'experimental';
    if (experimental) experimentalKeys.push(key);
    if (experimental && registryKeys.has(key)) {
      registryOk = false;
      fail(`${key} is experimental and must stay out of the v1 registry`);
    } else if (!experimental && !registryKeys.has(key)) {
      registryOk = false;
      fail(`OpenAPI operation missing from registry: ${key}`);
    }
  }
  if (registryOk) pass(`REST registry matches OpenAPI (${registryKeys.size} operations, ${experimentalKeys.length} experimental)`);

  if (found.has('POST /tax/void')) fail('OpenAPI defines POST /tax/void; void is a document_type, not an operation');
  else pass('no /tax/void operation');
  const expectedExperimental = ['POST /cross-border/calculate', 'GET /obligations'];
  if (expectedExperimental.every((key) => experimentalKeys.includes(key))) {
    pass('cross-border and filing obligations are experimental');
  } else {
    fail(`experimental operations are ${experimentalKeys.join(', ') || '(none)'}; expected ${expectedExperimental.join(' and ')}`);
  }
  const hooks = doc.webhooks || {};
  const hookIds = Object.values(hooks).map((item) => item && item.post).filter(Boolean);
  if (hookIds.length === 4 && hookIds.every((op) => op['x-utcs-status'] === 'experimental')) {
    pass('webhook binding is experimental');
  } else {
    fail('webhook binding must publish four events, each with x-utcs-status: experimental');
  }

  const tx = readJson(join(schemasDir, 'transaction-context.schema.json'));
  for (const name of ['business_identification_no', 'delivery_terms', 'is_seller_importer_of_record']) {
    if (tx.properties && tx.properties[name]) fail(`transaction context still defines ${name}`);
  }
  const docTypes = (tx.properties && tx.properties.document_type && tx.properties.document_type.enum) || [];
  if (docTypes.includes('reverse_charge') || docTypes.includes('customs')) fail('document_type still includes a reserved value');
  else pass('transaction context omits reserved VAT and import members');

  const manifest = readJson(manifestFile);
  const published = manifestProblems(manifest, byCapability, found);
  if (published.length === 0) pass('discovery-manifest.example.json endpoints match the REST registry');
  else {
    fail('discovery-manifest.example.json disagrees with the REST binding');
    for (const p of published) console.error(`        ${p}`);
  }
  const staleProblems = manifestProblems(stale.data || readJson(join(negativeDir, 'manifest-stale-paths.json')), byCapability, found);
  if (staleProblems.length >= 2) pass(`manifest-stale-paths.json rejected (${staleProblems.length} problems)`);
  else fail(`manifest-stale-paths.json produced ${staleProblems.length} problem(s); expected the stale paths to fail`);

  const openApiErrorEnum = doc.components
    && doc.components.schemas
    && doc.components.schemas.ErrorResponse
    && doc.components.schemas.ErrorResponse.properties
    && doc.components.schemas.ErrorResponse.properties.error
    && doc.components.schemas.ErrorResponse.properties.error.properties
    && doc.components.schemas.ErrorResponse.properties.error.properties.code
    && doc.components.schemas.ErrorResponse.properties.error.properties.code.enum;
  if (openApiErrorEnum && JSON.stringify(openApiErrorEnum) === JSON.stringify(registryCodes)) {
    pass('OpenAPI ErrorResponse code enum matches the registry');
  } else {
    fail('OpenAPI ErrorResponse code enum does not match the registry');
  }

  const mcp = readJson(mcpFile);
  let toolsNamed = true;
  for (const tool of mcp.tools) {
    if (!specification.includes('`' + tool.name + '`')) {
      toolsNamed = false;
      fail(`SPECIFICATION.md does not name \`${tool.name}\``);
    }
  }
  if (toolsNamed) pass('MCP tool names are named in SPECIFICATION.md');
}

console.log('\nNeutrality and public references:');
const manifestText = readFileSync(manifestFile, 'utf8');
const isExampleHost = (host) => host === 'example.com' || host.endsWith('.example.com');
const hostsIn = (text) => [...text.matchAll(/https?:\/\/([^/\s"'<>)\]]+)/g)].map((match) => match[1].toLowerCase().replace(/:\d+$/, ''));
const mailDomainsIn = (text) => [...text.matchAll(/[A-Za-z0-9._%+-]+@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})/g)].map((match) => match[1].toLowerCase());
// Public reference sites the manifest example may cite. Every other host and every mailbox stays under example.com.
const manifestReferenceHosts = new Set(['www.streamlinedsalestax.org']);
const manifestNeutral = readJson(manifestFile).provider?.id === 'example-tax'
  && hostsIn(manifestText).every((host) => isExampleHost(host) || manifestReferenceHosts.has(host))
  && mailDomainsIn(manifestText).every(isExampleHost);
if (!manifestNeutral) {
  fail('discovery-manifest.example.json must use the provider id example-tax, with hosts and mailboxes under example.com');
} else pass('discovery manifest example uses a neutral provider');

const openApiContact = parseYaml(openApiText)?.info?.contact ?? {};
const openApiNeutral = openApiContact.name === 'UTCS Maintainers'
  && !openApiContact.email && !openApiContact.url
  && mailDomainsIn(openApiText).every(isExampleHost)
  && !/Avalara, Inc\./.test(openApiText);
if (!openApiNeutral) {
  fail('OpenAPI contact must be the UTCS Maintainers group, with no author and no mailbox outside example.com');
} else pass('OpenAPI contact is the maintainers group');

const examplesText = readdirSync(examplesDir).filter((name) => name.endsWith('.json')).map((name) => readFileSync(join(examplesDir, name), 'utf8')).join('\n');
if (/avalara/i.test(examplesText)) fail('a worked example still contains "avalara"');
else pass('worked examples do not name Avalara');

const ucpText = readFileSync(ucpBindingFile, 'utf8');
// Public hosts the UCP binding may link to. Add a host here when the binding needs one.
const ucpLinkHosts = new Set(['ucp.dev', 'github.com']);
if (!hostsIn(ucpText).every((host) => ucpLinkHosts.has(host))) fail('bindings/ucp.md links to a host that is not on its list of public hosts');
else pass('UCP binding links only to public hosts');
if (/\bA2A transport binding/.test(ucpText) || /beside the REST, MCP, and A2A/.test(ucpText)) {
  fail('bindings/ucp.md still treats an A2A binding as published');
} else pass('UCP binding does not claim a published A2A binding');

console.log('');
if (failures > 0) {
  console.error(`FAILED: ${failures} check(s) did not pass.`);
  process.exit(1);
}
console.log('OK: all conformance checks passed.');
