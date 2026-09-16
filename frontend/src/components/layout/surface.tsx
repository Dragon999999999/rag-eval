import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface SurfaceProps extends React.HTMLAttributes<HTMLDivElement> {
  level?: "base" | "raised" | "overlay";
}

const Surface = React.forwardRef<HTMLDivElement, SurfaceProps>(
  ({ className, level = "base", ...props }, ref) => {
    const levelClasses = {
      base: "bg-surface",
      raised: "bg-surface-elevated",
      overlay: "bg-surface-elevated/95 backdrop-blur",
    };

    return (
      <div
        ref={ref}
        className={cn(
          "rounded-lg border border-border-default",
          levelClasses[level],
          className
        )}
        {...props}
      />
    );
  }
);
Surface.displayName = "Surface";

export { Surface };
