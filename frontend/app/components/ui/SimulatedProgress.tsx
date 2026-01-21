import { useEffect, useState, useRef } from "react";

interface SimulatedProgressProps {
  /** 是否正在加载 */
  isLoading: boolean;
  /** 预估完成时间（秒），用于调整进度速度（auto 模式） */
  estimatedDuration?: number;
  /** 进度条高度 */
  height?: "xs" | "sm" | "md";
  /** 显示百分比文字 */
  showPercentage?: boolean;
  /** 进度条颜色 */
  color?: "primary" | "secondary" | "accent" | "info" | "success" | "warning";
  /** 进度模式：auto 自动模拟，external 外部控制 */
  mode?: "auto" | "external";
  /** 外部进度值（0-100），仅 external 模式有效 */
  externalProgress?: number;
  /** 完成回调，进度达到 100% 时触发 */
  onComplete?: () => void;
}

/**
 * 非线性缓动函数 - 开始快，中间慢，接近完成时更慢
 * 使用 easeOutExpo 变体，让进度增长更自然
 */
function easeOutExpo(x: number): number {
  return x === 1 ? 1 : 1 - Math.pow(2, -10 * x);
}

/**
 * 模拟进度条组件
 *
 * 支持两种模式：
 * - auto: 自动模拟进度增长（默认），使用非线性缓动
 * - external: 外部控制进度，支持双阶段增长
 *
 * 特点：
 * - 进度增长非线性，开始较快，越接近完成越慢
 * - 最高到 85%，完成时快速冲刺到 100%
 * - 完成后延迟淡出隐藏
 */
export function SimulatedProgress({
  isLoading,
  estimatedDuration = 60, // 默认 60 秒，让进度更慢
  height = "sm",
  showPercentage = true,
  color = "primary",
  mode = "auto",
  externalProgress = 0,
  onComplete,
}: SimulatedProgressProps) {
  const [progress, setProgress] = useState(0);
  const [phase, setPhase] = useState<"idle" | "loading" | "sprinting" | "complete" | "fading" | "hidden">("idle");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);
  const wasLoadingRef = useRef(false);

  // 清理函数
  const cleanup = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
  };

  // 监听 isLoading 变化
  useEffect(() => {
    const wasLoading = wasLoadingRef.current;
    wasLoadingRef.current = isLoading;

    if (isLoading && !wasLoading) {
      // 开始加载
      cleanup();
      setProgress(0);
      setPhase("loading");
      startTimeRef.current = Date.now();

      if (mode === "auto") {
        // Auto 模式：使用非线性进度增长
        intervalRef.current = setInterval(() => {
          const elapsed = (Date.now() - startTimeRef.current) / 1000;
          // 计算时间进度（0-1），基于预估时长
          const timeProgress = Math.min(elapsed / estimatedDuration, 1);
          // 应用非线性缓动，让进度增长更慢
          const easedProgress = easeOutExpo(timeProgress);
          // 映射到 0-85% 范围
          const naturalProgress = easedProgress * 85;
          // 添加微小随机波动
          const jitter = (Math.random() - 0.5) * 0.5;
          const finalProgress = Math.min(85, Math.max(0, naturalProgress + jitter));
          setProgress(finalProgress);
        }, 300); // 更新间隔 300ms，更慢
      }
    } else if (!isLoading && wasLoading && phase === "loading") {
      // 停止加载，开始冲刺到 100%
      cleanup();
      setPhase("sprinting");

      const startProgress = progress;
      const sprintDuration = 800; // 冲刺动画时长 800ms
      let sprintStartTime: number | null = null;

      const sprint = (timestamp: number) => {
        if (!sprintStartTime) sprintStartTime = timestamp;
        const elapsed = timestamp - sprintStartTime;
        const fraction = Math.min(elapsed / sprintDuration, 1);

        // 使用 easeOutCubic 缓动
        const easeOutCubic = (x: number) => 1 - Math.pow(1 - x, 3);
        const easedFraction = easeOutCubic(fraction);

        const newProgress = startProgress + (100 - startProgress) * easedFraction;
        setProgress(newProgress);

        if (fraction < 1) {
          animationFrameRef.current = requestAnimationFrame(sprint);
        } else {
          // 冲刺完成
          setProgress(100);
          setPhase("complete");
          onComplete?.();

          // 延迟 500ms 后开始淡出
          setTimeout(() => {
            setPhase("fading");
            // 淡出动画 500ms 后隐藏
            setTimeout(() => {
              setPhase("hidden");
            }, 500);
          }, 500);
        }
      };

      animationFrameRef.current = requestAnimationFrame(sprint);
    }

    return cleanup;
  }, [isLoading, mode, estimatedDuration, onComplete, phase, progress]);

  // External 模式：跟随外部进度
  useEffect(() => {
    if (mode !== "external" || phase !== "loading") return;

    // 确保进度不会倒退，且上限为 85%
    const clampedProgress = Math.min(85, Math.max(0, externalProgress));
    setProgress((prev) => Math.max(prev, clampedProgress));
  }, [externalProgress, mode, phase]);

  // 隐藏状态不渲染
  if (phase === "hidden" || phase === "idle") {
    return null;
  }

  const heightClass = {
    xs: "h-1",
    sm: "h-2",
    md: "h-3",
  }[height];

  const colorClass = `progress-${color}`;
  const isFading = phase === "fading";
  const isComplete = phase === "complete" || phase === "fading";

  return (
    <div
      className={`mt-3 transition-opacity duration-500 ${
        isFading ? "opacity-0" : "opacity-100 animate-fade-in"
      }`}
    >
      {showPercentage && (
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="opacity-70 flex items-center gap-1">
            {!isComplete && (
              <span className="loading loading-spinner loading-xs"></span>
            )}
            <span>{isComplete ? "完成" : "处理中"}</span>
          </span>
          <span className="font-semibold tabular-nums">
            {Math.round(progress)}%
          </span>
        </div>
      )}
      <div className="relative">
        <progress
          className={`progress ${colorClass} w-full ${heightClass} transition-all duration-300`}
          value={progress}
          max="100"
        />
        {/* 闪光效果 - 只在未完成时显示 */}
        {!isComplete && (
          <div
            className="absolute top-0 left-0 h-full bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"
            style={{
              width: "30%",
              transform: `translateX(${progress * 3}%)`,
            }}
          />
        )}
      </div>
    </div>
  );
}
