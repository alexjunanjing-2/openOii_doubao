from __future__ import annotations

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.models.project import Scene, Shot


class VideoMergerAgent(BaseAgent):
    """拼接所有分镜视频为完整视频"""
    name = "video_merger"

    async def run(self, ctx: AgentContext) -> None:
        # 检查项目是否已有最终视频
        if ctx.project.video_url:
            await self.send_message(ctx, "项目已有最终视频。")
            return

        # 获取所有带视频的 Shot，按场景和镜头顺序排序
        res = await ctx.session.execute(
            select(Shot)
            .join(Scene, Shot.scene_id == Scene.id)
            .where(
                Scene.project_id == ctx.project.id,
                Shot.video_url.isnot(None)
            )
            .order_by(Scene.order.asc(), Shot.order.asc())
        )
        shots = res.scalars().all()

        if not shots:
            await self.send_message(ctx, "没有可拼接的分镜视频，请先生成各分镜视频。")
            return

        # 收集视频 URL
        video_urls = [shot.video_url for shot in shots if shot.video_url]

        if not video_urls:
            await self.send_message(ctx, "没有有效的视频 URL 可拼接。")
            return

        try:
            # 发送开始消息
            await self.send_message(
                ctx,
                f"🎞️ 开始拼接 {len(video_urls)} 个分镜视频...",
                progress=0.0,
                is_loading=True
            )

            # 调用视频服务拼接
            merged_url = await ctx.video.merge_urls(video_urls)

            # 更新项目
            ctx.project.video_url = merged_url
            ctx.session.add(ctx.project)
            await ctx.session.commit()

            # 发送 project_updated 事件，通知前端刷新
            await ctx.ws.send_event(
                ctx.project.id,
                {
                    "type": "project_updated",
                    "data": {
                        "project": {
                            "id": ctx.project.id,
                            "video_url": merged_url,
                        }
                    },
                },
            )

            # 发送完成消息
            await self.send_message(
                ctx,
                f"🎉 漫剧制作完成！已将 {len(video_urls)} 个分镜拼接为完整视频。",
                progress=1.0,
                is_loading=False
            )
        except Exception as e:
            # 合并失败不影响整体流程
            await self.send_message(
                ctx,
                f"视频拼接失败: {e}。您可以稍后手动拼接。",
                progress=1.0,
                is_loading=False
            )
