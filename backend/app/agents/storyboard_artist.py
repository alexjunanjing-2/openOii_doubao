from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.models.project import Character, Shot

logger = logging.getLogger(__name__)


class StoryboardArtistAgent(BaseAgent):
    """为分镜生成首帧图片"""
    name = "storyboard_artist"

    def _build_image_prompt(self, shot: Shot, characters: list[Character], *, style: str, use_character_reference: bool = False, style_mode: str = "cartoon") -> str:
        """构建首帧图片生成 prompt"""
        # 优先使用 image_prompt，否则使用 description
        desc = shot.image_prompt or shot.description
        parts = [desc.strip()]

        # 根据风格模式添加不同的风格关键词
        if style_mode == "cartoon":
            # 卡通/热血战斗类日系动漫风格
            anime_style = "hot-blooded battle anime, Japanese shonen style, dynamic action angles, vibrant colors, dramatic lighting"
            parts.append(anime_style)
        else:
            # 真人/电影级风格
            realistic_style = "photorealistic, cinematic, natural lighting, realistic textures, film quality, high detail"
            parts.append(realistic_style)

        if style.strip():
            parts.append(style.strip())

        prompt = ", ".join(parts)

        # 如果启用角色图参考，添加参考图说明
        if use_character_reference and characters:
            char_refs = []
            for i, char in enumerate(characters, 1):
                if char.name:
                    char_refs.append(f"图{i} 是角色 {char.name} 参考图")
            if char_refs:
                prompt += "，" + "，".join(char_refs)

        return prompt

    async def run(self, ctx: AgentContext) -> None:
        print(f"[StoryboardArtist] 开始运行，项目ID: {ctx.project.id}")
        use_character_reference = ctx.settings.storyboard_use_character_reference

        # 使用基类方法查询项目角色
        characters = await self.get_project_characters(ctx)
        print(f"[StoryboardArtist] 获取到 {len(characters)} 个角色")

        # 收集有图片的角色 URL（用于角色图参考）
        character_image_urls: list[str] = []
        if use_character_reference:
            character_image_urls = [c.image_url for c in characters if c.image_url]
            print(f"[StoryboardArtist] 收集到的角色图片 URL: {character_image_urls}")
            if not character_image_urls:
                logger.info("Character reference enabled but no character images available; will fall back to text-to-image")
                print(f"[StoryboardArtist] 没有角色图片，将使用文生图模式")
            else:
                logger.info("Character reference enabled: using %d character images as reference", len(character_image_urls))
                print(f"[StoryboardArtist] 角色图参考模式已启用，包含 {len(character_image_urls)} 个角色")

        # 查找没有首帧图片的 Shot（可按目标分镜过滤）
        query = (
            select(Shot)
            .where(
                Shot.project_id == ctx.project.id,
                Shot.image_url.is_(None),
            )
            .order_by(Shot.order)
        )
        if ctx.target_ids and ctx.target_ids.shot_ids:
            query = query.where(Shot.id.in_(ctx.target_ids.shot_ids))
        res = await ctx.session.execute(query)
        shots = res.scalars().all()
        if not shots:
            print(f"[StoryboardArtist] 所有分镜已有首帧图片，跳过")
            await self.send_message(ctx, "所有分镜已有首帧图片。")
            return

        total = len(shots)
        updated_count = 0
        failed_count = 0

        # 发送带进度的消息
        print(f"[StoryboardArtist] 开始为 {total} 个分镜生成首帧图片")
        await self.send_message(ctx, f"🖼️ 开始为 {total} 个分镜生成首帧图片...", progress=0.0, is_loading=True)

        for i, shot in enumerate(shots):
            shot_order = shot.order
            shot_id = shot.id
            try:
                print(f"[StoryboardArtist] 正在处理分镜 {i+1}/{total}, ID: {shot_id}, 顺序: {shot_order}")
                # 使用基类方法发送进度消息
                await self.send_progress_batch(
                    ctx,
                    total=total,
                    current=i,
                    message=f"   正在绘制分镜 {i+1}/{total}...",
                )
                await ctx.session.commit()  # Release lock before slow generation

                image_prompt = self._build_image_prompt(shot, characters, style=ctx.project.style, use_character_reference=use_character_reference, style_mode=ctx.style_mode)

                # 仅对 URL 生成阶段加超时（8分钟），缓存/下载不受此超时影响
                image_url = await self.generate_and_cache_image(
                    ctx,
                    prompt=image_prompt,
                    image_urls=character_image_urls if use_character_reference else None,
                    timeout_s=480.0,
                )

                shot.image_url = image_url
                ctx.session.add(shot)
                await ctx.session.flush()  # 确保更新生效
                # 发送分镜更新事件
                await self.send_shot_event(ctx, shot, "shot_updated")
                await ctx.session.commit()  # Release lock after update
                updated_count += 1
                print(f"[StoryboardArtist] 分镜 {shot_order} 首帧图片生成成功")

                # 添加延迟避免 API 限流（每张图片后等待 1 秒）
                if i < total - 1:
                    await asyncio.sleep(1.0)

            except Exception as e:
                failed_count += 1
                print(f"[StoryboardArtist] 分镜 {shot_order} 首帧图片生成失败: {e}")
                error_msg = f"⚠️ 镜头 {shot_order} 首帧图片生成失败: {str(e)[:100]}"
                await self.send_message(ctx, error_msg)
                await ctx.session.rollback()  # Rollback on error
                # 失败后等待更长时间再继续
                await asyncio.sleep(2.0)
        
        # Final commit just in case
        await ctx.session.commit()
        print(f"[StoryboardArtist] 完成，成功 {updated_count}/{total}，失败 {failed_count}")

        # 完成消息
        if updated_count > 0:
            msg = f"✅ 已为 {updated_count} 个分镜生成首帧图片，接下来将生成视频。"
            if failed_count > 0:
                msg += f"（{failed_count} 个失败）"
            await self.send_message(ctx, msg, progress=1.0, is_loading=False)
        elif failed_count > 0:
            await self.send_message(ctx, f"❌ 所有 {failed_count} 个分镜首帧图片生成均失败。", progress=1.0, is_loading=False)
