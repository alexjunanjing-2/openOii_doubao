import {
  HTMLContainer,
  Rectangle2d,
  ShapeUtil,
  T,
  type Geometry2d,
  type RecordProps,
} from "tldraw";
import { type VideoSectionShape } from "./types";
import { FireIcon, VideoCameraIcon } from "@heroicons/react/24/outline";

export class VideoSectionShapeUtil extends ShapeUtil<VideoSectionShape> {
  static override type = "video-section" as const;

  static override props: RecordProps<VideoSectionShape> = {
    w: T.number,
    h: T.number,
    videoUrl: T.string,
    title: T.string,
  };

  getDefaultProps(): VideoSectionShape["props"] {
    return {
      w: 600,
      h: 450,
      videoUrl: "",
      title: "最终视频",
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

  getGeometry(shape: VideoSectionShape): Geometry2d {
    return new Rectangle2d({
      width: shape.props.w,
      height: shape.props.h,
      isFilled: true,
    });
  }

  component(shape: VideoSectionShape) {
    const { videoUrl, title } = shape.props;

    const handleDownload = async (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      try {
        const response = await fetch(videoUrl);
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${title || "video"}.mp4`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } catch (err) {
        console.error("下载失败:", err);
        window.open(videoUrl, "_blank");
      }
    };

    return (
      <HTMLContainer
        style={{
          width: shape.props.w,
          pointerEvents: "all",
        }}
      >
        <div className="card-doodle bg-base-100 p-5">
          {/* 标题栏 */}
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-full bg-error/20 flex items-center justify-center">
              <FireIcon className="w-4 h-4 text-error" />
            </div>
            <h2 className="text-lg font-heading font-bold text-base-content">艺术总监</h2>
          </div>

          {/* 视频播放器 */}
          {videoUrl ? (
            <div className="relative">
              <video
                className="w-full rounded-lg bg-black"
                src={videoUrl}
                controls
                onPointerDown={(e) => e.stopPropagation()}
              />
              {/* 下载按钮 */}
              <button
                onClick={handleDownload}
                onPointerDown={(e) => e.stopPropagation()}
                className="mt-3 w-full btn btn-outline btn-primary gap-2"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="w-4 h-4"
                >
                  <path d="M10.75 2.75a.75.75 0 0 0-1.5 0v8.614L6.295 8.235a.75.75 0 1 0-1.09 1.03l4.25 4.5a.75.75 0 0 0 1.09 0l4.25-4.5a.75.75 0 0 0-1.09-1.03l-2.955 3.129V2.75Z" />
                  <path d="M3.5 12.75a.75.75 0 0 0-1.5 0v2.5A2.75 2.75 0 0 0 4.75 18h10.5A2.75 2.75 0 0 0 18 15.25v-2.5a.75.75 0 0 0-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5Z" />
                </svg>
                导出视频
              </button>
            </div>
          ) : (
            <div className="text-center py-12 text-base-content/50">
              <VideoCameraIcon className="w-16 h-16 mx-auto mb-3 opacity-30" />
              <p className="text-sm">等待视频合成...</p>
            </div>
          )}
        </div>
      </HTMLContainer>
    );
  }

  indicator() {
    return null;
  }
}
