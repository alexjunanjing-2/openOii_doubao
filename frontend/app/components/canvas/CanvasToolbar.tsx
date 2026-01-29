import { useCallback } from "react";
import { track, useEditor } from "tldraw";
import {
  HandRaisedIcon,
  CursorArrowRaysIcon,
  MagnifyingGlassPlusIcon,
  MagnifyingGlassMinusIcon,
  ArrowsPointingOutIcon,
} from "@heroicons/react/24/outline";

interface CanvasToolbarProps {
  className?: string;
}

export const CanvasToolbar = track(function CanvasToolbar({
  className,
}: CanvasToolbarProps) {
  const editor = useEditor();

  // 获取当前工具和缩放级别
  const currentTool = editor.getCurrentToolId();
  const zoom = editor.getZoomLevel();
  const zoomPercent = Math.round(zoom * 100);

  // 工具切换
  const handleSelectTool = useCallback(() => {
    editor.setCurrentTool("select");
  }, [editor]);

  const handleHandTool = useCallback(() => {
    editor.setCurrentTool("hand");
  }, [editor]);

  // 缩放操作
  const handleZoomIn = useCallback(() => {
    editor.zoomIn(editor.getViewportScreenCenter(), { animation: { duration: 200 } });
  }, [editor]);

  const handleZoomOut = useCallback(() => {
    editor.zoomOut(editor.getViewportScreenCenter(), { animation: { duration: 200 } });
  }, [editor]);

  const handleZoomToFit = useCallback(() => {
    editor.zoomToFit({ animation: { duration: 300 } });
  }, [editor]);

  const handleZoomReset = useCallback(() => {
    editor.resetZoom(editor.getViewportScreenCenter(), { animation: { duration: 200 } });
  }, [editor]);

  return (
    <div
      className={`absolute bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-1 p-1.5 rounded-xl bg-base-100/90 backdrop-blur-sm border-2 border-base-content/20 shadow-brutal text-base-content ${className || ""}`}
    >
      {/* 选择工具 */}
      <div className="tooltip tooltip-top" data-tip="选择工具 (V)">
        <button
          className={`btn btn-sm btn-square ${
            currentTool === "select" ? "btn-primary" : "btn-ghost text-base-content"
          }`}
          onClick={handleSelectTool}
          aria-label="选择工具"
        >
          <CursorArrowRaysIcon className="w-5 h-5" />
        </button>
      </div>

      {/* 抓手工具 */}
      <div className="tooltip tooltip-top" data-tip="抓手工具 (H)">
        <button
          className={`btn btn-sm btn-square ${
            currentTool === "hand" ? "btn-primary" : "btn-ghost text-base-content"
          }`}
          onClick={handleHandTool}
          aria-label="抓手工具"
        >
          <HandRaisedIcon className="w-5 h-5" />
        </button>
      </div>

      {/* 分隔线 */}
      <div className="w-px h-6 bg-base-content/20 mx-1" />

      {/* 缩小 */}
      <div className="tooltip tooltip-top" data-tip="缩小">
        <button
          className="btn btn-sm btn-square btn-ghost text-base-content"
          onClick={handleZoomOut}
          aria-label="缩小"
        >
          <MagnifyingGlassMinusIcon className="w-5 h-5" />
        </button>
      </div>

      {/* 缩放百分比 */}
      <div className="tooltip tooltip-top" data-tip="重置缩放">
        <button
          className="btn btn-sm btn-ghost min-w-[60px] font-mono text-sm text-base-content"
          onClick={handleZoomReset}
          aria-label="重置缩放"
        >
          {zoomPercent}%
        </button>
      </div>

      {/* 放大 */}
      <div className="tooltip tooltip-top" data-tip="放大">
        <button
          className="btn btn-sm btn-square btn-ghost text-base-content"
          onClick={handleZoomIn}
          aria-label="放大"
        >
          <MagnifyingGlassPlusIcon className="w-5 h-5" />
        </button>
      </div>

      {/* 分隔线 */}
      <div className="w-px h-6 bg-base-content/20 mx-1" />

      {/* 适应视图 */}
      <div className="tooltip tooltip-top" data-tip="适应视图">
        <button
          className="btn btn-sm btn-square btn-ghost text-base-content"
          onClick={handleZoomToFit}
          aria-label="适应视图"
        >
          <ArrowsPointingOutIcon className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
});
