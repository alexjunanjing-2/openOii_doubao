from __future__ import annotations

import json

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.agents.prompts.character import SYSTEM_PROMPT
from app.agents.utils import extract_json
from app.models.project import Character, Shot


class CharacterAgent(BaseAgent):
    name = "character"

    def _character_to_description(self, item: dict) -> str:
        name = item.get("name", "")
        design_intent = item.get("design_intent")
        if isinstance(design_intent, str) and design_intent.strip():
            desc = design_intent.strip()
            if isinstance(name, str) and name.strip():
                return f"{name.strip()}，{desc}"
            return desc
        visual_design = item.get("visual_design")
        if isinstance(visual_design, dict) and visual_design:
            desc = json.dumps(visual_design, ensure_ascii=False)
            if isinstance(name, str) and name.strip():
                return f"{name.strip()}，{desc}"
            return desc
        desc = json.dumps(item, ensure_ascii=False)
        if isinstance(name, str) and name.strip():
            return f"{name.strip()}，{desc}"
        return desc

    def _build_image_prompt(self, item: dict) -> str:
        prompt = item.get("reference_image_prompt") or {}
        if not isinstance(prompt, dict):
            return json.dumps(item, ensure_ascii=False)

        positive = prompt.get("positive")
        negative = prompt.get("negative")
        parts: list[str] = []
        if isinstance(positive, str) and positive.strip():
            parts.append(positive.strip())
        if isinstance(negative, str) and negative.strip():
            parts.append(f"Negative: {negative.strip()}")
        if parts:
            return "\n".join(parts)
        return json.dumps(item, ensure_ascii=False)

    async def run(self, ctx: AgentContext) -> None:
        res = await ctx.session.execute(select(Character).where(Character.project_id == ctx.project.id))
        chars = res.scalars().all()
        if chars:
            return
        res = await ctx.session.execute(
            select(Shot).where(Shot.project_id == ctx.project.id).order_by(Shot.order.asc())
        )
        shots = res.scalars().all()

        user_prompt = json.dumps(
            {
                "project": {
                    "id": ctx.project.id,
                    "title": ctx.project.title,
                    "story": ctx.project.story,
                    "style": ctx.project.style,
                    "status": ctx.project.status,
                },
                "shots": [{"order": s.order, "description": s.description} for s in shots],
                "existing_characters": [],
                "style_mode": ctx.style_mode,
            },
            ensure_ascii=False,
        )

        resp = await self.call_llm(ctx, system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, max_tokens=4096)
        data = extract_json(resp.text)

        raw_characters = data.get("characters") or []
        if not isinstance(raw_characters, list) or not raw_characters:
            raise ValueError("LLM 响应未返回任何角色")

        new_characters: list[Character] = []
        for item in raw_characters:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not (isinstance(name, str) and name.strip()):
                continue

            image_prompt = self._build_image_prompt(item)
            image_url = await self.generate_and_cache_image(ctx, prompt=image_prompt)

            new_characters.append(
                Character(
                    project_id=ctx.project.id,
                    name=name.strip(),
                    description=self._character_to_description(item),
                    image_url=image_url,
                )
            )

        if not new_characters:
            raise ValueError("LLM 响应的角色列表为空或无效")

        ctx.session.add_all(new_characters)
        await ctx.session.commit()
        await self.send_message(ctx, f"已生成 {len(new_characters)} 个角色。")
