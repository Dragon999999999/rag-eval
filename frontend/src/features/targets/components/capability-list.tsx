/**
 * Target capabilities display component.
 *
 * Shows discovered capabilities in a compact format.
 */
import { Check, Minus } from "lucide-react";
import { Surface } from "@/components/layout/surface";
import type { TargetCapabilities } from "../target-types";

interface CapabilityListProps {
  capabilities: TargetCapabilities["capabilities"];
  className?: string;
}

export function CapabilityList({ capabilities, className }: CapabilityListProps) {
  return (
    <Surface className={className}>
      <div className="space-y-4">
        <h3 className="text-base font-medium text-text-primary">Capabilities</h3>
        
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Core capabilities */}
          <CapabilityGroup
            title="Core"
            items={[
              { key: "query", label: "Query" },
              { key: "streaming", label: "Streaming" },
              { key: "conversation_history", label: "Conversation History" },
              { key: "context_injection", label: "Context Injection" },
            ]}
            capabilities={capabilities}
          />

          {/* Retrieval capabilities */}
          <CapabilityGroup
            title="Retrieval"
            items={[
              { key: "retrieval", label: "Retrieval" },
              { key: "retrieval_stages", label: "Retrieval Stages" },
              { key: "document_ingestion", label: "Document Ingestion" },
              { key: "chunk_ingestion", label: "Chunk Ingestion" },
            ]}
            capabilities={capabilities}
          />

          {/* Output capabilities */}
          <CapabilityGroup
            title="Output"
            items={[
              { key: "citations", label: "Citations" },
              { key: "confidence", label: "Confidence" },
              { key: "target_trace", label: "Trace" },
              { key: "usage", label: "Usage", nested: "tokens" },
            ]}
            capabilities={capabilities}
          />

          {/* Advanced capabilities */}
          <CapabilityGroup
            title="Advanced"
            items={[
              { key: "idempotency", label: "Idempotency" },
              { key: "request_recovery", label: "Request Recovery" },
              { key: "effective_configuration", label: "Effective Configuration" },
            ]}
            capabilities={capabilities}
          />
        </div>

        {/* Protocol version */}
        {capabilities.protocol_version && (
          <div className="flex items-center gap-2 text-sm text-text-tertiary">
            <span>Protocol Version:</span>
            <code className="rounded bg-surface-hover px-2 py-0.5">
              {capabilities.protocol_version}
            </code>
          </div>
        )}
      </div>
    </Surface>
  );
}

interface CapabilityGroupProps {
  title: string;
  items: Array<{
    key: string;
    label: string;
    nested?: string;
  }>;
  capabilities: Record<string, unknown>;
}

function CapabilityGroup({ title, items, capabilities }: CapabilityGroupProps) {
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-text-secondary">{title}</h4>
      <ul className="space-y-1">
        {items.map((item) => {
          let value: unknown;
          
          if (item.nested) {
            const nested = capabilities[item.key] as Record<string, unknown> | undefined;
            value = nested?.[item.nested];
          } else {
            value = capabilities[item.key];
          }

          const isEnabled = value === true;

          return (
            <li key={item.key} className="flex items-center gap-2 text-sm">
              {isEnabled ? (
                <Check className="h-4 w-4 text-success" />
              ) : (
                <Minus className="h-4 w-4 text-text-tertiary" />
              )}
              <span className={isEnabled ? "text-text-primary" : "text-text-tertiary"}>
                {item.label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
