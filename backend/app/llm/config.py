"""LLM 配置：统一管理 DeepSeek / 通义千问（百炼）两个 OpenAI 兼容端点。

运行期系统只消费 LLM 能力（不训练/不生成参数），此处仅负责：
  * 从环境变量加载 provider / endpoint / key / model
  * 切换 provider 时无需改动调用方代码
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# backend/.env（与 uvicorn 启动目录一致）；已存在则不覆盖
load_dotenv()

# 各提供商的 OpenAI 兼容默认端点 / 默认模型 / 密钥环境变量
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "api_key_env": "QWEN_API_KEY",
    },
    "mimo": {
        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "default_model": "mimo-v2.5-pro",
        "api_key_env": "MIMO_API_KEY",
    },
}


class LLMSettings(BaseModel):
    provider: str = Field(default="deepseek")
    base_url: str
    api_key: str = ""
    model: str
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout: float = 60.0

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


def _build_settings() -> LLMSettings:
    provider = os.getenv("LLM_PROVIDER", "deepseek").lower()
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["deepseek"])
    prefix = provider.upper()
    return LLMSettings(
        provider=provider,
        base_url=os.getenv(f"{prefix}_BASE_URL", preset["base_url"]),
        api_key=os.getenv(preset["api_key_env"], ""),
        model=os.getenv(f"{prefix}_MODEL", preset["default_model"]),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
        timeout=float(os.getenv("LLM_TIMEOUT", "60.0")),
    )


@lru_cache
def get_settings() -> LLMSettings:
    return _build_settings()
