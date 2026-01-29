import { useMemo } from "react";
import type { TLShapePartial } from "tldraw";
import { SHAPE_TYPES } from "~/components/canvas/shapes";
import type { Character, Shot } from "~/types";

interface LayoutConfig {
  startX: number;
  startY: number;
  sectionWidth: number;
  sectionGap: number;
  connectorGap: number;
}

const DEFAULT_CONFIG: LayoutConfig = {
  startX: 100,
  startY: 100,
  sectionWidth: 800,
  sectionGap: 150,
  connectorGap: 50,
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
    const centerX = config.startX + config.sectionWidth / 2;

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

      const scriptEndY = currentY + scriptHeight;
      currentY = scriptEndY + config.sectionGap;

      // 连接线: 剧本 -> 角色设计
      if (characters.length > 0) {
        result.push({
          id: "shape:connector-1" as any,
          type: SHAPE_TYPES.CONNECTOR,
          x: 0,
          y: 0,
          props: {
            start: { x: centerX, y: scriptEndY + config.connectorGap },
            end: { x: centerX, y: currentY - config.connectorGap },
          },
        });
      }
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

      const characterEndY = currentY + characterHeight;
      currentY = characterEndY + config.sectionGap;

      // 连接线: 角色设计 -> 分镜图
      if (shots.some((s) => s.image_url)) {
        result.push({
          id: "shape:connector-2" as any,
          type: SHAPE_TYPES.CONNECTOR,
          x: 0,
          y: 0,
          props: {
            start: { x: centerX, y: characterEndY + config.connectorGap },
            end: { x: centerX, y: currentY - config.connectorGap },
          },
        });
      }
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

      const storyboardEndY = currentY + storyboardHeight;
      currentY = storyboardEndY + config.sectionGap;

      // 连接线: 分镜图 -> 视频
      if (videoUrl) {
        result.push({
          id: "shape:connector-3" as any,
          type: SHAPE_TYPES.CONNECTOR,
          x: 0,
          y: 0,
          props: {
            start: { x: centerX, y: storyboardEndY + config.connectorGap },
            end: { x: centerX, y: currentY - config.connectorGap },
          },
        });
      }
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
    }

    return result;
  }, [summary, characters, shots, videoUrl, videoTitle, config]);

  return shapes;
}

// 计算剧本区域高度
function calculateScriptHeight(
  summary: string | null,
  characters: Character[],
  shots: Shot[]
): number {
  let height = 80; // 标题 + padding

  if (summary) {
    const summaryLines = Math.ceil(summary.length / 80);
    height += 40 + summaryLines * 24 + 20;
  }

  if (characters.length > 0) {
    const charRows = Math.ceil(characters.length / 2);
    height += 30 + charRows * 80 + 20;
  }

  if (shots.length > 0) {
    const shotHeight = Math.min(shots.length * 28, 300);
    height += 30 + shotHeight + 20;
  }

  return Math.max(height, 200);
}

// 计算角色区域高度
function calculateCharacterHeight(characters: Character[]): number {
  if (characters.length === 0) return 200;
  const rows = Math.ceil(characters.length / 2);
  return 80 + rows * 280 + 20;
}

// 计算分镜区域高度
function calculateStoryboardHeight(shots: Shot[]): number {
  if (shots.length === 0) return 200;
  const rows = Math.ceil(shots.length / 4);
  return 80 + rows * 180 + 20;
}
