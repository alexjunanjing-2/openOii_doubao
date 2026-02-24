"""
openOii Agent 工具定义模块

基于 Claude Agent SDK 的 @tool 装饰器定义可供 agent 使用的工具。
这些工具通过 MCP server 暴露给 Claude，让 AI 能够自主调用。
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from claude_agent_sdk import create_sdk_mcp_server, tool

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _tool_text(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": is_error}


# ============================================================================
# 全局状态 - 用于在工具调用之间共享数据库会话和项目上下文
# ============================================================================

class AgentState:
    """Agent 运行时状态"""
    def __init__(self):
        self.session: AsyncSession | None = None
        self.project_id: int | None = None
        self.ws_manager: Any = None

    def set_context(self, session: AsyncSession, project_id: int, ws_manager: Any = None):
        self.session = session
        self.project_id = project_id
        self.ws_manager = ws_manager

    def clear(self):
        self.session = None
        self.project_id = None
        self.ws_manager = None


# 全局状态实例
agent_state = AgentState()


# ============================================================================
# 项目管理工具
# ============================================================================

@tool("get_project_info", "获取当前项目的详细信息", {})
async def get_project_info(args: dict[str, Any]) -> dict[str, Any]:
    """获取项目信息"""
    from app.models.project import Project

    if not agent_state.session or not agent_state.project_id:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    project = await agent_state.session.get(Project, agent_state.project_id)
    if not project:
        return _tool_text("错误：项目不存在", is_error=True)

    return _tool_text(
        f"项目信息:\n- ID: {project.id}\n- 标题: {project.title}\n- 故事: {project.story}\n- 风格: {project.style}\n- 状态: {project.status}"
    )


@tool("update_project", "更新项目信息（标题、故事、风格）", {
    "title": str,
    "story": str,
    "style": str,
})
async def update_project(args: dict[str, Any]) -> dict[str, Any]:
    """更新项目信息"""
    from app.models.project import Project

    if not agent_state.session or not agent_state.project_id:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    project = await agent_state.session.get(Project, agent_state.project_id)
    if not project:
        return _tool_text("错误：项目不存在", is_error=True)

    updated = []
    if "title" in args and args["title"]:
        project.title = args["title"].strip()
        updated.append(f"标题: {project.title}")
    if "story" in args and args["story"]:
        project.story = args["story"].strip()
        updated.append(f"故事: {project.story[:50]}...")
    if "style" in args and args["style"]:
        project.style = args["style"].strip()
        updated.append(f"风格: {project.style}")

    if updated:
        agent_state.session.add(project)
        await agent_state.session.commit()
        return _tool_text(f"已更新项目:\n" + "\n".join(f"- {u}" for u in updated))

    return _tool_text("没有需要更新的内容")


# ============================================================================
# 角色管理工具
# ============================================================================

@tool("list_characters", "列出项目的所有角色", {})
async def list_characters(args: dict[str, Any]) -> dict[str, Any]:
    """列出所有角色"""
    from sqlalchemy import select
    from app.models.project import Character

    if not agent_state.session or not agent_state.project_id:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    res = await agent_state.session.execute(
        select(Character).where(Character.project_id == agent_state.project_id)
    )
    characters = res.scalars().all()

    if not characters:
        return _tool_text("项目暂无角色")

    text = "角色列表:\n"
    for c in characters:
        text += f"- [{c.id}] {c.name}: {c.description[:50] if c.description else '无描述'}...\n"
        text += f"  图片: {'有' if c.image_url else '无'}\n"

    return _tool_text(text)


@tool("create_character", "创建新角色", {"name": str, "description": str})
async def create_character(args: dict[str, Any]) -> dict[str, Any]:
    """创建角色"""
    from app.models.project import Character

    if not agent_state.session or not agent_state.project_id:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    name = args.get("name", "").strip()
    description = args.get("description", "").strip()

    if not name:
        return _tool_text("错误：角色名称不能为空", is_error=True)

    character = Character(
        project_id=agent_state.project_id,
        name=name,
        description=description or None,
        image_url=None,
    )
    agent_state.session.add(character)
    await agent_state.session.commit()
    await agent_state.session.refresh(character)

    character_id = character.id
    character_name = character.name
    return _tool_text(f"已创建角色 [{character_id}] {character_name}")


@tool("update_character", "更新角色信息", {"character_id": int, "name": str, "description": str})
async def update_character(args: dict[str, Any]) -> dict[str, Any]:
    """更新角色"""
    from app.models.project import Character

    if not agent_state.session:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    character_id = args.get("character_id")
    if not character_id:
        return _tool_text("错误：需要指定角色 ID", is_error=True)

    character = await agent_state.session.get(Character, character_id)
    if not character:
        return _tool_text(f"错误：角色 {character_id} 不存在", is_error=True)

    updated = []
    if "name" in args and args["name"]:
        character.name = args["name"].strip()
        updated.append(f"名称: {character.name}")
    if "description" in args and args["description"]:
        character.description = args["description"].strip()
        updated.append(f"描述: {character.description[:30]}...")

    if updated:
        agent_state.session.add(character)
        await agent_state.session.commit()
        return _tool_text(f"已更新角色 [{character_id}]:\n" + "\n".join(f"- {u}" for u in updated))

    return _tool_text("没有需要更新的内容")


@tool("delete_character", "删除角色", {"character_id": int})
async def delete_character(args: dict[str, Any]) -> dict[str, Any]:
    """删除角色"""
    from app.models.project import Character

    if not agent_state.session:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    character_id = args.get("character_id")
    if not character_id:
        return _tool_text("错误：需要指定角色 ID", is_error=True)

    character = await agent_state.session.get(Character, character_id)
    if not character:
        return _tool_text(f"错误：角色 {character_id} 不存在", is_error=True)

    name = character.name
    await agent_state.session.delete(character)
    await agent_state.session.commit()

    return _tool_text(f"已删除角色 [{character_id}] {name}")


# ============================================================================
# 分镜管理工具
# ============================================================================

@tool("list_shots", "列出项目的所有分镜", {})
async def list_shots(args: dict[str, Any]) -> dict[str, Any]:
    """列出分镜"""
    from sqlalchemy import select
    from app.models.project import Shot

    if not agent_state.session or not agent_state.project_id:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    res = await agent_state.session.execute(
        select(Shot)
        .where(Shot.project_id == agent_state.project_id)
        .order_by(Shot.order)
    )
    shots = res.scalars().all()

    if not shots:
        return _tool_text("项目暂无分镜")

    text = "分镜列表:\n"
    for s in shots:
        text += f"- [{s.id}] 镜头 {s.order}: {s.description[:40] if s.description else '无描述'}...\n"
        text += f"  图片: {'有' if s.image_url else '无'} | 视频: {'有' if s.video_url else '无'}\n"

    return _tool_text(text)


@tool("create_shot", "创建新分镜", {
    "order": int,
    "description": str,
    "prompt": str,
    "image_prompt": str,
})
async def create_shot(args: dict[str, Any]) -> dict[str, Any]:
    """创建分镜"""
    from app.models.project import Shot

    if not agent_state.session or not agent_state.project_id:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    order = args.get("order", 1)
    description = args.get("description", "").strip()
    prompt = args.get("prompt", "").strip() or description
    image_prompt = args.get("image_prompt", "").strip() or description

    if not description:
        return _tool_text("错误：分镜描述不能为空", is_error=True)

    shot = Shot(
        project_id=agent_state.project_id,
        order=order,
        description=description,
        prompt=prompt,
        image_prompt=image_prompt,
        image_url=None,
        video_url=None,
    )
    agent_state.session.add(shot)
    await agent_state.session.commit()
    await agent_state.session.refresh(shot)

    shot_id = shot.id
    shot_order = shot.order
    return _tool_text(f"已创建分镜 [{shot_id}] 镜头 {shot_order}")


@tool("update_shot", "更新分镜信息", {
    "shot_id": int,
    "order": int,
    "description": str,
    "prompt": str,
    "image_prompt": str,
})
async def update_shot(args: dict[str, Any]) -> dict[str, Any]:
    """更新分镜"""
    from app.models.project import Shot

    if not agent_state.session:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    shot_id = args.get("shot_id")
    if not shot_id:
        return _tool_text("错误：需要指定分镜 ID", is_error=True)

    shot = await agent_state.session.get(Shot, shot_id)
    if not shot:
        return _tool_text(f"错误：分镜 {shot_id} 不存在", is_error=True)

    updated = []
    if "order" in args and args["order"]:
        shot.order = args["order"]
        updated.append(f"顺序: {shot.order}")
    if "description" in args and args["description"]:
        shot.description = args["description"].strip()
        updated.append(f"描述: {shot.description[:30]}...")
    if "prompt" in args and args["prompt"]:
        shot.prompt = args["prompt"].strip()
        updated.append(f"视频提示词已更新")
    if "image_prompt" in args and args["image_prompt"]:
        shot.image_prompt = args["image_prompt"].strip()
        updated.append(f"图片提示词已更新")

    if updated:
        agent_state.session.add(shot)
        await agent_state.session.commit()
        return _tool_text(f"已更新分镜 [{shot_id}]:\n" + "\n".join(f"- {u}" for u in updated))

    return _tool_text("没有需要更新的内容")


@tool("delete_shot", "删除分镜", {"shot_id": int})
async def delete_shot(args: dict[str, Any]) -> dict[str, Any]:
    """删除分镜"""
    from app.models.project import Shot

    if not agent_state.session:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    shot_id = args.get("shot_id")
    if not shot_id:
        return _tool_text("错误：需要指定分镜 ID", is_error=True)

    shot = await agent_state.session.get(Shot, shot_id)
    if not shot:
        return _tool_text(f"错误：分镜 {shot_id} 不存在", is_error=True)

    order = shot.order
    await agent_state.session.delete(shot)
    await agent_state.session.commit()

    return _tool_text(f"已删除分镜 [{shot_id}] 镜头 {order}")


@tool("regenerate_shot_image", "标记分镜需要重新生成图片", {"shot_id": int})
async def regenerate_shot_image(args: dict[str, Any]) -> dict[str, Any]:
    """标记重新生成图片"""
    from app.models.project import Shot

    if not agent_state.session:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    shot_id = args.get("shot_id")
    if not shot_id:
        return _tool_text("错误：需要指定分镜 ID", is_error=True)

    shot = await agent_state.session.get(Shot, shot_id)
    if not shot:
        return _tool_text(f"错误：分镜 {shot_id} 不存在", is_error=True)

    shot.image_url = None
    agent_state.session.add(shot)
    await agent_state.session.commit()

    return _tool_text(f"分镜 [{shot_id}] 已标记为需要重新生成图片")


@tool("regenerate_shot_video", "标记分镜需要重新生成视频", {"shot_id": int})
async def regenerate_shot_video(args: dict[str, Any]) -> dict[str, Any]:
    """标记重新生成视频"""
    from app.models.project import Shot

    if not agent_state.session:
        return _tool_text("错误：未设置项目上下文", is_error=True)

    shot_id = args.get("shot_id")
    if not shot_id:
        return _tool_text("错误：需要指定分镜 ID", is_error=True)

    shot = await agent_state.session.get(Shot, shot_id)
    if not shot:
        return _tool_text(f"错误：分镜 {shot_id} 不存在", is_error=True)

    shot.video_url = None
    agent_state.session.add(shot)
    await agent_state.session.commit()

    return _tool_text(f"分镜 [{shot_id}] 已标记为需要重新生成视频")


# ============================================================================
# 创建 MCP Server
# ============================================================================

# 所有工具列表
ALL_TOOLS = [
    # 项目
    get_project_info,
    update_project,
    # 角色
    list_characters,
    create_character,
    update_character,
    delete_character,
    # 分镜
    list_shots,
    create_shot,
    update_shot,
    delete_shot,
    regenerate_shot_image,
    regenerate_shot_video,
]


def create_openOii_mcp_server():
    """创建 openOii 工具 MCP Server"""
    return create_sdk_mcp_server(
        name="openOii",
        version="0.1.0",
        tools=ALL_TOOLS,
    )


# 工具名称列表（用于 allowed_tools）
ALLOWED_TOOLS = [
    "mcp__openOii__get_project_info",
    "mcp__openOii__update_project",
    "mcp__openOii__list_characters",
    "mcp__openOii__create_character",
    "mcp__openOii__update_character",
    "mcp__openOii__delete_character",
    "mcp__openOii__list_shots",
    "mcp__openOii__create_shot",
    "mcp__openOii__update_shot",
    "mcp__openOii__delete_shot",
    "mcp__openOii__regenerate_shot_image",
    "mcp__openOii__regenerate_shot_video",
]
