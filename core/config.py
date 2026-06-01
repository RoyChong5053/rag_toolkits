"""统一配置管理"""
import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("Config")

DEFAULT_CONFIG: Dict[str, Any] = {
    "api": {
        "openrouter": {
            "api_key": "",
            "base_url": "https://openrouter.ai/api/v1",
            "site_url": "RAG-WebUI",
            "site_name": "RAG-WebUI",
        },
        "local": {
            "base_url": "http://127.0.0.1:12888/v1",
        },
        "deepseek": {
            "api_key": "",
            "base_url": "https://api.deepseek.com/v1",
        },
    },
    "rag": {
        "models": {
            "openrouter": "nvidia/nemotron-nano-12b-v2-vl:free",
            "deepseek": "deepseek-chat",
            "local": "local-model",
        },
        "max_input_chars": 12000,
        "request_interval": 1,
        "overlap_paragraphs": 1,
        "auto_save_interval": 5,
        "keep_intermediate_files": True,
        "max_retries_cloud": 5,
        "max_retries_local": 2,
        "retry_delay_base": 2,
    },
    "ocr": {
        "models": {
            "openrouter": "nvidia/nemotron-nano-12b-v2-vl:free",
            "deepseek": "deepseek-chat",
            "local": "local-model",
        },
        "input_dir": "./input/photo",
        "output_dir": "output/ocr",
        "default_prompt": "请帮我提取图片中的文字内容，如果图片中没有文字，请描述图片的主要内容和信息。",
        "max_tokens": 2000,
        "temperature": 0.1,
        "timeout": 120,
        "retry_attempts": 3,
        "delay_between_requests": 1,
    },
    "preprocess": {
        "input_dir": "input/raw",
        "output_dir": "input/clean",
        "remove_emoji": True,
        "split_threshold_mb": 5,
        "target_mb_per_file": 1,
    },
}


class ConfigManager:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config = self._load()

    def _load(self) -> Dict:
        cfg = self.config_path

        if not cfg.exists():
            old_ocr = Path("ocr_config.json")
            if old_ocr.exists():
                return self._migrate(cfg, old_ocr)
            self._save(DEFAULT_CONFIG)
            logger.info(f"已创建默认配置: {cfg}")
            return dict(DEFAULT_CONFIG)

        try:
            with open(cfg) as f:
                user = json.load(f)
        except Exception as e:
            logger.warning(f"读取配置失败: {e}，使用默认配置")
            return dict(DEFAULT_CONFIG)

        if "api" in user:
            merged = self._deep_merge(dict(DEFAULT_CONFIG), user)
            self._apply_env_overrides(merged)
            return merged

        old_ocr = Path("ocr_config.json")
        return self._migrate(cfg, old_ocr if old_ocr.exists() else None)

    def _migrate(self, old_rag: Path, old_ocr: Optional[Path] = None) -> Dict:
        new = dict(DEFAULT_CONFIG)

        if old_rag and old_rag.exists():
            try:
                with open(old_rag) as f:
                    old = json.load(f)
                new["api"]["openrouter"]["api_key"] = old.get("api_key", "")
                new["api"]["openrouter"]["site_url"] = old.get("site_url", "RAG-WebUI")
                new["api"]["openrouter"]["site_name"] = old.get("site_name", "RAG-WebUI")
                new["rag"]["models"]["openrouter"] = old.get("model", new["rag"]["models"]["openrouter"])
                new["rag"]["max_input_chars"] = old.get("max_input_chars", new["rag"]["max_input_chars"])
                new["rag"]["request_interval"] = old.get("request_interval", new["rag"]["request_interval"])
            except Exception as e:
                logger.warning(f"旧配置迁移失败: {e}")

        if old_ocr and old_ocr.exists():
            try:
                with open(old_ocr) as f:
                    old = json.load(f)
                or_api = old.get("openrouter_api", {})
                if or_api.get("api_key"):
                    new["api"]["openrouter"]["api_key"] = or_api["api_key"]
                new["ocr"]["models"]["openrouter"] = or_api.get("model", new["ocr"]["models"]["openrouter"])
                new["ocr"]["default_prompt"] = old.get("prompt", new["ocr"]["default_prompt"])
                new["ocr"]["input_dir"] = old.get("input_dir", new["ocr"]["input_dir"])
                new["ocr"]["output_dir"] = old.get("output_dir", new["ocr"]["output_dir"])
                new["ocr"]["max_tokens"] = old.get("max_tokens", new["ocr"]["max_tokens"])
                new["ocr"]["temperature"] = old.get("temperature", new["ocr"]["temperature"])
                new["ocr"]["timeout"] = old.get("timeout", new["ocr"]["timeout"])
                new["ocr"]["retry_attempts"] = old.get("retry_attempts", new["ocr"]["retry_attempts"])
                new["ocr"]["delay_between_requests"] = old.get("delay_between_requests", new["ocr"]["delay_between_requests"])
                local_url = old.get("local_api", {}).get("url", "")
                if local_url:
                    new["api"]["local"]["base_url"] = local_url.replace("/chat/completions", "")
            except Exception as e:
                logger.warning(f"旧 OCR 配置迁移失败: {e}")

        for p in [old_rag, old_ocr]:
            if p and p.exists():
                try:
                    p.rename(p.with_suffix(p.suffix + ".old"))
                except Exception:
                    pass

        self._save(new)
        logger.info("已从旧配置迁移到新格式")
        return new

    def _apply_env_overrides(self, cfg: Dict):
        env_key = os.environ.get("OPENROUTER_API_KEY")
        if env_key:
            cfg["api"]["openrouter"]["api_key"] = env_key
        env_url = os.environ.get("LOCAL_API_URL")
        if env_url:
            cfg["api"]["local"]["base_url"] = env_url
        env_deepseek = os.environ.get("DEEPSEEK_API_KEY")
        if env_deepseek:
            cfg["api"]["deepseek"]["api_key"] = env_deepseek

    def _save(self, data: Dict):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        result = dict(base)
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = ConfigManager._deep_merge(result[k], v)
            else:
                result[k] = v
        return result

    def get(self, *keys, default=None):
        c = self.config
        for k in keys:
            if isinstance(c, dict):
                c = c.get(k)
                if c is None:
                    return default
            else:
                return default
        return c if c is not None else default

    def set(self, value, *keys):
        c = self.config
        for k in keys[:-1]:
            if k not in c or not isinstance(c[k], dict):
                c[k] = {}
            c = c[k]
        c[keys[-1]] = value
        self._save(self.config)

    def save(self):
        self._save(self.config)

    @property
    def api_key(self):
        env_key = os.environ.get("OPENROUTER_API_KEY")
        return env_key or self.get("api", "openrouter", "api_key", default="")

    def get_api_config(self, api_type: str = "openrouter") -> Dict:
        base = self.get("api", api_type, "base_url", default="")
        if api_type == "deepseek":
            env_key = os.environ.get("DEEPSEEK_API_KEY")
            return {
                "base_url": base,
                "api_key": env_key or self.get("api", "deepseek", "api_key", default=""),
            }
        if api_type == "openrouter":
            return {
                "base_url": base,
                "api_key": self.api_key,
                "site_url": self.get("api", "openrouter", "site_url", default="RAG-WebUI"),
                "site_name": self.get("api", "openrouter", "site_name", default="RAG-WebUI"),
            }
        return {"base_url": base, "api_key": "sk-no-key-required"}


config = ConfigManager()
