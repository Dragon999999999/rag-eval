import { Page } from "@/components/layout/page-layout";
import { EmptyState } from "@/components/ui/empty-state";
import { Settings as SettingsIcon } from "lucide-react";

/**
 * Settings page - application configuration.
 *
 * Placeholder for future settings functionality.
 */
export function SettingsPage() {
  return (
    <Page>
      <Page.Header
        title="Settings"
        description="Configure application preferences and system settings."
      />

      <Page.Content>
        <EmptyState
          icon={<SettingsIcon className="h-8 w-8" />}
          title="Settings not configured"
          description="Application settings will be available here."
        />
      </Page.Content>
    </Page>
  );
}
