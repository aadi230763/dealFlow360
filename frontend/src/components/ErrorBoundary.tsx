import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertCircleIcon } from "@/components/icons";
import { Button } from "@/components/Button";

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled UI error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-canvas px-4 text-center">
          <AlertCircleIcon width={28} height={28} className="text-danger" />
          <h1 className="text-lg font-semibold text-ink">Something went wrong</h1>
          <p className="max-w-sm text-sm text-ink-muted">
            This screen hit an unexpected error. Your data is safe — reloading usually fixes it.
          </p>
          <Button variant="primary" onClick={() => window.location.reload()}>
            Reload
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
