from __future__ import annotations

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.models.project import Character


class CharacterArtistAgent(BaseAgent):
    """为角色生成参考图片"""
    name = "character_artist"

    async def _generate_character_image(self, ctx: AgentContext, character: Character) -> None:
        image_prompt = self._build_image_prompt(character, style=ctx.project.style, style_mode=ctx.style_mode)
        external_url = await ctx.image.generate_url(prompt=image_prompt)

        # 保存原始 URL（不缓存）
        character.image_url = external_url
        ctx.session.add(character)
        await ctx.session.flush()

        # 发送角色更新事件
        await self.send_character_event(ctx, character, "character_updated")

    def _build_image_prompt(self, character: Character, *, style: str, style_mode: str = "cartoon") -> str:
        """根据角色描述构建图片生成 prompt"""
        desc = character.description or character.name
        style = style.strip()

        if style_mode == "cartoon":
            # 卡通/热血战斗类日系动漫风格
            anime_style = "hot-blooded battle anime, Japanese shonen style, dynamic action poses, vibrant colors, expressive eyes, stylized features"
            if style:
                return f"{desc}, {anime_style}, {style}"
            return f"{desc}, {anime_style}"
        else:
            # 真人/电影级风格
            realistic_style = "photorealistic, cinematic, natural lighting, realistic textures, film quality, high detail"
            if style:
                return f"{desc}, {realistic_style}, {style}"
            return f"{desc}, {realistic_style}"

    async def run_for_character(self, ctx: AgentContext, character: Character) -> None:
        character_name = character.name
        character_id = character.id
        print(f"[CharacterArtist] 开始为角色生成图片，角色ID: {character_id}, 名称: {character_name}")
        await self.send_message(
            ctx,
            f"🎨 开始为角色 {character_name} 生成形象图...",
            progress=0.0,
            is_loading=True,
        )
        await ctx.session.commit()  # Commit to release lock before slow generation

        updated = False
        try:
            await self._generate_character_image(ctx, character)
            updated = True
            print(f"[CharacterArtist] 角色 {character_name} 图片生成成功")
        except Exception as e:
            print(f"[CharacterArtist] 角色 {character_name} 图片生成失败: {e}")
            await self.send_message(ctx, f"⚠️ 角色 {character_name} 图片生成失败: {str(e)[:50]}")

        await ctx.session.commit()

        if updated:
            await self.send_message(
                ctx,
                f"✅ 已为角色 {character_name} 生成形象图。",
                progress=1.0,
                is_loading=False,
            )

    async def run(self, ctx: AgentContext) -> None:
        print(f"[CharacterArtist] 开始运行，项目ID: {ctx.project.id}")
        # 查找没有图片的角色
        res = await ctx.session.execute(
            select(Character).where(
                Character.project_id == ctx.project.id,
                Character.image_url.is_(None)
            )
        )
        characters = res.scalars().all()
        if not characters:
            print(f"[CharacterArtist] 所有角色已有图片，跳过")
            await self.send_message(ctx, "所有角色已有图片。")
            return

        total = len(characters)
        print(f"[CharacterArtist] 开始为 {total} 个角色生成形象图")
        await self.send_message(ctx, f"🎨 开始为 {total} 个角色生成形象图...", progress=0.0, is_loading=True)

        updated_count = 0
        for i, char in enumerate(characters):
            char_name = char.name
            try:
                print(f"[CharacterArtist] 正在处理角色 {i+1}/{total}: {char_name}")
                await self.send_progress_batch(
                    ctx,
                    total=total,
                    current=i,
                    message=f"   正在绘制：{char_name} ({i+1}/{total})",
                )
                await ctx.session.commit()  # Commit to release lock before slow generation

                await self._generate_character_image(ctx, char)
                await ctx.session.commit()  # Commit immediately to release lock
                updated_count += 1
                print(f"[CharacterArtist] 角色 {char_name} 图片生成成功")
            except Exception as e:
                print(f"[CharacterArtist] 角色 {char_name} 图片生成失败: {e}")
                # 单个失败不影响其他
                await self.send_message(ctx, f"⚠️ 角色 {char_name} 图片生成失败: {str(e)[:50]}")
                await ctx.session.rollback()  # Rollback on error to clean session

        # Final commit just in case, though we committed inside loop
        await ctx.session.commit()
        print(f"[CharacterArtist] 完成，成功生成 {updated_count}/{total} 个角色图片")
        if updated_count > 0:
            await self.send_message(ctx, f"✅ 已为 {updated_count} 个角色生成形象图，接下来将绘制分镜。", progress=1.0)


class SingleCharacterArtistAgent(CharacterArtistAgent):
    name = "character_artist"

    def __init__(self, character_id: int):
        super().__init__()
        self.character_id = character_id

    async def run(self, ctx: AgentContext) -> None:
        character = await ctx.session.get(Character, self.character_id)
        if not character or character.project_id != ctx.project.id:
            await self.send_message(ctx, "未找到指定角色，无法重新生成。")
            await ctx.session.commit()
            return

        await self.run_for_character(ctx, character)
