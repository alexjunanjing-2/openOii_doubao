from __future__ import annotations

import json

from app.agents.base import AgentContext, BaseAgent
from app.agents.prompts.onboarding import SYSTEM_PROMPT
from app.agents.utils import extract_json, utcnow


class OnboardingAgent(BaseAgent):
    name = "onboarding"

    async def run(self, ctx: AgentContext) -> None:
        # 发送开始消息
        await self.send_message(ctx, "正在分析故事...", progress=0.0, is_loading=True)

        user_prompt = json.dumps(
            {
                "project": {
                    "id": ctx.project.id,
                    "title": ctx.project.title,
                    "story": ctx.project.story,
                    "style": ctx.project.style,
                    "status": ctx.project.status,
                }
            },
            ensure_ascii=False,
        )

        resp = await self.call_llm(ctx, system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, max_tokens=4096)
        data = extract_json(resp.text)

        # 提取并显示故事分析结果
        story_breakdown = data.get("story_breakdown") or {}
        key_elements = data.get("key_elements") or {}
        style_rec = data.get("style_recommendation") or {}

        # 构建简洁的分析结果消息
        lines = []

        # 一句话概括
        logline = story_breakdown.get("logline")
        if logline:
            lines.append(f"📖 故事概括：{logline}")

        # 类型和主题
        genre = story_breakdown.get("genre") or []
        themes = story_breakdown.get("themes") or []
        if genre or themes:
            parts = []
            if genre:
                parts.append(f"类型：{', '.join(genre)}")
            if themes:
                parts.append(f"主题：{', '.join(themes)}")
            lines.append(f"🎭 {' | '.join(parts)}")

        # 场景和基调
        setting = story_breakdown.get("setting")
        tone = story_breakdown.get("tone")
        if setting or tone:
            parts = []
            if setting:
                parts.append(f"场景：{setting}")
            if tone:
                parts.append(f"基调：{tone}")
            lines.append(f"🌍 {' | '.join(parts)}")

        # 角色
        characters = key_elements.get("characters") or []
        if characters:
            lines.append(f"👥 角色：{', '.join(characters)}")  # 显示全部角色

        # 视觉风格推荐
        primary_style = style_rec.get("primary")
        if primary_style:
            lines.append(f"🎨 推荐风格：{primary_style}")
            rationale = style_rec.get("rationale")
            if rationale:
                lines.append(f"   {rationale}")

        # 发送分析结果
        if lines:
            await self.send_message(ctx, "\n".join(lines))

        # 更新项目信息
        project_update = data.get("project_update") or {}
        updated_fields: dict = {}

        if isinstance(project_update, dict):
            title = project_update.get("title")
            story = project_update.get("story")
            style = project_update.get("style")

            if isinstance(title, str) and title.strip():
                ctx.project.title = title.strip()
                updated_fields["title"] = ctx.project.title
            if isinstance(story, str) and story.strip():
                ctx.project.story = story.strip()
                updated_fields["story"] = ctx.project.story
            if isinstance(style, str) and style.strip():
                ctx.project.style = style.strip()
                updated_fields["style"] = ctx.project.style

        ctx.project.status = "planning"
        updated_fields["status"] = ctx.project.status
        ctx.project.updated_at = utcnow()
        ctx.session.add(ctx.project)
        await ctx.session.commit()

        # 发送 project_updated 事件，通知前端刷新标题等信息
        if updated_fields:
            await ctx.ws.send_event(
                ctx.project.id,
                {
                    "type": "project_updated",
                    "data": {
                        "project": {
                            "id": ctx.project.id,
                            **updated_fields,
                        }
                    },
                },
            )

        # 发送完成消息
        title_msg = f"「{ctx.project.title}」" if ctx.project.title else ""
        await self.send_message(ctx, f"✅ 项目初始化完成{title_msg}，接下来将由导演进行详细规划。", progress=1.0)
