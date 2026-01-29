import {
  ShapeUtil,
  T,
  type Geometry2d,
  type RecordProps,
  Polyline2d,
  Vec,
} from "tldraw";
import { type ConnectorShape } from "./types";

export class ConnectorShapeUtil extends ShapeUtil<ConnectorShape> {
  static override type = "connector" as const;

  static override props: RecordProps<ConnectorShape> = {
    start: T.any,
    end: T.any,
  };

  getDefaultProps(): ConnectorShape["props"] {
    return {
      start: { x: 0, y: 0 },
      end: { x: 0, y: 100 },
    };
  }

  override canSelect() {
    return false;
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
    const { start, end } = shape.props;
    return new Polyline2d({
      points: [new Vec(start.x, start.y), new Vec(end.x, end.y)],
    });
  }

  component(shape: ConnectorShape) {
    const { start, end } = shape.props;

    // 计算贝塞尔曲线控制点
    const midY = (start.y + end.y) / 2;
    const controlPoint1 = { x: start.x, y: midY };
    const controlPoint2 = { x: end.x, y: midY };

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

  indicator() {
    return null;
  }
}
