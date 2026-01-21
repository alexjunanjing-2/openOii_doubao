from __future__ import annotations

import asyncio
from datetime import datetime, UTC

import redis.asyncio as redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext
from app.agents.character_artist import CharacterArtistAgent
from app.agents.director import DirectorAgent
from app.agents.onboarding import OnboardingAgent
from app.agents.scriptwriter import ScriptwriterAgent
from app.agents.storyboard_artist import StoryboardArtistAgent
from app.agents.video_generator import VideoGeneratorAgent
from app.agents.video_merger import VideoMergerAgent
from app.agents.review import ReviewAgent
from app.config import Settings
from app.models.agent_run import AgentMessage, AgentRun
from app.models.project import Character, Project, Scene, Shot
from app.schemas.project import GenerateRequest
from app.services.file_cleaner import delete_file, delete_files
from app.services.image import ImageService
from app.services.llm import LLMService
from app.services.video_factory import create_video_service
from app.ws.manager import ConnectionManager


# Agent 到工作流阶段的映射
AGENT_STAGE_MAP = {
    "onboarding": "ideate",
    "director": "ideate",
    "scriptwriter": "ideate",
    "character_artist": "visualize",
    "storyboard_artist": "visualize",
    "video_generator": "animate",
    "video_merger": "deploy",
    "review": "ideate",
}

# Agent 完成后的描述信息
AGENT_COMPLETION_INFO = {
    "onboarding": {
        "completed": "已完成项目初始化",
        "next": "接下来将由导演规划整体创作方向",
        "question": "项目设置看起来如何？",
    },
    "director": {
        "completed": "已完成创作方向规划",
        "next": "接下来编剧将创作剧本、设计角色和规划分镜",
        "question": "创作方向是否符合您的预期？",
    },
    "scriptwriter": {
        "completed": "已完成剧本创作",
        "details": "生成了角色设定、场景描述和分镜脚本",
        "next": "接下来将为角色生成参考图片",
        "question": "剧本内容和角色设定是否满意？如果需要修改，请告诉我具体的调整意见。",
    },
    "character_artist": {
        "completed": "已完成角色图片生成",
        "next": "接下来将为每个分镜生成首帧图片",
        "question": "角色形象是否符合您的想象？如果需要重新生成某个角色，请告诉我。",
    },
    "storyboard_artist": {
        "completed": "已完成分镜首帧图片生成",
        "next": "接下来将根据分镜生成视频片段",
        "question": "分镜画面是否满意？如果某些镜头需要调整，请告诉我。",
    },
    "video_generator": {
        "completed": "已完成视频片段生成",
        "next": "接下来将把所有片段拼接成完整视频",
        "question": "视频片段效果如何？是否需要重新生成某些镜头？",
    },
    "video_merger": {
        "completed": "已完成视频拼接",
        "next": "您的漫剧已经准备就绪！可以下载或分享了。",
        "question": "最终视频效果满意吗？",
    },
}


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        from app.config import get_settings

        settings = get_settings()
        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client


def get_confirm_event_key(run_id: int) -> str:
    return f"openoii:confirm:{run_id}"


def get_confirm_channel(run_id: int) -> str:
    return f"openoii:confirm_channel:{run_id}"


async def clear_confirm_event_redis(run_id: int) -> None:
    r = await get_redis()
    await r.delete(get_confirm_event_key(run_id))


async def trigger_confirm_redis(run_id: int) -> bool:
    """通过 Redis 发布 confirm 信号（用于多 worker 共享）"""
    r = await get_redis()
    await r.set(get_confirm_event_key(run_id), "1", ex=3600)  # 1 小时过期
    await r.publish(get_confirm_channel(run_id), "confirm")
    return True


async def wait_for_confirm_redis(run_id: int, timeout: int = 1800) -> bool:
    """通过 Redis 订阅等待 confirm 信号"""
    r = await get_redis()
    key = get_confirm_event_key(run_id)
    channel = get_confirm_channel(run_id)

    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        # 订阅前 confirm 先到的情况：用 key 兜底
        if await r.get(key):
            await r.delete(key)
            return True

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return False

            msg = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=min(1.0, remaining),
            )
            if msg is not None:
                await r.delete(key)
                return True

            # publish 丢失时，用 key 再兜底一次
            if await r.get(key):
                await r.delete(key)
                return True
    finally:
        try:
            await pubsub.unsubscribe(channel)
        finally:
            await pubsub.close()


class GenerationOrchestrator:
    def __init__(self, *, settings: Settings, ws: ConnectionManager, session: AsyncSession):
        self.settings = settings
        self.ws = ws
        self.session = session
        self._last_user_feedback_id: int | None = None
        self.agents = [
            OnboardingAgent(),
            DirectorAgent(),
            ScriptwriterAgent(),  # 生成角色+场景+分镜描述
            CharacterArtistAgent(),  # 生成角色图片
            StoryboardArtistAgent(),  # 生成分镜首帧图片
            VideoGeneratorAgent(),  # 生成分镜视频
            VideoMergerAgent(),  # 拼接完整视频
            ReviewAgent(),  # 处理用户反馈并路由重新生成（不会参与正常生成流程）
        ]

    def _agent_index(self, agent_name: str) -> int:
        for idx, agent in enumerate(self.agents):
            if agent.name == agent_name:
                return idx
        raise ValueError(f"Unknown agent: {agent_name}")

    async def _delete_project_shots(self, project_id: int) -> None:
        scene_ids_subq = select(Scene.id).where(Scene.project_id == project_id)
        await self.session.execute(delete(Shot).where(Shot.scene_id.in_(scene_ids_subq)))

    async def _delete_project_scenes(self, project_id: int) -> None:
        await self.session.execute(delete(Scene).where(Scene.project_id == project_id))

    async def _delete_project_characters(self, project_id: int) -> None:
        await self.session.execute(delete(Character).where(Character.project_id == project_id))

    async def _clear_character_images(self, project_id: int) -> None:
        """清空角色图片（先删除文件再清空 URL）"""
        res = await self.session.execute(
            select(Character).where(Character.project_id == project_id)
        )
        chars = res.scalars().all()
        # 先删除文件
        delete_files([char.image_url for char in chars])
        # 再清空 URL
        for char in chars:
            char.image_url = None
            self.session.add(char)

    async def _clear_shot_images(self, project_id: int) -> None:
        """清空分镜首帧图片（先删除文件再清空 URL）"""
        scene_ids_subq = select(Scene.id).where(Scene.project_id == project_id)
        res = await self.session.execute(select(Shot).where(Shot.scene_id.in_(scene_ids_subq)))
        shots = res.scalars().all()
        # 先删除文件
        delete_files([shot.image_url for shot in shots])
        # 再清空 URL
        for shot in shots:
            shot.image_url = None
            self.session.add(shot)

    async def _clear_shot_videos(self, project_id: int) -> None:
        """清空分镜视频（先删除文件再清空 URL）"""
        scene_ids_subq = select(Scene.id).where(Scene.project_id == project_id)
        res = await self.session.execute(select(Shot).where(Shot.scene_id.in_(scene_ids_subq)))
        shots = res.scalars().all()
        # 先删除文件
        delete_files([shot.video_url for shot in shots])
        # 再清空 URL
        for shot in shots:
            shot.video_url = None
            self.session.add(shot)

    async def _clear_project_video(self, project_id: int) -> None:
        """清空项目最终视频（先删除文件再清空 URL）"""
        project = await self.session.execute(select(Project).where(Project.id == project_id))
        proj = project.scalars().first()
        if proj:
            # 先删除文件
            delete_file(proj.video_url)
            # 再清空 URL
            proj.video_url = None
            self.session.add(proj)

    async def _cleanup_for_rerun(self, project_id: int, start_agent: str, mode: str = "full") -> None:
        """清理逻辑：根据重新运行的 agent 和模式清理数据

        Args:
            project_id: 项目 ID
            start_agent: 从哪个 agent 开始重新运行
            mode: "full" 全量清理，"incremental" 增量清理（只清理下游产物，保留数据）
        """
        cleared_types: list[str] = []

        if mode == "incremental":
            # 增量模式：只清理下游产物（图片/视频），保留数据结构
            if start_agent in {"onboarding", "director", "scriptwriter"}:
                # 增量模式下 scriptwriter 不删除数据，只清理下游产物
                await self._clear_character_images(project_id)
                await self._clear_shot_images(project_id)
                await self._clear_shot_videos(project_id)
                await self._clear_project_video(project_id)
                # 不发送 data_cleared 事件，因为数据结构保留
            elif start_agent == "character_artist":
                await self._clear_character_images(project_id)
                await self._clear_shot_images(project_id)
                await self._clear_shot_videos(project_id)
                await self._clear_project_video(project_id)
            elif start_agent == "storyboard_artist":
                await self._clear_shot_images(project_id)
                await self._clear_shot_videos(project_id)
                await self._clear_project_video(project_id)
            elif start_agent == "video_generator":
                await self._clear_shot_videos(project_id)
                await self._clear_project_video(project_id)
            elif start_agent == "video_merger":
                await self._clear_project_video(project_id)
            else:
                raise ValueError(f"Unsupported start_agent for cleanup: {start_agent}")
        else:
            # 全量模式：原有逻辑
            if start_agent in {"onboarding", "director", "scriptwriter"}:
                # 从头开始：删除角色、场景、镜头
                # 注意：必须先删除 Shot（依赖 Scene），再删除 Scene
                await self._delete_project_shots(project_id)
                await self._delete_project_scenes(project_id)
                await self._delete_project_characters(project_id)
                await self._clear_project_video(project_id)
                cleared_types = ["characters", "scenes", "shots"]
            elif start_agent == "character_artist":
                # 重新生成角色图片，并清空下游产物
                await self._clear_character_images(project_id)
                await self._clear_shot_images(project_id)
                await self._clear_shot_videos(project_id)
                await self._clear_project_video(project_id)
            elif start_agent == "storyboard_artist":
                # 重新生成分镜首帧，并清空下游产物
                await self._clear_shot_images(project_id)
                await self._clear_shot_videos(project_id)
                await self._clear_project_video(project_id)
            elif start_agent == "video_generator":
                # 重新生成分镜视频，并清空下游产物
                await self._clear_shot_videos(project_id)
                await self._clear_project_video(project_id)
            elif start_agent == "video_merger":
                # 重新拼接视频：清空 Project.video_url
                await self._clear_project_video(project_id)
            else:
                raise ValueError(f"Unsupported start_agent for cleanup: {start_agent}")

        await self.session.commit()

        # 通知前端数据已清理（仅全量模式）
        if cleared_types:
            await self.ws.send_event(
                project_id,
                {
                    "type": "data_cleared",
                    "data": {"cleared_types": cleared_types, "start_agent": start_agent, "mode": mode},
                },
            )

    async def _set_run(self, run: AgentRun, **fields) -> AgentRun:
        for k, v in fields.items():
            setattr(run, k, v)
        run.updated_at = utcnow()
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def _log(self, run_id: int, *, agent: str, role: str, content: str) -> None:
        msg = AgentMessage(run_id=run_id, agent=agent, role=role, content=content)
        self.session.add(msg)
        await self.session.commit()

    async def _wait_for_confirm(self, project_id: int, run_id: int, agent_name: str) -> str | None:
        # 获取 agent 完成信息
        info = AGENT_COMPLETION_INFO.get(agent_name, {})
        completed = info.get("completed", f"「{agent_name}」已完成")
        details = info.get("details", "")
        next_step = info.get("next", "继续下一步")
        question = info.get("question", "是否继续？")

        # 构建详细消息
        message_parts = [f"✅ {completed}"]
        if details:
            message_parts.append(f"📋 {details}")
        message_parts.append(f"➡️ {next_step}")
        message_parts.append(f"❓ {question}")

        full_message = "\n".join(message_parts)

        # 清理上一轮遗留的 confirm（避免误触导致直接跳过等待）
        await clear_confirm_event_redis(run_id)

        await self.ws.send_event(
            project_id,
            {
                "type": "run_awaiting_confirm",
                "data": {
                    "run_id": run_id,
                    "agent": agent_name,
                    "message": full_message,
                    "completed": completed,
                    "next_step": next_step,
                    "question": question,
                },
            },
        )

        try:
            ok = await wait_for_confirm_redis(run_id, timeout=1800)
            if not ok:
                raise asyncio.TimeoutError()
        except asyncio.TimeoutError:
            raise RuntimeError(f"等待确认超时（agent: {agent_name}）")

        await self.ws.send_event(
            project_id,
            {
                "type": "run_confirmed",
                "data": {"run_id": run_id, "agent": agent_name},
            },
        )

        # 刷新 session 以确保能读取到其他 session 提交的新数据
        await self.session.commit()  # 提交当前事务

        # 读取本次确认携带的最新用户反馈（若有）
        res = await self.session.execute(
            select(AgentMessage)
            .where(AgentMessage.run_id == run_id)
            .where(AgentMessage.role == "user")
            .order_by(AgentMessage.created_at.desc())
            .limit(1)
        )
        msg = res.scalars().first()
        if msg and msg.id != self._last_user_feedback_id and msg.content.strip():
            self._last_user_feedback_id = msg.id
            return msg.content.strip()

        return None

    async def run_from_agent(
        self,
        *,
        project_id: int,
        run_id: int,
        request: GenerateRequest,
        agent_name: str,
        auto_mode: bool = False,
    ) -> None:
        project = await self.session.get(Project, project_id)
        run = await self.session.get(AgentRun, run_id)
        if not project or not run:
            return

        try:
            self._agent_index(agent_name)

            await self._set_run(
                run, status="running", current_agent="orchestrator", progress=0.01, error=None
            )
            await self.ws.send_event(
                project_id,
                {"type": "run_started", "data": {"run_id": run_id, "project_id": project_id}},
            )
            await self._log(
                run_id,
                agent="orchestrator",
                role="system",
                content=f"Generate started from {agent_name}: {request!r}",
            )

            ctx = AgentContext(
                settings=self.settings,
                session=self.session,
                ws=self.ws,
                project=project,
                run=run,
                llm=LLMService(self.settings),
                image=ImageService(self.settings),
                video=create_video_service(self.settings),
            )

            # 初始化当前 run 已存在的用户反馈消息（避免后续确认不带反馈时误读历史反馈）
            res = await ctx.session.execute(
                select(AgentMessage.id)
                .where(AgentMessage.run_id == ctx.run.id)
                .where(AgentMessage.role == "user")
                .order_by(AgentMessage.created_at.desc())
                .limit(1)
            )
            self._last_user_feedback_id = res.scalar_one_or_none()

            prev_handoff_agent: str | None = None
            if agent_name == "review":
                # 让后续 agent 能直接读取用户反馈（例如编剧需要遵循数量限制等）
                res = await ctx.session.execute(
                    select(AgentMessage)
                    .where(AgentMessage.run_id == ctx.run.id)
                    .where(AgentMessage.role == "user")
                    .order_by(AgentMessage.created_at.desc())
                    .limit(1)
                )
                msg = res.scalars().first()
                if msg and msg.content.strip():
                    ctx.user_feedback = msg.content.strip()
                elif request.notes and request.notes.strip():
                    ctx.user_feedback = request.notes.strip()

                prev_handoff_agent = "review"
                review_agent = self.agents[self._agent_index("review")]

                await self._set_run(run, current_agent=review_agent.name, progress=0.0)
                await self.ws.send_event(
                    project_id,
                    {
                        "type": "run_progress",
                        "data": {
                            "run_id": run_id,
                            "current_agent": review_agent.name,
                            "stage": AGENT_STAGE_MAP.get(review_agent.name, "ideate"),
                            "progress": 0.0,
                        },
                    },
                )

                routing = await review_agent.run(ctx)
                start_agent = routing.get("start_agent") if isinstance(routing, dict) else None
                # 直接从 routing 读取 mode（review.py 已经解析好了）
                mode = "full"
                if isinstance(routing, dict):
                    m = routing.get("mode")
                    if isinstance(m, str) and m.strip() in ("incremental", "full"):
                        mode = m.strip()
                if not (isinstance(start_agent, str) and start_agent.strip()):
                    start_agent = "scriptwriter"
                agent_name = start_agent.strip()
                self._agent_index(agent_name)  # validate
                # 保存 mode 到 ctx 供 scriptwriter 使用
                ctx.rerun_mode = mode
                await self._log(
                    run_id,
                    agent="orchestrator",
                    role="system",
                    content=f"Review routed to {agent_name} (mode={mode}): {routing!r}",
                )

            await self._cleanup_for_rerun(project_id, agent_name, mode=getattr(ctx, 'rerun_mode', 'full'))

            # 刷新 project 对象，因为 cleanup 可能修改了它
            await self.session.refresh(ctx.project)

            start_idx = self._agent_index(agent_name)
            plan = [a.name for a in self.agents[start_idx:] if a.name != "review"]

            i = 0
            while i < len(plan):
                cur_name = plan[i]
                cur_idx = self._agent_index(cur_name)
                agent = self.agents[cur_idx]

                # 发送 Agent 邀请消息
                prev_agent_name: str | None = None
                if i > 0:
                    prev_agent_name = plan[i - 1]
                elif prev_handoff_agent:
                    prev_agent_name = prev_handoff_agent

                if prev_agent_name:
                    await self.ws.send_event(
                        project_id,
                        {
                            "type": "agent_handoff",
                            "data": {
                                "from_agent": prev_agent_name,
                                "to_agent": agent.name,
                                "message": f"@{prev_agent_name} 邀请 @{agent.name} 加入了群聊",
                            },
                        },
                    )

                progress = i / max(len(plan), 1)
                await self._set_run(run, current_agent=agent.name, progress=progress)
                await self.ws.send_event(
                    project_id,
                    {
                        "type": "run_progress",
                        "data": {
                            "run_id": run_id,
                            "current_agent": agent.name,
                            "stage": AGENT_STAGE_MAP.get(agent.name, "ideate"),
                            "progress": progress,
                        },
                    },
                )

                await agent.run(ctx)

                # 最后一个 agent 完成后，设置项目状态为 ready
                if i == len(plan) - 1:
                    ctx.project.status = "ready"
                    ctx.session.add(ctx.project)
                    await ctx.session.commit()

                if not auto_mode and i < (len(plan) - 1):
                    feedback = await self._wait_for_confirm(project_id, run_id, agent.name)
                    if feedback:
                        # 用户提供了反馈，跳转到 review agent 处理
                        ctx.user_feedback = feedback
                        await self._log(
                            run_id,
                            agent="orchestrator",
                            role="system",
                            content=f"User feedback received, routing to review: {feedback[:100]}...",
                        )

                        # 调用 review agent 分析反馈并决定从哪个 agent 重新开始
                        review_agent = self.agents[self._agent_index("review")]
                        routing = await review_agent.run(ctx)
                        start_agent = (
                            routing.get("start_agent") if isinstance(routing, dict) else None
                        )
                        # 直接从 routing 读取 mode（review.py 已经解析好了）
                        mode = "full"
                        if isinstance(routing, dict):
                            m = routing.get("mode")
                            if isinstance(m, str) and m.strip() in ("incremental", "full"):
                                mode = m.strip()
                        if not (isinstance(start_agent, str) and start_agent.strip()):
                            start_agent = "scriptwriter"
                        agent_name = start_agent.strip()
                        self._agent_index(agent_name)  # validate
                        # 保存 mode 到 ctx 供 scriptwriter 使用
                        ctx.rerun_mode = mode
                        await self._log(
                            run_id,
                            agent="orchestrator",
                            role="system",
                            content=f"Review routed to {agent_name} (mode={mode}): {routing!r}",
                        )

                        # 清理并重新规划
                        await self._cleanup_for_rerun(project_id, agent_name, mode=mode)
                        # 刷新 project 对象，因为 cleanup 可能修改了它
                        await self.session.refresh(ctx.project)
                        start_idx = self._agent_index(agent_name)
                        plan = [a.name for a in self.agents[start_idx:] if a.name != "review"]
                        i = 0
                        prev_handoff_agent = "review"
                        continue

                i += 1

            await self._set_run(run, status="succeeded", current_agent=None, progress=1.0)
            await self.ws.send_event(
                project_id, {"type": "run_completed", "data": {"run_id": run_id}}
            )
        except Exception as e:
            # 先 rollback 以清理可能的脏状态
            await self.session.rollback()
            try:
                await self._log(
                    run_id, agent="orchestrator", role="system", content=f"Run failed: {e!r}"
                )
                await self._set_run(run, status="failed", error=str(e))
            except Exception:
                pass  # 如果日志记录也失败，忽略
            await self.ws.send_event(
                project_id, {"type": "run_failed", "data": {"run_id": run_id, "error": str(e)}}
            )
        finally:
            await clear_confirm_event_redis(run_id)

    async def run(
        self, *, project_id: int, run_id: int, request: GenerateRequest, auto_mode: bool = False
    ) -> None:
        await self.run_from_agent(
            project_id=project_id,
            run_id=run_id,
            request=request,
            agent_name=self.agents[0].name,
            auto_mode=auto_mode,
        )
