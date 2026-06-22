"""OpenAI互換APIによるエージェント - Excelファイルを自律的に分析・操作する"""

import os
import json

import openai

from .tools import TOOL_SCHEMAS, call_tool


SYSTEM_PROMPT = """\
あなたはExcelファイルを操作して原価集計を行うAIエージェントです。

あなたの仕事:
1. data/ディレクトリにあるExcelファイルを確認する
2. ファイルの構造を理解する
3. マトメ表（集計先）と明細一覧（データソース）を特定する
4. 明細一覧から分番ごとの費用を集計する
5. 集計結果をマトメ表の購入品（小計）に書き込む

重要な戦略:
- 日本のExcelファイルはセル結合やタイトル行があるため、まず read_excel_raw で生データを見てヘッダー行を特定する
- ヘッダー行を特定したら read_excel_info に header_row を指定して正しい列名を取得する
- 列を1つずつ調べるのではなく、read_excel_raw の結果から一度に構造を把握する
- 分番ごとの集計には group_and_sum を使うと1回で全分番の合計が得られる
- ユーザーに質問せず、自分でファイルを読んで判断する
- 「分番」に相当する列を自分で特定する（品番、部番、分番、Part No.など類似の列名を探す）
- 「費用」「金額」「購入費」「原価」に相当する列を自分で特定する
- 作業完了後、結果のサマリーを報告する
"""


def create_client() -> openai.OpenAI:
    """OpenAI互換クライアントを作成"""
    return openai.OpenAI(
        api_key=os.environ["API_KEY"],
        base_url=os.environ["API_ENDPOINT"],
    )


def run(user_input: str = None) -> str:
    """エージェントを実行する（ツール呼び出しループ）"""
    if user_input is None:
        user_input = (
            "data/ディレクトリのExcelファイルを確認し、"
            "分番ごとの購入費用を集計してマトメ表に記入してください。"
        )

    client = create_client()
    model = os.environ.get("LLM_MODEL", "gemini-3-flash-preview")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    max_iterations = 30
    for i in range(max_iterations):
        print(f"\n--- ステップ {i+1} ---")

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
        )

        choice = response.choices[0]
        message = choice.message

        # ツール呼び出しがなければ終了
        if not message.tool_calls:
            print(f"エージェント応答: {message.content}")
            return message.content or ""

        # ツール呼び出しを実行
        messages.append(message.model_dump())

        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = tool_call.function.arguments
            print(f"  ツール呼び出し: {func_name}({func_args})")

            result = call_tool(func_name, func_args)
            print(f"  結果: {result[:200]}...")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    return "最大ステップ数に達しました。処理を中断します。"
