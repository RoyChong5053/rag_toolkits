"""共享 Prompt 预设管理"""
import json
from pathlib import Path

PROMPT_TEMPLATES = {
    "标准知识提取": {
        "system": "你是一个专业的知识库整理专家。你的任务是将输入的原始文本转化为结构清晰、利于 RAG 系统检索的原子化知识点。\n\n请遵循以下原则：\n1. **去除噪音**：删除寒暄、表情符号、无关的元数据。\n2. **结构化输出**：将内容整理为 Markdown 格式。\n3. **Q&A 提取**：如果文本包含对话或问题解决过程，请将其重写为标准的'问题 - 答案'对。\n4. **事实提取**：如果文本是陈述性的，请提取核心概念和定义。\n5. **保持原意**：不要编造内容，仅对已有信息进行清洗和重组。",
        "user_template": "请处理以下文本块。输出格式要求如下：\n\n## 核心主题\n(一句话概括这段内容)\n\n### 知识点/Q&A\n- **Q**: [这里填写问题或概念]\n  **A**: [这里填写详细的解释或答案]\n\n### 关键实体\n(列出提到的人名、工具、技术名词)\n\n---\n\n待处理文本：\n\n{text}"
    },
    "技术文档整理": {
        "system": "你是一个技术文档整理专家。请将技术文档整理为结构化的知识库，便于后续检索和学习。",
        "user_template": "请将以下技术文档整理为结构化的格式：\n\n## 文档主题\n(概括文档主题)\n\n## 核心概念\n(列出并解释核心概念)\n\n## 技术要点\n- 要点 1\n- 要点 2\n\n## 代码示例\n(如有代码，整理为代码块)\n\n## 注意事项\n(重要的注意事项)\n\n---\n\n原文内容：\n\n{text}"
    },
    "会议记录整理": {
        "system": "你是一个会议纪要整理专家。请将会议记录整理为结构化的纪要，提取关键信息和行动项。",
        "user_template": "请整理以下会议记录：\n\n## 会议主题\n(概括会议主题)\n\n## 参会人员\n(列出参会人员)\n\n## 讨论要点\n- 要点 1\n- 要点 2\n\n## 决策事项\n(会议中做出的决策)\n\n## 行动项\n- [ ] 行动项 1 (负责人)\n- [ ] 行动项 2 (负责人)\n\n## 下次会议安排\n(如有)\n\n---\n\n会议记录原文：\n\n{text}"
    },
    "书籍内容摘要": {
        "system": "你是一个书籍内容整理专家。请将书籍内容整理为结构化的知识摘要。",
        "user_template": "请整理以下书籍内容：\n\n## 章节主题\n(概括章节主题)\n\n## 核心观点\n(列出核心观点)\n\n## 重要引用\n(重要的引用或金句)\n\n## 关键概念\n(解释关键概念)\n\n## 实践建议\n(如有实践建议)\n\n---\n\n原文内容：\n\n{text}"
    },
    "聊天记录摘要": {
        "system": "你是一个对话记忆压缩专家。将原始对话压缩为精简版对话，只保留对了解用户有价值的记忆信息。\n\n规则：\n1. 丢弃所有代码、技术原理等 LLM 已知内容\n2. 保留用户透露的个人信息、偏好、情感表达、过去讨论过的话题线索\n3. 保留 assistant 对用户的回应（承诺、确认、情感回应等）\n4. 输出格式保持 user/assistant 交替对话，每条消息控制在 1-3 句\n5. 最终输出像是原对话的\"记忆精华版\"，而非知识提取",
        "user_template": "请将以下对话压缩为精简记忆版对话，保留 user 个人信息、偏好、情感、话题线索。丢弃代码、技术细节等 LLM 已知内容。\n\n输出格式保持 user/assistant 交替：\n\nuser: ...\nassistant: ...\n\n---\n\n原始对话：\n\n{text}"
    },
    "自定义": {
        "system": "",
        "user_template": "{text}"
    }
}


def get_template_names() -> list:
    names = list(PROMPT_TEMPLATES.keys())
    custom_dir = Path("prompts")
    if custom_dir.exists():
        for f in sorted(custom_dir.glob("*.json")):
            names.append(f.stem)
    return names


def get_template(name: str) -> dict:
    if name in PROMPT_TEMPLATES:
        return PROMPT_TEMPLATES[name]
    custom_dir = Path("prompts")
    custom_file = custom_dir / f"{name}.json"
    if custom_file.exists():
        try:
            with open(custom_file) as f:
                return json.load(f)
        except Exception:
            pass
    return PROMPT_TEMPLATES["标准知识提取"]


def add_custom_prompt(name: str, system: str, user_template: str):
    custom_dir = Path("prompts")
    custom_dir.mkdir(exist_ok=True)
    with open(custom_dir / f"{name}.json", "w") as f:
        json.dump({"system": system, "user_template": user_template}, f, indent=2, ensure_ascii=False)


def interactive_select(title: str = "📝 选择 Prompt 模板") -> tuple:
    names = get_template_names()
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    for i, name in enumerate(names, 1):
        print(f"  [{i}] {name}")
    print(f"{'='*60}")
    try:
        choice = input(f"\n👉 请选择 [1-{len(names)}] (默认 1): ").strip()
        idx = int(choice) - 1 if choice else 0
        idx = max(0, min(idx, len(names) - 1))
        selected = names[idx]
        tpl = get_template(selected)
        print(f"  ✅ 已选择: {selected}")
        return tpl.get("system", ""), tpl.get("user_template", "{text}")
    except (ValueError, IndexError):
        tpl = get_template(names[0])
        return tpl.get("system", ""), tpl.get("user_template", "{text}")
