/**
 * Label component for forms.
 */
import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {}

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn(
        "text-sm font-medium leading-none text-text-primary",
        className
      )}
      {...props}
    />
  )
);
Label.displayName = "Label";

export { Label };
