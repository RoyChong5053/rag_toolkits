#!/usr/bin/env python3
"""RAG Toolkits 统一入口"""
import sys
import argparse
from pathlib import Path

LOG = "📋"
WARN = "⚠️"
ERR = "❌"
DONE = "✅"


def show_interactive_menu():
    from core.task_manager import TaskManager
    tm = TaskManager()
    changed, msg = tm.detect_change()
    if changed:
        action = tm.ask_user_for_action(msg)
        if action == "y":
            tm.reset_for_new_task()
        elif action == "c":
            return

    while True:
        print(f"\n{'='*60}")
        print(f"   🤖 RAG Toolkits")
        print(f"{'='*60}")
        print(f"  [1] {LOG} 文本 RAG 处理")
        print(f"  [2] 🖼️  图片 OCR 处理")
        print(f"  [3] 🌐 启动 WebUI (Gradio)")
        print(f"  [4] 🔧 模型选择器")
        print(f"  [5] ⚙️  配置管理")
        print(f"  [6] 📝 文本预处理")
        print(f"  [7] ❌ 退出")
        print(f"{'='*60}")
        choice = input(f"\n👉 请选择 [1-7]: ").strip()

        if choice == "1":
            run_rag_interactive()
        elif choice == "2":
            run_ocr_interactive()
        elif choice == "3":
            run_gui()
        elif choice == "4":
            run_models_interactive()
        elif choice == "5":
            manage_config()
        elif choice == "6":
            run_preprocess_interactive()
        elif choice == "7":
            print(f"\n👋 再见")
            break
        else:
            print(f"{ERR} 无效选项")


def pick_backend(purpose: str = "rag") -> str:
    print(f"\n🔌 选择后端:")
    print(f"  [1] ☁️  OpenRouter")
    print(f"  [2] 🏠 本地 Llama.cpp")
    print(f"  [3] 🔮 DeepSeek")
    choice = input("👉 [1/2/3]: ").strip()
    if choice == "2":
        return "local"
    elif choice == "3":
        return "deepseek"
    return "openrouter"


def run_rag_interactive():
    raw_dir = Path("input/raw")
    raw_files = sorted(raw_dir.glob("*")) if raw_dir.exists() else []
    if raw_files:
        print(f"\n📂 input/raw/ 中的文件:")
        for i, f in enumerate(raw_files, 1):
            sz = f.stat().st_size
            print(f"  [{i}] {f.name} ({sz/1024:.1f} KB)")
        idx = input(f"\n📄 选择文件编号 (或直接输入路径，默认 [1]): ").strip()
        if idx:
            try:
                default_file = str(raw_files[int(idx) - 1])
            except (ValueError, IndexError):
                default_file = idx
        else:
            default_file = str(raw_files[0])
    else:
        default_file = "input.txt"
        if not Path(default_file).exists():
            Path(default_file).touch()
        f = input(f"📄 输入文件 [{default_file}]: ").strip() or default_file
        if not Path(f).exists():
            print(f"{ERR} 文件不存在: {f}")
            return
        default_file = f

    api_type = pick_backend("rag")

    from core.prompts import interactive_select
    system_prompt, user_template = interactive_select()

    from rag_processor import RAGProcessor
    processor = RAGProcessor(
        input_file=default_file,
        api_type=api_type,
        system_prompt=system_prompt,
        user_template=user_template,
    )
    processor.run()


def run_ocr_interactive():
    from core.config import config
    default_dir = config.get("ocr", "input_dir", default="./input/photo")
    Path(default_dir).mkdir(exist_ok=True)
    d = input(f"📂 图片文件夹 [{default_dir}]: ").strip() or default_dir
    if not Path(d).is_dir():
        print(f"{ERR} 目录不存在: {d}")
        return

    api_type = pick_backend("ocr")

    from ocr_processor import OCRProcessor
    processor = OCRProcessor()
    processor.run(input_dir=d, api_type=api_type)


def run_preprocess_interactive():
    from preprocess_processor import PreprocessProcessor
    processor = PreprocessProcessor()
    processor.run()


def run_gui():
    from app import main as gui_main
    gui_main()


def run_models_interactive():
    print(f"\n📊 模型用途:")
    print(f"  [1] 📄 RAG 文本模型")
    print(f"  [2] 🖼️  OCR 视觉模型")
    m = input("👉 [1/2]: ").strip()
    mode = "ocr" if m == "2" else "rag"
    from models_selector import main as models_main
    sys.argv = ["models_selector.py", "--mode", mode]
    models_main()


def manage_config():
    from core.config import config
    print(f"\n{'='*60}")
    print(f"   ⚙️  配置管理")
    print(f"{'='*60}")
    print(f"  当前配置文件: {config.config_path}")
    print(f"  [1] 查看配置")
    print(f"  [2] 重置为默认")
    c = input("👉 [1/2]: ").strip()
    if c == "1":
        import json
        print(f"\n{json.dumps(config.config, indent=2, ensure_ascii=False)}")
    elif c == "2":
        confirm = input(f"{WARN} 确认重置? (y/n): ").strip().lower()
        if confirm == "y":
            from core.config import DEFAULT_CONFIG
            config.config = dict(DEFAULT_CONFIG)
            config.save()
            print(f"{DONE} 已重置为默认配置")
    input(f"\n按回车继续...")


def main():
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="RAG Toolkits")
        sub = parser.add_subparsers(dest="command")

        sub.add_parser("gui", help="启动 WebUI")

        p_rag = sub.add_parser("rag", help="文本 RAG 处理")
        p_rag.add_argument("--file", default="input.txt")
        p_rag.add_argument("--provider", choices=["openrouter", "local", "deepseek"], default="openrouter")
        p_rag.add_argument("--prompt", help="Prompt 模板名称")

        p_ocr = sub.add_parser("ocr", help="图片 OCR 处理")
        p_ocr.add_argument("--dir", default=None)
        p_ocr.add_argument("--provider", choices=["openrouter", "local", "deepseek"], default="openrouter")

        p_pre = sub.add_parser("preprocess", help="文本预处理 (emoji + split)")
        p_pre.add_argument("--no-emoji", action="store_true", help="跳过 emoji 清理")
        p_pre.add_argument("--split", action="store_true", help="强制分割")
        p_pre.add_argument("--no-split", action="store_true", help="跳过分割")

        p_models = sub.add_parser("models", help="模型选择器")
        p_models.add_argument("--mode", choices=["rag", "ocr"], default="rag")

        sub.add_parser("prompts", help="Prompt 管理")

        args = parser.parse_args()

        if args.command == "gui":
            run_gui()
        elif args.command == "rag":
            system_prompt = user_template = None
            if args.prompt:
                from core.prompts import get_template
                tpl = get_template(args.prompt)
                system_prompt = tpl["system"]
                user_template = tpl["user_template"]
            from rag_processor import RAGProcessor
            processor = RAGProcessor(
                input_file=args.file,
                api_type=args.provider,
                system_prompt=system_prompt,
                user_template=user_template,
            )
            processor.run()
        elif args.command == "ocr":
            from ocr_processor import OCRProcessor
            processor = OCRProcessor()
            processor.run(input_dir=args.dir, api_type=args.provider)
        elif args.command == "preprocess":
            from preprocess_processor import PreprocessProcessor
            processor = PreprocessProcessor()
            do_emoji = not args.no_emoji
            do_split = None
            if args.split:
                do_split = True
            elif args.no_split:
                do_split = False
            processor.run(do_emoji=do_emoji, do_split=do_split)
        elif args.command == "models":
            sys.argv = ["models_selector.py", "--mode", args.mode]
            from models_selector import main as models_main
            models_main()
        elif args.command == "prompts":
            from core.prompts import interactive_select
            interactive_select()
        else:
            show_interactive_menu()
    else:
        show_interactive_menu()


if __name__ == "__main__":
    main()
