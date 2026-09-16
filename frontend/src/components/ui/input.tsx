import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  leftElement?: React.ReactNode;
  rightElement?: React.ReactNode;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, leftElement, rightElement, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="mb-1.5 block text-sm font-medium text-text-secondary">
            {label}
          </label>
        )}
        <div className="relative">
          {leftElement && (
            <div className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary">
              {leftElement}
            </div>
          )}
          <input
            ref={ref}
            className={cn(
              "w-full rounded-md border border-border-default bg-surface px-3 py-2 text-sm text-text-primary transition-colors placeholder:text-text-tertiary focus-visible:border-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50",
              leftElement && "pl-10",
              rightElement && "pr-10",
              error && "border-error focus-visible:ring-error",
              className
            )}
            {...props}
          />
          {rightElement && (
            <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary">
              {rightElement}
            </div>
          )}
        </div>
        {error && <p className="mt-1.5 text-xs text-error">{error}</p>}
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };
