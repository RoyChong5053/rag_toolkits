# RAG Toolkits 构建笔记

## 📋 项目概述

多功能知识提取工具 v3.0，四个核心功能：
1. **文本预处理** — 文档格式转换、去 Emoji、按大小分割
2. **文本 RAG 处理** — 将非结构化文本转化为结构化知识库
3. **图片 OCR 处理** — 从图片中提取文字内容
4. **Gradio WebUI** — 浏览器界面，集成以上所有功能

## 🆕 v3.0 重构 (2026-06-01)

### 新增功能

| 功能 | 说明 |
|------|------|
| **文本预处理** | 集成自 `RAG_MD_preprocess`：文档转换(txt/pdf/doc/docx→md) → 去 Emoji → 按 1MB 分割 |
| **DeepSeek API** | 新增 `api.deepseek` 配置，OpenAI 兼容，模型默认 `deepseek-chat` |
| **任务隔离机制** | `.task_manifest.json` 追踪 input 变更，按 Y/N/C 交互处理新旧任务冲突 |
| **旧任务自动归档** | `output/archive/{timestamp}/` 保留旧结果快照 |

### 结构变更

```
旧结构 (v2.0)              新结构 (v3.0)
─────────────────          ─────────────────
results/                   output/rag/
ocr_results/               output/ocr/
(无统一输入)               input/raw/ + input/clean/ + input/photo/
(无归档)                   output/archive/
```

### 配置结构变更

```json
// v2.0
"rag": { "default_model": "..." }

// v3.0 — 按 provider 区分
"rag": {
    "models": {
        "openrouter": "nvidia/nemotron-nano-12b-v2-vl:free",
        "deepseek": "deepseek-chat",
        "local": "local-model"
    }
}
```

### 依赖变更

| 依赖 | 用途 |
|------|------|
| `openai>=1.0.0` | LLM API 调用（OpenRouter / DeepSeek / Local 共用） |
| `requests>=2.28.0` | 模型列表获取 |
| `gradio>=4.0.0` | WebUI 框架 |

## 📁 项目结构

```
rag_toolkits/
├── input/
│   ├── raw/             放入原始文档 (txt/pdf/doc/docx/md)
│   ├── clean/           预处理后成品 (去 emoji + 分割)
│   └── photo/           放入 OCR 图片 (jpg/png/bmp/webp/gif)
├── output/
│   ├── rag/             RAG 知识提取结果
│   ├── ocr/             OCR 文字提取结果
│   └── archive/         旧任务自动归档快照
├── checkpoints/         断点续传数据 (独立)
├── intermediate/        中间结果自动保存 (独立)
├── logs/                运行日志 (独立)
├── core/
│   ├── __init__.py      v3.0.0
│   ├── client.py        统一 API 客户端 + strip_emoji 兜底
│   ├── config.py        配置管理 (支持 env 覆盖 OPENROUTER/DEEPSEEK/LOCAL)
│   ├── prompts.py       Prompt 模板管理 (6 套预置 + 自定义)
│   └── task_manager.py  任务隔离 + manifest 追踪 (新增)
├── preprocess_processor.py  文本预处理模块 (新增)
├── rag_processor.py          RAG 知识提取 (输出 → output/rag/)
├── ocr_processor.py          OCR 文字提取 (输入 → input/photo/, 输出 → output/ocr/)
├── app.py               Gradio WebUI (含预处理标签页)
├── main.py              统一 CLI 入口 (含 preprocess 子命令)
├── models_selector.py   OpenRouter 模型选择器
├── config.json          统一配置
├── run.sh               启动脚本
├── requirements.txt     Python 依赖
├── build-note.md        本文件
└── .task_manifest.json  自动维护 (不纳入 git)
```

## 🚀 使用方式

```
./run.sh                         交互菜单
./run.sh preprocess              预处理 input/raw/ → input/clean/
./run.sh rag --file input.txt --provider deepseek
./run.sh ocr --provider openrouter
./run.sh gui                     WebUI (端口 7862)
```

## 🔌 API 配置 (config.json)

```json
{
  "api": {
    "openrouter": {
      "api_key": "sk-or-v1-...",
      "base_url": "https://openrouter.ai/api/v1"
    },
    "deepseek": {
      "api_key": "sk-...",
      "base_url": "https://api.deepseek.com/v1"
    },
    "local": {
      "base_url": "http://127.0.0.1:12888/v1"
    }
  },
  "rag": {
    "models": {
      "openrouter": "nvidia/nemotron-nano-12b-v2-vl:free",
      "deepseek": "deepseek-chat",
      "local": "local-model"
    }
  },
  "ocr": {
    "models": {
      "openrouter": "nvidia/nemotron-nano-12b-v2-vl:free",
      "deepseek": "deepseek-chat",
      "local": "local-model"
    }
  }
}
```

环境变量覆盖: `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`, `LOCAL_API_URL`

## ✅ 已完成

- [x] 文本 RAG 处理器 (智能分块 / 断点续传 / 多后端 / emoji 兜底)
- [x] 图片 OCR 处理器 (批量处理 / 多格式 / JSON 日志 / 统计摘要)
- [x] Gradio WebUI (RAG + OCR + 预处理三标签页)
- [x] 模型选择器 (OpenRouter 模型浏览 / 按价格分类 / 搜索)
- [x] 文本预处理 (格式转换 / 去 Emoji / 按 MB 分割)
- [x] DeepSeek API 集成
- [x] 任务隔离机制 (manifest 追踪 / 变更检测 / 归档)
- [x] 统一 input/output 目录结构
- [x] per-provider 默认模型配置
- [x] 启动脚本 run.sh (目录状态显示 / 自动创建目录)
