#!/usr/bin/env python3
"""RAG 知识提取工具 - Gradio WebUI"""
import os
import sys
import time
import json
import queue
from pathlib import Path
from datetime import datetime
from typing import List
import gradio as gr

from core.config import config
from core.prompts import PROMPT_TEMPLATES, get_template
from core.client import create_client, call_with_retry, create_chunks, encode_image, get_mime_type, build_rag_messages, build_vision_messages, strip_emoji
from preprocess_processor import PreprocessProcessor, remove_emoji_from_text


API_TYPE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "local": "http://127.0.0.1:12888/v1",
    "deepseek": "https://api.deepseek.com/v1",
}


class ProgressManager:
    def __init__(self):
        self.progress_queue = queue.Queue()
        self.current_task = None
        self.is_cancelled = False

    def reset(self):
        self.is_cancelled = False
        while not self.progress_queue.empty():
            try:
                self.progress_queue.get_nowait()
            except queue.Empty:
                break

    def update_progress(self, step: int, total: int, message: str):
        percentage = (step / total * 100) if total > 0 else 0
        self.progress_queue.put({"type": "progress", "step": step, "total": total, "percentage": percentage, "message": message})

    def update_status(self, status: str):
        self.progress_queue.put({"type": "status", "message": status})

    def update_result(self, result: str, result_file: str = None):
        self.progress_queue.put({"type": "result", "result": result, "result_file": result_file})

    def update_error(self, error: str):
        self.progress_queue.put({"type": "error", "message": error})

    def get_progress(self):
        try:
            while True:
                yield self.progress_queue.get_nowait()
        except queue.Empty:
            pass

    def cancel(self):
        self.is_cancelled = True


progress_manager = ProgressManager()


def process_rag_webui(input_text: str, api_type: str, api_key: str, api_url: str,
                      model: str, template_name: str, custom_system: str,
                      custom_user: str, max_chars: int):
    progress_manager.reset()

    if template_name == "自定义":
        system_prompt = custom_system
        user_template = custom_user
    else:
        tpl = get_template(template_name)
        system_prompt = tpl["system"]
        user_template = tpl["user_template"]

    try:
        client, headers = create_client(api_type)
        if api_key:
            client.api_key = api_key
        if api_url:
            client.base_url = api_url

        if not model:
            models = config.get("rag", "models", default={})
            model = models.get(api_type, models.get("openrouter", "gpt-3.5-turbo"))

        chunks = list(create_chunks(input_text, max_chars))
        total = len(chunks)
        results = []

        for i, chunk in enumerate(chunks):
            if progress_manager.is_cancelled:
                progress_manager.update_status("已取消")
                break

            progress_manager.update_progress(i + 1, total, f"处理块 {i + 1}/{total}")
            progress_manager.update_status(f"处理中... 块 {i + 1}/{total}")

            safe_chunk = strip_emoji(chunk)
            messages = build_rag_messages(system_prompt, user_template.format(text=safe_chunk))
            content = call_with_retry(
                client, model, messages,
                extra_headers=headers, temperature=0.3,
            )
            results.append(content if content else "[Empty]")

            if i < total - 1:
                time.sleep(config.get("rag", "request_interval", default=1))

        if results:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            header = f"# RAG Knowledge Base\n\n**Model**: {model}\n**Date**: {ts}\n\n---\n\n"
            final_result = header + "\n\n---\n\n".join(results)

            output_dir = Path("output/rag")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"rag_result_{ts}.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(final_result)

            progress_manager.update_result(final_result, str(output_file))
            progress_manager.update_status(f"完成! 结果: {output_file}")
            return 100, "完成", final_result, str(output_file)

        return 0, "结果为空", "", None
    except Exception as e:
        progress_manager.update_error(str(e))
        return 0, f"错误: {e}", "", None


def process_ocr_webui(image_files: List[str], api_type: str, api_key: str,
                      api_url: str, model: str, prompt: str):
    progress_manager.reset()

    try:
        if not image_files:
            return 0, "没有图片", "", None

        client, headers = create_client(api_type)
        if api_key:
            client.api_key = api_key
        if api_url:
            client.base_url = api_url

        if not model:
            models = config.get("ocr", "models", default={})
            model = models.get(api_type, models.get("openrouter", "gpt-4o-mini"))
        if not prompt:
            prompt = config.get("ocr", "default_prompt", default="")

        total = len(image_files)
        results = []

        for i, img in enumerate(image_files):
            if progress_manager.is_cancelled:
                progress_manager.update_status("已取消")
                break

            progress_manager.update_progress(i + 1, total, f"处理 {Path(img).name}")
            progress_manager.update_status(f"处理中... {i + 1}/{total}")

            b64 = encode_image(img)
            mime = get_mime_type(img)
            messages = build_vision_messages(prompt, b64, mime)

            content = call_with_retry(
                client, model, messages,
                extra_headers=headers,
                max_tokens=config.get("ocr", "max_tokens", default=2000),
                temperature=config.get("ocr", "temperature", default=0.1),
            )
            results.append({"filename": Path(img).name, "content": content if content else "[Empty]"})

            if i < total - 1:
                time.sleep(config.get("ocr", "delay_between_requests", default=1))

        if results:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            header = f"# OCR Knowledge Base\n\n**Date**: {ts}\n**Total**: {len(results)}\n\n---\n\n"
            body = "\n\n".join(f"## {r['filename']}\n\n{r['content']}\n\n---" for r in results)
            final_result = header + body

            output_dir = Path("output/ocr")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"ocr_result_{ts}.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(final_result)

            progress_manager.update_result(final_result, str(output_file))
            progress_manager.update_status(f"完成! 结果: {output_file}")
            return 100, "完成", final_result, str(output_file)

        return 0, "结果为空", "", None
    except Exception as e:
        progress_manager.update_error(str(e))
        return 0, f"错误: {e}", "", None


def process_preprocess_webui(do_emoji: bool, do_split: bool):
    progress_manager.reset()
    try:
        processor = PreprocessProcessor()
        files = processor.scan_input()
        if not files:
            return "❌ input/raw/ 中没有支持的文档文件"

        msg_lines = [f"找到 {len(files)} 个文件:\n"]
        for f in files:
            sz = f.stat().st_size
            msg_lines.append(f"  {f.name} ({sz/1024:.1f} KB)")
        msg_lines.append(f"\n总大小: {processor.total_size(files)/1024/1024:.2f} MB")

        processor.output_dir.mkdir(parents=True, exist_ok=True)

        converted = []
        for f in files:
            out_name = f.stem + ".md"
            out_path = processor.output_dir / out_name
            ok = processor.convert_to_md(f, out_path)
            if ok:
                converted.append(out_path)
                msg_lines.append(f"✅ 转换: {f.name}")

        if do_emoji:
            for f in converted:
                content = f.read_text(encoding="utf-8")
                cleaned = remove_emoji_from_text(content)
                f.write_text(cleaned, encoding="utf-8")
            msg_lines.append("✅ Emoji 清理完成")

        if do_split:
            mb = processor.target_mb
            for f in list(processor.output_dir.glob("*.md")):
                if len(f.read_bytes()) > mb * 1024 * 1024:
                    parts = processor.split_by_mb(f, mb)
                    f.unlink()
                    msg_lines.append(f"✅ 分割: {f.name} -> {len(parts)} 个文件")

        final = list(processor.output_dir.glob("*.md"))
        msg_lines.append(f"\n🎉 完成! 输出目录: {processor.output_dir}/, {len(final)} 个文件")

        return "\n".join(msg_lines)
    except Exception as e:
        return f"❌ 错误: {e}"


def get_model_for_provider(section: str, api_type: str) -> str:
    models = config.get(section, "models", default={})
    return models.get(api_type, models.get("openrouter", ""))


def on_api_type_change(api_type, section="rag"):
    url = API_TYPE_URLS.get(api_type, "")
    key = ""
    if api_type == "openrouter":
        key = config.api_key
    elif api_type == "deepseek":
        key = config.get("api", "deepseek", "api_key", default="")
    model = get_model_for_provider(section, api_type)
    return gr.update(value=url), gr.update(value=key), gr.update(value=model)


def create_ui():
    with gr.Blocks(title="RAG Toolkits") as demo:
        gr.Markdown("# 🤖 RAG Toolkits\n文本知识提取、图片 OCR、文档预处理")

        with gr.Tabs():
            with gr.TabItem("📄 文本 RAG 处理"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 输入文本")
                        input_text = gr.Textbox(label="输入文本", placeholder="粘贴要处理的文本内容...", lines=10)
                        file_input = gr.File(label="或上传文本文件", file_types=[".txt", ".md"])

                        with gr.Accordion("⚙️ API 配置", open=True):
                            api_type = gr.Dropdown(["openrouter", "local", "deepseek"], value="openrouter", label="API 类型")
                            api_key = gr.Textbox(label="API Key", type="password", value=config.api_key, placeholder="sk-or-v1-...")
                            api_url = gr.Textbox(label="API URL", value="https://openrouter.ai/api/v1")
                            model = gr.Textbox(label="模型", value=get_model_for_provider("rag", "openrouter"))

                        with gr.Accordion("📝 Prompt 配置", open=True):
                            template_name = gr.Dropdown(choices=list(PROMPT_TEMPLATES.keys()), value="标准知识提取", label="选择模板")
                            custom_system = gr.Textbox(label="System Prompt (自定义)", lines=3, visible=False)
                            custom_user = gr.Textbox(label="User Template (用 {text} 作占位符)", lines=3, visible=False)

                        max_chars = gr.Slider(2000, 20000, 12000, step=1000, label="每块最大字符数")
                        process_btn = gr.Button("🚀 开始处理", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        gr.Markdown("### 处理进度")
                        progress_bar = gr.Slider(0, 100, 0, label="进度", interactive=False)
                        status_text = gr.Textbox(label="状态", value="等待处理...", interactive=False)
                        gr.Markdown("### 处理结果")
                        result_text = gr.Textbox(label="结果预览", lines=15)
                        result_file = gr.File(label="下载结果文件")

                def on_template_change(name):
                    vs = name == "自定义"
                    return gr.update(visible=vs), gr.update(visible=vs)

                template_name.change(on_template_change, template_name, [custom_system, custom_user])

                api_type.change(lambda t: on_api_type_change(t, "rag"), api_type, [api_url, api_key, model])

                process_btn.click(
                    process_rag_webui,
                    [input_text, api_type, api_key, api_url, model, template_name, custom_system, custom_user, max_chars],
                    [progress_bar, status_text, result_text, result_file],
                )

            with gr.TabItem("🖼️ 图片 OCR 处理"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 上传图片")
                        image_input = gr.File(label="上传图片 (JPG/PNG/BMP/WebP/GIF)", file_count="multiple",
                                              file_types=[".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"])

                        with gr.Accordion("⚙️ API 配置", open=True):
                            ocr_api_type = gr.Dropdown(["openrouter", "local", "deepseek"], value="openrouter", label="API 类型")
                            ocr_api_key = gr.Textbox(label="API Key", type="password", value=config.api_key)
                            ocr_api_url = gr.Textbox(label="API URL", value="https://openrouter.ai/api/v1")
                            ocr_model = gr.Textbox(label="模型", value=get_model_for_provider("ocr", "openrouter"))

                        ocr_prompt = gr.Textbox(label="OCR Prompt", value=config.get("ocr", "default_prompt"), lines=3)
                        ocr_process_btn = gr.Button("🚀 开始处理", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        gr.Markdown("### 处理进度")
                        ocr_progress_bar = gr.Slider(0, 100, 0, label="进度", interactive=False)
                        ocr_status_text = gr.Textbox(label="状态", value="等待处理...", interactive=False)
                        gr.Markdown("### 处理结果")
                        ocr_result_text = gr.Textbox(label="结果预览", lines=15)
                        ocr_result_file = gr.File(label="下载结果文件")

                ocr_api_type.change(lambda t: on_api_type_change(t, "ocr"), ocr_api_type, [ocr_api_url, ocr_api_key, ocr_model])

                ocr_process_btn.click(
                    process_ocr_webui,
                    [image_input, ocr_api_type, ocr_api_key, ocr_api_url, ocr_model, ocr_prompt],
                    [ocr_progress_bar, ocr_status_text, ocr_result_text, ocr_result_file],
                )

            with gr.TabItem("📝 文本预处理"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 预处理设置")
                        gr.Markdown("从 `input/raw/` 读取文档 → 转换 → 去 Emoji → 分割 → `input/clean/`")
                        pre_emoji = gr.Checkbox(value=True, label="去除 Emoji")
                        pre_split = gr.Checkbox(value=False, label="按 1MB 分割大文件 (>5MB)")
                        pre_process_btn = gr.Button("🚀 开始预处理", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        gr.Markdown("### 处理输出")
                        pre_output = gr.Textbox(label="处理日志", lines=20)

                pre_process_btn.click(
                    process_preprocess_webui,
                    [pre_emoji, pre_split],
                    [pre_output],
                )

            with gr.TabItem("📖 使用说明"):
                gr.Markdown("""
                ## 功能说明

                ### 📄 文本 RAG 处理
                1. 粘贴文本或上传文件 → 2. 配置 API → 3. 选择 Prompt 模板 → 4. 开始处理

                ### 🖼️ 图片 OCR 处理
                1. 上传图片 → 2. 配置 API → 3. 设置 Prompt → 4. 开始处理

                ### 📝 文本预处理
                将 `input/raw/` 中的文档自动转换、去 Emoji、按文件大小分割到 `input/clean/`

                ### API 说明
                - **OpenRouter**: 配置 API Key，使用云端模型
                - **DeepSeek**: 配置 DeepSeek API Key
                - **本地模式**: 连接本地 llama.cpp 服务 (端口 12888)

                ### 输出目录结构
                ```
                input/
                ├── raw/      # 放入原始文档
                ├── clean/    # 预处理后的文档
                └── photo/    # 放入 OCR 图片
                output/
                ├── rag/      # RAG 提取结果
                └── ocr/      # OCR 提取结果
                ```
                """)

        gr.Markdown("---\n**RAG Toolkits** | 文本处理 + OCR + 文档预处理")

    return demo


def main():
    demo = create_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7862,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(),
    )


if __name__ == "__main__":
    main()
