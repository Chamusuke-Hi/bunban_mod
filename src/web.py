"""FastAPI Webインターフェース"""

import os
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Excel集計エージェント")

DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>Excel集計エージェント</title>
        <style>
            body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }
            h1 { color: #333; }
            .upload-form { background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0; }
            input[type="file"] { margin: 10px 0; }
            button { background: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background: #45a049; }
            .result { background: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0; white-space: pre-wrap; }
            .error { background: #ffebee; }
            #loading { display: none; color: #666; }
        </style>
    </head>
    <body>
        <h1>Excel集計エージェント</h1>
        <div class="upload-form">
            <h3>Excelファイルをアップロード</h3>
            <form id="uploadForm" enctype="multipart/form-data">
                <p>マトメ表: <input type="file" name="matome" accept=".xlsx,.xls"></p>
                <p>伝票明細一覧: <input type="file" name="meisai" accept=".xlsx,.xls"></p>
                <p>指示（任意）: <input type="text" name="instruction" placeholder="分番ごとの購入費用を集計してください" style="width:100%"></p>
                <button type="submit">実行</button>
            </form>
            <p id="loading">処理中...</p>
        </div>
        <div id="result"></div>
        <script>
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const form = new FormData(e.target);
                document.getElementById('loading').style.display = 'block';
                document.getElementById('result').innerHTML = '';
                try {
                    const res = await fetch('/run', { method: 'POST', body: form });
                    const data = await res.json();
                    const cls = data.error ? 'result error' : 'result';
                    document.getElementById('result').innerHTML = `<div class="${cls}">${data.result || data.error}</div>`;
                    if (data.output_file) {
                        document.getElementById('result').innerHTML += `<p><a href="/download/${data.output_file}">結果ファイルをダウンロード</a></p>`;
                    }
                } catch(err) {
                    document.getElementById('result').innerHTML = `<div class="result error">${err}</div>`;
                }
                document.getElementById('loading').style.display = 'none';
            });
        </script>
    </body>
    </html>
    """


@app.post("/run")
async def run_agent(
    matome: UploadFile = File(None),
    meisai: UploadFile = File(None),
    instruction: str = Form(None),
):
    # ファイルを保存
    for upload in [matome, meisai]:
        if upload and upload.filename:
            dest = DATA_DIR / upload.filename
            content = await upload.read()
            dest.write_bytes(content)

    # エージェント実行
    from .agent import run

    try:
        result = run(instruction)
    except Exception as e:
        return {"error": str(e)}

    # 出力ファイルを探す
    output_files = list(DATA_DIR.glob("output_*.xlsx"))
    output_file = output_files[0].name if output_files else None

    return {"result": result, "output_file": output_file}


@app.get("/download/{filename}")
async def download(filename: str):
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return {"error": "ファイルが見つかりません"}
    return FileResponse(filepath, filename=filename)
