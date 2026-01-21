from __future__ import annotations

import json

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.agents.prompts.storyboard import SYSTEM_PROMPT
from app.agents.utils import extract_json
from app.models.project import Character, Scene, Shot


class StoryboardAgent(BaseAgent):
    name = "storyboard"

    async def run(self, ctx: AgentContext) -> None:
        res = await ctx.session.execute(
            select(Scene).where(Scene.project_id == ctx.project.id).order_by(Scene.order.asc())
        )
        scenes = res.scalars().all()
        if not scenes:
            return

        scenes_by_order = {s.order: s for s in scenes}
        missing_scene_orders: list[int] = []
        for scene in scenes:
            existing = await ctx.session.execute(select(Shot).where(Shot.scene_id == scene.id))
            if existing.scalars().first():
                continue
            missing_scene_orders.append(scene.order)

        if not missing_scene_orders:
            return

        res = await ctx.session.execute(select(Character).where(Character.project_id == ctx.project.id))
        characters = res.scalars().all()

        user_prompt = json.dumps(
            {
                "project": {
                    "id": ctx.project.id,
                    "title": ctx.project.title,
                    "story": ctx.project.story,
                    "style": ctx.project.style,
                    "status": ctx.project.status,
                },
                "characters": [
                    {"name": c.name, "description": c.description, "image_url": c.image_url} for c in characters
                ],
                "scenes": [{"order": s.order, "description": s.description} for s in scenes],
            },
            ensure_ascii=False,
        )

        resp = await self.call_llm(ctx, system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, max_tokens=4096)
        data = extract_json(resp.text)

        project_update = data.get("project_update") or {}
        if isinstance(project_update, dict):
            status = project_update.get("status")
            if isinstance(status, str) and status.strip():
                ctx.project.status = status.strip()
                ctx.session.add(ctx.project)

        raw_scenes = data.get("scenes") or []
        if not isinstance(raw_scenes, list) or not raw_scenes:
            raise ValueError("LLM 响应未返回任何分镜场景")

        new_shots: list[Shot] = []
        for item in raw_scenes:
            if not isinstance(item, dict):
                continue
            scene_order = item.get("scene_order")
            if not (isinstance(scene_order, int) and scene_order > 0):
                continue
            if scene_order not in missing_scene_orders:
                continue
            scene = scenes_by_order.get(scene_order)
            if scene is None:
                continue

            raw_shots = item.get("shots") or []
            if not isinstance(raw_shots, list):
                continue

            for shot_item in raw_shots:
                if not isinstance(shot_item, dict):
                    continue
                order = shot_item.get("order")
                description = shot_item.get("description")
                prompt = shot_item.get("prompt")
                duration = shot_item.get("duration")

                if not (isinstance(order, int) and order > 0):
                    continue
                if not (isinstance(description, str) and description.strip()):
                    continue
                if not (isinstance(prompt, str) and prompt.strip()):
                    continue
                dur = float(duration) if isinstance(duration, (int, float)) else 5.0

                video_url = await ctx.video.generate_url(prompt=prompt.strip(), duration=dur)

                new_shots.append(
                    Shot(
                        scene_id=scene.id,
                        order=order,
                        description=description.strip(),
                        prompt=prompt.strip(),
                        duration=dur,
                        video_url=video_url,
                    )
                )

        if not new_shots:
            raise ValueError("LLM 响应的分镜列表为空或无效")

        ctx.session.add_all(new_shots)
        await ctx.session.commit()
        await self.send_message(ctx, f"已生成 {len(new_shots)} 个镜头。")
