export type ClientTelemetryEvent = {
  event: string;
  message?: string;
  stack?: string;
  component_stack?: string | null;
  route?: string;
  request_id?: string | null;
};

const REQUEST_ID_KEY = 'airchitect.request_id';

export function getClientRequestId(): string | null {
  return window.sessionStorage.getItem(REQUEST_ID_KEY);
}

export function recordClientRequestId(requestId: string | null): void {
  if (requestId) window.sessionStorage.setItem(REQUEST_ID_KEY, requestId);
}

export function reportClientError(event: ClientTelemetryEvent): void {
  const payload = JSON.stringify({
    ...event,
    request_id: event.request_id ?? getClientRequestId(),
    route: event.route ?? window.location.pathname,
    timestamp: new Date().toISOString(),
  });
  console.error('[observability]', payload);
}
