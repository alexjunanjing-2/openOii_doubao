from __future__ import annotations

import json

from app.agents.base import AgentContext, BaseAgent
from app.agents.prompts.director import SYSTEM_PROMPT
from app.agents.utils import extract_json, utcnow


class DirectorAgent(BaseAgent):
    name = "director"

    async def run(self, ctx: AgentContext) -> None:
        # 发送开始消息
        await self.send_message(ctx, "🎬 正在进行导演规划...", progress=0.0, is_loading=True)
        await ctx.session.commit()  # Release lock before LLM call

        user_prompt_data = {
            "project": {
                "id": ctx.project.id,
                "title": ctx.project.title,
                "story": ctx.project.story,
                "style": ctx.project.style,
                "status": ctx.project.status,
            }
        }

        # 添加 onboarding 输出（如果有）
        if ctx.onboarding_output:
            user_prompt_data["onboarding_output"] = ctx.onboarding_output
            print(f"[Director] 已加载 onboarding 输出")

        user_prompt = json.dumps(user_prompt_data, ensure_ascii=False)

        print(f"[Director] 开始调用LLM进行导演规划，项目ID: {ctx.project.id}, 标题: {ctx.project.title}")
        resp = await self.call_llm(ctx, system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, max_tokens=4096)
        print(f"[Director] LLM响应已收到，开始解析规划数据")
        data = extract_json(resp.text)
        print(f"[Director] 规划数据解析完成，开始处理各部分内容")

        # 提取导演规划信息
        lines = []

        # 视觉风格
        project_update = data.get("project_update") or {}
        if isinstance(project_update, dict):
            print(f"[Director] 处理视觉风格和状态更新")
            style = project_update.get("style")
            status = project_update.get("status")
            if isinstance(style, str) and style.strip():
                ctx.project.style = style.strip()
                lines.append(f"🎨 视觉风格：{ctx.project.style}")
            if isinstance(status, str) and status.strip():
                ctx.project.status = status.strip()

        # 导演笔记
        director_notes = data.get("director_notes") or {}
        if isinstance(director_notes, dict):
            print(f"[Director] 处理导演笔记")
            vision = director_notes.get("vision")
            if vision:
                lines.append(f"🎯 创作愿景：{vision}")

            pacing = director_notes.get("pacing")
            if pacing:
                lines.append(f"⏱️ 节奏把控：{pacing}")

            mood = director_notes.get("mood")
            if mood:
                lines.append(f"🌙 情绪基调：{mood}")

        # 剧情大纲 - 显示故事段落
        scene_outline = data.get("scene_outline") or []
        if isinstance(scene_outline, list) and scene_outline:
            print(f"[Director] 处理剧情大纲，共 {len(scene_outline)} 个段落")
            lines.append(f"📋 剧情大纲：共 {len(scene_outline)} 个段落")
            for i, scene in enumerate(scene_outline):
                if isinstance(scene, dict):
                    title = scene.get("title") or scene.get("description", "")[:30]
                    if title:
                        lines.append(f"   {i+1}. {title}")

        # 发送规划结果
        if lines:
            print(f"[Director] 准备发送规划结果，共 {len(lines)} 条信息")
            await self.send_message(ctx, "\n".join(lines))

        print(f"[Director] 开始保存项目更新到数据库")
        ctx.project.updated_at = utcnow()
        ctx.session.add(ctx.project)
        await ctx.session.commit()
        print(f"[Director] 项目更新已保存到数据库")

        await self.send_message(ctx, f"✅ 导演规划完成，接下来将由编剧创作详细剧本。", progress=1.0)
