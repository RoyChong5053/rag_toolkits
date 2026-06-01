#!/usr/bin/env python3
"""OpenRouter Model Selector - 更新版，使用核心配置"""
import requests
import json
import argparse
from pathlib import Path
from typing import List, Dict

from core.config import config

RAG_CONFIG = "config.json"
OCR_CONFIG = "ocr_config.json"


class Colors:
    GREEN = "\033[0;32m"
    BLUE = "\033[0;34m"
    YELLOW = "\033[1;33m"
    CYAN = "\033[0;36m"
    RED = "\033[0;31m"
    BOLD = "\033[1m"
    NC = "\033[0m"


def save_rag_model(model_id: str):
    config.set(model_id, "rag", "models", "openrouter")
    print(f"\n{Colors.GREEN}✅ 已更新 RAG 模型 (OpenRouter){Colors.NC}")
    print(f"{Colors.CYAN}   当前: {Colors.BOLD}{model_id}{Colors.NC}")


def save_ocr_model(model_id: str):
    config.set(model_id, "ocr", "models", "openrouter")
    print(f"\n{Colors.GREEN}✅ 已更新 OCR 模型 (OpenRouter){Colors.NC}")
    print(f"{Colors.CYAN}   当前: {Colors.BOLD}{model_id}{Colors.NC}")


def get_openrouter_models() -> List[Dict]:
    print(f"{Colors.YELLOW}⏳ 正在从 OpenRouter 获取模型列表...{Colors.NC}")
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception as e:
        print(f"{Colors.RED}❌ 获取失败: {e}{Colors.NC}")
        return []


def process_models(models_data: List[Dict], vision_only: bool = False) -> List[Dict]:
    processed = []
    for model in models_data:
        model_id = model.get("id", "")
        pricing = model.get("pricing", {})
        if vision_only:
            modalities = model.get("architecture", {}).get("modality", "")
            if "image" not in modalities.lower():
                continue
        try:
            p_prompt = float(pricing.get("prompt", "0")) * 1_000_000
            p_completion = float(pricing.get("completion", "0")) * 1_000_000
            processed.append({
                "id": model_id,
                "name": model.get("name", "Unknown"),
                "context": int(model.get("context_length", 0)),
                "input_price": p_prompt,
                "output_price": p_completion,
                "avg_price": (p_prompt + p_completion) / 2,
            })
        except Exception:
            continue
    return processed


def format_price(price: float) -> str:
    if price == 0:
        return f"{Colors.GREEN}FREE{Colors.NC}"
    elif price < 0.1:
        return f"{Colors.GREEN}${price:.4f}{Colors.NC}"
    elif price < 1.0:
        return f"{Colors.YELLOW}${price:.3f}{Colors.NC}"
    else:
        return f"{Colors.RED}${price:.2f}{Colors.NC}"


def print_models_table(models: List[Dict], title: str, max_rows: int = 20):
    if not models:
        print(f"{Colors.YELLOW}   (无可用模型){Colors.NC}")
        return
    print(f"\n{Colors.CYAN}{'='*100}{Colors.NC}")
    print(f"{Colors.BOLD}{title}{Colors.NC}")
    print(f"{Colors.CYAN}{'='*100}{Colors.NC}")
    print(f"{Colors.BOLD}{'序号':<5}{'模型 ID':<50}{'输入':<20}{'输出':<20}{'上下文':<10}{Colors.NC}")
    print(f"{Colors.CYAN}{'-'*100}{Colors.NC}")
    for idx, model in enumerate(models[:max_rows], 1):
        mid = model["id"]
        if len(mid) > 48:
            mid = mid[:45] + "..."
        context = f"{model['context']:,}" if model["context"] > 0 else "N/A"
        print(f"{idx:<5}{mid:<50}{format_price(model['input_price']):<20}{format_price(model['output_price']):<20}{context:<10}")
    print(f"{Colors.CYAN}{'='*100}{Colors.NC}")


def categorize_models(models: List[Dict]) -> Dict[str, List[Dict]]:
    sorted_models = sorted(models, key=lambda x: x["avg_price"])
    free_cheap, medium, expensive = [], [], []
    for m in sorted_models:
        avg = m["avg_price"]
        if avg < 0.5:
            free_cheap.append(m)
        elif avg < 5.0:
            medium.append(m)
        else:
            expensive.append(m)
    return {"free_cheap": free_cheap, "medium": medium, "expensive": expensive}


def search_models(models: List[Dict], keyword: str) -> List[Dict]:
    kw = keyword.lower()
    results = [m for m in models if kw in m["id"].lower() or kw in m["name"].lower()]
    return sorted(results, key=lambda x: x["avg_price"])


def select_from_list(models: List[Dict], mode: str) -> bool:
    while True:
        choice = input(f"\n{Colors.YELLOW}👉 输入序号 (或回车返回): {Colors.NC}").strip()
        if not choice:
            return False
        try:
            idx = int(choice)
            if 1 <= idx <= len(models):
                selected = models[idx - 1]
                print(f"\n{Colors.CYAN}已选择:{Colors.NC}")
                print(f"  模型: {Colors.BOLD}{selected['id']}{Colors.NC}")
                print(f"  输入: {format_price(selected['input_price'])}/M")
                print(f"  输出: {format_price(selected['output_price'])}/M")
                confirm = input(f"{Colors.YELLOW}确认保存? (y/n): {Colors.NC}").strip().lower()
                if confirm == "y":
                    (save_rag_model if mode == "rag" else save_ocr_model)(selected["id"])
                    return True
            else:
                print(f"{Colors.RED}❌ 无效序号{Colors.NC}")
        except ValueError:
            print(f"{Colors.RED}❌ 请输入数字{Colors.NC}")


def main():
    parser = argparse.ArgumentParser(description="OpenRouter 模型选择器")
    parser.add_argument("--mode", choices=["rag", "ocr"], default="rag", help="rag (文本) 或 ocr (视觉)")
    args = parser.parse_args()

    raw_data = get_openrouter_models()
    if not raw_data:
        return

    models = process_models(raw_data, vision_only=(args.mode == "ocr"))
    if not models:
        print(f"{Colors.RED}❌ 没有可用的模型{Colors.NC}")
        return

    categories = categorize_models(models)
    mode_name = "RAG 文本处理" if args.mode == "rag" else "OCR 视觉识别"

    print(f"\n{Colors.BLUE}{'='*100}{Colors.NC}")
    print(f"{Colors.BOLD}🔍 OpenRouter 模型选择器 - {mode_name}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*100}{Colors.NC}")
    print(f"{Colors.CYAN}可用模型总数: {len(models)}{Colors.NC}")

    while True:
        print(f"\n{Colors.CYAN}{'='*100}{Colors.NC}")
        print(f"{Colors.BOLD}主菜单{Colors.NC}")
        print(f"{Colors.CYAN}{'='*100}{Colors.NC}")
        print(f"  [1] 💚 免费/便宜 (< $0.50/M) Top 20")
        print(f"  [2] 💛 中等价位 ($0.50-5.00/M) Top 20")
        print(f"  [3] 💰 高端 (> $5.00/M) Top 20")
        print(f"  [4] 🔍 搜索模型")
        print(f"  [5] ✏️  手动输入模型 ID")
        print(f"  [6] 📊 当前配置")
        print(f"  [7] ❌ 退出")

        choice = input(f"\n{Colors.YELLOW}👉 请选择 [1-7]: {Colors.NC}").strip()

        if choice == "1":
            print_models_table(categories["free_cheap"], f"💚 免费/便宜 (共 {len(categories['free_cheap'])} 个)", 20)
            if select_from_list(categories["free_cheap"][:20], args.mode):
                break
        elif choice == "2":
            print_models_table(categories["medium"], f"💛 中等价位 (共 {len(categories['medium'])} 个)", 20)
            if select_from_list(categories["medium"][:20], args.mode):
                break
        elif choice == "3":
            print_models_table(categories["expensive"], f"💰 高端 (共 {len(categories['expensive'])} 个)", 20)
            if select_from_list(categories["expensive"][:20], args.mode):
                break
        elif choice == "4":
            kw = input(f"\n{Colors.YELLOW}🔍 搜索关键词: {Colors.NC}").strip()
            if kw:
                results = search_models(models, kw)
                if results:
                    print_models_table(results, f"搜索结果: '{kw}' (共 {len(results)} 个)", 20)
                    if select_from_list(results[:20], args.mode):
                        break
                else:
                    print(f"{Colors.YELLOW}⚠️  未找到{Colors.NC}")
        elif choice == "5":
            mid = input(f"\n{Colors.YELLOW}📝 输入模型 ID: {Colors.NC}").strip()
            if mid:
                ids = {m["id"] for m in models}
                if mid in ids:
                    (save_rag_model if args.mode == "rag" else save_ocr_model)(mid)
                    break
                else:
                    print(f"{Colors.RED}❌ 模型 ID 不存在{Colors.NC}")
        elif choice == "6":
            print(f"\n{Colors.CYAN}{'='*100}{Colors.NC}")
            if args.mode == "rag":
                print(f"  RAG 模型 (OpenRouter): {Colors.BOLD}{config.get('rag', 'models', 'openrouter', default='未设置')}{Colors.NC}")
            else:
                print(f"  OCR 模型 (OpenRouter): {Colors.BOLD}{config.get('ocr', 'models', 'openrouter', default='未设置')}{Colors.NC}")
            has_key = bool(config.api_key)
            print(f"  API Key: {Colors.GREEN if has_key else Colors.RED}{'已配置' if has_key else '未配置'}{Colors.NC}")
            print(f"{Colors.CYAN}{'='*100}{Colors.NC}")
            input(f"\n{Colors.YELLOW}按回车继续...{Colors.NC}")
        elif choice == "7":
            print(f"\n{Colors.CYAN}👋 退出{Colors.NC}")
            break
        else:
            print(f"{Colors.RED}❌ 无效选项{Colors.NC}")


if __name__ == "__main__":
    main()
