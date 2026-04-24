"""DeepSeek client wrapper."""

from openai import OpenAI

from azdeeploy.config import Settings


def build_deepseek_client(settings: Settings | None = None) -> OpenAI:
    """Create an OpenAI-compatible client pointed at DeepSeek."""
    cfg = settings or Settings()
    return OpenAI(api_key=cfg.deepseek_api_key, base_url=cfg.deepseek_base_url)
