from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.agents.prompts.scriptwriter import SYSTEM_PROMPT
from app.agents.utils import extract_json, utcnow
from app.models.project import Character, Shot


def _character_to_description(item: dict) -> str:
    """将角色数据转换为描述文本"""
    name = item.get("name", "")
    parts: list[str] = []
    for key in ["personality_traits", "goals", "fears", "voice_notes", "costume_notes"]:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(f"{key}: {value.strip()}")
        elif isinstance(value, list):
            vals = [v for v in value if isinstance(v, str) and v.strip()]
            if vals:
                parts.append(f"{key}: {', '.join(vals)}")

    description = item.get("description")
    if isinstance(description, str) and description.strip():
        parts.insert(0, description.strip())

    result = "\n".join(parts) if parts else ""
    if isinstance(name, str) and name.strip():
        if result:
            return f"{name.strip()}，{result}"
        return name.strip()
    return result if result else json.dumps(item, ensure_ascii=False)


def _scene_to_description(scene: dict) -> str:
    title = scene.get("title")
    location = scene.get("location")
    time = scene.get("time")
    description = scene.get("description")

    parts: list[str] = []
    if isinstance(title, str) and title.strip():
        parts.append(f"Title: {title.strip()}")
    if isinstance(location, str) and location.strip():
        parts.append(f"Location: {location.strip()}")
    if isinstance(time, str) and time.strip():
        parts.append(f"Time: {time.strip()}")
    if isinstance(description, str) and description.strip():
        parts.append(description.strip())

    beats = scene.get("beats")
    if isinstance(beats, list):
        beat_lines = [b.strip() for b in beats if isinstance(b, str) and b.strip()]
        if beat_lines:
            parts.append("Beats:\n" + "\n".join(f"- {b}" for b in beat_lines))

    dialogue = scene.get("dialogue")
    if isinstance(dialogue, list):
        lines: list[str] = []
        for item in dialogue:
            if not isinstance(item, dict):
                continue
            character = item.get("character")
            line = item.get("line")
            emotion = item.get("emotion")
            if not (isinstance(character, str) and character.strip() and isinstance(line, str) and line.strip()):
                continue
            suffix = ""
            if isinstance(emotion, str) and emotion.strip():
                suffix = f" ({emotion.strip()})"
            lines.append(f"- {character.strip()}: {line.strip()}{suffix}")
        if lines:
            parts.append("Dialogue:\n" + "\n".join(lines))

    shot_plan = scene.get("shot_plan")
    if isinstance(shot_plan, list):
        lines: list[str] = []
        for item in shot_plan:
            if not isinstance(item, dict):
                continue
            shot_desc = item.get("description")
            if isinstance(shot_desc, str) and shot_desc.strip():
                lines.append(f"- {shot_desc.strip()}")
        if lines:
            parts.append("Shot plan:\n" + "\n".join(lines))

    result = "\n".join(parts).strip()
    if result:
        return result
    return json.dumps(scene, ensure_ascii=False)


class ScriptwriterAgent(BaseAgent):
    name = "scriptwriter"

    async def _get_existing_state(self, ctx: AgentContext) -> dict[str, Any]:
        """获取现有的角色、分镜状态"""
        from sqlalchemy import select
        from app.models.project import Character, Shot

        # 获取现有角色
        char_res = await ctx.session.execute(
            select(Character).where(Character.project_id == ctx.project.id)
        )
        characters = [
            {"id": c.id, "name": c.name, "description": c.description}
            for c in char_res.scalars().all()
        ]

        # 获取现有分镜
        shot_res = await ctx.session.execute(
            select(Shot).where(Shot.project_id == ctx.project.id).order_by(Shot.order)
        )
        shots = [
            {
                "id": s.id,
                "order": s.order,
                "description": s.description,
                "prompt": s.prompt,
                "image_prompt": s.image_prompt,
            }
            for s in shot_res.scalars().all()
        ]

        return {"characters": characters, "shots": shots}

    async def _apply_incremental_changes(self, ctx: AgentContext, data: dict) -> tuple[int, int, int]:
        """应用增量更新，返回 (新建角色数, 新建场景数, 新建分镜数)"""
        preserve_ids = data.get("preserve_ids") or {}
        preserve_char_ids = set(preserve_ids.get("characters") or [])
        preserve_shot_ids = set(preserve_ids.get("shots") or [])

        # 删除不在 preserve_ids 中的项目
        # 获取现有数据
        char_res = await ctx.session.execute(
            select(Character).where(Character.project_id == ctx.project.id)
        )
        deleted_char_ids = []
        for char in char_res.scalars().all():
            if char.id not in preserve_char_ids:
                deleted_char_ids.append(char.id)
                await ctx.session.delete(char)

        deleted_shot_ids = []
        shot_res = await ctx.session.execute(
            select(Shot).where(Shot.project_id == ctx.project.id)
        )
        for shot in shot_res.scalars().all():
            if shot.id not in preserve_shot_ids:
                deleted_shot_ids.append(shot.id)
                await ctx.session.delete(shot)

        await ctx.session.flush()

        # 发送删除事件通知前端
        for char_id in deleted_char_ids:
            await ctx.ws.send_event(
                ctx.project.id,
                {"type": "character_deleted", "data": {"character_id": char_id}},
            )
        for shot_id in deleted_shot_ids:
            await ctx.ws.send_event(
                ctx.project.id,
                {"type": "shot_deleted", "data": {"shot_id": shot_id}},
            )

        # 处理新增/更新的角色
        new_char_count = 0
        raw_characters = data.get("characters") or []
        if isinstance(raw_characters, list):
            for item in raw_characters:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if not (isinstance(name, str) and name.strip()):
                    continue
                char_id = item.get("id")
                if char_id is None:
                    # 新建角色
                    new_char = Character(
                        project_id=ctx.project.id,
                        name=name.strip(),
                        description=_character_to_description(item),
                        image_url=None,
                    )
                    ctx.session.add(new_char)
                    new_char_count += 1
                else:
                    existing_char = await ctx.session.get(Character, char_id)
                    if existing_char and existing_char.project_id == ctx.project.id:
                        existing_char.name = name.strip()
                        existing_char.description = _character_to_description(item)
                        ctx.session.add(existing_char)

        await ctx.session.flush()

        # 处理新增/更新的分镜
        new_scene_count = 0
        new_shot_count = 0
        raw_shots = data.get("shots") or []
        if isinstance(raw_shots, list):
            for idx, shot_data in enumerate(raw_shots):
                if not isinstance(shot_data, dict):
                    continue
                shot_id = shot_data.get("id")
                shot_desc = shot_data.get("description")
                if not (isinstance(shot_desc, str) and shot_desc.strip()):
                    continue
                shot_order = shot_data.get("order") if isinstance(shot_data.get("order"), int) else idx + 1
                video_prompt = shot_data.get("video_prompt") or shot_data.get("prompt") or shot_desc
                image_prompt = shot_data.get("image_prompt") or shot_desc

                if shot_id is None:
                    new_shot = Shot(
                        project_id=ctx.project.id,
                        order=shot_order,
                        description=shot_desc.strip(),
                        prompt=video_prompt.strip() if isinstance(video_prompt, str) else shot_desc.strip(),
                        image_prompt=image_prompt.strip() if isinstance(image_prompt, str) else shot_desc.strip(),
                        video_url=None,
                        image_url=None,
                    )
                    ctx.session.add(new_shot)
                    new_shot_count += 1
                else:
                    existing_shot = await ctx.session.get(Shot, shot_id)
                    if existing_shot and existing_shot.project_id == ctx.project.id:
                        existing_shot.order = shot_order
                        existing_shot.description = shot_desc.strip()
                        existing_shot.prompt = video_prompt.strip() if isinstance(video_prompt, str) else shot_desc.strip()
                        existing_shot.image_prompt = image_prompt.strip() if isinstance(image_prompt, str) else shot_desc.strip()
                        ctx.session.add(existing_shot)

        await ctx.session.flush()
        return new_char_count, new_scene_count, new_shot_count

    async def run(self, ctx: AgentContext) -> None:
        print(f"[Scriptwriter] 开始运行，项目ID: {ctx.project.id}, 标题: {ctx.project.title}, 模式: {ctx.rerun_mode}")
        # 发送开始消息
        is_incremental = ctx.rerun_mode == "incremental"
        if is_incremental:
            await self.send_message(ctx, "✍️ 正在增量更新剧本...", progress=0.0, is_loading=True)
        else:
            await self.send_message(ctx, "✍️ 正在创作剧本...", progress=0.0, is_loading=True)
        
        await ctx.session.commit()  # Release lock before LLM call

        print(f"[Scriptwriter] 构建用户提示词，包含项目信息和模式")
        # 注意：不再检查是否已有场景，因为 _cleanup_for_rerun 会在重新运行前清理数据
        # 如果需要跳过已完成的项目，应该在 orchestrator 层面处理

        payload: dict[str, Any] = {
            "project": {
                "id": ctx.project.id,
                "title": ctx.project.title,
                "story": ctx.project.story,
                "style": ctx.project.style,
                "status": ctx.project.status,
            },
            "mode": ctx.rerun_mode,
            "style_mode": ctx.style_mode,
        }
        if ctx.user_feedback:
            payload["user_feedback"] = ctx.user_feedback

        # 增量模式下，传递现有状态
        if is_incremental:
            print(f"[Scriptwriter] 增量模式，获取现有状态")
            existing_state = await self._get_existing_state(ctx)
            payload["existing_state"] = existing_state

        user_prompt = json.dumps(payload, ensure_ascii=False)

        print(f"[Scriptwriter] 调用LLM生成剧本，max_tokens=4096")
        resp = await self.call_llm(ctx, system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, max_tokens=4096)
        print(f"[Scriptwriter] LLM响应已收到，开始解析剧本数据")
        data = extract_json(resp.text)

        # 更新项目状态
        project_update = data.get("project_update") or {}
        if isinstance(project_update, dict):
            status = project_update.get("status")
            if isinstance(status, str) and status.strip():
                ctx.project.status = status.strip()
                ctx.project.updated_at = utcnow()
                ctx.session.add(ctx.project)

        # 增量模式：使用增量更新逻辑
        if is_incremental:
            print(f"[Scriptwriter] 增量模式，应用增量更新")
            new_char_count, _, new_shot_count = await self._apply_incremental_changes(ctx, data)

            # 重新查询最终状态
            char_res = await ctx.session.execute(
                select(Character).where(Character.project_id == ctx.project.id)
            )
            final_chars = list(char_res.scalars().all())
            shot_res = await ctx.session.execute(
                select(Shot).where(Shot.project_id == ctx.project.id).order_by(Shot.order.asc())
            )
            final_shots = list(shot_res.scalars().all())

            # 发送事件
            for char in final_chars:
                await self.send_character_event(ctx, char, "character_updated")
            for shot in final_shots:
                await self.send_shot_event(ctx, shot, "shot_updated")

            await ctx.session.commit()

            # 显示更新摘要
            char_names = [c.name for c in final_chars]
            print(f"[Scriptwriter] 增量更新完成：{len(final_chars)} 个角色，{len(final_shots)} 个分镜")
            await self.send_message(ctx, f"👥 角色设定：{', '.join(char_names)}")

            total_shots = len(final_shots)
            await self.send_message(
                ctx,
                f"✅ 增量更新完成：{len(final_chars)} 个角色、{total_shots} 个分镜，接下来将进行角色设计。",
                progress=1.0
            )
            return

        # 全量模式：原有逻辑
        print(f"[Scriptwriter] 全量模式，创建角色和分镜")
        # 创建角色（不含图片）
        raw_characters = data.get("characters") or []
        if isinstance(raw_characters, list) and raw_characters:
            print(f"[Scriptwriter] 开始创建 {len(raw_characters)} 个角色")
            new_characters: list[Character] = []
            char_names: list[str] = []
            for item in raw_characters:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if not (isinstance(name, str) and name.strip()):
                    continue
                char_names.append(name.strip())
                new_characters.append(
                    Character(
                        project_id=ctx.project.id,
                        name=name.strip(),
                        description=_character_to_description(item),
                        image_url=None,  # 图片由 CharacterArtist 生成
                    )
                )
            if new_characters:
                ctx.session.add_all(new_characters)
                await ctx.session.flush()  # 获取分配的 ID
                # 发送角色创建事件
                for character in new_characters:
                    await self.send_character_event(ctx, character, "character_created")
                await self.send_message(ctx, f"👥 角色设定：{', '.join(char_names)}")

        # 创建镜头（不含图片和视频）
        raw_shots = data.get("shots") or []
        if not isinstance(raw_shots, list) or not raw_shots:
            raise ValueError("LLM 响应未返回任何分镜")

        print(f"[Scriptwriter] 开始创建 {len(raw_shots)} 个分镜")
        new_shots: list[Shot] = []
        fallback_order = 1
        for idx, shot_data in enumerate(raw_shots):
            if not isinstance(shot_data, dict):
                continue
            shot_desc = shot_data.get("description")
            if not (isinstance(shot_desc, str) and shot_desc.strip()):
                continue
            order = shot_data.get("order")
            if isinstance(order, int) and order > 0:
                shot_order = order
            else:
                shot_order = fallback_order
            fallback_order = max(fallback_order, shot_order + 1)

            video_prompt = shot_data.get("video_prompt") or shot_data.get("prompt") or shot_desc
            image_prompt = shot_data.get("image_prompt") or shot_desc

            new_shots.append(
                Shot(
                    project_id=ctx.project.id,
                    order=shot_order,
                    description=shot_desc.strip(),
                    prompt=video_prompt.strip() if isinstance(video_prompt, str) else shot_desc.strip(),
                    image_prompt=image_prompt.strip() if isinstance(image_prompt, str) else shot_desc.strip(),
                    video_url=None,  # 视频由 VideoGenerator 生成
                    image_url=None,  # 图片由 StoryboardArtist 生成
                )
            )

        if not new_shots:
            raise ValueError("LLM 响应的分镜列表为空或无效")

        new_shots.sort(key=lambda s: s.order)
        ctx.session.add_all(new_shots)
        await ctx.session.flush()  # 获取分配的 ID
        for shot in new_shots:
            await self.send_shot_event(ctx, shot, "shot_created")
        await ctx.session.commit()
        print(f"[Scriptwriter] 剧本创作完成，共 {len(new_shots)} 个镜头")
        await self.send_message(ctx, f"✅ 剧本创作完成：{len(new_shots)} 个镜头，接下来将进行角色设计。", progress=1.0)
