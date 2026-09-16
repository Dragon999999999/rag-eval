import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface PageHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}

function PageHeader({
  className,
  title,
  description,
  actions,
  ...props
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-4 border-b border-border-default px-6 py-4 md:flex-row md:items-center md:justify-between",
        className
      )}
      {...props}
    >
      <div className="space-y-1">
        <h1 className="text-xl font-semibold text-text-primary">{title}</h1>
        {description && <p className="text-sm text-text-tertiary">{description}</p>}
      </div>
      {actions && <div className="flex-shrink-0">{actions}</div>}
    </div>
  );
}

export { PageHeader };
