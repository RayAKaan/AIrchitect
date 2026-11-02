import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { parseArgs, serverArguments, validateOrigin, runtimeDirectory, isMainModule, OPENCODE_PACKAGE, OPENCODE_VERSION } from './agent-runtime.mjs';

describe('AIrchitect OpenCode runtime bootstrap', () => {
  it('pins the audited OpenCode package version', () => {
    assert.equal(OPENCODE_PACKAGE, 'opencode-ai');
    assert.match(OPENCODE_VERSION, /^1\.19\.\d+$/);
  });

  it('parses explicit options without shell expansion', () => {
    assert.deepEqual(parseArgs(['start', '--port', '4096']), { command: 'start', options: { port: '4096' } });
    assert.throws(() => parseArgs(['start', '--origin']), /Missing value/);
    assert.throws(() => parseArgs(['start', '&& rm -rf']), /Unexpected argument/);
  });

  it('only binds to loopback and validates port bounds', () => {
    assert.deepEqual(serverArguments({ port: 4096 }), ['serve', '--hostname', '127.0.0.1', '--port', '4096']);
    assert.throws(() => serverArguments({ host: '0.0.0.0' }), /loopback/);
    assert.throws(() => serverArguments({ port: 80 }), /Port must/);
    assert.throws(() => serverArguments({ port: 65536 }), /Port must/);
  });

  it('allows localhost HTTP origins and requires HTTPS for remote origins', () => {
    assert.equal(validateOrigin('http://localhost:5173'), 'http://localhost:5173');
    assert.equal(validateOrigin('https://app.example.com'), 'https://app.example.com');
    assert.throws(() => validateOrigin('http://app.example.com'), /HTTPS/);
    assert.throws(() => validateOrigin('https://app.example.com/path'), /Origin must/);
  });

  it('recognizes direct CLI execution when invoked with a relative script path', () => {
    const moduleUrl = new URL('./agent-runtime.mjs', import.meta.url).href;
    assert.equal(isMainModule(moduleUrl, 'scripts/agent-runtime.mjs'), true);
    assert.equal(isMainModule(moduleUrl, undefined), false);
    assert.equal(isMainModule(moduleUrl, 'scripts/other-script.mjs'), false);
  });

  it('stores runtime metadata in the platform user configuration directory', () => {
    assert.match(runtimeDirectory({ XDG_CONFIG_HOME: '/tmp/config' }, '/home/test'), /^\/tmp\/config\/airchitect/);
  });
});
