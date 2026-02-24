from __future__ import annotations

from sqlalchemy import select

from app.agents.base import AgentContext, BaseAgent
from app.models.project import Character, Shot
from app.services.doubao_video import DoubaoVideoService
from app.services.image_composer import ImageComposer


class VideoGeneratorAgent(BaseAgent):
    """为分镜生成视频"""
    name = "video_generator"

    def __init__(self):
        super().__init__()
        self.image_composer = ImageComposer()

    def _build_video_prompt(self, shot: Shot, characters: list[Character], *, style: str, style_mode: str = "cartoon") -> str:
        """构建视频生成 prompt"""
        # 优先使用 prompt（由 Scriptwriter 生成的 video_prompt）
        desc = shot.prompt or shot.description
        parts = [desc.strip()]

        # 根据风格模式添加不同的风格关键词
        if style_mode == "cartoon":
            # 卡通/热血战斗类日系动漫风格
            anime_style = "hot-blooded battle anime, Japanese shonen style, 2D animation, vibrant colors, dynamic action movements"
            parts.append(anime_style)
        else:
            # 真人/电影级风格
            realistic_style = "photorealistic, cinematic, natural movements, realistic lighting, film quality"
            parts.append(realistic_style)

        if style.strip():
            parts.append(f"Style: {style.strip()}")

        return ", ".join(parts)

    def _get_duration(self, shot: Shot, default_duration: float) -> float:
        """获取视频时长（秒）"""
        if shot.duration and shot.duration > 0:
            return shot.duration
        return default_duration

    async def run(self, ctx: AgentContext) -> None:
        print(f"[VideoGenerator] 开始运行，项目ID: {ctx.project.id}")
        # 使用基类方法查询项目角色
        characters = await self.get_project_characters(ctx)
        print(f"[VideoGenerator] 获取到 {len(characters)} 个角色")

        # 查找没有视频的 Shot（可按目标分镜过滤）
        query = (
            select(Shot)
            .where(
                Shot.project_id == ctx.project.id,
                Shot.video_url.is_(None),
            )
        )
        if ctx.target_ids and ctx.target_ids.shot_ids:
            query = query.where(Shot.id.in_(ctx.target_ids.shot_ids))
        res = await ctx.session.execute(query)
        shots = res.scalars().all()
        if not shots:
            print(f"[VideoGenerator] 所有分镜已有视频，跳过")
            await self.send_message(ctx, "所有分镜已有视频。")
            return

        # 检查是否使用图生视频模式
        use_image_mode = ctx.settings.use_i2v()
        # 检查是否使用豆包服务
        is_doubao = isinstance(ctx.video, DoubaoVideoService)
        if is_doubao:
            if ctx.settings.doubao_video_fixed_duration:
                default_duration = float(ctx.settings.doubao_video_duration)
            else:
                default_duration = -1
        else:
            default_duration = 5.0

        total = len(shots)
        updated_count = 0

        mode_desc = "图生视频" if use_image_mode else "文生视频"
        provider_desc = "豆包" if is_doubao else "OpenAI兼容"
        image_mode = (ctx.settings.video_image_mode or "first_frame").strip().lower()
        print(f"[VideoGenerator] 开始为 {total} 个分镜生成视频，模式: {mode_desc}, 提供商: {provider_desc}, 图片模式: {image_mode}")
        # 发送带进度的消息
        await self.send_message(
            ctx,
            f"🎬 开始为 {total} 个分镜生成视频（{mode_desc}）...",
            progress=0.0,
            is_loading=True
        )

        for i, shot in enumerate(shots):
            shot_order = shot.order
            shot_id = shot.id
            try:
                print(f"[VideoGenerator] 正在处理分镜 {i+1}/{total}, ID: {shot_id}, 顺序: {shot_order}")
                # 使用基类方法发送进度消息
                await self.send_progress_batch(
                    ctx,
                    total=total,
                    current=i,
                    message=f"   正在生成视频 {i+1}/{total}...",
                )
                await ctx.session.commit()  # Release lock before slow generation

                video_prompt = self._build_video_prompt(shot, characters, style=ctx.project.style, style_mode=ctx.style_mode)
                duration = self._get_duration(shot, default_duration)

                # 根据服务类型选择不同的调用方式
                if is_doubao:
                    print(f"[VideoGenerator] 使用豆包服务生成视频")
                    # 豆包服务：使用图片 URL
                    image_url: str | None = None
                    if use_image_mode and shot.image_url:
                        if image_mode == "reference":
                            try:
                                # 收集有图片的角色
                                char_image_urls = [c.image_url for c in characters if c.image_url]

                                # 拼接分镜图和角色图，保存到本地并获取 URL
                                image_url = await self.image_composer.compose_and_save_reference_image(
                                    shot_image_url=shot.image_url,
                                    character_image_urls=char_image_urls,
                                )
                                await self.send_message(
                                    ctx,
                                    f"镜头 {shot_order}: 已生成参考图（分镜图 + {len(char_image_urls)} 个角色图）",
                                )
                                await ctx.session.commit()  # Release lock
                                print(f"[VideoGenerator] 镜头 {shot_order}: 已生成参考图（分镜图 + {len(char_image_urls)} 个角色图）")
                            except Exception as e:
                                await self.send_message(
                                    ctx,
                                    f"镜头 {shot_order}: 参考图生成失败，将使用分镜首帧图: {e}",
                                )
                                await ctx.session.commit()  # Release lock
                                print(f"[VideoGenerator] 镜头 {shot_order}: 参考图生成失败，将使用分镜首帧图: {e}")
                                image_url = shot.image_url
                        else:
                            image_url = shot.image_url

                    # 豆包服务的 generate_url 接口
                    video_url = await ctx.video.generate_url(
                        prompt=video_prompt,
                        image_url=image_url,
                        duration=int(duration),
                        ratio=ctx.settings.doubao_video_ratio,
                        generate_audio=ctx.settings.doubao_generate_audio,
                    )
                else:
                    print(f"[VideoGenerator] 使用OpenAI兼容服务生成视频")
                    # OpenAI 兼容服务：使用图片字节流
                    reference_image_bytes: bytes | None = None
                    if use_image_mode and shot.image_url:
                        try:
                            if image_mode == "reference":
                                # 收集有图片的角色
                                char_image_urls = [c.image_url for c in characters if c.image_url]

                                # 拼接分镜图和角色图
                                reference_image_bytes = await self.image_composer.compose_reference_image(
                                    shot_image_url=shot.image_url,
                                    character_image_urls=char_image_urls,
                                )
                                await self.send_message(ctx, f"镜头 {shot_order}: 已生成参考图（分镜图 + {len(char_image_urls)} 个角色图）")
                                await ctx.session.commit()  # Release lock
                                print(f"[VideoGenerator] 镜头 {shot_order}: 已生成参考图（分镜图 + {len(char_image_urls)} 个角色图）")
                            else:
                                # 仅使用分镜首帧图
                                reference_image_bytes = await self.image_composer.compose_reference_image(
                                    shot_image_url=shot.image_url,
                                    character_image_urls=[],
                                )
                        except Exception as e:
                            await self.send_message(ctx, f"镜头 {shot_order}: 参考图生成失败，将使用文生视频模式: {e}")
                            await ctx.session.commit()  # Release lock
                            print(f"[VideoGenerator] 镜头 {shot_order}: 参考图生成失败，将使用文生视频模式: {e}")
                            reference_image_bytes = None

                    # OpenAI 兼容服务的 generate_url 接口
                    video_url = await ctx.video.generate_url(
                        prompt=video_prompt,
                        image_bytes=reference_image_bytes,
                    )

                shot.video_url = video_url
                shot.duration = duration  # 确保时长被记录
                ctx.session.add(shot)
                await ctx.session.flush()  # 确保更新生效
                # 发送分镜更新事件
                await self.send_shot_event(ctx, shot, "shot_updated")
                await ctx.session.commit()  # Release lock after update
                updated_count += 1
                print(f"[VideoGenerator] 分镜 {shot_order} 视频生成成功")
            except Exception as e:
                print(f"[VideoGenerator] 分镜 {shot_order} 视频生成失败: {e}")
                await self.send_message(ctx, f"镜头 {shot_order} 视频生成失败: {e}")
                await ctx.session.rollback()  # Rollback on error
        
        # Final commit just in case
        await ctx.session.commit()
        print(f"[VideoGenerator] 完成，成功生成 {updated_count}/{total} 个视频")
        # 完成消息
        if updated_count > 0:
            await self.send_message(ctx, f"✅ 已为 {updated_count} 个分镜生成视频，接下来将合成完整视频。", progress=1.0, is_loading=False)
        else:
            await self.send_message(ctx, f"❌ 所有分镜视频生成均失败。", progress=1.0, is_loading=False)
