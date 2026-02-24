from __future__ import annotations

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.models.project import Shot


class StoryboardAgent(BaseAgent):
    name = "storyboard"

    async def run(self, ctx: AgentContext) -> None:
        res = await ctx.session.execute(
            select(Shot).where(Shot.project_id == ctx.project.id).order_by(Shot.order.asc())
        )
        shots = list(res.scalars().all())
        if not shots:
            return

        # 获取默认时长
        if ctx.settings.video_provider == "doubao":
            if ctx.settings.doubao_video_fixed_duration:
                default_duration = float(ctx.settings.doubao_video_duration)
            else:
                default_duration = -1
        else:
            default_duration = 5.0

        updated: list[Shot] = []
        for shot in shots:
            changed = False
            if not shot.prompt:
                shot.prompt = shot.description
                changed = True
            if not shot.image_prompt:
                shot.image_prompt = shot.description
                changed = True
            if shot.duration is None:
                shot.duration = default_duration
                changed = True
            if changed:
                ctx.session.add(shot)
                updated.append(shot)

        if not updated:
            return

        await ctx.session.commit()
        for shot in updated:
            await self.send_shot_event(ctx, shot, "shot_updated")
        await self.send_message(ctx, f"已补全 {len(updated)} 个分镜的提示词/时长。")
