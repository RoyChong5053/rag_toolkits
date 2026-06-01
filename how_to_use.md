# RAG 知识提取工具使用指南

## 🚀 快速开始

### 一键启动（推荐）

```bash
# 进入项目目录
cd rag_toolkits

# 首次使用先创建 venv + 安装依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 启动交互式菜单
./run.sh
```

`run.sh` 会自动激活虚拟环境并启动 `main.py`，提供交互式菜单：

```
  [1] 📋 文本 RAG 处理
  [2] 🖼️  图片 OCR 处理
  [3] 🌐 启动 WebUI (Gradio)
  [4] 🔧 模型选择器
  [5] ⚙️  配置管理
  [6] ❌ 退出
```

### 直接指定模式

```bash
# 文本 RAG（交互式选择 Prompt 模板）
./run.sh rag --file input.txt

# 图片 OCR
./run.sh ocr --dir ./images

# 启动 WebUI（本地桌面）
./run.sh gui

# 模型选择器
./run.sh models --mode rag

# 查看帮助
./run.sh --help
```

---

## 🌐 WebUI 模式（适合本地桌面）

启动 WebUI 后浏览器访问 `http://localhost:7862`：

```bash
./run.sh gui
```

### WebUI 功能

1. **📄 文本 RAG 处理**
   - 粘贴文本或上传 `.txt` / `.md` 文件
   - 配置 API（OpenRouter 或本地 Llama.cpp）
   - 下拉选择 Prompt 模板（标准/技术文档/会议记录/书籍/聊天记录/自定义）
   - 实时进度条，结果在线预览 + 下载

2. **🖼️ 图片 OCR 处理**
   - 上传多张图片（JPG / PNG / BMP / WebP / GIF）
   - 自定义 OCR Prompt
   - 实时进度，结果预览 + 下载

---

## 🖥️ CLI 模式（适合 Vast.ai 等无头环境）

### 交互式菜单

```bash
./run.sh
```

进入菜单后按数字选择，CLI 会自动：
1. 询问输入文件路径
2. 选择后端（OpenRouter / 本地 Llama.cpp）
3. **交互式选择 Prompt 模板**（与 WebUI 共享同一套预设）
4. 执行业务处理

### 命令行直通

```bash
# 云端 OpenRouter
./run.sh rag --file input.txt

# 本地 Llama.cpp
./run.sh rag --file input.txt --local

# 指定 Prompt 模板（跳过交互选择）
./run.sh rag --file input.txt --prompt "技术文档整理"

# OCR 处理
./run.sh ocr --dir ./images --local
./run.sh ocr --dir ./images                        # 默认 OpenRouter
```

### 直接调用底层脚本

各模块也可以独立运行（不经过 main.py）：

```bash
# RAG
python3 rag_processor.py input.txt
python3 rag_processor.py input.txt --local --local-url "http://127.0.0.1:12888/v1"
python3 rag_processor.py input.txt --no-resume --debug

# OCR
python3 ocr_processor.py --dir ./images --api-type local
python3 ocr_processor.py --dir ./images --api-type openrouter

# 模型选择
python3 models_selector.py --mode rag
python3 models_selector.py --mode ocr
```

---

## 📝 Prompt 模板

内置 6 套预设，CLI 和 GUI 共享：

| 模板 | 适用场景 |
|------|----------|
| 标准知识提取 | 通用，将凌乱文本转为 Q&A + 关键实体 |
| 技术文档整理 | API 文档、开发指南等 |
| 会议记录整理 | 提取讨论要点、决策、行动项 |
| 书籍内容摘要 | 章节核心观点 + 引用 |
| 聊天记录分析 | 提取讨论主题、共识、待办 |
| 自定义 | 用户自由编写 System / User Prompt |

### 自定义 Prompt 文件

把 `{name}.json` 放入 `prompts/` 目录即可被自动加载：

```json
{
  "system": "你是一个...",
  "user_template": "请处理以下内容：\n\n{text}"
}
```

CLI 和 GUI 都会自动识别并出现在模板选择列表中。

---

## ⚙️ 配置说明

统一配置文件 `config.json`，RAG 和 OCR 共用：

```json
{
  "api": {
    "openrouter": {
      "api_key": "sk-or-v1-...",
      "base_url": "https://openrouter.ai/api/v1",
      "site_url": "RAG-WebUI",
      "site_name": "RAG-WebUI"
    },
    "local": {
      "base_url": "http://127.0.0.1:12888/v1"
    }
  },
  "rag": {
    "default_model": "nvidia/nemotron-nano-12b-v2-vl:free",
    "max_input_chars": 12000,
    "request_interval": 1,
    "overlap_paragraphs": 1,
    "max_retries_cloud": 5,
    "max_retries_local": 2,
    "retry_delay_base": 2
  },
  "ocr": {
    "default_model": "nvidia/nemotron-nano-12b-v2-vl:free",
    "default_prompt": "请帮我提取图片中的文字内容...",
    "max_tokens": 2000,
    "temperature": 0.1,
    "timeout": 120,
    "retry_attempts": 3,
    "delay_between_requests": 1
  }
}
```

### 环境变量覆盖

对 Vast.ai 等容器环境友好：

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
export LOCAL_API_URL="http://127.0.0.1:12888/v1"

# 环境变量会自动覆盖 config.json 中的值
./run.sh rag --file input.txt
```

### 旧配置自动迁移

如果之前有旧版 `config.json` + `ocr_config.json`，首次运行会自动合并为新格式，旧文件重命名为 `.old`。

---

## 📂 项目结构

```
rag_toolkits/
├── main.py              # 统一入口（交互菜单 + CLI 子命令）
├── run.sh               # 激活 venv 并调用 main.py
├── core/                # 共享核心模块
│   ├── config.py        # 统一配置管理
│   ├── prompts.py       # Prompt 模板预设
│   └── client.py        # API 客户端 + 分块工具
├── rag_processor.py     # RAG 处理器（断点续传、日志）
├── ocr_processor.py     # OCR 处理器
├── app.py               # Gradio WebUI
├── models_selector.py   # OpenRouter 模型选择器
├── config.json          # 统一配置文件
├── requirements.txt
├── prompts/             # 用户自定义 Prompt（可选）
├── results/             # RAG 处理结果
├── ocr_results/         # OCR 处理结果
├── checkpoints/         # 断点续传
├── intermediate/        # 中间文件
└── logs/                # 运行日志
```

---

## 📊 输出格式

### RAG 处理结果（results/）

```markdown
# RAG Knowledge Base
**Source**: input.txt
**Model**: nvidia/nemotron-nano-12b-v2-vl:free
**Date**: 20260228_143022

---

## 核心主题
...

### 知识点/Q&A
- **Q**: 问题
  **A**: 答案

### 关键实体
- 实体1
```

### OCR 处理结果（ocr_results/）

```markdown
# OCR Knowledge Base
- **来源**: ./images
- **处理时间**: 2026-02-28 14:30:22
- **API 类型**: openrouter

---

## 📄 photo.jpg
**耗时**: 2.1s

图片中的文字内容...
```

---

## 🔧 常见操作

### 查看/重置配置

```bash
# 菜单方式
./run.sh → [5] 配置管理

# 或直接查看文件
cat config.json
```

### 调整处理参数

```bash
# 分块大小（默认 12000）
./run.sh rag --file input.txt

# 在 config.json 中修改：
#   rag.max_input_chars     每块字符数
#   rag.request_interval    请求间隔（秒）
#   rag.overlap_paragraphs  块间重叠段落数
#   rag.max_retries_cloud   云端重试次数
```

### 调试模式

```bash
python3 rag_processor.py input.txt --debug
tail -f logs/rag_*.log
```

---

## 📎 资源链接

- [OpenRouter 文档](https://openrouter.ai/docs)
- [llama.cpp](https://github.com/ggerganov/llama.cpp)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [Gradio](https://www.gradio.app/)
