import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Header } from "./header";
import { Sidebar } from "./sidebar";
import { ActiveRunIndicator } from "@/features/tests/components/active-run-indicator";

/**
 * Main application shell containing:
 * - Persistent sidebar navigation (desktop)
 * - Collapsible mobile menu overlay
 * - Header with mobile menu trigger
 * - Main content area with Outlet
 *
 * All product pages render inside this shell.
 */
export function AppShell() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar - hidden on mobile */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          {/* Backdrop */}
          <div
            className="bg-background/80 fixed inset-0 backdrop-blur-sm"
            onClick={() => {
              setMobileMenuOpen(false);
            }}
            aria-hidden="true"
          />

          {/* Slide-out sidebar */}
          <div className="relative flex h-full w-64 flex-col bg-surface shadow-xl">
            <div className="flex h-12 items-center gap-2 border-b border-border-default px-4">
              <div className="flex h-6 w-6 items-center justify-center rounded-sm bg-accent text-xs font-bold text-white">
                R
              </div>
              <span className="text-sm font-semibold text-text-primary">RAG-Eval</span>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              <Sidebar />
            </div>
          </div>
        </div>
      )}

      {/* Main content area */}
      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          onMobileMenuToggle={() => {
            setMobileMenuOpen(true);
          }}
        />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
      <ActiveRunIndicator />
    </div>
  );
}
