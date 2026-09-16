"use client";

import * as React from "react";
import * as SwitchPrimitives from "@radix-ui/react-switch";
import { cn } from "@/lib/utils/cn";

export interface SwitchProps extends React.ComponentPropsWithoutRef<
  typeof SwitchPrimitives.Root
> {
  label?: string;
}

const Switch = React.forwardRef<
  React.ElementRef<typeof SwitchPrimitives.Root>,
  SwitchProps
>(({ className, label, ...props }, ref) => {
  return (
    <div className="flex items-center gap-2">
      <SwitchPrimitives.Root
        ref={ref}
        className={cn(
          "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-accent data-[state=unchecked]:bg-surface-elevated",
          className
        )}
        {...props}
      >
        <SwitchPrimitives.Thumb
          className={cn(
            "pointer-events-none block h-4 w-4 rounded-full bg-text-primary shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0"
          )}
        />
      </SwitchPrimitives.Root>
      {label && (
        <label
          className="cursor-pointer text-sm text-text-secondary"
          onClick={() => props.onCheckedChange?.(!props.checked)}
        >
          {label}
        </label>
      )}
    </div>
  );
});
Switch.displayName = SwitchPrimitives.Root.displayName;

export { Switch };
