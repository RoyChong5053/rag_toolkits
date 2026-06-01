# RAG Toolkits

文本知识提取 + 图片 OCR + 文档预处理 工具集。

## 功能

- **📄 文本 RAG 处理** — 将非结构化文本分块送入 LLM，提取为结构化知识库。支持断点续传、多 Prompt 模板。
- **🖼️ 图片 OCR 处理** — 批量识别图片中的文字，输出 Markdown 格式。
- **📝 文本预处理** — 文档放入 `input/raw/`，自动完成格式转换 → 去 Emoji → 按大小分割。
- **🌐 WebUI** — Gradio 图形界面，集成以上所有功能。

## 支持的 API 后端

| 后端 | 配置位置 | 默认模型 |
|------|----------|----------|
| OpenRouter | `api.openrouter` | `nvidia/nemotron-nano-12b-v2-vl:free` |
| DeepSeek | `api.deepseek` | `deepseek-chat` |
| 本地 Llama.cpp | `api.local` | `local-model` |

API Key 通过 `config.json` 或环境变量设置。

## 目录结构

```
rag_toolkits/
├── input/
│   ├── raw/       ← 放入原始文档 (txt/pdf/doc/docx/md)
│   ├── clean/     ← 预处理后成品 (去 Emoji + 分割)
│   └── photo/     ← 放入 OCR 图片
├── output/
│   ├── rag/       ← RAG 知识提取结果
│   ├── ocr/       ← OCR 文字提取结果
│   └── archive/   ← 旧任务自动归档
├── core/          ← 核心模块 (config/prompts/client/task_manager)
├── main.py        ← CLI 入口
├── app.py         ← Gradio WebUI
└── setup.sh       ← 新机器一键初始化
```

## 快速开始

```bash
# 新机器首次使用
bash setup.sh
cp config.json.example config.json
# 编辑 config.json 填入 API Key

# 交互菜单
./run.sh

# 或直接指定子命令
./run.sh preprocess                  # 预处理 input/raw/
./run.sh rag --file input.txt        # RAG 处理
./run.sh ocr                         # OCR 图片处理
./run.sh gui                         # 启动 WebUI (端口 7862)
```

## 任务隔离

项目通过 `.task_manifest.json` 自动追踪 `input/` 的文件变更。当检测到新文件或文件变动时，提示：

- **Y** — 开始新任务：旧结果归档到 `output/archive/`，清空断点，从头处理
- **N** — 继续当前任务，忽略变更
- **C** — 取消操作

## 链接

- GitHub: https://github.com/RoyChong5053/rag_toolkits
