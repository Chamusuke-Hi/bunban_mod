"""Excel操作ツール群 - OpenAI function calling用のツール定義"""

import json
import pandas as pd
from pathlib import Path


DATA_DIR = Path("/app/data")
OUTPUT_DIR = Path("/app/output")


def _read_df(filename: str, sheet_name: str = None, header_row: int = None):
    """共通のExcel読み込み。header_rowでヘッダー行(0始まり)を指定可能"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"{filename} が見つかりません")
    kwargs = {}
    if sheet_name:
        kwargs["sheet_name"] = sheet_name
    if header_row is not None:
        kwargs["header"] = header_row
    return pd.read_excel(filepath, **kwargs)


def list_excel_files() -> str:
    """data/ディレクトリにあるExcelファイル一覧を返す"""
    files = list(DATA_DIR.glob("*.xlsx")) + list(DATA_DIR.glob("*.xls"))
    if not files:
        return "Excelファイルが見つかりません。data/ディレクトリにファイルを配置してください。"
    return "\n".join([f.name for f in files])


def read_excel_sheet_names(filename: str) -> str:
    """指定したExcelファイルのシート名一覧を返す"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return f"エラー: {filename} が見つかりません"
    xls = pd.ExcelFile(filepath)
    return f"シート一覧: {', '.join(xls.sheet_names)}"


def read_excel_raw(filename: str, sheet_name: str = None, start_row: int = 0, num_rows: int = 15) -> str:
    """Excelの生データをヘッダー無しで読み取る。セル結合されたExcelの構造把握に使う。
    各行は行番号付きで表示される。"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return f"エラー: {filename} が見つかりません"
    kwargs = {"header": None}
    if sheet_name:
        kwargs["sheet_name"] = sheet_name
    df = pd.read_excel(filepath, **kwargs)
    end_row = min(start_row + num_rows, len(df))
    subset = df.iloc[start_row:end_row]
    info = [f"ファイル: {filename} (全{len(df)}行x{len(df.columns)}列) 表示: 行{start_row}-{end_row-1}"]
    for idx, row in subset.iterrows():
        vals = [f"[{i}]{v}" for i, v in enumerate(row.values) if pd.notna(v)]
        info.append(f"行{idx}: {', '.join(vals)}")
    return "\n".join(info)


def read_excel_info(filename: str, sheet_name: str = None, header_row: int = None) -> str:
    """Excelファイルの構造情報（列名、行数、先頭数行のサンプル）を返す。
    header_rowでヘッダー行を指定可能(0始まり)。日本のExcelは上部にタイトル行があるので適切に指定する。"""
    try:
        df = _read_df(filename, sheet_name, header_row)
    except FileNotFoundError as e:
        return f"エラー: {e}"
    info = [f"ファイル: {filename}"]
    if sheet_name:
        info.append(f"シート: {sheet_name}")
    if header_row is not None:
        info.append(f"ヘッダー行: {header_row}")
    info.append(f"行数: {len(df)}, 列数: {len(df.columns)}")
    info.append(f"列名: {list(df.columns)}")
    info.append(f"先頭5行:\n{df.head().to_string()}")
    return "\n".join(info)


def read_excel_column_values(filename: str, column_name: str, sheet_name: str = None, header_row: int = None) -> str:
    """指定列のユニーク値一覧を返す"""
    try:
        df = _read_df(filename, sheet_name, header_row)
    except FileNotFoundError as e:
        return f"エラー: {e}"
    if column_name not in df.columns:
        return f"エラー: 列 '{column_name}' が見つかりません。利用可能な列: {list(df.columns)}"
    values = df[column_name].dropna().unique()
    return f"列 '{column_name}' のユニーク値 ({len(values)}件):\n{list(values[:100])}"


def filter_and_sum(
    filename: str, filter_column: str, filter_value: str, sum_column: str,
    sheet_name: str = None, header_row: int = None,
) -> str:
    """指定列でフィルタリングし、別の列の合計を求める"""
    try:
        df = _read_df(filename, sheet_name, header_row)
    except FileNotFoundError as e:
        return f"エラー: {e}"
    if filter_column not in df.columns:
        return f"エラー: 列 '{filter_column}' が見つかりません。利用可能: {list(df.columns)}"
    if sum_column not in df.columns:
        return f"エラー: 列 '{sum_column}' が見つかりません。利用可能: {list(df.columns)}"
    clean_val = str(filter_value).strip('"\'')
    filtered = df[df[filter_column].astype(str).str.strip() == clean_val]
    total = pd.to_numeric(filtered[sum_column], errors="coerce").sum()
    return f"フィルタ条件: {filter_column}='{clean_val}' → {sum_column}の合計: {total} ({len(filtered)}件)"


def batch_filter_and_sum(
    filename: str, filter_column: str, filter_values: list, sum_column: str,
    sheet_name: str = None, header_row: int = None,
) -> str:
    """複数のフィルタ値それぞれについて合計を求める"""
    try:
        df = _read_df(filename, sheet_name, header_row)
    except FileNotFoundError as e:
        return f"エラー: {e}"
    if filter_column not in df.columns:
        return f"エラー: 列 '{filter_column}' が見つかりません"
    if sum_column not in df.columns:
        return f"エラー: 列 '{sum_column}' が見つかりません"
    results = []
    for val in filter_values:
        clean_val = str(val).strip('"\'')
        filtered = df[df[filter_column].astype(str).str.strip() == clean_val]
        total = pd.to_numeric(filtered[sum_column], errors="coerce").sum()
        results.append(f"  {clean_val}: {total} ({len(filtered)}件)")
    return f"フィルタ列: {filter_column}, 合計列: {sum_column}\n" + "\n".join(results)


def group_and_sum(
    filename: str, group_column: str, sum_column: str,
    sheet_name: str = None, header_row: int = None,
) -> str:
    """指定列でグループ化し、別の列の合計を求める。分番ごとの集計に便利。"""
    try:
        df = _read_df(filename, sheet_name, header_row)
    except FileNotFoundError as e:
        return f"エラー: {e}"
    if group_column not in df.columns:
        return f"エラー: 列 '{group_column}' が見つかりません。利用可能: {list(df.columns)}"
    if sum_column not in df.columns:
        return f"エラー: 列 '{sum_column}' が見つかりません。利用可能: {list(df.columns)}"
    df[sum_column] = pd.to_numeric(df[sum_column], errors="coerce")
    grouped = df.groupby(group_column)[sum_column].sum()
    results = [f"  {k}: {v}" for k, v in grouped.items()]
    return f"グループ列: {group_column}, 合計列: {sum_column} ({len(grouped)}グループ)\n" + "\n".join(results)


def write_to_excel(
    filename: str, key_column: str, value_column: str, data: dict,
    sheet_name: str = None, header_row: int = None,
) -> str:
    """Excelファイルの指定列に値を書き込む（キー列の値で行を特定）"""
    try:
        df = _read_df(filename, sheet_name, header_row)
    except FileNotFoundError as e:
        return f"エラー: {e}"
    if key_column not in df.columns:
        return f"エラー: 列 '{key_column}' が見つかりません"
    if value_column not in df.columns:
        df[value_column] = None
    updated = 0
    for key, value in data.items():
        # LLMが余分なクォートを付けることがあるので除去
        clean_key = str(key).strip('"\'')
        mask = df[key_column].astype(str).str.strip() == clean_key
        if mask.any():
            df.loc[mask, value_column] = value
            updated += 1
    output_path = OUTPUT_DIR / f"output_{filename}"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False)
    return f"完了: {updated}件更新。出力先: output/{output_path.name}"


# --- OpenAI function calling用スキーマ ---

TOOL_FUNCTIONS = {
    "list_excel_files": list_excel_files,
    "read_excel_sheet_names": read_excel_sheet_names,
    "read_excel_raw": read_excel_raw,
    "read_excel_info": read_excel_info,
    "read_excel_column_values": read_excel_column_values,
    "filter_and_sum": filter_and_sum,
    "batch_filter_and_sum": batch_filter_and_sum,
    "group_and_sum": group_and_sum,
    "write_to_excel": write_to_excel,
}

_HEADER_ROW_PARAM = {"type": "integer", "description": "ヘッダーとして使う行番号(0始まり)。日本のExcelはタイトル行があるので適切に指定。省略時は0行目"}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_excel_files",
            "description": "data/ディレクトリにあるExcelファイル一覧を返す",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_excel_sheet_names",
            "description": "指定したExcelファイルのシート名一覧を返す",
            "parameters": {
                "type": "object",
                "properties": {"filename": {"type": "string", "description": "Excelファイル名"}},
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_excel_raw",
            "description": "Excelの生データをヘッダー無しで読み取る。セル結合されたExcelの構造把握に最適。まずこれで構造を確認し、ヘッダー行を特定する。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Excelファイル名"},
                    "sheet_name": {"type": "string", "description": "シート名（省略時は最初のシート）"},
                    "start_row": {"type": "integer", "description": "開始行(0始まり、デフォルト0)"},
                    "num_rows": {"type": "integer", "description": "表示行数(デフォルト15)"},
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_excel_info",
            "description": "Excelファイルの構造情報（列名、行数、先頭数行のサンプル）を返す。header_rowを指定してヘッダー行を正しく設定できる。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Excelファイル名"},
                    "sheet_name": {"type": "string", "description": "シート名（省略時は最初のシート）"},
                    "header_row": _HEADER_ROW_PARAM,
                },
                "required": ["filename"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_excel_column_values",
            "description": "指定列のユニーク値一覧を返す",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Excelファイル名"},
                    "column_name": {"type": "string", "description": "列名"},
                    "sheet_name": {"type": "string", "description": "シート名（省略時は最初のシート）"},
                    "header_row": _HEADER_ROW_PARAM,
                },
                "required": ["filename", "column_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "filter_and_sum",
            "description": "指定列でフィルタリングし、別の列の合計を求める",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Excelファイル名"},
                    "filter_column": {"type": "string", "description": "フィルタ対象の列名"},
                    "filter_value": {"type": "string", "description": "フィルタ値"},
                    "sum_column": {"type": "string", "description": "合計を求める列名"},
                    "sheet_name": {"type": "string", "description": "シート名（省略時は最初のシート）"},
                    "header_row": _HEADER_ROW_PARAM,
                },
                "required": ["filename", "filter_column", "filter_value", "sum_column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "batch_filter_and_sum",
            "description": "複数のフィルタ値それぞれについて合計を求める",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Excelファイル名"},
                    "filter_column": {"type": "string", "description": "フィルタ対象の列名"},
                    "filter_values": {"type": "array", "items": {"type": "string"}, "description": "フィルタ値のリスト"},
                    "sum_column": {"type": "string", "description": "合計を求める列名"},
                    "sheet_name": {"type": "string", "description": "シート名（省略時は最初のシート）"},
                    "header_row": _HEADER_ROW_PARAM,
                },
                "required": ["filename", "filter_column", "filter_values", "sum_column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "group_and_sum",
            "description": "指定列でグループ化し、別の列の合計を一括で求める。分番ごとの費用集計に最適。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Excelファイル名"},
                    "group_column": {"type": "string", "description": "グループ化する列名（例:分番）"},
                    "sum_column": {"type": "string", "description": "合計を求める列名（例:金額）"},
                    "sheet_name": {"type": "string", "description": "シート名（省略時は最初のシート）"},
                    "header_row": _HEADER_ROW_PARAM,
                },
                "required": ["filename", "group_column", "sum_column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_to_excel",
            "description": "Excelファイルの指定列に値を書き込む（キー列の値で行を特定）。結果はoutput_ファイル名.xlsxに出力。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Excelファイル名"},
                    "key_column": {"type": "string", "description": "行を特定するためのキー列名"},
                    "value_column": {"type": "string", "description": "書き込み先の列名"},
                    "data": {"type": "object", "description": "{キー値: 書き込む値} の辞書"},
                    "sheet_name": {"type": "string", "description": "シート名（省略時は最初のシート）"},
                    "header_row": _HEADER_ROW_PARAM,
                },
                "required": ["filename", "key_column", "value_column", "data"],
            },
        },
    },
]


def call_tool(name: str, arguments: str) -> str:
    """ツールを名前と引数JSON文字列で呼び出す"""
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return f"エラー: 未知のツール '{name}'"
    try:
        args = json.loads(arguments) if arguments else {}
        return func(**args)
    except Exception as e:
        return f"エラー: {e}"
