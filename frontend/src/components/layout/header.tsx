import { Link } from "react-router-dom";

export function Header() {
  return (
    <header className="bg-surface/95 supports-[backdrop-filter]:bg-surface/60 sticky top-0 z-50 border-b border-border-default backdrop-blur">
      <div className="flex h-12 items-center justify-between px-4">
        <div className="flex items-center gap-4">
          <Link to="/" className="text-lg font-semibold text-text-primary">
            RAG-Eval
          </Link>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-text-tertiary">v0.1.0</span>
        </div>
      </div>
    </header>
  );
}
