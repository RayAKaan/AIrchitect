export const DEFAULT_OPENCODE_URL = 'http://127.0.0.1:4096';

function normalizedBaseUrl(baseUrl: string): string {
  const url = new URL(baseUrl.trim());
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error('OpenCode URL must be an http(s) URL without embedded credentials, query or fragment.');
  }
  if (url.protocol === 'http:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) {
    throw new Error('Remote OpenCode servers must use HTTPS.');
  }
  return url.toString().replace(/\/+$/, '');
}

function assertLoopbackOpenCodeServer(baseUrl: string): void {
  const server = new URL(normalizedBaseUrl(baseUrl));
  if (!['localhost', '127.0.0.1', '[::1]'].includes(server.hostname)) {
    throw new Error('Sensitive credentials may only be sent to a loopback OpenCode server.');
  }
}

function authHeaders(username: string, password: string): HeadersInit {
  if (!password) return {};
  return { Authorization: `Basic ${btoa(`${username || 'opencode'}:${password}`)}` };
}

async function request<T>(baseUrl: string, path: string, init: RequestInit = {}, username = 'opencode', password = ''): Promise<T> {
  const response = await fetch(`${normalizedBaseUrl(baseUrl)}${path}`, {
    ...init,
    headers: { Accept: 'application/json', ...authHeaders(username, password), ...init.headers },
    signal: init.signal ?? AbortSignal.timeout(15000),
  });
  if (!response.ok) {
    if (response.status === 401) throw new Error('OpenCode authentication failed. Check the local server password.');
    if (response.status === 403) throw new Error('OpenCode rejected this browser origin or request.');
    throw new Error(`OpenCode request failed (${response.status}).`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type OpenCodeHealth = { healthy: boolean; version: string };
export type OpenCodeSession = { id: string; title?: string };
export type OpenCodeModel = { id: string; name?: string; [key: string]: unknown };
export type OpenCodeProvider = { id: string; name: string; models: Record<string, OpenCodeModel>; [key: string]: unknown };
export type OpenCodeProviderCatalog = { all: OpenCodeProvider[]; default: Record<string, string>; connected: string[] };
export type OpenCodeModelSelection = { providerID: string; modelID: string };

export function checkOpenCodeHealth(baseUrl: string, username: string, password: string): Promise<OpenCodeHealth> {
  return request<OpenCodeHealth>(baseUrl, '/global/health', {}, username, password);
}

export function registerOpenCodeMcpServer(
  baseUrl: string,
  mcpUrl: string,
  sessionToken: string,
  username: string,
  password: string,
): Promise<unknown> {
  assertLoopbackOpenCodeServer(baseUrl);
  if (!sessionToken.trim()) throw new Error('An active AIrchitect session is required to connect architectural tools.');
  const endpoint = new URL(mcpUrl);
  if (!['http:', 'https:'].includes(endpoint.protocol)) throw new Error('AIrchitect MCP endpoint must use HTTP or HTTPS.');
  return request(baseUrl, '/mcp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: 'airchitect',
      config: {
        type: 'remote',
        url: endpoint.toString(),
        oauth: false,
        enabled: true,
        headers: { Authorization: `Bearer ${sessionToken}` },
      },
    }),
  }, username, password);
}

export function resolveMcpEndpoint(apiBaseUrl: string, origin = window.location.origin): string {
  const base = apiBaseUrl.trim().replace(/\/+$/, '');
  if (/^https?:\/\//i.test(base)) return new URL(`${base}/mcp`).toString();
  return new URL(`${base.startsWith('/') ? base : `/${base}`}/mcp`, origin).toString();
}

export function listOpenCodeProviders(baseUrl: string, username: string, password: string): Promise<OpenCodeProviderCatalog> {
  return request<OpenCodeProviderCatalog>(baseUrl, '/provider', {}, username, password);
}

/** Sends the API key directly to the user's OpenCode server; AIrchitect never persists it. */
export function setOpenCodeProviderKey(baseUrl: string, providerId: string, apiKey: string, username: string, password: string): Promise<boolean> {
  if (!providerId.trim() || !apiKey.trim()) throw new Error('A provider and API key are required.');
  assertLoopbackOpenCodeServer(baseUrl);
  return request<boolean>(baseUrl, `/auth/${encodeURIComponent(providerId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: 'api', key: apiKey }),
  }, username, password);
}

export function createOpenCodeSession(baseUrl: string, title: string, username: string, password: string): Promise<OpenCodeSession> {
  return request<OpenCodeSession>(baseUrl, '/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  }, username, password);
}

export function abortOpenCodeSession(baseUrl: string, sessionId: string, username: string, password: string): Promise<boolean> {
  return request<boolean>(baseUrl, `/session/${encodeURIComponent(sessionId)}/abort`, { method: 'POST' }, username, password);
}

export function extractOpenCodeResponseText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value !== 'object' || value === null) return String(value ?? '');
  const parts = 'parts' in value && Array.isArray(value.parts) ? value.parts : [];
  const textParts = parts
    .filter((part): part is { type: string; text: string } =>
      typeof part === 'object' && part !== null && 'type' in part && part.type === 'text' && 'text' in part && typeof part.text === 'string')
    .map(part => part.text.trim())
    .filter(Boolean);
  if (textParts.length) return textParts.join('\\n\\n');
  const toolParts = parts.filter((part): part is Record<string, unknown> =>
    typeof part === 'object' && part !== null && 'type' in part && part.type === 'tool');
  const toolSummaries = toolParts.map(part => {
    const state = typeof part.state === 'object' && part.state !== null ? part.state as Record<string, unknown> : {};
    const title = typeof state.title === 'string' ? state.title : typeof part.tool === 'string' ? part.tool : 'Architectural tool';
    const output = typeof state.output === 'string' ? state.output : typeof state.status === 'string' ? state.status : 'completed';
    return `${title}: ${output}`;
  });
  if (toolSummaries.length) return toolSummaries.join('\\n');
  return JSON.stringify(value, null, 2);
}

export function sendOpenCodePrompt(baseUrl: string, sessionId: string, text: string, username: string, password: string, model?: OpenCodeModelSelection, system?: string, tools?: Record<string, boolean>, signal?: AbortSignal): Promise<unknown> {
  return request(baseUrl, `/session/${encodeURIComponent(sessionId)}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...(model ? { model } : {}), ...(system ? { system } : {}), ...(tools ? { tools } : {}), parts: [{ type: 'text', text }] }),
    signal: signal ?? AbortSignal.timeout(300000),
  }, username, password);
}
