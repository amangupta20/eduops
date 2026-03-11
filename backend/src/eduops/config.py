from typing import Literal
from pydantic import BaseModel

class LLMConfig(BaseModel):
    # Literal restricts the provider to only these specific strings
    provider: Literal["openai", "gemini", "openrouter", "custom"]
    api_key: str
    model: str
    base_url: str = "" # Defaults to an empty string if not provided

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