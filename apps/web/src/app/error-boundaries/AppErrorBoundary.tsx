import React, { ErrorInfo, ReactNode } from 'react';
import { reportClientError } from '../../shared/observability/clientTelemetry';

type Props = { children: ReactNode };
type State = { hasError: boolean; message: string };

export default class AppErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, message: '' };

  static getDerivedStateFromError(error: unknown): State {
    return { hasError: true, message: error instanceof Error ? error.message : 'Unexpected application error' };
  }

  componentDidCatch(error: unknown, info: ErrorInfo) {
    const message = error instanceof Error ? error.message : 'Unexpected application error';
    reportClientError({
      event: 'frontend.error_boundary',
      message,
      stack: error instanceof Error ? error.stack : undefined,
      component_stack: info.componentStack,
    });
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <main role="alert" style={{ padding: 32, fontFamily: 'system-ui, sans-serif' }}>
        <h1>AIrchitect could not render this workspace.</h1>
        <p>{this.state.message}</p>
        <button type="button" onClick={() => window.location.reload()}>Reload workspace</button>
      </main>
    );
  }
}
