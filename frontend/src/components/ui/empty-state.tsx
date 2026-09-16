import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

function EmptyState({
  className,
  icon,
  title,
  description,
  action,
  ...props
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-border-default bg-surface p-8 text-center",
        className
      )}
      {...props}
    >
      {icon && <div className="mb-4 text-text-tertiary">{icon}</div>}
      <h3 className="mb-1 text-sm font-medium text-text-primary">{title}</h3>
      {description && (
        <p className="mb-4 max-w-sm text-sm text-text-tertiary">{description}</p>
      )}
      {action && <div>{action}</div>}
    </div>
  );
}

export { EmptyState };
