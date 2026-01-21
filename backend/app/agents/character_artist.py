from __future__ import annotations

import json

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.agents.utils import extract_json
from app.models.project import Character


class CharacterArtistAgent(BaseAgent):
    """为角色生成参考图片"""
    name = "character_artist"

    def _build_image_prompt(self, character: Character) -> str:
        """根据角色描述构建图片生成 prompt"""
        style_hints = {
            "anime": "anime style, manga character design, clean lines, vibrant colors",
            "realistic": "realistic style, detailed character art, cinematic lighting",
        }
        style_hint = style_hints.get(self._project_style(character), "")

        # 使用角色的 description 作为主要 prompt
        desc = character.description or character.name
        parts: list[str] = [desc.strip()]

        if style_hint:
            parts.append(style_hint)

        return ", ".join(parts)

    def _project_style(self, character: Character) -> str:
        """获取项目风格（从 character 关联的 project）"""
        # 这里简化处理，实际可能需要 join project 表
        # 暂时返回 anime 作为默认
        return "anime"

    async def run(self, ctx: AgentContext) -> None:
        # 查找没有图片的角色
        res = await ctx.session.execute(
            select(Character).where(
                Character.project_id == ctx.project.id,
                Character.image_url.is_(None)
            )
        )
        characters = res.scalars().all()
        if not characters:
            await self.send_message(ctx, "所有角色已有图片。")
            return

        total = len(characters)
        await self.send_message(ctx, f"🎨 开始为 {total} 个角色生成形象图...", progress=0.0, is_loading=True)

        updated_count = 0
        for i, char in enumerate(characters):
            try:
                # 计算进度并发送更新消息
                current_progress = i / total
                await self.send_message(
                    ctx,
                    f"   正在绘制：{char.name} ({i+1}/{total})",
                    progress=current_progress,
                    is_loading=True
                )

                image_prompt = self._build_image_prompt(char)
                image_url = await ctx.image.generate_url(prompt=image_prompt)

                char.image_url = image_url
                ctx.session.add(char)
                await ctx.session.flush()  # 确保更新生效
                # 发送角色更新事件
                await self.send_character_event(ctx, char, "character_updated")
                updated_count += 1
            except Exception as e:
                # 单个失败不影响其他
                await self.send_message(ctx, f"⚠️ 角色 {char.name} 图片生成失败: {str(e)[:50]}")

        await ctx.session.commit()
        if updated_count > 0:
            await self.send_message(ctx, f"✅ 已为 {updated_count} 个角色生成形象图，接下来将绘制分镜。", progress=1.0)
