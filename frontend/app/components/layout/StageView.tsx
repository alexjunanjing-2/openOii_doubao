import { useEditorStore } from "~/stores/editorStore";
import { Canvas } from "~/components/canvas/Canvas";
import { LightBulbIcon } from "@heroicons/react/24/outline";

interface StageViewProps {
  projectId: number;
}

export function StageView({ projectId }: StageViewProps) {
  const { currentStage, shots, scenes, characters } = useEditorStore();

  // 判断是否有内容
  const hasContent = shots.length > 0 || scenes.length > 0 || characters.length > 0;

  // 如果有内容，优先显示Canvas（包括 deploy 阶段）
  if (hasContent) {
    return <Canvas projectId={projectId} />;
  }

  // 没有内容时显示引导页面（ideate 阶段）
  if (currentStage === "ideate") {
    return (
      <div className="h-full flex items-center justify-center bg-base-200 rounded-box p-8">
        <div className="text-center max-w-lg">
          <div className="text-primary mb-6 flex justify-center">
            <LightBulbIcon className="w-16 h-16" />
          </div>
          <h2 className="text-2xl font-heading font-bold mb-3">
            构思你的故事
          </h2>
          <p className="text-base-content/70 mb-6">
            在左侧对话框中描述你的故事想法，AI 将帮你创作剧本、设计角色和规划分镜。
          </p>

          {/* 引导箭头指向左侧 */}
          <div className="flex items-center justify-center gap-3 text-primary/60">
            <svg className="w-6 h-6 animate-bounce-x" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            <span className="text-sm">点击左侧「开始生成」按钮</span>
          </div>
        </div>
      </div>
    );
  }

  // 其他阶段显示 Canvas
  return <Canvas projectId={projectId} />;
}
