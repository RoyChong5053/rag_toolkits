"""统一 API 客户端"""
import time
import base64
from pathlib import Path
from typing import Optional, List, Generator
from openai import OpenAI

from core.config import config


def create_client(api_type: str = "openrouter"):
    api_conf = config.get_api_config(api_type)
    extra_headers = None
    if api_type == "openrouter":
        extra_headers = {
            "HTTP-Referer": api_conf.get("site_url", "RAG-WebUI"),
            "X-Title": api_conf.get("site_name", "RAG-WebUI"),
        }
    client = OpenAI(
        base_url=api_conf["base_url"],
        api_key=api_conf["api_key"],
    )
    return client, extra_headers


def call_with_retry(client: OpenAI, model: str, messages: list,
                    max_retries: int = 3, retry_delay: int = 2,
                    extra_headers: Optional[dict] = None, **kwargs) -> str:
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                extra_headers=extra_headers,
                **kwargs
            )
            content = response.choices[0].message.content
            return content if content else ""
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                raise


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_mime_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/jpeg")


def build_rag_messages(system_prompt: str, user_text: str) -> list:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]


def build_vision_messages(prompt: str, image_base64: str, mime_type: str) -> list:
    return [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
        ],
    }]


def create_chunks(text: str, max_chars: int = 12000, overlap: int = 1) -> Generator[str, None, None]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    current_chunk, current_len = [], 0
    for para in paragraphs:
        para_len = len(para)
        if current_len + para_len > max_chars and current_chunk:
            yield "\n\n".join(current_chunk)
            overlap_paras = current_chunk[-overlap:] if len(current_chunk) >= overlap else current_chunk[-1:] if current_chunk else []
            current_chunk, current_len = list(overlap_paras), sum(len(p) for p in overlap_paras)
        current_chunk.append(para)
        current_len += para_len
    if current_chunk:
        yield "\n\n".join(current_chunk)


def strip_emoji(text: str) -> str:
    """从文本中移除 emoji（供 RAG chunk 预处理兜底使用）"""
    import re
    pattern = re.compile(
        "[\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U0001FB00-\U0001FBFF"
        "\U00002700-\U000027BF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002600-\U000026FF"
        "\U0001F170-\U0001F251"
        "\U0001F3FB-\U0001F3FF"
        "\U00002640-\U00002642"
        "\u200d"
        "]+",
        flags=re.UNICODE,
    )
    return pattern.sub("", text).replace("\u200b", "")
