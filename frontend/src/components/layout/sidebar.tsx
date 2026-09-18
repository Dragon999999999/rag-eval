import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils/cn";
import { PRIMARY_NAVIGATION, SECONDARY_NAVIGATION } from "@/config/routes";
import { getIcon, type IconName } from "@/lib/icons";

/**
 * Main application sidebar with primary and secondary navigation.
 *
 * Features:
 * - Active route detection with path matching
 * - Icon + label navigation items
 * - Subtle active state with accent background
 * - Responsive behavior (collapses on narrow screens)
 * - Semantic HTML nav with proper accessibility
 */
export function Sidebar() {
  return (
    <aside className="flex h-full w-56 flex-col border-r border-border-default bg-surface">
      {/* Branding */}
      <div className="flex h-12 items-center gap-2 border-b border-border-default px-4">
        <div className="flex h-6 w-6 items-center justify-center rounded-sm bg-accent text-xs font-bold text-white">
          R
        </div>
        <span className="text-sm font-semibold text-text-primary">RAG-Eval</span>
      </div>

      {/* Primary Navigation */}
      <nav
        className="flex-1 space-y-1 overflow-y-auto p-3"
        aria-label="Primary navigation"
      >
        {PRIMARY_NAVIGATION.map((item) => (
          <SidebarNavItem
            key={item.path}
            path={item.path}
            icon={item.icon}
            label={item.label}
          />
        ))}
      </nav>

      {/* Secondary Navigation */}
      <nav
        className="space-y-1 border-t border-border-default p-3"
        aria-label="Secondary navigation"
      >
        {SECONDARY_NAVIGATION.map((item) => (
          <SidebarNavItem
            key={item.path}
            path={item.path}
            icon={item.icon}
            label={item.label}
          />
        ))}
      </nav>
    </aside>
  );
}

interface SidebarNavItemProps {
  path: string;
  icon: IconName;
  label: string;
}

function SidebarNavItem({ path, icon, label }: SidebarNavItemProps) {
  const Icon = getIcon(icon);

  return (
    <NavLink
      to={path}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
          isActive
            ? "bg-accent-subtle text-text-primary"
            : "text-text-secondary hover:bg-surface-hover hover:text-text-primary"
        )
      }
    >
      <Icon className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </NavLink>
  );
}

/**
 * Mobile menu trigger button (shown on narrow screens).
 */
export function MobileMenuTrigger({
  onClick,
  className,
}: {
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex h-8 w-8 items-center justify-center rounded-md text-text-secondary hover:bg-surface-hover hover:text-text-primary",
        className
      )}
      aria-label="Toggle navigation menu"
    >
      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M4 6h16M4 12h16M4 18h16"
        />
      </svg>
    </button>
  );
}
