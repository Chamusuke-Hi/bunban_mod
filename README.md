# Excel集計エージェント

OpenAI互換APIの **Function Calling** を使い、Excelファイルを自律的に読み取り・分析・集計するAIエージェントです。

---

## 概要

- マトメ表と伝票明細一覧を `data/` に置いて起動するだけ
- AIが自分でファイル構造を読み取り、分番ごとの費用集計を実行
- 列名や手順を指示する必要なし — エージェントが自律判断

---

## クイックスタート
```bash
UID=$(id -u) docker compose up --build
```

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│  Docker コンテナ (excel-agent)                              
│                                                             
│  main.py                                                    
│    └── agent.py  ← エージェントループ                       
│          │                                                  
│          │  ① システムプロンプト + ユーザー指示を送信         
│          ▼                                                        
│  ┌──────────────────┐    OpenAI互換API    ┌──────────────┐    
│  │  openai.OpenAI   │ ◄──────────────────► │ LLM (Gemini) │       
│  │  (base_url方式)  │    Function Calling  │              │   │  
│  └──────────────────┘                      └──────────────┘   │
│          │                                                     │
│          │  ② LLMが「どのツールを呼ぶか」を判断して返答         │
│          ▼                                                     │
│  ┌──────────────────┐                                         │
│  │  tools.py        │  ← Excel操作ツール群                     │
│  │  - list_excel_files                                         │
│  │  - read_excel_raw     ← 生データ表示 (構造把握用)           │
│  │  - read_excel_info    ← 列名・データ型確認                  │
│  │  - read_excel_column_values                                 │
│  │  - group_and_sum      ← 分番ごと一括集計                    │
│  │  - filter_and_sum                                           │
│  │  - batch_filter_and_sum                                     │
│  │  - write_to_excel     ← 結果書き込み                       │
│  └──────────────────┘                                         │
│          │                                                     │
│          │  ③ ツール実行結果をLLMに返し、次の判断を仰ぐ          │
│          │     (①〜③をループ。最大30ステップ)                    │
│          ▼                                                     │
│  data/output_*.xlsx   ← 集計結果ファイル                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 仕組み（詳細）

### 1. エージェントループ (`agent.py`)

OpenAI の **Function Calling** (tool use) の仕組みで動きます。
LangChainなどのフレームワークは使わず、`openai` ライブラリを直接使用しています。

```
while ステップ < 30:
    ① messages をLLMに送信（tools=ツールスキーマ一覧 付き）
    ② LLMの応答を確認
       - tool_calls がある → ツールを実行し、結果を messages に追加 → ①へ
       - tool_calls がない → 最終回答として返す（ループ終了）
```

- LLMは**どのツールを、どの引数で呼ぶか**を自分で判断します
- ツールの実行結果を見て、次に何をすべきか再び自分で判断します
- 人間の代わりにAIが「考える→操作→確認→次の操作」を繰り返す仕組みです

### 2. ツール定義 (`tools.py`)

各ツールは以下の3要素で構成されています：

| 要素 | 説明 |
|------|------|
| **Python関数** | 実際のExcel操作ロジック（pandas/openpyxl使用） |
| **JSONスキーマ** | LLMに渡すツール定義（名前・説明・引数の型） |
| **call_tool()** | LLMが返した関数名+引数JSONを受けて実行するディスパッチャ |

LLMはJSONスキーマを見て「このツールはこういう引数で呼べば、こういう結果が返る」と理解します。

### 3. 日本のExcelへの対応

日本の業務Excelはセル結合・タイトル行・装飾が多く、`pd.read_excel()` のデフォルトでは列名が `Unnamed: 0, Unnamed: 1, ...` になりがちです。

これを解決するため：

1. **`read_excel_raw`** でヘッダー無しの生データを表示 → タイトル行・ヘッダー行の位置を把握
2. **`header_row` パラメータ** で正しいヘッダー行を指定 → 正しい列名を取得
3. **`group_and_sum`** で分番列をキーに金額列を一括集計 → 1回のツール呼び出しで全分番の合計を取得

### 4. システムプロンプト

エージェントには以下の戦略をプロンプトで指示しています：

- まず `read_excel_raw` で生データを見てヘッダー行を特定する
- 列を1つずつ調べるのではなく一度に構造を把握する
- `group_and_sum` を使い1回で全分番の集計を得る
- ユーザーに質問せず自律的に判断する

---

## セットアップ

### 1. 環境変数の設定

```bash
cp .env.example .env
# .env を編集して API_ENDPOINT と API_KEY を設定
```

| ファイル | 用途 |
|----------|------|
| `.env` | `API_ENDPOINT`, `API_KEY` — 秘密情報（git管理外） |
| `.eenv` | `LLM_MODEL` — モデル設定（チーム共有可） |

### 2. Excelファイルの配置

`data/` ディレクトリにExcelファイルを配置します。

```bash
cp マトメ表.xlsx data/
cp 伝票明細一覧表.xlsx data/
```

---

## 実行方法

### CLI（コンテナ）

```bash
docker compose up --build
```

### カスタム指示付き

```bash
docker compose run excel-agent python -m src.main "分番ごとの購入費用を集計してマトメ表に記入してください"
```

### Web UI

docker-compose.yml の command を変更:

```yaml
command: ["uvicorn", "src.web:app", "--host", "0.0.0.0", "--port", "8501"]
```

ブラウザで http://localhost:8501 にアクセス

---

## 実行の流れ（実例）

```
--- ステップ 1 ---
  ツール: list_excel_files()
  結果: ZE02-133.xlsx, H1A_Voucher_Details_List_HD30040.xlsx

--- ステップ 2 ---
  ツール: read_excel_raw(filename="H1A_Voucher_Details_List_HD30040.xlsx")
  結果: 行0: [0]月次原価　＞　原価伝票明細　3456件
        行1: [0]No., [1]伝票区分, ... [34]分番, [35]金額
        行2: [0]1, [1]仕入, ... [34]09A, [35]125000
        （→ ヘッダーは行1と判断）

--- ステップ 3 ---
  ツール: read_excel_info(filename="...", header_row=1)
  結果: 列名: ['No.', '伝票区分', ..., '分番', '金額']
        （→ 正しい列名が取れた）

--- ステップ 4 ---
  ツール: group_and_sum(filename="...", group_column="分番", sum_column="金額", header_row=1)
  結果: 09A: 1,250,000  09B: 830,000  10A: 2,100,000  ...
        （→ 1回で全分番の集計完了）

--- ステップ 5 ---
  ツール: write_to_excel(filename="ZE02-133.xlsx", key_column="記号", value_column="購入費", data={...})
  結果: 完了: 85件更新。出力先: output_ZE02-133.xlsx
```

---

## ファイル構成

```
excel_agent/
├── docker-compose.yml   # コンテナ定義（プロキシ・UID対応済）
├── Dockerfile           # マルチステージビルド（dev target）
├── requirements.txt     # openai, pandas, openpyxl, fastapi
├── .env.example         # 環境変数テンプレート
├── .eenv                # モデル設定
├── data/                # Excelファイル配置先 & 出力先
└── src/
    ├── __init__.py
    ├── main.py          # エントリポイント（環境変数チェック）
    ├── agent.py         # エージェントループ（Function Calling）
    ├── tools.py         # Excel操作ツール群 + JSONスキーマ
    └── web.py           # Web UI（FastAPI、ファイルアップロード対応）
```

---

## ツール一覧

| ツール名 | 説明 |
|----------|------|
| `list_excel_files` | data/内のExcelファイル一覧 |
| `read_excel_sheet_names` | シート名一覧 |
| `read_excel_raw` | 生データ表示（セル結合Excel対応、構造把握用） |
| `read_excel_info` | 列名・行数・先頭データ表示（header_row指定可） |
| `read_excel_column_values` | 指定列のユニーク値一覧 |
| `group_and_sum` | グループ化して一括集計（分番ごと集計に最適） |
| `filter_and_sum` | 1つのフィルタ値で集計 |
| `batch_filter_and_sum` | 複数フィルタ値で一括集計 |
| `write_to_excel` | キー列で行を特定して値を書き込み → output_*.xlsx出力 |
