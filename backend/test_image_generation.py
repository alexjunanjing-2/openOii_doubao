#!/usr/bin/env python
"""测试 ModelScope 图片生成功能"""
import asyncio
from app.config import get_settings
from app.services.image import ImageService


async def main():
    print("🎨 测试 ModelScope 图片生成功能...")
    print()

    settings = get_settings()
    print(f"📋 配置信息:")
    print(f"  - Base URL: {settings.image_base_url}")
    print(f"  - Model: {settings.image_model}")
    print(f"  - API Key: {settings.image_api_key[:20]}..." if settings.image_api_key else "  - API Key: None")
    print()

    service = ImageService(settings)

    # 检测是否是 ModelScope API
    is_modelscope = service._is_modelscope_api()
    print(f"✅ ModelScope API 检测: {is_modelscope}")
    print()

    if not is_modelscope:
        print("❌ 错误: 当前配置不是 ModelScope API")
        return

    # 测试图片生成
    prompt = "A golden cat"
    print(f"🎨 生成图片: {prompt}")
    print("⏳ 请稍候，这可能需要几分钟...")
    print()

    try:
        image_url = await service.generate_url(prompt=prompt)
        print(f"✅ 图片生成成功!")
        print(f"📸 图片 URL: {image_url}")
        print()
        print("🎉 测试完成!")
    except Exception as e:
        print(f"❌ 图片生成失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
