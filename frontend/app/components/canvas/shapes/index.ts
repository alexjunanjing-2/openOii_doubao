import { OriginalPromptShapeUtil } from "./OriginalPromptShape";
import { ScriptSectionShapeUtil } from "./ScriptSectionShape";
import { CharacterSectionShapeUtil } from "./CharacterSectionShape";
import { StoryboardSectionShapeUtil } from "./StoryboardSectionShape";
import { VideoSectionShapeUtil } from "./VideoSectionShape";
import { ConnectorShapeUtil } from "./ConnectorShape";

export { OriginalPromptShapeUtil } from "./OriginalPromptShape";
export { ScriptSectionShapeUtil } from "./ScriptSectionShape";
export { CharacterSectionShapeUtil } from "./CharacterSectionShape";
export { StoryboardSectionShapeUtil } from "./StoryboardSectionShape";
export { VideoSectionShapeUtil } from "./VideoSectionShape";
export { ConnectorShapeUtil } from "./ConnectorShape";
export { SHAPE_TYPES } from "./types";
export type {
  OriginalPromptShape,
  ScriptSectionShape,
  CharacterSectionShape,
  StoryboardSectionShape,
  VideoSectionShape,
  ConnectorShape,
} from "./types";

// 所有自定义 Shape 工具类
export const customShapeUtils = [
  OriginalPromptShapeUtil,
  ScriptSectionShapeUtil,
  CharacterSectionShapeUtil,
  StoryboardSectionShapeUtil,
  VideoSectionShapeUtil,
  ConnectorShapeUtil,
];
