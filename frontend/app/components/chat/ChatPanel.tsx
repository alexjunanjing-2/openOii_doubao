import { useState, useRef, useEffect } from "react";
import { useEditorStore } from "~/stores/editorStore";
import { MessageList } from "./MessageList";
import { MessageInput } from "./MessageInput";
import { Button } from "~/components/ui/Button";
import type { WorkflowStage } from "~/types";
import {
  CheckIcon,
  FilmIcon,
  LightBulbIcon,
  PaintBrushIcon,
  PauseIcon,
  RocketLaunchIcon,
  StopIcon,
} from "@heroicons/react/24/outline";

interface ChatPanelProps {
  onSendFeedback: (content: string) => void;
  onConfirm: (feedback?: string) => void;
  onGenerate: () => void;
  onCancel: () => void;
  isGenerating: boolean;
}
// ... (imports and interface definition remain the same) ...

const stageInfo: Record<
  WorkflowStage,
  {
    title: string;
    description: string;
    icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  }
> = {
  ideate: {
    title: "构思阶段",
    description: "描述你的故事想法，我来帮你创作剧本...",
    icon: LightBulbIcon,
  },
  visualize: {
    title: "可视化阶段",
    description: "正在设计角色和绘制分镜...",
    icon: PaintBrushIcon,
  },
  animate: {
    title: "动画阶段",
    description: "正在生成视频片段...",
    icon: FilmIcon,
  },
  deploy: {
    title: "完成",
    description: "你的漫剧已经准备好了！",
    icon: RocketLaunchIcon,
  },
};

// Agent 名称映射
const agentNameMap: Record<string, string> = {
  onboarding: "项目初始化",
  director: "导演",
  scriptwriter: "编剧",
  character_artist: "角色设计师",
  storyboard_artist: "分镜画师",
  video_generator: "视频生成器",
  video_merger: "视频合成器",
};


export function ChatPanel({
  onSendFeedback,
  onConfirm,
  onGenerate,
  onCancel,
  isGenerating,
}: ChatPanelProps) {
  const {
    messages,
    currentAgent,
    awaitingConfirm,
    awaitingAgent,
    currentStage,
    currentRunId,
  } = useEditorStore();

  const [input, setInput] = useState("");
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // 自动滚动到最新消息
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;

    if (currentRunId || isGenerating || awaitingConfirm) {
      onConfirm(input.trim());
      setInput("");
      return;
    }

    onSendFeedback(input);
    setInput("");
  };

  const info = stageInfo[currentStage];
  const StageIcon = info.icon;
  const hasMessages = messages.length > 0;
  const agentDisplayName = awaitingAgent ? agentNameMap[awaitingAgent] || awaitingAgent : "";
  const currentAgentDisplayName = currentAgent ? agentNameMap[currentAgent] || currentAgent : "";

  return (
    <div className="flex flex-col h-full bg-base-200 rounded-box shadow-lg">
      {/* Stage Header */}
      <div className="p-4 border-b border-base-300">
        <h3 className="font-heading font-semibold text-primary mb-1">
          <span className="inline-flex items-center gap-2">
            <StageIcon className="w-5 h-5" aria-hidden="true" />
            {info.title}
          </span>
        </h3>
        <p className="text-sm text-base-content/80">{info.description}</p>

        {isGenerating && (
          <div className="mt-3">
            <div className="flex items-center justify-between gap-2 text-sm text-base-content/70">
              <div className="flex items-center gap-2">
                {awaitingConfirm ? (
                  <span className="text-warning font-medium inline-flex items-center gap-1">
                    <PauseIcon className="w-5 h-5" aria-hidden="true" />
                    等待您的确认
                  </span>
                ) : (
                  <>
                    <span className="loading loading-dots loading-xs" />
                    <span>{currentAgentDisplayName || "处理中"}...</span>
                  </>
                )}
              </div>
              {!awaitingConfirm && (
                <Button size="sm" variant="ghost" onClick={onCancel} className="text-error hover:bg-error/10 gap-1">
                  <StopIcon className="w-5 h-5" aria-hidden="true" />
                  停止
                </Button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Content Area */}
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4">
        {!hasMessages && !isGenerating ? (
          <div className="flex flex-col h-full">
            <div className="flex-1 flex flex-col items-center justify-center text-center px-4">
              <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <StageIcon className="w-6 h-6 text-primary" aria-hidden="true" />
              </div>
              <h2 className="text-xl font-heading font-bold mb-2">
                准备好创作你的漫剧了吗？
              </h2>
              <p className="text-base-content/80 mb-6 max-w-xs">
                点击下方按钮，AI 将根据你的故事自动生成剧本、角色和分镜
              </p>
              <Button variant="primary" size="lg" onClick={onGenerate} className="gap-2">
                <RocketLaunchIcon className="w-5 h-5" aria-hidden="true" />
                开始生成
              </Button>
            </div>
          </div>
        ) : (
          <MessageList messages={messages} />
        )}
      </div>


      {awaitingConfirm && (
        <div className="p-4 border-t border-base-300 bg-warning/20">
          <div className="mb-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="badge badge-warning badge-sm text-warning-content">等待确认</span>
              <span className="font-medium text-sm">{agentDisplayName} 已完成</span>
            </div>
            <p className="text-sm text-base-content/80 mb-2">
              请在右侧预览区查看生成结果，确认满意后点击继续。
            </p>
            <p className="text-xs text-base-content/60">
              <span className="inline-flex items-center gap-1">
                <LightBulbIcon className="w-5 h-5" aria-hidden="true" />
                如果需要修改，请在下方输入框中描述您的调整意见，然后点击发送。
              </span>
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="primary"
              onClick={() => {
                const feedback = input.trim();
                onConfirm(feedback || undefined);
                setInput("");
              }}
              className="flex-1"
            >
              <span className="inline-flex items-center gap-2">
                <CheckIcon className="w-5 h-5" aria-hidden="true" />
                满意，继续下一步
              </span>
            </Button>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="p-4 border-t border-base-300">
        <MessageInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          disabled={false}
          placeholder={
            awaitingConfirm
              ? "输入修改意见后点击发送..."
              : isGenerating
                ? "输入反馈或等待完成..."
                : "输入你的想法或反馈..."
          }
        />
      </div>
    </div>
  );
}
