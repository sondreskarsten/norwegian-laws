const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const [output, executable, ...args] = process.argv.slice(2);
if (!output || !executable) {
  throw new Error('Usage: node test_published_mcp.cjs OUTPUT.json COMMAND [ARGS...]');
}
const cwd = fs.mkdtempSync(path.join(os.tmpdir(), 'laws-mcp-consumer-'));
const env = { ...process.env };
for (const key of Object.keys(env)) {
  if (key.startsWith('NORWEGIAN_LAWS_') || ['PYTHONPATH', 'PYTHONHOME'].includes(key)) {
    delete env[key];
  }
}
const child = spawn(executable, args, { cwd, env, stdio: ['pipe', 'pipe', 'pipe'] });
let nextId = 0;
let buffer = '';
let stderr = '';
let finished = false;
const transcript = [];
const pending = new Map();

function save(result) {
  fs.writeFileSync(path.resolve(output), JSON.stringify({ ...result, transcript, stderr }, null, 2));
}
function fail(error) {
  if (finished) return;
  finished = true;
  clearTimeout(timer);
  save({ passed: false, error: String(error) });
  console.error(error);
  child.kill('SIGTERM');
  process.exitCode = 1;
}
const timer = setTimeout(() => {
  fail(new Error('MCP distribution check timed out after 180 seconds'));
  child.kill('SIGKILL');
}, 180000);
child.on('error', fail);
child.on('exit', (code, signal) => {
  fs.rmSync(cwd, { recursive: true, force: true });
  if (!finished) fail(new Error(`Server exited before checks finished: ${code}, ${signal}`));
});
child.stdin.on('error', fail);
child.stderr.on('data', bytes => { stderr += bytes; });
child.stdout.on('data', bytes => {
  buffer += bytes;
  let newline;
  while ((newline = buffer.indexOf('\n')) >= 0) {
    const line = buffer.slice(0, newline);
    buffer = buffer.slice(newline + 1);
    try {
      const response = JSON.parse(line);
      transcript.push(response);
      if (pending.has(response.id)) {
        pending.get(response.id)(response);
        pending.delete(response.id);
      }
    } catch (error) {
      fail(new Error(`Non-JSON protocol output: ${line}`));
    }
  }
});
function request(method, params) {
  return new Promise(resolve => {
    const id = ++nextId;
    pending.set(id, resolve);
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  });
}
async function call(name, args) {
  const response = await request('tools/call', { name, arguments: args });
  assert(!response.error, JSON.stringify(response));
  return response.result;
}
async function main() {
  const init = await request('initialize', {
    protocolVersion: '2025-11-25', capabilities: {},
    clientInfo: { name: 'distribution-audit', version: '1.0' },
  });
  assert(init.result, JSON.stringify(init));
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
  const tools = await request('tools/list', {});
  assert.equal(tools.result.tools.length, 21);
  for (const name of ['search', 'fetch', 'laws_get_document']) {
    assert(tools.result.tools.some(tool => tool.name === name));
  }
  const search = await call('search', { query: 'enhetsregisterloven' });
  assert(!search.isError);
  const data = JSON.parse(search.content[0].text);
  assert(data.results.length > 0);
  assert(data.results.every(result => result.id && result.title && result.url));
  const fetched = await call('fetch', { id: data.results[0].id });
  assert(!fetched.isError);
  const doc = JSON.parse(fetched.content[0].text);
  assert(doc.text.length > 100);
  assert.equal(doc.id, data.results[0].id);
  assert(doc.url && doc.metadata.refid);
  const section = await call('laws_get_document', { ref: 'lov/2025-06-20-105', section: '§ 4-7' });
  assert(!section.isError);
  assert(section.content[0].text.includes('underenhet'));
  const missing = await call('fetch', { id: 'lov/9999-01-01-1' });
  assert(missing.content[0].text.startsWith('Error:'));
  if (finished) return;
  finished = true;
  clearTimeout(timer);
  save({ passed: true });
  console.log('21 tools; search, fetch, section and missing-ID checks passed');
  child.kill('SIGTERM');
}
main().catch(fail);
