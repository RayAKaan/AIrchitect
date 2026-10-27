import { afterEach, describe, expect, it, vi } from 'vitest';
import { checkOpenCodeHealth, createOpenCodeSession, sendOpenCodePrompt } from './openCodeClient';

describe('openCodeClient', () => {
  afterEach(() => vi.restoreAllMocks());

  it('checks server health', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ healthy: true, version: '1.0.0' }), { status: 200 }));
    await expect(checkOpenCodeHealth('http://127.0.0.1:4096', 'opencode', '')).resolves.toEqual({ healthy: true, version: '1.0.0' });
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:4096/global/health', { headers: { Accept: 'application/json' } });
  });

  it('creates a session and sends a text prompt', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'ses_1', title: 'AIrchitect' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ info: { id: 'msg_1' }, parts: [] }), { status: 200 }));

    const session = await createOpenCodeSession('http://127.0.0.1:4096/', 'AIrchitect', 'opencode', 'secret');
    await sendOpenCodePrompt('http://127.0.0.1:4096/', session.id, 'Design a house.', 'opencode', 'secret');

    expect(session.id).toBe('ses_1');
    expect(fetchMock).toHaveBeenNthCalledWith(1, 'http://127.0.0.1:4096/session', expect.objectContaining({ method: 'POST' }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://127.0.0.1:4096/session/ses_1/message', expect.objectContaining({ method: 'POST' }));
    const second = fetchMock.mock.calls[1][1] as RequestInit;
    expect(second.body).toContain('Design a house.');
    expect(second.headers).toMatchObject({ Authorization: expect.stringContaining('Basic ') });
  });

  it('surfaces non-success responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 503 }));
    await expect(checkOpenCodeHealth('http://127.0.0.1:4096', 'opencode', '')).rejects.toThrow('OpenCode request failed (503).');
  });
});
