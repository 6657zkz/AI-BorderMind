"""LLM 抽象层：DeepSeek / 通义千问（百炼）OpenAI 兼容。"""

from .client import LLMClient, LLMError, get_client
from .config import LLMSettings, get_settings

__all__ = ["LLMClient", "LLMError", "LLMSettings", "get_client", "get_settings"]
