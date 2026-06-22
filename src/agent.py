"""OpenAI互換APIによるエージェント - Excelファイルを自律的に分析・操作する"""

import os
import json

import openai

from .tools import TOOL_SCHEMAS, call_tool


SYSTEM_PROMPT = """\
あなたはExcelデータを分析するAIエージェントです。
ユーザーの依頼を達成するために、利用可能なツールを使って自律的に作業を行います。

作業手順:
1. まずユーザーの依頼を分析し、何を達成すべきかを整理する
2. 達成するために必要な情報収集の計画を立て、ユーザーに提示する
3. 計画に沿ってツールを使い、データを収集・分析する
4. 結果をまとめて報告する。必要であればExcelファイルに書き込む

ルール:
- 作業開始前に必ず「計画」を立てて提示すること
- 計画は番号付きのステップで記述する
- 各ステップ完了後、次のステップに進む前に中間結果を簡潔に報告する
- 想定外のデータ構造に出会った場合は、計画を修正して提示する
- ユーザーに質問せず、自分で判断して進める
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
        user_input = "分番ごとに購入品の費用を集計してください。"

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
