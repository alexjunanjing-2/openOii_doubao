import { useMemo } from "react";
import type { TLShapePartial } from "tldraw";
import { SHAPE_TYPES } from "~/components/canvas/shapes";
import type { Character, Shot } from "~/types";

interface LayoutConfig {
  startX: number;
  startY: number;
  sectionWidth: number;
  sectionGap: number;
}

const DEFAULT_CONFIG: LayoutConfig = {
  startX: 100,
  startY: 100,
  sectionWidth: 800,
  sectionGap: 60,
};

interface UseCanvasLayoutProps {
  summary: string | null;
  characters: Character[];
  shots: Shot[];
  videoUrl: string | null;
  videoTitle: string;
  config?: Partial<LayoutConfig>;
}

export function useCanvasLayout({
  summary,
  characters,
  shots,
  videoUrl,
  videoTitle,
  config: customConfig,
}: UseCanvasLayoutProps) {
  const config = useMemo(
    () => ({ ...DEFAULT_CONFIG, ...customConfig }),
    [customConfig]
  );

  const shapes = useMemo(() => {
    const result: TLShapePartial[] = [];
    let currentY = config.startY;

    // 计算各区域高度
    const scriptHeight = calculateScriptHeight(summary, characters, shots);
    const characterHeight = calculateCharacterHeight(characters);
    const storyboardHeight = calculateStoryboardHeight(shots);
    const videoHeight = 450;

    // 1. 剧本区域 (编剧)
    const hasScriptContent = summary || characters.length > 0 || shots.length > 0;
    if (hasScriptContent) {
      result.push({
        id: "shape:script-section" as any,
        type: SHAPE_TYPES.SCRIPT_SECTION,
        x: config.startX,
        y: currentY,
        props: {
          w: config.sectionWidth,
          h: scriptHeight,
          summary: summary || "",
          characters,
          shots,
        },
      });

      currentY += scriptHeight + config.sectionGap;
    }

    // 2. 角色设计区域
    if (characters.length > 0) {
      result.push({
        id: "shape:character-section" as any,
        type: SHAPE_TYPES.CHARACTER_SECTION,
        x: config.startX,
        y: currentY,
        props: {
          w: config.sectionWidth,
          h: characterHeight,
          characters,
        },
      });

      // 连接线: 剧本 -> 角色设计
      if (hasScriptContent) {
        result.push({
          id: "shape:connector-1" as any,
          type: SHAPE_TYPES.CONNECTOR,
          x: 0,
          y: 0,
          props: {
            fromId: "shape:script-section",
            toId: "shape:character-section",
          },
        });
      }

      currentY += characterHeight + config.sectionGap;
    }

    // 3. 分镜图区域
    const hasStoryboardImages = shots.some((s) => s.image_url);
    if (hasStoryboardImages) {
      result.push({
        id: "shape:storyboard-section" as any,
        type: SHAPE_TYPES.STORYBOARD_SECTION,
        x: config.startX,
        y: currentY,
        props: {
          w: config.sectionWidth,
          h: storyboardHeight,
          shots,
        },
      });

      // 连接线: 角色设计 -> 分镜图
      if (characters.length > 0) {
        result.push({
          id: "shape:connector-2" as any,
          type: SHAPE_TYPES.CONNECTOR,
          x: 0,
          y: 0,
          props: {
            fromId: "shape:character-section",
            toId: "shape:storyboard-section",
          },
        });
      } else if (hasScriptContent) {
        // 如果没有角色区域，直接从剧本连接到分镜
        result.push({
          id: "shape:connector-2" as any,
          type: SHAPE_TYPES.CONNECTOR,
          x: 0,
          y: 0,
          props: {
            fromId: "shape:script-section",
            toId: "shape:storyboard-section",
          },
        });
      }

      currentY += storyboardHeight + config.sectionGap;
    }

    // 4. 视频区域
    if (videoUrl) {
      result.push({
        id: "shape:video-section" as any,
        type: SHAPE_TYPES.VIDEO_SECTION,
        x: config.startX + (config.sectionWidth - 600) / 2,
        y: currentY,
        props: {
          w: 600,
          h: videoHeight,
          videoUrl,
          title: videoTitle,
        },
      });

      // 连接线: 分镜图/角色设计/剧本 -> 视频
      if (hasStoryboardImages) {
        result.push({
          id: "shape:connector-3" as any,
          type: SHAPE_TYPES.CONNECTOR,
          x: 0,
          y: 0,
          props: {
            fromId: "shape:storyboard-section",
            toId: "shape:video-section",
          },
        });
      } else if (characters.length > 0) {
        result.push({
          id: "shape:connector-3" as any,
          type: SHAPE_TYPES.CONNECTOR,
          x: 0,
          y: 0,
          props: {
            fromId: "shape:character-section",
            toId: "shape:video-section",
          },
        });
      } else if (hasScriptContent) {
        result.push({
          id: "shape:connector-3" as any,
          type: SHAPE_TYPES.CONNECTOR,
          x: 0,
          y: 0,
          props: {
            fromId: "shape:script-section",
            toId: "shape:video-section",
          },
        });
      }
    }

    return result;
  }, [summary, characters, shots, videoUrl, videoTitle, config]);

  return shapes;
}

// 计算剧本区域高度 - 宽松估算确保内容完全显示
function calculateScriptHeight(
  summary: string | null,
  characters: Character[],
  shots: Shot[]
): number {
  let height = 80; // 标题栏 + padding

  if (summary) {
    // 摘要：每80字符约一行，行高24px
    const summaryLines = Math.ceil(summary.length / 60) + 1;
    height += 40 + summaryLines * 24 + 24;
  }

  if (characters.length > 0) {
    const charRows = Math.ceil(characters.length / 2);
    // 脚本区角色卡包含完整描述（personality_traits/goals/fears等），每行约 160px
    height += 36 + charRows * 160 + 24;
  }

  if (shots.length > 0) {
    // 每条分镜描述约 50px（含多行文本）
    height += 36 + shots.length * 50 + 24;
  }

  return Math.max(height, 250);
}

// 计算角色区域高度 - 包含图片和描述
function calculateCharacterHeight(characters: Character[]): number {
  if (characters.length === 0) return 250;
  const rows = Math.ceil(characters.length / 2);
  // 每行: 描述文本 ~120px + 图片 192px + padding/gap = ~340px
  return 90 + rows * 360 + 24;
}

// 计算分镜区域高度
function calculateStoryboardHeight(shots: Shot[]): number {
  if (shots.length === 0) return 250;
  const rows = Math.ceil(shots.length / 4);
  // 每行: 序号+图片(96px)+描述+padding = ~200px
  return 90 + rows * 200 + 24;
}
