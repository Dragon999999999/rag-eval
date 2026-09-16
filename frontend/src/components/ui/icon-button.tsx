import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: React.ReactNode;
  variant?: "ghost" | "secondary";
  size?: "sm" | "md" | "lg";
}

const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ className, icon, variant = "ghost", size = "md", ...props }, ref) => {
    const sizeClasses = {
      sm: "h-8 w-8",
      md: "h-10 w-10",
      lg: "h-12 w-12",
    };

    const variantClasses = {
      ghost: "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
      secondary:
        "bg-surface-elevated text-text-primary border border-border-default hover:bg-surface-hover",
    };

    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50",
          sizeClasses[size],
          variantClasses[variant],
          className
        )}
        {...props}
      >
        <span className="h-4 w-4">{icon}</span>
      </button>
    );
  }
);
IconButton.displayName = "IconButton";

export { IconButton };
