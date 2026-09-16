import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface SectionHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

function SectionHeader({
  className,
  title,
  description,
  action,
  ...props
}: SectionHeaderProps) {
  return (
    <div className={cn("mb-4 flex items-center justify-between", className)} {...props}>
      <div className="space-y-1">
        <h2 className="text-base font-medium text-text-primary">{title}</h2>
        {description && <p className="text-sm text-text-tertiary">{description}</p>}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  );
}

export { SectionHeader };
