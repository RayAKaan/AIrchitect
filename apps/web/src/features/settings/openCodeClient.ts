export const DEFAULT_OPENCODE_URL = 'http://127.0.0.1:4096';

function normalizedBaseUrl(baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, '');
}

function authHeaders(username: string, password: string): HeadersInit {
  if (!password) return {};
  return { Authorization: `Basic ${btoa(`${username || 'opencode'}:${password}`)}` };
}

async function request<T>(baseUrl: string, path: string, init: RequestInit = {}, username = 'opencode', password = ''): Promise<T> {
  const response = await fetch(`${normalizedBaseUrl(baseUrl)}${path}`, {
    ...init,
    headers: { Accept: 'application/json', ...authHeaders(username, password), ...init.headers },
  });
  if (!response.ok) throw new Error(`OpenCode request failed (${response.status}).`);
  return response.json() as Promise<T>;
}

export type OpenCodeHealth = { healthy: boolean; version: string };
export type OpenCodeSession = { id: string; title?: string };

export function checkOpenCodeHealth(baseUrl: string, username: string, password: string): Promise<OpenCodeHealth> {
  return request<OpenCodeHealth>(baseUrl, '/global/health', {}, username, password);
}

export async function createOpenCodeSession(baseUrl: string, title: string, username: string, password: string): Promise<OpenCodeSession> {
  return request<OpenCodeSession>(baseUrl, '/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  }, username, password);
}

export async function sendOpenCodePrompt(
  baseUrl: string,
  sessionId: string,
  text: string,
  username: string,
  password: string,
): Promise<unknown> {
  return request(baseUrl, `/session/${encodeURIComponent(sessionId)}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parts: [{ type: 'text', text }] }),
  }, username, password);
}
