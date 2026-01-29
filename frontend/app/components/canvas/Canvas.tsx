import { InfiniteCanvas } from "./InfiniteCanvas";

interface CanvasProps {
  projectId: number;
}

export function Canvas({ projectId }: CanvasProps) {
  return <InfiniteCanvas projectId={projectId} />;
}
