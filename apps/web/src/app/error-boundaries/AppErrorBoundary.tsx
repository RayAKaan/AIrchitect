import React, { ErrorInfo, ReactNode } from 'react';

type Props = { children: ReactNode };
type State = { hasError: boolean; message: string };

export default class AppErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, message: '' };

  static getDerivedStateFromError(error: unknown): State {
    return { hasError: true, message: error instanceof Error ? error.message : 'Unexpected application error' };
  }

  componentDidCatch(error: unknown, info: ErrorInfo) {
    console.error('AIrchitect application error', { error, componentStack: info.componentStack });
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
