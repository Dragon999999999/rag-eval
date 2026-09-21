/**
 * Targets feature exports.
 */
export { TargetsPage } from "./pages/targets-page";
export { TargetCreatePage } from "./pages/target-create-page";
export { TargetDetailPage } from "./pages/target-detail-page";
export { TargetEditPage } from "./pages/target-edit-page";

export { TargetList } from "./components/target-list";
export { TargetForm } from "./components/target-form";
export { CapabilityList } from "./components/capability-list";
export { ConnectionTestResult } from "./components/connection-test-result";
export { TargetStatus } from "./components/target-status";

export {
  useTargetList,
  useTarget,
  useTargetAdapters,
  useTargetConfiguration,
  useTargetConfigurationVersions,
  useTargetAdapterSource,
  useTargetConnection,
  useTargetCapabilities,
  useCreateTarget,
  useUpdateTarget,
  useDeleteTarget,
  useSaveTargetConfiguration,
  useUploadPythonAdapter,
  useTestConnection,
  useDiscoverCapabilities,
  targetQueryKeys,
} from "./use-targets";

export { TargetService } from "./target-service";

export type {
  Target,
  TargetSummary,
  TargetCreate,
  TargetUpdate,
  TargetAdapterInfo,
  TargetAdapterSourceInfo,
  TargetCapabilitiesInfo,
  TargetConfigVersionDetail,
  TargetConfigVersionInfo,
  TargetConfigurationDraft,
  TargetConfigurationResponse,
  TargetConnection,
  TargetConnectionInfo,
  TargetConnectionStatus,
} from "./target-types";

export {
  formatAdapterType,
  formatTargetStatus,
  formatTargetEndpoint,
  formatRelativeTime,
  getConnectionStatus,
  statusVariant,
} from "./target-formatters";
