"""メインエントリポイント"""

import os
import sys
import warnings
from dotenv import load_dotenv

warnings.filterwarnings("ignore", module="openpyxl")
load_dotenv()


def main():
    if not os.environ.get("API_KEY"):
        print("エラー: API_KEY 環境変数を設定してください")
        sys.exit(1)
    if not os.environ.get("API_ENDPOINT"):
        print("エラー: API_ENDPOINT 環境変数を設定してください")
        sys.exit(1)

    from .agent import run

    # コマンドライン引数があればそれを指示として使う
    user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    result = run(user_input)
    print("\n" + "=" * 60)
    print("【実行結果】")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
