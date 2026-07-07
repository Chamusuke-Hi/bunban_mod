"""メインエントリポイント"""

import os
import sys
import warnings
from dotenv import load_dotenv

warnings.filterwarnings("ignore", module="openpyxl")
load_dotenv()


def main():
    from .workflow_graph import execute_workflow

    # 承認済み経験の一覧表示
    if len(sys.argv) >= 2 and sys.argv[1] == "list-approved":
        result = execute_workflow(action="list-approved")
        print(result)
        return

    if not os.environ.get("API_KEY"):
        print("エラー: API_KEY 環境変数を設定してください")
        sys.exit(1)
    if not os.environ.get("API_ENDPOINT"):
        print("エラー: API_ENDPOINT 環境変数を設定してください")
        sys.exit(1)

    # --experience フラグ or 環境変数 USE_EXPERIENCE=1 で経験参照を強制有効
    use_experience = "--experience" in sys.argv or os.environ.get("USE_EXPERIENCE", "").strip() == "1"
    args = [a for a in sys.argv[1:] if a != "--experience"]
    user_input = " ".join(args) if args else None

    if use_experience:
        print("モード: 経験参照あり（確認スキップ）")
    else:
        print("モード: 実行前に経験の有無を確認します")

    print("モード: 実行後に承認/却下を確認します")

    result = execute_workflow(
        action="run",
        user_input=user_input,
        use_experience=use_experience,
    )
    print("\n" + result)


if __name__ == "__main__":
    main()
