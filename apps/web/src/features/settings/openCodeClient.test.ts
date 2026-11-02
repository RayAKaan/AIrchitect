import { afterEach, describe, expect, it, vi } from 'vitest';
import { checkOpenCodeHealth, createOpenCodeSession, listOpenCodeProviders, registerOpenCodeMcpServer, resolveMcpEndpoint, sendOpenCodePrompt, setOpenCodeProviderKey } from './openCodeClient';

describe('openCodeClient', () => {
  afterEach(() => vi.restoreAllMocks());

  it('checks health and discovers configured providers', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({ healthy: true, version: '1.0.0' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ all: [], default: {}, connected: ['openai'] }), { status: 200 }));
    await expect(checkOpenCodeHealth('http://127.0.0.1:4096', 'opencode', '')).resolves.toEqual({ healthy: true, version: '1.0.0' });
    await expect(listOpenCodeProviders('http://127.0.0.1:4096', 'opencode', '')).resolves.toMatchObject({ connected: ['openai'] });
    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://127.0.0.1:4096/global/health', expect.objectContaining({ headers: { Accept: 'application/json' } }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://127.0.0.1:4096/provider', expect.any(Object));
  });

  it('sends provider credentials directly to OpenCode', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('true', { status: 200 }));
    await expect(setOpenCodeProviderKey('http://127.0.0.1:4096', 'anthropic', 'secret-key', 'opencode', 'pw')).resolves.toBe(true);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('http://127.0.0.1:4096/auth/anthropic');
    expect(init?.method).toBe('PUT');
    expect(init?.body).toBe(JSON.stringify({ type: 'api', key: 'secret-key' }));
  });

  it('creates sessions and sends a model-specific prompt', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'ses_1', title: 'AIrchitect' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ info: { id: 'msg_1' }, parts: [] }), { status: 200 }));
    const session = await createOpenCodeSession('http://127.0.0.1:4096/', 'AIrchitect', 'opencode', 'secret');
    await sendOpenCodePrompt('http://127.0.0.1:4096/', session.id, 'Design a house.', 'opencode', 'secret', { providerID: 'anthropic', modelID: 'claude-sonnet' }, 'Architectural system policy', { bash: false, airchitect_get_project_context: true });
    expect(session.id).toBe('ses_1');
    const second = fetchMock.mock.calls[1][1] as RequestInit;
    expect(JSON.parse(second.body as string)).toMatchObject({ model: { providerID: 'anthropic', modelID: 'claude-sonnet' }, system: 'Architectural system policy', tools: { bash: false, airchitect_get_project_context: true }, parts: [{ type: 'text', text: 'Design a house.' }] });
    expect(second.headers).toMatchObject({ Authorization: expect.stringContaining('Basic ') });
  });

  it('rejects insecure remote URLs and surfaces auth errors', async () => {
    await expect(checkOpenCodeHealth('http://192.168.1.20:4096', 'opencode', '')).rejects.toThrow('Remote OpenCode servers must use HTTPS.');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 401 }));
    await expect(checkOpenCodeHealth('http://127.0.0.1:4096', 'opencode', '')).rejects.toThrow('authentication failed');
  });

  it('registers the authenticated architectural MCP bridge only with a local OpenCode runtime', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ status: 'connected' }), { status: 200 }));
    await registerOpenCodeMcpServer('http://127.0.0.1:4096', 'https://app.example.com/api/v1/mcp', 'session-token', 'opencode', 'pw');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('http://127.0.0.1:4096/mcp');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toMatchObject({
      name: 'airchitect',
      config: {
        type: 'remote',
        url: 'https://app.example.com/api/v1/mcp',
        oauth: false,
        enabled: true,
        headers: { Authorization: 'Bearer session-token' },
      },
    });
    expect(() => registerOpenCodeMcpServer('https://agent.example.com', 'https://app.example.com/api/v1/mcp', 'session-token', 'opencode', 'pw'))
      .toThrow('loopback OpenCode server');
    expect(resolveMcpEndpoint('/api/v1', 'https://app.example.com')).toBe('https://app.example.com/api/v1/mcp');
    expect(resolveMcpEndpoint('https://api.example.com/api/v1', 'https://app.example.com')).toBe('https://api.example.com/api/v1/mcp');
  });

  it('surfaces provider server errors', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 503 }));
    await expect(checkOpenCodeHealth('http://127.0.0.1:4096', 'opencode', '')).rejects.toThrow('OpenCode request failed (503).');
  });
});
