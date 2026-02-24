from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent, TargetIds
from app.agents.prompts.review import SYSTEM_PROMPT
from app.agents.utils import extract_json
from app.models.agent_run import AgentMessage
from app.models.project import Character, Shot


ALLOWED_START_AGENTS = {
    "scriptwriter",
    "character_artist",
    "storyboard_artist",
    "video_generator",
    "video_merger",
}


def _fallback_start_agent(feedback_type: str | None) -> str:
    if feedback_type == "character":
        return "character_artist"
    if feedback_type == "shot":
        return "storyboard_artist"
    if feedback_type == "video":
        return "video_generator"
    # scene|style|story|general|unknown
    return "scriptwriter"


class ReviewAgent(BaseAgent):
    name = "review"

    async def _get_latest_feedback(self, ctx: AgentContext) -> str:
        res = await ctx.session.execute(
            select(AgentMessage)
            .where(AgentMessage.run_id == ctx.run.id)
            .where(AgentMessage.role == "user")
            .order_by(AgentMessage.created_at.desc())
            .limit(1)
        )
        msg = res.scalars().first()
        return msg.content if msg else ""

    async def _get_project_state(self, ctx: AgentContext) -> dict[str, Any]:
        char_res = await ctx.session.execute(select(Character).where(Character.project_id == ctx.project.id))
        characters = list(char_res.scalars().all())

        shot_res = await ctx.session.execute(
            select(Shot)
            .where(Shot.project_id == ctx.project.id)
            .order_by(Shot.order.asc())
        )
        shots = list(shot_res.scalars().all())

        return {
            "project": {
                "id": ctx.project.id,
                "title": ctx.project.title,
                "story": ctx.project.story,
                "style": ctx.project.style,
                "status": ctx.project.status,
                "video_url": ctx.project.video_url,
            },
            "characters": [
                {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "image_url": c.image_url,
                }
                for c in characters
            ],
            "shots": [
                {
                    "id": sh.id,
                    "order": sh.order,
                    "description": sh.description,
                    "prompt": sh.prompt,
                    "image_prompt": sh.image_prompt,
                    "image_url": sh.image_url,
                    "video_url": sh.video_url,
                    "duration": sh.duration,
                }
                for sh in shots
            ],
        }

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        print(f"[Review] 开始运行，项目ID: {ctx.project.id}")
        # 优先使用 ctx.user_feedback（orchestrator 已设置），DB 查询作为兜底
        feedback = ""
        if hasattr(ctx, "user_feedback") and ctx.user_feedback:
            feedback = ctx.user_feedback.strip()
        if not feedback:
            feedback = (await self._get_latest_feedback(ctx)).strip()
        if not feedback:
            print(f"[Review] 未找到用户反馈内容")
            await self.send_message(ctx, "未找到用户反馈内容，将默认从编剧开始重新生成。")
            return {"start_agent": "scriptwriter", "reason": "未提供具体反馈"}

        print(f"[Review] 获取用户反馈，长度: {len(feedback)}")
        state = await self._get_project_state(ctx)
        print(f"[Review] 获取项目状态，角色数: {len(state['characters'])}, 分镜数: {len(state['shots'])}")
        user_prompt = json.dumps({"feedback": feedback, "state": state}, ensure_ascii=False)

        print(f"[Review] 调用LLM分析反馈，max_tokens=2048")
        resp = await self.call_llm(ctx, system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, max_tokens=2048)
        print(f"[Review] LLM响应已收到，开始解析分析结果")
        data = extract_json(resp.text)

        analysis = data.get("analysis") if isinstance(data, dict) else None
        routing = data.get("routing") if isinstance(data, dict) else None

        feedback_type: str | None = None
        summary: str | None = None
        if isinstance(analysis, dict):
            ft = analysis.get("feedback_type")
            if isinstance(ft, str) and ft.strip():
                feedback_type = ft.strip()
            s = analysis.get("summary")
            if isinstance(s, str) and s.strip():
                summary = s.strip()

        start_agent: str | None = None
        reason: str | None = None
        mode: str = "full"  # 默认全量模式
        if isinstance(routing, dict):
            sa = routing.get("start_agent")
            if isinstance(sa, str) and sa.strip():
                start_agent = sa.strip()
            r = routing.get("reason")
            if isinstance(r, str) and r.strip():
                reason = r.strip()
            # 读取 mode 字段
            m = routing.get("mode")
            if isinstance(m, str) and m.strip() in ("incremental", "full"):
                mode = m.strip()

        # 解析 target_ids（精细化控制）
        target_ids: TargetIds | None = None
        raw_target_ids = data.get("target_ids") if isinstance(data, dict) else None
        if isinstance(raw_target_ids, dict):
            character_ids = raw_target_ids.get("character_ids") or []
            shot_ids = raw_target_ids.get("shot_ids") or []
            # 确保都是整数列表
            character_ids = [int(x) for x in character_ids if isinstance(x, (int, float))]
            shot_ids = [int(x) for x in shot_ids if isinstance(x, (int, float))]
            if character_ids or shot_ids:
                target_ids = TargetIds(
                    character_ids=character_ids,
                    shot_ids=shot_ids,
                )

        if start_agent not in ALLOWED_START_AGENTS:
            print(f"[Review] 路由结果 {start_agent} 不在允许列表中，使用默认路由")
            start_agent = _fallback_start_agent(feedback_type)
            if not reason:
                reason = "未识别到有效的路由结果，采用默认路由策略"

        mode_desc = "增量更新" if mode == "incremental" else "重新生成"
        msg_summary = summary or "已收到您的反馈"
        msg_reason = f"原因：{reason}" if reason else ""

        # 如果有精细化控制目标，显示具体信息
        target_info = ""
        if target_ids and target_ids.has_targets():
            parts = []
            if target_ids.character_ids:
                parts.append(f"{len(target_ids.character_ids)} 个角色")
            if target_ids.shot_ids:
                parts.append(f"{len(target_ids.shot_ids)} 个分镜")
            target_info = f"（仅处理 {', '.join(parts)}）"
            print(f"[Review] 精细化控制目标：{target_info}")

        print(f"[Review] 路由结果：start_agent={start_agent}, mode={mode}, reason={reason}")
        await self.send_message(ctx, f"{msg_summary}。将从 @{start_agent} 开始{mode_desc}{target_info}。{msg_reason}".strip())

        return {
            "start_agent": start_agent,
            "mode": mode,
            "reason": reason or "",
            "analysis": analysis or {},
            "target_ids": target_ids,
            "raw": data,
        }
