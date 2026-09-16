"use client";

import * as React from "react";
import * as RadioGroupPrimitive from "@radix-ui/react-radio-group";
import { Circle } from "lucide-react";
import { cn } from "@/lib/utils/cn";

export interface RadioProps extends React.ComponentPropsWithoutRef<
  typeof RadioGroupPrimitive.Item
> {
  label?: string;
}

const Radio = React.forwardRef<
  React.ElementRef<typeof RadioGroupPrimitive.Item>,
  RadioProps
>(({ className, label, ...props }, ref) => {
  return (
    <div className="flex items-center gap-2">
      <RadioGroupPrimitive.Item
        ref={ref}
        className={cn(
          "peer h-4 w-4 shrink-0 rounded-full border border-border-default bg-surface ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-accent",
          className
        )}
        {...props}
      >
        <RadioGroupPrimitive.Indicator className="flex items-center justify-center">
          <Circle className="h-2.5 w-2.5 fill-accent" />
        </RadioGroupPrimitive.Indicator>
      </RadioGroupPrimitive.Item>
      {label && <label className="text-sm text-text-secondary">{label}</label>}
    </div>
  );
});
Radio.displayName = RadioGroupPrimitive.Item.displayName;

export { Radio };
