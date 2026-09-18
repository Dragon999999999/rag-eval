import * as React from "react";
import { cn } from "@/lib/utils/cn";
import { Breadcrumbs, type BreadcrumbItem } from "./breadcrumbs";

export interface PageLayoutProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * Standard page layout wrapper.
 * Provides consistent padding and max-width for all pages.
 */
export function PageLayout({ children, className }: PageLayoutProps) {
  return (
    <div className={cn("flex min-h-full flex-col", className)}>
      <main className="flex-1">{children}</main>
    </div>
  );
}

export interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: React.ReactNode;
  className?: string;
}

/**
 * Standard page header with breadcrumbs, title, description, and actions.
 *
 * Usage:
 * <PageHeader
 *   title="Targets"
 *   description="Connect RAG or LLM systems to evaluate."
 *   actions={<Button>Add Target</Button>}
 * />
 */
export function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 border-b border-border-default px-6 py-6",
        className
      )}
    >
      {/* Breadcrumbs - only shown when useful */}
      {breadcrumbs && <Breadcrumbs items={breadcrumbs} />}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold text-text-primary">{title}</h1>
          {description && <p className="text-sm text-text-tertiary">{description}</p>}
        </div>
        {actions && <div className="flex-shrink-0">{actions}</div>}
      </div>
    </div>
  );
}

export interface PageContentProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * Standard page content area.
 * Use for the main content below the page header.
 */
export function PageContent({ children, className }: PageContentProps) {
  return <div className={cn("flex-1 px-6 py-6", className)}>{children}</div>;
}

/**
 * Combined page structure helper.
 *
 * Usage:
 * <Page>
 *   <Page.Header
 *     title="Targets"
 *     description="..."
 *     actions={...}
 *   />
 *   <Page.Content>
 *     ...content...
 *   </Page.Content>
 * </Page>
 */
export const Page = Object.assign(PageLayout, {
  Header: PageHeader,
  Content: PageContent,
});
