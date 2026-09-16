import * as React from "react";
import { cn } from "@/lib/utils/cn";
import { Card } from "@/components/layout/card";
import { Spinner } from "./spinner";

export interface MetricCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string;
  value: string | number | React.ReactNode;
  trend?: {
    value: string | number;
    direction: "up" | "down" | "neutral";
  };
  loading?: boolean;
  description?: string;
}

function MetricCard({
  className,
  label,
  value,
  trend,
  loading = false,
  description,
  ...props
}: MetricCardProps) {
  return (
    <Card className={cn("p-4", className)} {...props}>
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-medium text-text-tertiary">{label}</p>
          {loading ? (
            <div className="flex items-center gap-2">
              <Spinner size="sm" />
              <span className="text-2xl font-semibold text-text-primary">---</span>
            </div>
          ) : (
            <p className="text-2xl font-semibold text-text-primary">{value}</p>
          )}
          {description && <p className="text-xs text-text-tertiary">{description}</p>}
        </div>
        {trend && !loading && (
          <div
            className={cn(
              "flex items-center gap-1 text-xs font-medium",
              trend.direction === "up" && "text-success",
              trend.direction === "down" && "text-error",
              trend.direction === "neutral" && "text-text-tertiary"
            )}
          >
            {trend.direction === "up" && "↑"}
            {trend.direction === "down" && "↓"}
            {trend.value}
          </div>
        )}
      </div>
    </Card>
  );
}

export { MetricCard };
