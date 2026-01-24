import { ProjectOverview } from "./ProjectOverview";

interface CanvasProps {
  projectId: number;
}

export function Canvas({ projectId }: CanvasProps) {
  return <ProjectOverview projectId={projectId} />;
}
