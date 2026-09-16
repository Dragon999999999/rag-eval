import * as React from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/lib/toast";
import { queryClient } from "@/lib/query-client";

interface AppProvidersProps {
  children: React.ReactNode;
}

/**
 * Centralized application providers.
 *
 * Wraps the application with all necessary context providers:
 * - TanStack Query for server state
 * - Tooltip for accessible tooltips
 * - Toast for notifications
 */
export function AppProviders({ children }: AppProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <ToastProvider>{children}</ToastProvider>
      </TooltipProvider>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
