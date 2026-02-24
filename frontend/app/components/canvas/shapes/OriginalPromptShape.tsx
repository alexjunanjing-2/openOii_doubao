import {
  HTMLContainer,
  Rectangle2d,
  ShapeUtil,
  T,
  type Geometry2d,
  type RecordProps,
} from "tldraw";
import { type OriginalPromptShape } from "./types";
import { LightBulbIcon } from "@heroicons/react/24/outline";

export class OriginalPromptShapeUtil extends ShapeUtil<OriginalPromptShape> {
  static override type = "original-prompt" as const;

  static override props: RecordProps<OriginalPromptShape> = {
    w: T.number,
    h: T.number,
    story: T.string,
    style: T.string,
  };

  getDefaultProps(): OriginalPromptShape["props"] {
    return {
      w: 800,
      h: 300,
      story: "",
      style: "",
    };
  }

  override canEdit() {
    return false;
  }

  override canResize() {
    return false;
  }

  override hideSelectionBoundsFg() {
    return true;
  }

  override hideSelectionBoundsBg() {
    return true;
  }

  getGeometry(shape: OriginalPromptShape): Geometry2d {
    return new Rectangle2d({
      width: shape.props.w,
      height: shape.props.h,
      isFilled: true,
    });
  }

  component(shape: OriginalPromptShape) {
    const { story, style } = shape.props;

    return (
      <HTMLContainer
        style={{
          width: shape.props.w,
          height: shape.props.h,
          pointerEvents: "all",
        }}
        className="h-full"
      >
        <OriginalPromptContent
          story={story}
          style={style}
        />
      </HTMLContainer>
    );
  }

  indicator() {
    return null;
  }
}

function OriginalPromptContent({
  story,
  style,
}: {
  story: string | null;
  style: string | null;
}) {
  return (
    <div className="card-doodle bg-base-100 p-5 h-full">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
          <LightBulbIcon className="w-4 h-4 text-primary" />
        </div>
        <h2 className="text-lg font-heading font-bold text-base-content">原始提示词</h2>
      </div>

      {story && story.trim() && (
        <div className="mb-4">
          <h3 className="text-sm font-bold text-base-content mb-2">用户输入</h3>
          <div className="bg-base-200 rounded-lg p-3">
            <p className="text-sm text-base-content/80 whitespace-pre-wrap">{story}</p>
          </div>
        </div>
      )}

      {style && style.trim() && style !== "anime" && (
        <div>
          <h3 className="text-sm font-bold text-base-content mb-2">风格设定</h3>
          <div className="bg-base-200 rounded-lg p-3">
            <p className="text-sm text-base-content/80 whitespace-pre-wrap">{style}</p>
          </div>
        </div>
      )}

      {(!story || !story.trim()) && (!style || !style.trim() || style === "anime") && (
        <div className="text-center py-8 text-base-content/50">
          <p className="text-sm">等待原始提示词...</p>
        </div>
      )}
    </div>
  );
}
