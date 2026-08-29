import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Catches rendering errors in its subtree so one broken panel (e.g. a
 * malformed API response the code didn't expect) shows an inline fallback
 * instead of blanking the whole page. Class component because React only
 * supports error boundaries via componentDidCatch/getDerivedStateFromError
 * — there is no hook equivalent.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, info);
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);

    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        <p className="font-medium">Something went wrong rendering this section.</p>
        <p className="mt-1 text-red-600">{error.message}</p>
        <button
          type="button"
          onClick={this.reset}
          className="mt-3 rounded-md border border-red-300 bg-white px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
        >
          Try again
        </button>
      </div>
    );
  }
}
