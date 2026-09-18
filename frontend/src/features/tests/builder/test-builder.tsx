/**
 * Test Builder Wizard - Main orchestrator component.
 *
 * Manages the 5-step builder flow:
 * 1. Target Selection
 * 2. Dataset Selection
 * 3. Metrics Configuration
 * 4. Execution Settings
 * 5. Review
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Surface } from "@/components/layout/surface";
import {
  useTestBuilderForm,
  BuilderStep,
  STEP_METADATA,
  getNextStep,
  getPreviousStep,
} from "../test-builder-form";
import { TargetStep } from "./target-step";
import { DatasetStep } from "./dataset-step";
import { MetricsStep } from "./metrics-step";
import { ExecutionStep } from "./execution-step";
import { ReviewStep } from "./review-step";

interface TestBuilderProps {
  /** Optional: Edit existing test definition ID */
  testDefinitionId?: string;
}

// eslint-disable-next-line no-empty-pattern
export function TestBuilder({}: TestBuilderProps) {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState<BuilderStep>(BuilderStep.TARGET);

  const form = useTestBuilderForm();

  // Get current step metadata
  const stepMeta = STEP_METADATA[currentStep];
  const handleNext = () => {
    const next = getNextStep(currentStep);
    if (next) setCurrentStep(next);
  };

  const handlePrevious = () => {
    const prev = getPreviousStep(currentStep);
    if (prev) setCurrentStep(prev);
  };

  const handleStepClick = (step: BuilderStep) => {
    // Allow navigating back to previous steps
    const stepNum = Object.values(BuilderStep).indexOf(step) + 1;
    const currentNum = Object.values(BuilderStep).indexOf(currentStep) + 1;
    if (stepNum < currentNum) {
      setCurrentStep(step);
    }
  };

  // Handle save completion
  const handleSave = (testId: string) => {
    navigate(`/tests/${testId}`);
  };

  const handleSaveAndRun = (testId: string) => {
    // Navigate to run creation or show run dialog
    navigate(`/tests/${testId}/run`);
  };

  // Render current step
  const renderStep = () => {
    switch (currentStep) {
      case BuilderStep.TARGET:
        return <TargetStep form={form} onNext={handleNext} />;

      case BuilderStep.DATASET:
        return (
          <DatasetStep form={form} onPrevious={handlePrevious} onNext={handleNext} />
        );

      case BuilderStep.METRICS:
        return (
          <MetricsStep
            form={form}
            targetId={form.getValues().target_id}
            benchmarkId={form.getValues().benchmark_id}
            onPrevious={handlePrevious}
            onNext={handleNext}
          />
        );

      case BuilderStep.EXECUTION:
        return (
          <ExecutionStep form={form} onPrevious={handlePrevious} onNext={handleNext} />
        );

      case BuilderStep.REVIEW:
        return (
          <ReviewStep
            form={form}
            onPrevious={handlePrevious}
            onSave={handleSave}
            onSaveAndRun={handleSaveAndRun}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Progress indicator */}
      <Surface className="p-4">
        <div className="flex items-center justify-between">
          {Object.values(BuilderStep).map((step, index) => {
            const stepNum = index + 1;
            const isCurrent = step === currentStep;
            // eslint-disable-next-line @typescript-eslint/no-unsafe-enum-comparison
            const isPast = stepNum < (currentStep);
            // eslint-disable-next-line @typescript-eslint/no-unsafe-enum-comparison
            const canNavigate = stepNum <= (currentStep);

            return (
              <div key={step} className="flex items-center">
                <button
                  onClick={() => { if (canNavigate) handleStepClick(step as BuilderStep); }}
                  disabled={!canNavigate}
                  className={`flex items-center gap-2 rounded-md px-3 py-2 transition-colors ${
                    isCurrent
                      ? "text-accent-foreground bg-accent"
                      : isPast
                        ? "bg-surface-hover text-text-primary"
                        : "text-text-tertiary"
                  } ${canNavigate && !isCurrent ? "cursor-pointer hover:bg-surface-hover" : "cursor-default"}`}
                >
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                      isCurrent
                        ? "bg-accent-foreground text-accent"
                        : isPast
                          ? "bg-surface-hover text-text-primary"
                          : "bg-surface text-text-tertiary"
                    }`}
                  >
                    {isPast ? "✓" : stepNum}
                  </div>
                  <div className="hidden text-left md:block">
                    <div className="text-sm font-medium">{stepMeta.title}</div>
                    <div className="text-xs text-text-tertiary">
                      {STEP_METADATA[step as BuilderStep].description}
                    </div>
                  </div>
                </button>

                {stepNum < 5 && <div className="bg-border mx-2 h-px w-8 flex-1" />}
              </div>
            );
          })}
        </div>
      </Surface>

      {/* Step content */}
      <div>
        <div className="mb-4">
          <h1 className="text-2xl font-bold text-text-primary">{stepMeta.title}</h1>
          <p className="text-sm text-text-tertiary">{stepMeta.description}</p>
        </div>

        {renderStep()}
      </div>
    </div>
  );
}
