import {
  ShapeUtil,
  T,
  type Geometry2d,
  type RecordProps,
  Polyline2d,
  Vec,
  type TLShapeId,
  useEditor,
  useValue,
} from "tldraw";
import { type ConnectorShape } from "./types";

export class ConnectorShapeUtil extends ShapeUtil<ConnectorShape> {
  static override type = "connector" as const;

  static override props: RecordProps<ConnectorShape> = {
    fromId: T.string,
    toId: T.string,
  };

  getDefaultProps(): ConnectorShape["props"] {
    return {
      fromId: "",
      toId: "",
    };
  }

  override canEdit() {
    return false;
  }

  override canResize() {
    return false;
  }

  override canBind() {
    return false;
  }

  override hideSelectionBoundsFg() {
    return true;
  }

  override hideSelectionBoundsBg() {
    return true;
  }

  getGeometry(shape: ConnectorShape): Geometry2d {
    // 获取连接的 shapes
    const fromShape = this.editor.getShape(shape.props.fromId as TLShapeId);
    const toShape = this.editor.getShape(shape.props.toId as TLShapeId);

    if (!fromShape || !toShape) {
      return new Polyline2d({ points: [new Vec(0, 0), new Vec(0, 100)] });
    }

    const fromBounds = this.editor.getShapeGeometry(fromShape).bounds;
    const toBounds = this.editor.getShapeGeometry(toShape).bounds;

    const startX = fromShape.x + fromBounds.w / 2;
    const startY = fromShape.y + fromBounds.h;
    const endX = toShape.x + toBounds.w / 2;
    const endY = toShape.y;

    return new Polyline2d({
      points: [new Vec(startX, startY), new Vec(endX, endY)],
    });
  }

  component(shape: ConnectorShape) {
    return <ConnectorComponent shape={shape} />;
  }

  indicator() {
    return null;
  }
}

// 独立组件以使用 React hooks
function ConnectorComponent({ shape }: { shape: ConnectorShape }) {
  const editor = useEditor();

  // 响应式获取连接的 shapes
  const fromShape = useValue(
    "fromShape",
    () => editor.getShape(shape.props.fromId as TLShapeId),
    [shape.props.fromId]
  );

  const toShape = useValue(
    "toShape",
    () => editor.getShape(shape.props.toId as TLShapeId),
    [shape.props.toId]
  );

  if (!fromShape || !toShape) {
    return null;
  }

  // 获取 bounds
  const fromBounds = editor.getShapeGeometry(fromShape).bounds;
  const toBounds = editor.getShapeGeometry(toShape).bounds;

  // 计算连接点：from 的底部中心 -> to 的顶部中心
  const start = {
    x: fromShape.x + fromBounds.w / 2,
    y: fromShape.y + fromBounds.h,
  };
  const end = {
    x: toShape.x + toBounds.w / 2,
    y: toShape.y,
  };

  // 计算贝塞尔曲线控制点 - 更明显的 S 形曲线
  const gapY = end.y - start.y;
  const curveOffset = Math.min(60, gapY * 0.4); // 水平偏移量
  const controlPoint1 = { x: start.x - curveOffset, y: start.y + gapY * 0.3 };
  const controlPoint2 = { x: end.x + curveOffset, y: end.y - gapY * 0.3 };

  const pathD = `M ${start.x} ${start.y} C ${controlPoint1.x} ${controlPoint1.y}, ${controlPoint2.x} ${controlPoint2.y}, ${end.x} ${end.y}`;

  return (
    <svg
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        overflow: "visible",
        pointerEvents: "none",
      }}
    >
      {/* 连接线 */}
      <path
        d={pathD}
        fill="none"
        stroke="oklch(var(--bc) / 0.3)"
        strokeWidth={2}
        strokeDasharray="6 4"
      />
      {/* 起点圆点 */}
      <circle
        cx={start.x}
        cy={start.y}
        r={4}
        fill="oklch(var(--b1))"
        stroke="oklch(var(--bc) / 0.3)"
        strokeWidth={2}
      />
      {/* 终点圆点 */}
      <circle
        cx={end.x}
        cy={end.y}
        r={4}
        fill="oklch(var(--b1))"
        stroke="oklch(var(--bc) / 0.3)"
        strokeWidth={2}
      />
    </svg>
  );
}
