import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  action?: React.ReactNode;
}

const Panel = React.forwardRef<HTMLDivElement, PanelProps>(
  ({ className, title, action, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn("rounded-lg border border-border-default bg-surface", className)}
        {...props}
      >
        {(title || action) && (
          <div className="flex items-center justify-between border-b border-border-default px-4 py-3">
            {title && (
              <h3 className="text-sm font-medium text-text-primary">{title}</h3>
            )}
            {action && <div>{action}</div>}
          </div>
        )}
        <div className="p-4">{children}</div>
      </div>
    );
  }
);
Panel.displayName = "Panel";

export { Panel };
