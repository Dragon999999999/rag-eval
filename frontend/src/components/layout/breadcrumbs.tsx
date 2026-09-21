import { Link, useLocation } from "react-router-dom";
import { ChevronRight } from "lucide-react";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbsProps {
  items?: BreadcrumbItem[];
  className?: string;
}

/**
 * Breadcrumb navigation component.
 *
 * If items are provided, renders them directly.
 * If no items, automatically generates breadcrumbs from current route.
 *
 * Only shows breadcrumbs for nested routes (not top-level pages).
 */
export function Breadcrumbs({ items, className }: BreadcrumbsProps) {
  const location = useLocation();

  // Use provided items or generate from route
  const breadcrumbItems = items ?? generateBreadcrumbs(location.pathname);

  // Don't render if no items or only one item (top-level)
  if (breadcrumbItems.length <= 1) {
    return null;
  }

  return (
    <nav aria-label="Breadcrumb" className={className}>
      <ol className="flex items-center gap-1 text-sm text-text-tertiary">
        {breadcrumbItems.map((item, index) => {
          const isLast = index === breadcrumbItems.length - 1;

          return (
            <li key={item.href || item.label} className="flex items-center gap-1">
              {index > 0 && (
                <ChevronRight className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
              )}
              {isLast ? (
                <span aria-current="page" className="text-text-secondary">
                  {item.label}
                </span>
              ) : (
                <Link
                  to={item.href || "#"}
                  className="transition-colors hover:text-text-secondary"
                >
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/**
 * Generate breadcrumbs from pathname.
 * Example: /benchmarks/123 → [{label: "Benchmarks", href: "/benchmarks"}, {label: "QKD Benchmark"}]
 */
function generateBreadcrumbs(pathname: string): BreadcrumbItem[] {
  const segments = pathname.split("/").filter(Boolean);

  if (segments.length === 0) {
    return [{ label: "Dashboard", href: "/" }];
  }

  // Map known routes to labels
  const routeLabels: Record<string, string> = {
    targets: "Targets",
    datasets: "Benchmarks",
    benchmarks: "Benchmarks",
    tests: "Tests",
    runs: "Runs",
    results: "Results",
    settings: "Settings",
    "design-system": "Design System",
  };

  const breadcrumbs: BreadcrumbItem[] = [];

  // Build hierarchy
  let path = "";
  for (let i = 0; i < segments.length; i++) {
    const segment = segments[i] || "";
    path += `/${segment}`;

    // Use route label or segment value
    const label = routeLabels[segment] || segment;

    // For ID segments (not in routeLabels), don't add href
    if (i === segments.length - 1 && !routeLabels[segment]) {
      // Last segment is likely an ID - make it current page without link
      breadcrumbs.push({ label: segment || "", href: undefined });
    } else if (i === segments.length - 1 && routeLabels[segment]) {
      // Last segment is a known route
      breadcrumbs.push({ label, href: path });
    } else {
      // Intermediate segment
      breadcrumbs.push({ label, href: path });
    }
  }

  return breadcrumbs;
}
