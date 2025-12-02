# 採用戦略分析ジェネレーター (SerpAPI + LLM版)

YUTOさん作成の2段階プロンプトを使用し、企業の採用戦略分析レポートを自動生成するツールです。プロンプトは原文のまま使用し、改変しません。

## セットアップ

### 1. 仮想環境と依存パッケージ
```bash
cd "/Users/yutokumura/Desktop/Python/企業理解HOJO_model_v4"
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. APIキー設定
`.env`を作成し、以下を記載します。
```bash
OPENAI_API_KEY=your_openai_api_key
SERPAPI_KEY=your_serpapi_key
```

### 3. プロンプト配置
- `prompts/prompt_step1.txt` に第1プロンプトをコピペ（原文そのまま）
- `prompts/prompt_step2.txt` に第2プロンプトをコピペ（原文そのまま）

## 起動
```bash
streamlit run app.py
```
ブラウザで `http://localhost:8501` にアクセス。

## 使い方
1. 会社名を入力
2. 求人情報を貼り付け
3. 「分析を開始する」をクリック
4. 結果をダウンロード（JSON/Word/PDF）

## 注意事項
- IR/PDF日本語PDFのレイアウトによって抽出できない場合があります。
- PDFエクスポートは簡易ASCII対応です（日本語は将来対応）。
