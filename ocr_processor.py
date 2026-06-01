#!/usr/bin/env python3
"""OCR 图片文字识别处理器 - CLI 版本"""
import os
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple

from core.config import config
from core.client import create_client, call_with_retry, encode_image, get_mime_type, build_vision_messages

IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}


class OCRProcessor:
    def __init__(self):
        self.setup_directories()

    def setup_directories(self):
        self.output_dir = Path(config.get("ocr", "output_dir", default="output/ocr"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = self.output_dir / f"ocr_knowledge_{ts}.md"
        self.log_file = self.output_dir / "process_log.jsonl"
        self.summary_file = self.output_dir / f"summary_{ts}.txt"

    def collect_images(self, input_dir: Path) -> List[Path]:
        images = []
        for ext in IMG_EXTENSIONS:
            images.extend(input_dir.glob(f"*{ext}"))
            images.extend(input_dir.glob(f"*{ext.upper()}"))
        return sorted(set(images))

    def log_result(self, filename: str, success: bool, content: str, duration: float, api_type: str):
        entry = {
            "filename": filename,
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "duration": round(duration, 2),
            "content_preview": content[:100] if success else content,
            "api_type": api_type,
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def process_image(self, image_path: Path, client, model: str, prompt: str) -> Tuple[bool, str]:
        try:
            b64 = encode_image(str(image_path))
            mime = get_mime_type(str(image_path))
            messages = build_vision_messages(prompt, b64, mime)
            content = call_with_retry(
                client, model, messages,
                max_retries=config.get("ocr", "retry_attempts", default=3),
                retry_delay=config.get("ocr", "retry_delay_base", default=2),
                extra_headers=None,
                max_tokens=config.get("ocr", "max_tokens", default=2000),
                temperature=config.get("ocr", "temperature", default=0.1),
            )
            return True, content
        except Exception as e:
            return False, f"处理失败: {e}"

    def run(self, input_dir: Optional[str] = None, api_type: str = "local",
            model: str = None, prompt: str = None):
        DONE, ERR = "✅", "❌"
        input_path = Path(input_dir) if input_dir else Path(config.get("ocr", "input_dir", default="./input/photo"))

        if not model:
            models = config.get("ocr", "models", default={})
            model = models.get(api_type, models.get("openrouter", "gpt-4o-mini"))
        if not prompt:
            prompt = config.get("ocr", "default_prompt")

        client, _ = create_client(api_type)

        print(f"\n{'='*60}")
        print(f"  🖼️  OCR 批量处理")
        print(f"{'='*60}")
        print(f"  目录: {input_path}")
        print(f"  API:  {api_type}")
        print(f"  模型: {model}")
        print(f"{'='*60}")

        if not input_path.exists():
            print(f"{ERR} 目录不存在: {input_path}")
            return

        images = self.collect_images(input_path)
        if not images:
            print(f"  未找到图片文件")
            return

        print(f"  找到 {len(images)} 张图片\n")

        with open(self.output_file, "w") as f:
            f.write(f"# OCR Knowledge Base\n\n")
            f.write(f"- **来源**: {input_path}\n")
            f.write(f"- **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **API**: {api_type}\n")
            f.write(f"- **模型**: {model}\n")
            f.write(f"- **总数**: {len(images)}\n\n---\n\n")

        stats = {"total": len(images), "success": 0, "failed": 0, "total_time": 0.0}

        for idx, img_path in enumerate(images, 1):
            filename = img_path.name
            print(f"[{idx}/{len(images)}] 🔍 {filename}... ", end="", flush=True)

            start = time.time()
            success, content = self.process_image(img_path, client, model, prompt)
            duration = time.time() - start
            stats["total_time"] += duration

            self.log_result(filename, success, content, duration, api_type)

            if success:
                print(f"{DONE} ({duration:.1f}s)")
                stats["success"] += 1
                with open(self.output_file, "a") as f:
                    f.write(f"## 📄 {filename}\n\n**耗时**: {duration:.1f}s\n\n{content}\n\n---\n\n")
            else:
                print(f"{ERR} ({duration:.1f}s)")
                print(f"  {content}")
                stats["failed"] += 1

            if idx < len(images):
                time.sleep(config.get("ocr", "delay_between_requests", default=1))

        avg = stats["total_time"] / max(stats["success"] + stats["failed"], 1)
        print(f"\n{'='*60}")
        print(f"  处理完成!")
        print(f"  总计: {stats['total']}  |  成功: {stats['success']}  |  失败: {stats['failed']}")
        print(f"  耗时: {stats['total_time']:.1f}s  |  平均: {avg:.1f}s/张")
        print(f"  结果: {self.output_file}")
        print(f"{'='*60}")

        with open(self.summary_file, "w") as f:
            f.write(f"OCR 处理摘要\n{'='*60}\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"目录: {input_path}\n")
            f.write(f"API:  {api_type}\n")
            f.write(f"模型: {model}\n")
            f.write(f"总计: {stats['total']}\n")
            f.write(f"成功: {stats['success']}\n")
            f.write(f"失败: {stats['failed']}\n")
            f.write(f"耗时: {stats['total_time']:.1f}s\n")


def main():
    parser = argparse.ArgumentParser(description="OCR 批量处理工具")
    parser.add_argument("--dir", type=str, help="图片文件夹路径")
    parser.add_argument("--provider", choices=["local", "openrouter", "deepseek"], default="local", help="API 类型")
    parser.add_argument("--model", type=str, help="模型名称")
    parser.add_argument("--prompt", type=str, help="OCR 提示词")
    args = parser.parse_args()

    processor = OCRProcessor()
    processor.run(
        input_dir=args.dir,
        api_type=args.provider,
        model=args.model,
        prompt=args.prompt,
    )


if __name__ == "__main__":
    main()
