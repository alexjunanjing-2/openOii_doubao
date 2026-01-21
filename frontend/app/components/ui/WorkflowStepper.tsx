import {
  LightBulbIcon,
  EyeIcon,
  SparklesIcon,
  RocketLaunchIcon,
} from "@heroicons/react/24/outline";
import type { WorkflowStage } from "~/types";
import { clsx } from "clsx";

interface Step {
  id: WorkflowStage;
  name: string;
  label: string;
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
}

const steps: Step[] = [
  { id: "ideate", name: "Ideate", label: "1. 构思", Icon: LightBulbIcon },
  { id: "visualize", name: "Visualize", label: "2. 可视化", Icon: EyeIcon },
  { id: "animate", name: "Animate", label: "3. 动画", Icon: SparklesIcon },
  { id: "deploy", name: "Deploy", label: "4. 完成!", Icon: RocketLaunchIcon },
];

interface WorkflowStepperProps {
  currentStage: WorkflowStage;
  isGenerating?: boolean;
  className?: string;
}

export function WorkflowStepper({
  currentStage,
  isGenerating = false,
  className,
}: WorkflowStepperProps) {
  const currentStepIndex = steps.findIndex((step) => step.id === currentStage);

  return (
    <nav aria-label="Progress" className={clsx("py-2", className)}>
      <ol role="list" className="flex items-center justify-center gap-4">
        {steps.map((step, stepIdx) => {
          const isCompleted = stepIdx < currentStepIndex;
          const isCurrent = stepIdx === currentStepIndex;

          return (
            <li key={step.name} className="flex flex-col items-center gap-1">
              <div
                className={clsx(
                  "flex h-10 w-10 items-center justify-center rounded-full border-3 border-black transition-all duration-200",
                  isCurrent && isGenerating && "animate-pulse",
                  isCurrent
                    ? "bg-primary shadow-brutal scale-110"
                    : isCompleted
                      ? "bg-secondary"
                      : "bg-base-300",
                   isCurrent && isGenerating && "!bg-warning"
                )}
              >
                {isCompleted ? (
                   <span className="font-bold text-lg text-base-content">✓</span>
                ) : (
                  <step.Icon
                    className={clsx(
                      "h-6 w-6",
                      isCurrent ? "text-base-content" : "text-base-content/50"
                    )}
                    aria-hidden="true"
                  />
                )}
              </div>
               <span
                className={clsx(
                  "text-xs font-heading font-bold transition-colors",
                  isCurrent ? "text-primary" : "text-base-content/60"
                )}
              >
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
