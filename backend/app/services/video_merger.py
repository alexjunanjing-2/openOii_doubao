"""视频拼接服务

使用 ffmpeg 将多个视频片段拼接成一个完整视频。
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid
from pathlib import Path

import httpx

from app.services.file_cleaner import STATIC_DIR

logger = logging.getLogger(__name__)

# 输出目录（相对于 backend 目录）
OUTPUT_DIR = STATIC_DIR / "videos"


class VideoMergerService:
    """视频拼接服务

    使用 ffmpeg 的 concat demuxer 拼接多个视频文件。
    """

    def __init__(self, output_dir: Path | None = None):
        """初始化视频拼接服务

        Args:
            output_dir: 输出目录，默认为 backend/app/static/videos
        """
        self.output_dir = output_dir or OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端（连接复用）"""
        if self._client is None or self._client.is_closed:
            timeout = httpx.Timeout(300.0, connect=30.0)  # 5分钟超时
            self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def download_video(self, url: str, dest_path: Path) -> bool:
        """下载视频文件

        Args:
            url: 视频 URL
            dest_path: 目标路径

        Returns:
            bool: 下载是否成功且文件存在
        """
        print(f"[VideoMerger] 开始下载视频: {url[:100]}...")
        try:
            client = await self._get_client()
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                    # 强制刷新文件缓冲区到磁盘
                    f.flush()
                    os.fsync(f.fileno())

            # 验证文件是否存在且不为空
            file_exists = dest_path.exists()
            file_size = dest_path.stat().st_size if file_exists else 0
            
            print(f"[VideoMerger] 文件检查: 存在={file_exists}, 大小={file_size}")
            
            if not file_exists or file_size == 0:
                logger.error(f"Downloaded file {dest_path} is empty or missing")
                print(f"[VideoMerger] 下载失败，文件为空或不存在: {dest_path}")
                return False

            logger.info(f"Downloaded video to {dest_path}")
            print(f"[VideoMerger] 视频下载完成: {dest_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download video {url}: {e}")
            print(f"[VideoMerger] 下载异常: {e}")
            return False

    async def merge_videos(
        self,
        video_urls: list[str],
        output_filename: str | None = None,
    ) -> str:
        """拼接多个视频

        Args:
            video_urls: 视频 URL 列表
            output_filename: 输出文件名（不含扩展名），默认自动生成

        Returns:
            拼接后视频的本地路径（相对于 static 目录）
        """
        if not video_urls:
            raise ValueError("No video URLs provided")

        if len(video_urls) == 1:
            # 只有一个视频，直接返回
            return video_urls[0]

        # 生成输出文件名
        if not output_filename:
            output_filename = f"merged_{uuid.uuid4().hex[:8]}"

        output_path = self.output_dir / f"{output_filename}.mp4"

        # 使用项目静态目录下的临时视频目录（不使用系统临时目录）
        temp_dir = STATIC_DIR / "temp_videos"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 为本次合并创建一个唯一的子目录
        session_id = uuid.uuid4().hex[:12]
        session_dir = temp_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[VideoMerger] 使用临时目录: {session_dir}")

        try:
            downloaded_files: list[Path] = []

            # 并行下载所有视频
            logger.info(f"Downloading {len(video_urls)} videos...")
            download_tasks = []
            for i, url in enumerate(video_urls):
                # 从 URL 推断扩展名，默认 mp4
                ext = ".mp4"
                if "." in url.split("/")[-1].split("?")[0]:
                    ext = "." + url.split("/")[-1].split("?")[0].split(".")[-1]

                dest = session_dir / f"video_{i:03d}{ext}"
                downloaded_files.append(dest)
                download_tasks.append(self.download_video(url, dest))

            results = await asyncio.gather(*download_tasks)
            logger.info(f"All {len(video_urls)} videos downloaded processing finished")
            print(f"[VideoMerger] 下载任务完成，共 {len(results)} 个任务")

            # 过滤下载成功的文件
            valid_files: list[Path] = []
            for i, success in enumerate(results):
                file_path = downloaded_files[i]
                file_exists = file_path.exists()
                file_size = file_path.stat().st_size if file_exists else 0
                print(f"[VideoMerger] 视频 {i}: URL={video_urls[i][:60]}..., 下载结果={success}, 文件存在={file_exists}, 文件大小={file_size}")
                
                if success and file_exists and file_size > 0:
                    valid_files.append(file_path)
                else:
                    logger.warning(f"Skipping failed or missing video: {video_urls[i]}")
                    print(f"[VideoMerger] 跳过无效视频: {video_urls[i][:60]}...")

            print(f"[VideoMerger] 有效视频数量: {len(valid_files)}/{len(video_urls)}")

            if not valid_files:
                raise RuntimeError("No valid videos to merge")

            logger.info(f"Merging {len(valid_files)} valid videos")
            print(f"[VideoMerger] 准备合并 {len(valid_files)} 个有效视频")

            # 二次确认所有文件都存在
            final_valid_files: list[Path] = []
            for video_file in valid_files:
                if video_file.exists() and video_file.stat().st_size > 0:
                    final_valid_files.append(video_file)
                else:
                    logger.warning(f"File {video_file} disappeared or became empty before merge")
                    print(f"[VideoMerger] 文件在合并前消失或为空: {video_file}")
            
            if not final_valid_files:
                raise RuntimeError("No valid videos to merge (pre-merge check failed)")
            
            print(f"[VideoMerger] 最终确认有效视频数量: {len(final_valid_files)}")

            # 创建 ffmpeg concat 文件列表
            concat_file = session_dir / "concat.txt"
            with open(concat_file, "w") as f:
                for video_file in final_valid_files:
                    # ffmpeg concat 格式需要转义单引号
                    escaped_path = str(video_file).replace("'", "'\\''")
                    f.write(f"file '{escaped_path}'\n")

            # 使用 ffmpeg 拼接视频
            # -f concat: 使用 concat demuxer
            # -safe 0: 允许绝对路径
            # -c copy: 直接复制流，不重新编码（快速）
            # 如果视频格式不一致，需要重新编码
            cmd = [
                "ffmpeg",
                "-y",  # 覆盖输出文件
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",  # 尝试直接复制
                str(output_path),
            ]

            logger.info(f"Running ffmpeg: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                # 如果直接复制失败，尝试重新编码
                logger.warning(f"ffmpeg copy failed, trying re-encode: {stderr.decode()}")

                cmd_reencode = [
                    "ffmpeg",
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_file),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-movflags", "+faststart",
                    str(output_path),
                ]

                logger.info(f"Running ffmpeg (re-encode): {' '.join(cmd_reencode)}")

                process = await asyncio.create_subprocess_exec(
                    *cmd_reencode,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    raise RuntimeError(f"ffmpeg failed: {stderr.decode()}")

            logger.info(f"Video merged successfully: {output_path}")

            # 清理临时目录（只在成功时清理）
            if session_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(session_dir)
                    print(f"[VideoMerger] 已清理临时目录: {session_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp directory {session_dir}: {e}")
                    print(f"[VideoMerger] 清理临时目录失败: {e}")

        except Exception as e:
            # 发生异常时，保留临时目录用于调试
            logger.error(f"Video merge failed: {e}")
            print(f"[VideoMerger] 合并失败，保留临时目录用于调试: {session_dir}")
            raise

        # 返回相对路径（用于构建 URL）
        return f"/static/videos/{output_filename}.mp4"


# 全局单例
_merger_service: VideoMergerService | None = None


def get_video_merger_service() -> VideoMergerService:
    """获取视频拼接服务单例"""
    global _merger_service
    if _merger_service is None:
        _merger_service = VideoMergerService()
    return _merger_service
