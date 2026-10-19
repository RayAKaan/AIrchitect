import { recordClientRequestId, reportClientError } from '../../shared/observability/clientTelemetry';

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
      const requestId = response.headers.get('X-Request-Id');
      recordClientRequestId(requestId);
      const data = await response.json().catch(() => ({ detail: `Request failed (${response.status})` }));
      if (!response.ok) {
        const message = typeof data?.detail === 'string' ? data.detail : data?.error?.message || 'Request failed';
        reportClientError({ event: 'api.request_failed', message, request_id: requestId });
        throw new Error(message);
      }
      return data as T;
    },
  };
}
