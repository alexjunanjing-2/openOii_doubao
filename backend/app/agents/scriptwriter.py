from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.agents.prompts.scriptwriter import SYSTEM_PROMPT
from app.agents.utils import extract_json, utcnow
from app.models.project import Character, Scene, Shot


def _character_to_description(item: dict) -> str:
    """将角色数据转换为描述文本"""
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

    return "\n".join(parts) if parts else json.dumps(item, ensure_ascii=False)


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
        """获取现有的角色、场景、分镜状态"""
        from sqlalchemy import select
        from app.models.project import Character, Scene, Shot

        # 获取现有角色
        char_res = await ctx.session.execute(
            select(Character).where(Character.project_id == ctx.project.id)
        )
        characters = [
            {"id": c.id, "name": c.name, "description": c.description}
            for c in char_res.scalars().all()
        ]

        # 获取现有场景和分镜
        scene_res = await ctx.session.execute(
            select(Scene).where(Scene.project_id == ctx.project.id).order_by(Scene.order)
        )
        scenes = []
        for scene in scene_res.scalars().all():
            shot_res = await ctx.session.execute(
                select(Shot).where(Shot.scene_id == scene.id).order_by(Shot.order)
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
            scenes.append({
                "id": scene.id,
                "order": scene.order,
                "description": scene.description,
                "shots": shots,
            })

        return {"characters": characters, "scenes": scenes}

    async def _apply_incremental_changes(self, ctx: AgentContext, data: dict) -> tuple[int, int, int]:
        """应用增量更新，返回 (新建角色数, 新建场景数, 新建分镜数)"""
        preserve_ids = data.get("preserve_ids") or {}
        preserve_char_ids = set(preserve_ids.get("characters") or [])
        preserve_scene_ids = set(preserve_ids.get("scenes") or [])
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

        scene_res = await ctx.session.execute(
            select(Scene).where(Scene.project_id == ctx.project.id)
        )
        deleted_scene_ids = []
        deleted_shot_ids = []
        for scene in scene_res.scalars().all():
            if scene.id not in preserve_scene_ids:
                # 先删除该场景的所有分镜
                shot_res = await ctx.session.execute(
                    select(Shot).where(Shot.scene_id == scene.id)
                )
                for shot in shot_res.scalars().all():
                    deleted_shot_ids.append(shot.id)
                    await ctx.session.delete(shot)
                deleted_scene_ids.append(scene.id)
                await ctx.session.delete(scene)
            else:
                # 场景保留，但检查分镜
                shot_res = await ctx.session.execute(
                    select(Shot).where(Shot.scene_id == scene.id)
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
        for scene_id in deleted_scene_ids:
            await ctx.ws.send_event(
                ctx.project.id,
                {"type": "scene_deleted", "data": {"scene_id": scene_id}},
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

        await ctx.session.flush()

        # 处理新增/更新的场景和分镜
        new_scene_count = 0
        new_shot_count = 0
        raw_scenes = data.get("scenes") or []
        if isinstance(raw_scenes, list):
            for scene_data in raw_scenes:
                if not isinstance(scene_data, dict):
                    continue
                scene_id = scene_data.get("id")
                if scene_id is None:
                    # 新建场景
                    order = scene_data.get("order") or 1
                    new_scene = Scene(
                        project_id=ctx.project.id,
                        order=order,
                        description=_scene_to_description(scene_data),
                    )
                    ctx.session.add(new_scene)
                    await ctx.session.flush()
                    new_scene_count += 1

                    # 创建该场景的分镜
                    shot_plan = scene_data.get("shot_plan") or []
                    for idx, shot_data in enumerate(shot_plan):
                        if not isinstance(shot_data, dict):
                            continue
                        shot_desc = shot_data.get("description")
                        if not (isinstance(shot_desc, str) and shot_desc.strip()):
                            continue
                        shot_order = shot_data.get("order") if isinstance(shot_data.get("order"), int) else idx + 1
                        video_prompt = shot_data.get("video_prompt") or shot_data.get("prompt") or shot_desc
                        image_prompt = shot_data.get("image_prompt") or shot_desc
                        new_shot = Shot(
                            scene_id=new_scene.id,
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
                    # 保留的场景：检查是否有新的 shot_plan 需要创建
                    shot_plan = scene_data.get("shot_plan") or []
                    for idx, shot_data in enumerate(shot_plan):
                        if not isinstance(shot_data, dict):
                            continue
                        shot_id = shot_data.get("id")
                        # 只创建新的分镜（id 为 None 的）
                        if shot_id is not None:
                            continue
                        shot_desc = shot_data.get("description")
                        if not (isinstance(shot_desc, str) and shot_desc.strip()):
                            continue
                        shot_order = shot_data.get("order") if isinstance(shot_data.get("order"), int) else idx + 1
                        video_prompt = shot_data.get("video_prompt") or shot_data.get("prompt") or shot_desc
                        image_prompt = shot_data.get("image_prompt") or shot_desc
                        new_shot = Shot(
                            scene_id=scene_id,
                            order=shot_order,
                            description=shot_desc.strip(),
                            prompt=video_prompt.strip() if isinstance(video_prompt, str) else shot_desc.strip(),
                            image_prompt=image_prompt.strip() if isinstance(image_prompt, str) else shot_desc.strip(),
                            video_url=None,
                            image_url=None,
                        )
                        ctx.session.add(new_shot)
                        new_shot_count += 1

        await ctx.session.flush()
        return new_char_count, new_scene_count, new_shot_count

    async def run(self, ctx: AgentContext) -> None:
        # 发送开始消息
        is_incremental = ctx.rerun_mode == "incremental"
        if is_incremental:
            await self.send_message(ctx, "✍️ 正在增量更新剧本...", progress=0.0, is_loading=True)
        else:
            await self.send_message(ctx, "✍️ 正在创作剧本...", progress=0.0, is_loading=True)

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
        }
        if ctx.user_feedback:
            payload["user_feedback"] = ctx.user_feedback

        # 增量模式下，传递现有状态
        if is_incremental:
            existing_state = await self._get_existing_state(ctx)
            payload["existing_state"] = existing_state

        user_prompt = json.dumps(payload, ensure_ascii=False)

        resp = await self.call_llm(ctx, system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt, max_tokens=4096)
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
            new_char_count, new_scene_count, new_shot_count = await self._apply_incremental_changes(ctx, data)

            # 重新查询最终状态
            char_res = await ctx.session.execute(
                select(Character).where(Character.project_id == ctx.project.id)
            )
            final_chars = list(char_res.scalars().all())
            scene_res = await ctx.session.execute(
                select(Scene).where(Scene.project_id == ctx.project.id)
            )
            final_scenes = list(scene_res.scalars().all())

            # 发送事件
            for char in final_chars:
                await self.send_character_event(ctx, char, "character_updated")
            for scene in final_scenes:
                await self.send_scene_event(ctx, scene, "scene_updated")
                shot_res = await ctx.session.execute(
                    select(Shot).where(Shot.scene_id == scene.id)
                )
                for shot in shot_res.scalars().all():
                    await self.send_shot_event(ctx, shot, "shot_updated")

            await ctx.session.commit()

            # 显示更新摘要
            char_names = [c.name for c in final_chars]
            await self.send_message(ctx, f"👥 角色设定：{', '.join(char_names)}")

            # 统计分镜数量
            shot_count_res = await ctx.session.execute(
                select(Shot).join(Scene).where(Scene.project_id == ctx.project.id)
            )
            total_shots = len(list(shot_count_res.scalars().all()))
            await self.send_message(
                ctx,
                f"✅ 增量更新完成：{len(final_chars)} 个角色、{len(final_scenes)} 个场景、{total_shots} 个分镜，接下来将进行角色设计。",
                progress=1.0
            )
            return

        # 全量模式：原有逻辑
        # 创建角色（不含图片）
        raw_characters = data.get("characters") or []
        if isinstance(raw_characters, list) and raw_characters:
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

        # 创建场景
        raw_scenes = data.get("scenes") or []
        if not isinstance(raw_scenes, list) or not raw_scenes:
            raise ValueError("LLM 响应未返回任何场景")

        new_scenes: list[Scene] = []
        scene_shot_map: dict[int, list[dict]] = {}  # scene.order -> shots
        fallback_order = 1
        for scene in raw_scenes:
            if not isinstance(scene, dict):
                continue
            order = scene.get("order")
            if isinstance(order, int) and order > 0:
                scene_order = order
            else:
                scene_order = fallback_order
            fallback_order = max(fallback_order, scene_order + 1)
            new_scenes.append(
                Scene(
                    project_id=ctx.project.id,
                    order=scene_order,
                    description=_scene_to_description(scene),
                )
            )
            # 收集 shot_plan，稍后创建 Shot
            shot_plan = scene.get("shot_plan")
            if isinstance(shot_plan, list):
                scene_shot_map[scene_order] = shot_plan

        if not new_scenes:
            raise ValueError("LLM 响应的场景列表为空或无效")

        new_scenes.sort(key=lambda s: s.order)
        ctx.session.add_all(new_scenes)
        await ctx.session.flush()  # 获取分配的 ID

        # 发送场景创建事件
        for scene in new_scenes:
            await self.send_scene_event(ctx, scene, "scene_created")

        # 显示场景概要 - 显示全部场景
        scene_titles = []
        for scene in raw_scenes:
            if isinstance(scene, dict):
                title = scene.get("title") or scene.get("description", "")[:20]
                if title:
                    scene_titles.append(title if len(title) <= 20 else title[:20] + "...")
        scene_msg = f"🎬 场景列表：共 {len(new_scenes)} 个场景"
        if scene_titles:
            scene_msg += f"\n   " + " → ".join(scene_titles)
        await self.send_message(ctx, scene_msg)

        # 创建镜头（不含图片和视频）
        new_shots: list[Shot] = []
        for scene in new_scenes:
            shots = scene_shot_map.get(scene.order, [])
            for idx, shot in enumerate(shots):
                if not isinstance(shot, dict):
                    continue
                shot_desc = shot.get("description")
                if not (isinstance(shot_desc, str) and shot_desc.strip()):
                    continue
                # shot.order 如果没有则用索引+1
                shot_order = shot.get("order") if isinstance(shot.get("order"), int) else idx + 1
                # video_prompt 用于视频生成，image_prompt 用于首帧图片
                video_prompt = shot.get("video_prompt") or shot.get("prompt") or shot_desc
                image_prompt = shot.get("image_prompt") or shot_desc

                new_shots.append(
                    Shot(
                        scene_id=scene.id,
                        order=shot_order,
                        description=shot_desc.strip(),
                        prompt=video_prompt.strip() if isinstance(video_prompt, str) else shot_desc.strip(),
                        image_prompt=image_prompt.strip() if isinstance(image_prompt, str) else shot_desc.strip(),
                        video_url=None,  # 视频由 VideoGenerator 生成
                        image_url=None,  # 图片由 StoryboardArtist 生成
                    )
                )

        if new_shots:
            ctx.session.add_all(new_shots)
            await ctx.session.flush()  # 获取分配的 ID
            # 发送分镜创建事件
            for shot in new_shots:
                await self.send_shot_event(ctx, shot, "shot_created")
            await ctx.session.commit()
            await self.send_message(ctx, f"✅ 剧本创作完成：{len(new_scenes)} 个场景、{len(new_shots)} 个镜头，接下来将进行角色设计。", progress=1.0)
        else:
            await ctx.session.commit()
            await self.send_message(ctx, f"✅ 剧本创作完成：{len(new_scenes)} 个场景，接下来将进行角色设计。", progress=1.0)
