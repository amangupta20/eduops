import os
from pathlib import Path
from typing import Literal

import tomli
import tomli_w
from pydantic import BaseModel, ValidationError


class LLMConfig(BaseModel):
    # Literal restricts the provider to only these specific strings
    provider: Literal["openai", "gemini", "openrouter", "custom"]
    api_key: str
    model: str
    base_url: str = ""  # Defaults to an empty string if not provided


class ImagesConfig(BaseModel):
    # Defines the default list of approved images
    approved: list[str] = [
        "nginx:alpine",
        "httpd:alpine",
        "python:3.11-slim",
        "alpine:3",
        "busybox:latest",
        "node:20-alpine",
    ]


class Config(BaseModel):
    # This is the top-level model that groups the other two together
    llm: LLMConfig
    images: ImagesConfig = ImagesConfig()


def get_config_path() -> Path:
    return Path.home() / ".eduops" / "config.toml"


def load_config() -> Config | None:
    config_path = get_config_path()
    if not config_path.exists():
        return None

    try:
        with open(config_path, "rb") as f:
            data = tomli.load(f)
    except Exception:
        return None

    if "llm" not in data:
        return None

    llm_data = data["llm"]
    provider = llm_data.get("provider", "openai")
    # Write the defaulted provider back so Pydantic sees it
    if "provider" not in llm_data:
        llm_data["provider"] = provider
    base_url = llm_data.get("base_url", "")

    # Derive base_url from provider if not explicitly provided
    if not base_url:
        if provider == "openai":
            base_url = ""  # Will use OpenAI client default
        elif provider == "gemini":
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        elif provider == "openrouter":
            base_url = "https://openrouter.ai/api/v1"
        llm_data["base_url"] = base_url

    try:
        return Config(**data)
    except ValidationError:
        return None


def save_config(config: Config) -> None:
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "llm": {
            "provider": config.llm.provider,
            "api_key": config.llm.api_key,
            "model": config.llm.model,
            "base_url": config.llm.base_url,
        },
        "images": {
            "approved": config.images.approved,
        },
    }
    config_path.write_bytes(tomli_w.dumps(data).encode("utf-8"))
    # Restrict permissions to owner-only since the file contains the API key
    os.chmod(config_path, 0o600)
