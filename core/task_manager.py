"""任务隔离管理 - 追踪 input 变更，输出归档"""
import json
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

MANIFEST_FILE = ".task_manifest.json"
ARCHIVE_DIR = Path("output/archive")
CHECKPOINT_DIR = Path("checkpoints")
INTERMEDIATE_DIR = Path("intermediate")


class TaskManager:
    def __init__(self):
        self.manifest_path = Path(MANIFEST_FILE)
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> Optional[Dict]:
        if not self.manifest_path.exists():
            return None
        try:
            with open(self.manifest_path) as f:
                return json.load(f)
        except Exception:
            return None

    def _save_manifest(self, data: Dict):
        with open(self.manifest_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _compute_file_signature(self, file_path: Path) -> Dict:
        stat = file_path.stat()
        return {
            "name": file_path.name,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "md5": hashlib.md5(file_path.read_bytes()).hexdigest(),
        }

    def _scan_input_files(self, input_dirs: List[Path]) -> Dict[str, Dict]:
        files = {}
        for d in input_dirs:
            if d.exists():
                for f in sorted(d.iterdir()):
                    if f.is_file() and not f.name.startswith("."):
                        files[str(f)] = self._compute_file_signature(f)
        return files

    def detect_change(self, input_dirs: Optional[List[Path]] = None) -> Tuple[bool, str]:
        if input_dirs is None:
            input_dirs = [Path("input/raw"), Path("input/photo")]

        current_files = self._scan_input_files(input_dirs)

        if self.manifest is None:
            n = sum(len(v) for v in [list(Path(d).glob("*")) for d in input_dirs if Path(d).exists()])
            if n > 0:
                self._save_manifest({
                    "created_at": datetime.now().isoformat(),
                    "files": current_files,
                })
            return False, "首次运行，已创建任务清单"

        previous_files = self.manifest.get("files", {})

        if current_files == previous_files:
            return False, "input 文件无变化，继续当前任务"

        old_keys = set(previous_files.keys())
        new_keys = set(current_files.keys())

        added = new_keys - old_keys
        removed = old_keys - new_keys
        changed = {k for k in old_keys & new_keys if previous_files[k] != current_files[k]}

        changes = []
        if added:
            changes.append(f"新增 {len(added)} 个文件")
        if removed:
            changes.append(f"移除 {len(removed)} 个文件")
        if changed:
            changes.append(f"修改 {len(changed)} 个文件")

        return True, f"检测到 input 变更: {'; '.join(changes)}"

    def archive_old_output(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = ARCHIVE_DIR / ts
        archive_dir.mkdir(parents=True, exist_ok=True)
        for sub in ["rag", "ocr"]:
            src = Path(f"output/{sub}")
            if src.exists() and any(src.iterdir()):
                dst = archive_dir / sub
                dst.mkdir(parents=True, exist_ok=True)
                for f in src.iterdir():
                    if f.is_file():
                        shutil.copy2(f, dst / f.name)
        manifest_copy = archive_dir / ".task_manifest.json"
        if self.manifest_path.exists():
            shutil.copy2(self.manifest_path, manifest_copy)
        if archive_dir.exists() and any(archive_dir.iterdir()):
            print(f"📦 旧结果已归档到: {archive_dir}/")

    def reset_for_new_task(self, input_dirs: Optional[List[Path]] = None):
        if input_dirs is None:
            input_dirs = [Path("input/raw"), Path("input/photo")]

        self.archive_old_output()

        for d in [CHECKPOINT_DIR, INTERMEDIATE_DIR]:
            if d.exists():
                shutil.rmtree(d)
                d.mkdir(exist_ok=True)

        current_files = self._scan_input_files(input_dirs)
        self._save_manifest({
            "created_at": datetime.now().isoformat(),
            "files": current_files,
        })

    def ask_user_for_action(self, change_msg: str) -> str:
        print(f"\n{change_msg}")
        print("  [Y] 开始新任务 → 旧结果归档，从头处理")
        print("  [N] 继续当前任务 (忽略变更)")
        print("  [C] 取消")
        while True:
            choice = input("👉 请选择 [Y/N/C]: ").strip().lower()
            if choice in ("y", "n", "c"):
                return choice
            print("输入无效，请输入 Y/N/C")
