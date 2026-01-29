import type { TLBaseShape } from "tldraw";
import type { Character, Shot } from "~/types";

// Shape 类型常量
export const SHAPE_TYPES = {
  SCRIPT_SECTION: "script-section",
  CHARACTER_SECTION: "character-section",
  STORYBOARD_SECTION: "storyboard-section",
  VIDEO_SECTION: "video-section",
  CONNECTOR: "connector",
} as const;

// 剧本区域 Shape (包含摘要、角色列表文字版、分镜描述)
export type ScriptSectionShape = TLBaseShape<
  typeof SHAPE_TYPES.SCRIPT_SECTION,
  {
    w: number;
    h: number;
    summary: string;
    characters: Character[];
    shots: Shot[];
  }
>;

// 角色设计区域 Shape (角色图片)
export type CharacterSectionShape = TLBaseShape<
  typeof SHAPE_TYPES.CHARACTER_SECTION,
  {
    w: number;
    h: number;
    characters: Character[];
  }
>;

// 分镜图区域 Shape
export type StoryboardSectionShape = TLBaseShape<
  typeof SHAPE_TYPES.STORYBOARD_SECTION,
  {
    w: number;
    h: number;
    shots: Shot[];
  }
>;

// 视频区域 Shape
export type VideoSectionShape = TLBaseShape<
  typeof SHAPE_TYPES.VIDEO_SECTION,
  {
    w: number;
    h: number;
    videoUrl: string;
    title: string;
  }
>;

// 连接线 Shape
export type ConnectorShape = TLBaseShape<
  typeof SHAPE_TYPES.CONNECTOR,
  {
    start: { x: number; y: number };
    end: { x: number; y: number };
  }
>;

// 扩展 tldraw 全局类型
declare module "tldraw" {
  interface TLGlobalShapePropsMap {
    [SHAPE_TYPES.SCRIPT_SECTION]: ScriptSectionShape["props"];
    [SHAPE_TYPES.CHARACTER_SECTION]: CharacterSectionShape["props"];
    [SHAPE_TYPES.STORYBOARD_SECTION]: StoryboardSectionShape["props"];
    [SHAPE_TYPES.VIDEO_SECTION]: VideoSectionShape["props"];
    [SHAPE_TYPES.CONNECTOR]: ConnectorShape["props"];
  }
}
