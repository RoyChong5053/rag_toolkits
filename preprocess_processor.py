"""RAG 文本预处理处理器 - emoji 清理 + 按大小分割"""
import re
import shutil
from pathlib import Path
from typing import List, Optional

from core.config import config

MB = 1024 * 1024

EMOJI_PATTERN = re.compile(
    "[\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U0001FB00-\U0001FBFF"
    "\U00002700-\U000027BF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002600-\U000026FF"
    "\U0001F170-\U0001F251"
    "\U0001F3FB-\U0001F3FF"
    "\U00002640-\U00002642"
    "\u200d"
    "]+",
    flags=re.UNICODE,
)


def remove_emoji_from_text(text: str) -> str:
    return EMOJI_PATTERN.sub("", text).replace("\u200b", "")


class PreprocessProcessor:
    def __init__(self):
        self.input_dir = Path(config.get("preprocess", "input_dir", default="input/raw"))
        self.output_dir = Path(config.get("preprocess", "output_dir", default="input/clean"))
        self.remove_emoji_flag = config.get("preprocess", "remove_emoji", default=True)
        self.split_threshold = config.get("preprocess", "split_threshold_mb", default=5) * MB
        self.target_mb = config.get("preprocess", "target_mb_per_file", default=1)

    def scan_input(self) -> List[Path]:
        supported = {".txt", ".md", ".pdf", ".doc", ".docx"}
        files = []
        if self.input_dir.exists():
            for f in sorted(self.input_dir.iterdir()):
                if f.is_file() and f.suffix.lower() in supported:
                    files.append(f)
        return files

    def total_size(self, files: List[Path]) -> int:
        return sum(f.stat().st_size for f in files)

    def convert_to_md(self, file_path: Path, output_path: Path) -> bool:
        suffix = file_path.suffix.lower()
        try:
            if suffix == ".txt":
                for enc in ["utf-8", "gbk", "gb2312", "gb18030", "big5"]:
                    try:
                        content = file_path.read_text(encoding=enc)
                        output_path.write_text(content, encoding="utf-8")
                        return True
                    except UnicodeDecodeError:
                        continue
                return False
            elif suffix == ".md":
                shutil.copy2(file_path, output_path)
                return True
            elif suffix == ".pdf":
                try:
                    import pdfplumber
                    text_lines = []
                    with pdfplumber.open(file_path) as pdf:
                        for page in pdf.pages:
                            text = page.extract_text()
                            if text:
                                text_lines.append(text)
                    output_path.write_text("\n\n".join(text_lines), encoding="utf-8")
                    return True
                except ImportError:
                    try:
                        from pypdf import PdfReader
                        text_lines = []
                        reader = PdfReader(file_path)
                        for page in reader.pages:
                            text = page.extract_text()
                            if text:
                                text_lines.append(text)
                        output_path.write_text("\n\n".join(text_lines), encoding="utf-8")
                        return True
                    except Exception:
                        return False
            else:
                return False
        except Exception:
            return False

    def split_by_mb(self, file_path: Path, mb_per_file: int = None) -> List[Path]:
        if mb_per_file is None:
            mb_per_file = self.target_mb
        output_files = []
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        current_size = 0
        file_count = 1
        current_lines = []

        for line in lines:
            line_size = len(line.encode("utf-8")) + 1
            if current_size + line_size > mb_per_file * MB and current_lines:
                output_path = self.output_dir / f"{file_path.stem}_part{file_count:03d}.md"
                output_path.write_text("\n".join(current_lines), encoding="utf-8")
                output_files.append(output_path)
                file_count += 1
                current_lines = []
                current_size = 0

            current_lines.append(line)
            current_size += line_size

        if current_lines:
            output_path = self.output_dir / f"{file_path.stem}_part{file_count:03d}.md"
            output_path.write_text("\n".join(current_lines), encoding="utf-8")
            output_files.append(output_path)

        return output_files

    def run(self, do_emoji: Optional[bool] = None, do_split: Optional[bool] = None):
        DONE, ERR = "✅", "❌"
        files = self.scan_input()

        if not files:
            print(f"{ERR} input/raw/ 中没有支持的文档文件")
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"  📝 文本预处理")
        print(f"{'='*60}")
        print(f"  输入: {self.input_dir}/")
        print(f"  输出: {self.output_dir}/")
        print(f"  文件: {len(files)} 个")
        total_size = self.total_size(files)
        print(f"  大小: {total_size / MB:.2f} MB")
        print(f"{'='*60}")

        if do_emoji is None:
            r = input(f"\n去除 Emoji? (Y/n): ").strip().lower()
            do_emoji = r != "n"

        need_split = total_size > self.split_threshold
        if do_split is None and need_split:
            r = input(f"文件 >{self.split_threshold/MB:.0f}MB，是否分割为 {self.target_mb}MB 每文件? (Y/n): ").strip().lower()
            do_split = r != "n"
        elif do_split is None:
            do_split = False

        converted_files = []
        for f in files:
            out_name = f.stem + ".md"
            out_path = self.output_dir / out_name
            print(f"  转换: {f.name} -> {out_name}... ", end="", flush=True)
            ok = self.convert_to_md(f, out_path)
            if ok:
                print(f"{DONE}")
                converted_files.append(out_path)
            else:
                print(f"{ERR} 跳过")

        if not converted_files:
            print(f"{ERR} 没有文件转换成功")
            return

        if do_emoji:
            print(f"\n  清除 Emoji...")
            for f in converted_files:
                content = f.read_text(encoding="utf-8")
                cleaned = remove_emoji_from_text(content)
                f.write_text(cleaned, encoding="utf-8")
                print(f"  {DONE} {f.name}")

        if do_split:
            print(f"\n  分割文件 (目标 {self.target_mb}MB/文件)...")
            for f in list(self.output_dir.glob("*.md")):
                size = len(f.read_bytes())
                if size > self.target_mb * MB:
                    parts = self.split_by_mb(f, self.target_mb)
                    f.unlink()
                    print(f"  {DONE} {f.name} -> {len(parts)} 个文件")

        final = list(self.output_dir.glob("*.md"))
        print(f"\n{'='*60}")
        print(f"  ✅ 预处理完成!")
        print(f"  输出目录: {self.output_dir}/")
        print(f"  文件数量: {len(final)}")
        print(f"{'='*60}")
