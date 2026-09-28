import { Component, type ReactNode } from "react";

/**
 * If any component throws while rendering, React unmounts the whole tree and the
 * page goes blank. This catches the error and shows it instead.
 * (Error boundaries must be class components; there is no hook equivalent.)
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("Jarvis UI crashed:", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="crash">
        <h2>Something went wrong in the Jarvis UI.</h2>
        <pre>{this.state.error.message}</pre>
        <button onClick={() => location.reload()}>Reload</button>
      </div>
    );
  }
}
