import { MobileMenuTrigger } from "./sidebar";

interface HeaderProps {
  onMobileMenuToggle: () => void;
}

/**
 * Application header with mobile menu trigger.
 *
 * On desktop: minimal header with optional actions
 * On mobile: hamburger menu trigger + app label
 */
export function Header({ onMobileMenuToggle }: HeaderProps) {
  return (
    <header className="bg-background/95 supports-[backdrop-filter]:bg-background/60 sticky top-0 z-40 border-b border-border-default backdrop-blur">
      <div className="flex h-12 items-center gap-4 px-4">
        {/* Mobile menu trigger - hidden on desktop */}
        <div className="flex lg:hidden">
          <MobileMenuTrigger onClick={onMobileMenuToggle} />
        </div>

        {/* Page title area - can be customized per page */}
        <div className="flex-1" />

        {/* Optional header actions */}
        <div className="flex items-center gap-4">
          <span className="hidden text-xs text-text-tertiary sm:inline">v0.2.0</span>
        </div>
      </div>
    </header>
  );
}
