#!/usr/bin/env python3
"""RAG 知识提取处理器 - CLI 版本"""
import sys
import os
import time
import json
import threading
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from openai import OpenAI

from core.config import config
from core.client import create_client, call_with_retry, build_rag_messages, create_chunks, strip_emoji
from core.prompts import PROMPT_TEMPLATES, get_template, interactive_select

logger = logging.getLogger("RAG")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)


class CheckpointManager:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.checkpoint_dir = Path("checkpoints")
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / f"{session_id}.json"

    def save_checkpoint(self, data: Dict):
        try:
            with open(self.checkpoint_file, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存检查点失败: {e}")

    def load_checkpoint(self) -> Optional[Dict]:
        if not self.checkpoint_file.exists():
            return None
        try:
            with open(self.checkpoint_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载检查点失败: {e}")
            return None

    def clear_checkpoint(self):
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()


class ProgressAnimator:
    def __init__(self):
        self.running = False
        self.thread = None
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current = 0
        self.message = ""

    def start(self, msg: str = "Processing"):
        if self.running:
            self.stop()
        self.running = True
        self.message = msg
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 20) + "\r")
        sys.stdout.flush()

    def _animate(self):
        while self.running:
            frame = self.frames[self.current % len(self.frames)]
            sys.stdout.write(f"\r{frame} {self.message}...")
            sys.stdout.flush()
            self.current += 1
            time.sleep(0.1)


class RAGProcessor:
    def __init__(self, input_file: str, api_type: str = "openrouter",
                 model: str = None, resume: bool = True,
                 system_prompt: str = None, user_template: str = None):
        self.input_file = input_file
        self.api_type = api_type
        self.resume = resume

        self.client, self.extra_headers = create_client(api_type)

        if model:
            self.model = model
        else:
            models = config.get("rag", "models", default={})
            self.model = models.get(api_type, models.get("openrouter", "gpt-3.5-turbo"))

        self.max_input_chars = config.get("rag", "max_input_chars", default=12000)
        self.request_interval = config.get("rag", "request_interval", default=1)
        self.overlap_paragraphs = config.get("rag", "overlap_paragraphs", default=1)
        self.auto_save_interval = config.get("rag", "auto_save_interval", default=5)
        self.keep_intermediate = config.get("rag", "keep_intermediate_files", default=True)

        retry_key = "max_retries_local" if api_type == "local" else "max_retries_cloud"
        self.max_retries = config.get("rag", retry_key, default=3)
        self.retry_delay_base = config.get("rag", "retry_delay_base", default=2)

        if system_prompt and user_template:
            self.system_prompt = system_prompt
            self.user_template = user_template
        else:
            tpl = get_template(config.get("prompts", "current", default="标准知识提取"))
            self.system_prompt = tpl["system"]
            self.user_template = tpl["user_template"]

        Path("output/rag").mkdir(parents=True, exist_ok=True)
        Path("intermediate").mkdir(exist_ok=True)

        self.session_id = f"{Path(input_file).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.checkpoint_manager = CheckpointManager(self.session_id)
        self.animator = ProgressAnimator()

        Path("logs").mkdir(exist_ok=True)
        log_file = Path("logs") / f"rag_{self.session_id}.log"
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
        logger.addHandler(fh)

        logger.info(f"会话: {self.session_id}, 模型: {self.model}, API: {api_type}")

    def read_file(self) -> str:
        if not Path(self.input_file).exists():
            raise FileNotFoundError(f"文件未找到: {self.input_file}")
        with open(self.input_file, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info(f"读取文件: {self.input_file} ({len(content)} 字符)")
        return content

    def _make_chunks(self, text: str) -> list:
        return list(create_chunks(text, self.max_input_chars, self.overlap_paragraphs))

    def process_chunk(self, text: str, chunk_id: int) -> str:
        safe_text = strip_emoji(text)
        messages = build_rag_messages(self.system_prompt, self.user_template.format(text=safe_text))
        for attempt in range(self.max_retries):
            try:
                self.animator.start(f"块 {chunk_id}")
                content = call_with_retry(
                    self.client, self.model, messages,
                    max_retries=1, extra_headers=self.extra_headers,
                    temperature=0.3,
                )
                self.animator.stop()
                return content if content else "[Empty Response]"
            except KeyboardInterrupt:
                self.animator.stop()
                raise
            except Exception as e:
                self.animator.stop()
                logger.warning(f"块 {chunk_id} 失败 ({attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay_base * (attempt + 1))
        return f"__FAILED_CHUNK_{chunk_id}__"

    def _save_intermediate(self, results: list, count: int):
        path = Path(f"intermediate/temp_chunk_{count}.md")
        with open(path, "w") as f:
            f.write("\n\n---\n\n".join(results))

    def _save_final(self, results: list, suffix: str = ""):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = Path(self.input_file).stem
        out = Path("output/rag") / f"{name}_RAG{suffix}_{ts}.md"
        with open(out, "w") as f:
            f.write(
                f"# RAG Knowledge Base\n"
                f"**Source**: {self.input_file}\n"
                f"**Model**: {self.model}\n"
                f"**Date**: {ts}\n\n---\n\n"
            )
            f.write("\n\n---\n\n".join(results))
        print(f"\n✅ 处理完成! 结果已保存:\n👉 {out}")
        logger.info(f"结果已保存: {out}")

    def run(self):
        DONE, ERR = "✅", "❌"
        results = []
        try:
            print(f"\n{'='*60}")
            print(f"  📄 RAG 知识提取")
            print(f"{'='*60}")
            print(f"  文件: {self.input_file}")
            print(f"  模型: {self.model}")
            print(f"  API:  {self.api_type}")
            print(f"{'='*60}")

            text = self.read_file()
            chunks = self._make_chunks(text)
            total = len(chunks)
            print(f"  分块: {total} 块\n")

            start_index = 0
            if self.resume:
                cp = self.checkpoint_manager.load_checkpoint()
                if cp:
                    yn = input(f"\n发现未完成任务 (已处理 {cp['processed_count']}/{cp['total_chunks']} 块)\n继续? (y/n): ").lower()
                    if yn == "y":
                        results = cp.get("results", [])
                        start_index = cp.get("processed_count", 0)
                        print(f"  从块 {start_index + 1} 继续\n")

            for i in range(start_index, total):
                chunk_id = i + 1
                res = self.process_chunk(chunks[i], chunk_id)
                results.append(res)

                self.checkpoint_manager.save_checkpoint({
                    "session_id": self.session_id,
                    "input_file": self.input_file,
                    "total_chunks": total,
                    "processed_count": len(results),
                    "results": results,
                    "timestamp": datetime.now().isoformat(),
                })

                if chunk_id % self.auto_save_interval == 0:
                    self._save_intermediate(results, chunk_id)

                if i < total - 1:
                    print(f"{DONE} 块 {chunk_id}/{total} 完成. 等待 {self.request_interval}s...")
                    time.sleep(self.request_interval)
                else:
                    print(f"{DONE} 块 {chunk_id}/{total} 完成.")

            self._save_final(results)
            self.checkpoint_manager.clear_checkpoint()

        except KeyboardInterrupt:
            print(f"\n\n⏹️  中断。正在保存进度...")
            if results:
                self._save_final(results, suffix="_INTERRUPTED")
        except Exception as e:
            print(f"\n{ERR} 错误: {e}")
            logger.error(f"错误: {e}", exc_info=True)
            if results:
                self._save_final(results, suffix="_ERROR")


def main():
    parser = argparse.ArgumentParser(description="RAG 知识提取工具")
    parser.add_argument("input_file", nargs="?", default="input.txt", help="输入文本文件")
    parser.add_argument("--provider", choices=["openrouter", "local", "deepseek"], default="openrouter")
    parser.add_argument("--local-url", default=None, help="本地 API 地址")
    parser.add_argument("--model", default=None, help="模型名称")
    parser.add_argument("--prompt", default=None, help="Prompt 模板名称")
    parser.add_argument("--no-resume", action="store_true", help="禁用断点续传")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        for h in logger.handlers:
            h.setLevel(logging.DEBUG)

    if args.local_url:
        os.environ["LOCAL_API_URL"] = args.local_url

    system_prompt = user_template = None
    if args.prompt:
        tpl = get_template(args.prompt)
        system_prompt, user_template = tpl["system"], tpl["user_template"]
    else:
        system_prompt, user_template = interactive_select()

    processor = RAGProcessor(
        input_file=args.input_file,
        api_type=args.provider,
        model=args.model,
        resume=not args.no_resume,
        system_prompt=system_prompt,
        user_template=user_template,
    )
    processor.run()


if __name__ == "__main__":
    main()
