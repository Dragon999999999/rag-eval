import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils/cn";

const statusBadgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      status: {
        success: "bg-success-bg text-success",
        warning: "bg-warning-bg text-warning",
        error: "bg-error-bg text-error",
        info: "bg-info-bg text-info",
        neutral: "bg-surface-elevated text-text-secondary border border-border-default",
      },
    },
    defaultVariants: {
      status: "neutral",
    },
  }
);

export interface StatusBadgeProps
  extends
    React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof statusBadgeVariants> {
  status?: "success" | "warning" | "error" | "info" | "neutral";
  showDot?: boolean;
}

const statusColors = {
  success: "bg-success",
  warning: "bg-warning",
  error: "bg-error",
  info: "bg-info",
  neutral: "bg-text-tertiary",
};

function StatusBadge({
  className,
  status = "neutral",
  showDot = true,
  children,
  ...props
}: StatusBadgeProps) {
  return (
    <span className={cn(statusBadgeVariants({ status }), className)} {...props}>
      {showDot && (
        <span className={cn("h-1.5 w-1.5 rounded-full", statusColors[status])} />
      )}
      {children}
    </span>
  );
}

export { StatusBadge, statusBadgeVariants };
