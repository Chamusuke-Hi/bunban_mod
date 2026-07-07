"""経験メモリ — 保留保存・承認・参照"""

import json
import shutil
from datetime import datetime
from pathlib import Path

# 承認済み経験はホストマウント先（永続）
EXPERIENCE_DIR = Path("/app/output/experiences")
APPROVED_DIR = EXPERIENCE_DIR / "approved"

# 保留経験はコンテナ内tmpfs（docker compose down で自動破棄）
PENDING_DIR = Path("/tmp/experiences/pending")


def _build_experience(
    user_input: str,
    tool_trace: list[dict],
    final_answer: str,
    success: bool,
) -> dict:
    """実行トレース辞書を作成する。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "timestamp": ts,
        "user_input": user_input,
        "success": success,
        "tool_trace": tool_trace,
        "final_answer": final_answer[:500],
    }


def save_pending_experience(
    user_input: str,
    tool_trace: list[dict],
    final_answer: str,
    success: bool,
) -> Path:
    """実行トレースを保留経験として保存する。

    Args:
        user_input: ユーザーの入力テキスト
        tool_trace: [{"tool": name, "args": args_str, "result_summary": str}, ...]
        final_answer: エージェントの最終回答
        success: 成功フラグ（最大ステップ到達=False）
    Returns:
        保留ファイルの保存先パス
    """
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    experience = _build_experience(user_input, tool_trace, final_answer, success)
    path = PENDING_DIR / f"{experience['timestamp']}.json"
    path.write_text(json.dumps(experience, ensure_ascii=False, indent=2))
    print(f"  保留経験を保存: pending/{path.name}")
    return path


def _latest_pending_path() -> Path | None:
    """最新の保留経験ファイルを返す。"""
    if not PENDING_DIR.exists():
        return None
    files = sorted(PENDING_DIR.glob("*.json"), reverse=True)
    return files[0] if files else None


def approve_pending_experience(filename: str | None = None) -> Path | None:
    """保留経験を承認済みに移動する。filename未指定時は最新を承認。
    
    pendingはコンテナ内tmp、approvedはホストマウント先なので shutil.move を使用。
    """
    src = (PENDING_DIR / filename) if filename else _latest_pending_path()
    if src is None or not src.exists():
        return None
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    dst = APPROVED_DIR / src.name
    shutil.move(str(src), str(dst))
    return dst


def reject_pending_experience(filename: str | None = None) -> Path | None:
    """保留経験を却下（削除）する。filename未指定時は最新を却下。"""
    src = (PENDING_DIR / filename) if filename else _latest_pending_path()
    if src is None or not src.exists():
        return None
    src.unlink()
    return src


def load_experiences(max_count: int = 3) -> list[dict]:
    """最新の承認済み成功経験をmax_count件読み込む。"""
    if not APPROVED_DIR.exists() and not EXPERIENCE_DIR.exists():
        return []

    # 互換性: 旧実装でルートに保存されたJSONも読み込む
    files = []
    if APPROVED_DIR.exists():
        files.extend(APPROVED_DIR.glob("*.json"))
    files.extend(EXPERIENCE_DIR.glob("*.json"))
    files = sorted(files, reverse=True)
    experiences = []
    for f in files:
        try:
            exp = json.loads(f.read_text())
            if exp.get("success"):
                experiences.append(exp)
                if len(experiences) >= max_count:
                    break
        except (json.JSONDecodeError, KeyError):
            continue
    return experiences


def format_experiences_for_prompt(experiences: list[dict]) -> str:
    """経験リストをシステムプロンプト注入用テキストに整形する。"""
    if not experiences:
        return ""

    parts = ["\n\n--- 過去の成功事例 ---"]
    parts.append("以下は過去に同様のタスクを成功させた際の実行トレースです。参考にしてください。\n")

    for i, exp in enumerate(experiences, 1):
        parts.append(f"【事例{i}】 入力: {exp['user_input']}")
        for step in exp.get("tool_trace", []):
            parts.append(f"  → {step['tool']}({step.get('args', '')})")
            summary = step.get("result_summary", "")
            if summary:
                parts.append(f"    結果: {summary}")
        parts.append(f"  最終回答(抜粋): {exp.get('final_answer', '')[:200]}")
        parts.append("")

    return "\n".join(parts)


def list_approved_experiences_for_display() -> str:
    """承認済み経験を人間向け表示フォーマットで返す。"""
    if not APPROVED_DIR.exists():
        return "承認済み経験はまだありません。"
    
    files = sorted(APPROVED_DIR.glob("*.json"), reverse=True)
    if not files:
        return "承認済み経験はまだありません。"
    
    lines = ["\n【承認済み経験一覧】\n"]
    for i, f in enumerate(files, 1):
        try:
            exp = json.loads(f.read_text())
            ts = exp.get("timestamp", "")
            user_input = exp.get("user_input", "")
            success = exp.get("success", False)
            status = "✓ 成功" if success else "✗ 失敗"
            lines.append(f"{i}. [{ts}] {status}")
            lines.append(f"   入力: {user_input[:60]}..." if len(user_input) > 60 else f"   入力: {user_input}")
            lines.append(f"   ファイル: {f.name}")
            lines.append("")
        except (json.JSONDecodeError, KeyError):
            continue
    
    return "\n".join(lines) if len(lines) > 1 else "承認済み経験はまだありません。"
