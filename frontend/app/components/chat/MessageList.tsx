import { useCallback, useRef, useEffect } from "react";
import type { AgentMessage } from "~/types";
import { TypewriterText } from "~/components/ui/TypewriterText";
import {
  CameraIcon,
  ChatBubbleLeftIcon,
  CogIcon,
  CpuChipIcon,
  FilmIcon,
  HandRaisedIcon,
  PaintBrushIcon,
  PencilSquareIcon,
  RectangleStackIcon,
  SparklesIcon,
  UserIcon,
  VideoCameraIcon,
} from "@heroicons/react/24/outline";

interface MessageListProps {
  messages: AgentMessage[];
}

const agentColors: Record<string, string> = {
  onboarding: "badge-primary",
  director: "badge-secondary",
  scriptwriter: "badge-accent",
  character_artist: "badge-info",
  storyboard_artist: "badge-success",
  video_generator: "badge-warning",
  video_merger: "badge-error",
  system: "badge-neutral",
  user: "badge-ghost",
};

const agentIcons: Record<
  string,
  React.ComponentType<React.SVGProps<SVGSVGElement>>
> = {
  onboarding: FilmIcon,
  director: SparklesIcon,
  scriptwriter: PencilSquareIcon,
  character_artist: PaintBrushIcon,
  storyboard_artist: CameraIcon,
  video_generator: VideoCameraIcon,
  video_merger: RectangleStackIcon,
  system: CogIcon,
  user: UserIcon,
};

// 最小启用打字机效果的字符数
const MIN_TYPEWRITER_LENGTH = 50;

export function MessageList({ messages }: MessageListProps) {
  // 记录已经完成打字的消息 ID
  const completedMessagesRef = useRef<Set<string>>(new Set());
  // 记录消息首次出现的时间，用于判断是否为新消息
  const messageFirstSeenRef = useRef<Map<string, number>>(new Map());

  // 打字完成回调
  const handleComplete = useCallback((messageId: string) => {
    completedMessagesRef.current.add(messageId);
  }, []);

  // 判断消息是否应该启用打字机效果
  const shouldEnableTypewriter = useCallback((msg: AgentMessage, isLastMessage: boolean): boolean => {
    // 用户消息不启用
    if (msg.role === "user") return false;

    // 特殊消息类型不启用
    if (msg.role === "separator" || msg.role === "handoff" || msg.role === "info") return false;

    // 短消息不启用
    if (msg.content.length < MIN_TYPEWRITER_LENGTH) return false;

    // 已完成打字的消息不启用
    if (completedMessagesRef.current.has(msg.id || "")) return false;

    // 正在加载的消息启用
    if (msg.isLoading) return true;

    // 最后一条消息且是新消息（首次出现在 1 秒内）启用
    if (isLastMessage && msg.id) {
      const firstSeen = messageFirstSeenRef.current.get(msg.id);
      if (!firstSeen) {
        messageFirstSeenRef.current.set(msg.id, Date.now());
        return true;
      }
      // 如果消息首次出现在 1 秒内，认为是新消息
      return Date.now() - firstSeen < 1000;
    }

    return false;
  }, []);

  // 清理旧消息的首次出现记录
  useEffect(() => {
    const currentIds = new Set(messages.map(m => m.id).filter(Boolean));
    messageFirstSeenRef.current.forEach((_, id) => {
      if (!currentIds.has(id)) {
        messageFirstSeenRef.current.delete(id);
      }
    });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-base-content/70">
        <ChatBubbleLeftIcon className="w-6 h-6 mb-2" aria-hidden="true" />
        <p>暂无消息</p>
        <p className="text-sm">开始生成后可查看 AI 活动</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {messages.map((msg, idx) => {
        // 使用消息 ID 作为 key，如果没有则回退到索引
        const key = msg.id || `fallback_${idx}`;
        const isLastMessage = idx === messages.length - 1;

        // 分隔线特殊处理
        if (msg.role === "separator") {
          return (
            <div key={key} className="flex justify-center my-4 animate-fade-in">
              <div className="w-full border-t-2 border-base-300 opacity-50"></div>
            </div>
          );
        }

        // Agent 邀请消息特殊处理
        if (msg.role === "handoff") {
          return (
            <div key={key} className="flex justify-center my-3 animate-fade-in scale-[0.8]">
              <div className="badge badge-outline badge-lg gap-2 py-3 text-base-content">
                <HandRaisedIcon className="w-5 h-5" aria-hidden="true" />
                <span>{msg.content}</span>
              </div>
            </div>
          );
        }

        // 系统信息消息 - 不显示（已由确认区域替代）
        if (msg.role === "info" && msg.agent === "system") {
          return null;
        }

        // 判断消息方向，用于动画
        const isUserMessage = msg.role === "user";
        const slideAnimation = isUserMessage
          ? "animate-slide-in-right"
          : "animate-slide-in-left";

        // 判断是否启用打字机效果
        const enableTypewriter = shouldEnableTypewriter(msg, isLastMessage);

        // 普通消息
        const AgentIcon = agentIcons[msg.agent] || CpuChipIcon;
        return (
          <div
            key={key}
            className={`chat ${isUserMessage ? "chat-end" : "chat-start"} ${slideAnimation}`}
          >
            <div className="chat-header flex items-center gap-2 mb-1">
              <span className={`badge badge-sm flex items-center gap-1 ${agentColors[msg.agent] || "badge-ghost"} text-base-content`}>
                <AgentIcon className="w-5 h-5" aria-hidden="true" />
                {msg.agent}
              </span>
              {msg.timestamp && (
                <time className="text-xs opacity-50">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </time>
              )}
            </div>
            <div
              className={`chat-bubble px-4 py-3 ${
                msg.role === "error"
                  ? "chat-bubble-error"
                  : isUserMessage
                  ? "chat-bubble-primary"
                  : "bg-base-300 text-base-content"
              }`}
            >
              {/* 消息内容 - 使用打字机效果或直接显示 */}
              <div className="flex items-start gap-2">
                {msg.icon && (
                  <msg.icon className="w-5 h-5 mt-0.5 flex-shrink-0" aria-hidden="true" />
                )}
                <div className="whitespace-pre-wrap leading-relaxed">
                  {enableTypewriter ? (
                    <TypewriterText
                      text={msg.content}
                      enabled={true}
                      charDelay={20}
                      onComplete={() => handleComplete(msg.id || "")}
                    />
                  ) : (
                    msg.content
                  )}
                </div>
              </div>

              {/* 加载动画 */}
              {msg.isLoading && (
                <div className="flex items-center gap-2 mt-2 text-base-content/60">
                  <span className="loading loading-dots loading-xs" />
                  <span className="text-sm">处理中</span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
