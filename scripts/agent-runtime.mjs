#!/usr/bin/env node
import { spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const OPENCODE_PACKAGE = 'opencode-ai';
export const OPENCODE_VERSION = '1.19.4';
export const DEFAULT_HOST = '127.0.0.1';
export const DEFAULT_PORT = 4096;

export function runtimeDirectory(env = process.env, home = homedir()) {
  if (env.APPDATA && process.platform === 'win32') return join(env.APPDATA, 'AIrchitect', 'agent-runtime');
  return join(env.XDG_CONFIG_HOME || join(home, '.config'), 'airchitect', 'agent-runtime');
}

export function parseArgs(argv) {
  const [command = 'help', ...rest] = argv;
  const options = {};
  for (let i = 0; i < rest.length; i += 1) {
    const item = rest[i];
    if (!item.startsWith('--')) throw new Error(`Unexpected argument: ${item}`);
    const key = item.slice(2);
    const value = rest[i + 1];
    if (!value || value.startsWith('--')) throw new Error(`Missing value for --${key}`);
    options[key] = value;
    i += 1;
  }
  return { command, options };
}

export function validateOrigin(value) {
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
    throw new Error('Origin must be an http(s) origin without credentials, path, query or fragment.');
  }
  if (url.protocol === 'http:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) {
    throw new Error('Non-local browser origins must use HTTPS.');
  }
  return url.origin;
}

export function serverArguments({ host = DEFAULT_HOST, port = DEFAULT_PORT, origin }) {
  if (host !== DEFAULT_HOST && host !== '::1') {
    throw new Error('The local OpenCode runtime must bind to loopback only.');
  }
  if (!Number.isInteger(Number(port)) || Number(port) < 1024 || Number(port) > 65535) {
    throw new Error('Port must be an integer between 1024 and 65535.');
  }
  const args = ['serve', '--hostname', host, '--port', String(port)];
  if (origin) args.push('--cors', validateOrigin(origin));
  return args;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: 'utf8', stdio: 'inherit', shell: process.platform === 'win32', ...options });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} exited with status ${result.status ?? 'unknown'}.`);
  return result.stdout?.trim() || '';
}

function stateFile(env = process.env) {
  return join(runtimeDirectory(env), 'runtime.json');
}

function readState(env = process.env) {
  const path = stateFile(env);
  if (!existsSync(path)) return null;
  try { return JSON.parse(readFileSync(path, 'utf8')); }
  catch { throw new Error('Runtime state is unreadable. Remove the runtime state file and run setup again.'); }
}

function writeState(state, env = process.env) {
  const directory = runtimeDirectory(env);
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  writeFileSync(stateFile(env), `${JSON.stringify(state, null, 2)}\n`, { mode: 0o600 });
}

function opencodeExecutable(env = process.env) {
  const prefix = run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['prefix', '-g'], { env, stdio: ['ignore', 'pipe', 'inherit'], shell: process.platform === 'win32' });
  return join(prefix, process.platform === 'win32' ? 'opencode.cmd' : 'bin/opencode');
}

async function waitForHealth(baseUrl, password, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const headers = password ? { Authorization: `Basic ${Buffer.from(`opencode:${password}`).toString('base64')}` } : {};
      const response = await fetch(`${baseUrl}/global/health`, { headers, signal: AbortSignal.timeout(1500) });
      if (response.ok) {
        const body = await response.json();
        if (body.healthy === true) return body;
      }
    } catch { /* The child may still be starting. */ }
    await new Promise(resolve => setTimeout(resolve, 350));
  }
  throw new Error('OpenCode did not become healthy within 15 seconds.');
}

async function main(argv = process.argv.slice(2)) {
  const { command, options } = parseArgs(argv);
  const env = process.env;
  const state = readState(env);
  if (command === 'help' || command === '--help' || command === '-h') {
    process.stdout.write('Usage: node scripts/agent-runtime.mjs <install|start|setup|status|stop> [--origin https://app.example]\n');
    return;
  }
  if (command === 'install' || command === 'setup') {
    run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['install', '--global', '--no-audit', '--no-fund', `${OPENCODE_PACKAGE}@${OPENCODE_VERSION}`]);
    process.stdout.write(`Installed ${OPENCODE_PACKAGE}@${OPENCODE_VERSION}.\n`);
    if (command === 'install') return;
  }
  if (command === 'status') {
    if (!state?.pid) { process.stdout.write('OpenCode runtime is not managed by AIrchitect.\n'); return; }
    try { process.kill(state.pid, 0); }
    catch { process.stdout.write('OpenCode runtime is stopped. Run start to launch it.\n'); return; }
    process.stdout.write(`OpenCode process is running (PID ${state.pid}) at ${state.baseUrl}.\n`);
    return;
  }
  if (command === 'stop') {
    if (!state?.pid) { process.stdout.write('No managed OpenCode process was found.\n'); return; }
    try { process.kill(state.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    process.stdout.write('Stop signal sent to the managed OpenCode process.\n');
    return;
  }
  if (command !== 'start' && command !== 'setup') throw new Error(`Unknown command: ${command}`);
  if (state?.pid) {
    try { process.kill(state.pid, 0); throw new Error('A managed OpenCode process is already running. Use status or stop first.'); }
    catch (error) { if (error.message.includes('already running')) throw error; }
  }
  const origin = options.origin ? validateOrigin(options.origin) : undefined;
  const host = options.host || DEFAULT_HOST;
  const port = Number(options.port || DEFAULT_PORT);
  const args = serverArguments({ host, port, origin });
  const password = env.AIRCHITECT_OPENCODE_PASSWORD || randomBytes(32).toString('base64url');
  const executable = opencodeExecutable(env);
  if (!existsSync(executable)) throw new Error(`OpenCode executable not found at ${executable}. Run install first.`);
  const child = spawn(executable, args, {
    detached: true,
    stdio: 'ignore',
    shell: process.platform === 'win32',
    env: { ...env, OPENCODE_SERVER_PASSWORD: password, OPENCODE_SERVER_USERNAME: 'opencode' },
  });
  child.unref();
  const baseUrl = `http://${host.includes(':') ? `[${host}]` : host}:${port}`;
  writeState({ pid: child.pid, baseUrl, version: OPENCODE_VERSION, startedAt: new Date().toISOString() }, env);
  try {
    const health = await waitForHealth(baseUrl, password);
    process.stdout.write(JSON.stringify({ status: 'ready', baseUrl, version: health.version, username: 'opencode', password }, null, 2) + '\n');
  } catch (error) {
    try { process.kill(child.pid, 'SIGTERM'); } catch { /* best effort cleanup */ }
    throw error;
  }
}

export function isMainModule(moduleUrl, invokedPath) {
  return Boolean(invokedPath) && fileURLToPath(moduleUrl) === resolve(invokedPath);
}

const isMain = isMainModule(import.meta.url, process.argv[1]);
if (isMain) main().catch(error => { process.stderr.write(`AIrchitect agent runtime: ${error.message}\n`); process.exitCode = 1; });
