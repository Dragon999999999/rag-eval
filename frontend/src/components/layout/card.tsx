import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "elevated";
  padding?: "none" | "sm" | "md" | "lg";
}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = "default", padding = "md", ...props }, ref) => {
    const paddingClasses = {
      none: "",
      sm: "p-3",
      md: "p-4",
      lg: "p-6",
    };

    return (
      <div
        ref={ref}
        className={cn(
          "rounded-lg border",
          variant === "default" && "border-border-default bg-surface",
          variant === "elevated" &&
            "border-border-strong bg-surface-elevated shadow-lg",
          paddingClasses[padding],
          className
        )}
        {...props}
      />
    );
  }
);
Card.displayName = "Card";

export { Card };
