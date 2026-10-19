export type ApiClient = {
  request<T>(path: string, init?: RequestInit): Promise<T>;
};

export function createApiClient(baseUrl: string, getToken: () => string | null): ApiClient {
  return {
    async request<T>(path: string, init: RequestInit = {}) {
      const token = getToken();
      const response = await fetch(baseUrl + path, {
        ...init,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...init.headers,
        },
      });
      const data = await response.json().catch(() => ({ detail: `Request failed (${response.status})` }));
      if (!response.ok) throw new Error(data.detail || 'Request failed');
      return data as T;
    },
  };
}
