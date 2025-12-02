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

# 採用戦略分析ジェネレーター（SerpAPI + LLM）

このリポジトリは、企業名と求人情報から企業理解レポート（Step1：生成、Step2：レビュー／拡充）を自動生成するStreamlitアプリです。主な特徴:

- LLM（`gpt-5-mini`）を利用した2段階プロンプトワークフロー
- SerpAPIを利用したIR/企業情報の自動収集（PDF抽出とウェブ検索のフォールバック）
- Streamlitでのインタラクティブな操作とエクスポート機能（JSON/Wordなど）

**重要な設計・運用メモ**:
- `prompts/` 配下のプロンプトは基本的に改変しない前提で動作します（プロンプトはアプリの核です）。
- `gpt-5-mini` は一部パラメータ（例：`temperature`の0.7指定）がサポートされていないため、SDK呼び出しはデフォルト値を使用しています。
- Streamlit Cloudなど読み取り専用ファイルシステム上で動かす場合、`modules/logger.py` にてファイルハンドラの作成失敗を安全にスキップする実装を追加しています。

**リポジトリ**: https://github.com/Yu10Kumura/hojo_model_company_understand

---

**必要条件**

- Python 3.11 以上（推奨）
- `pip` と仮想環境（`venv`）
- `requirements.txt` に記載のパッケージ（`openai==2.8.1` など）

**環境変数**

プロジェクトルートに `.env` ファイルを作成するか、環境に以下を設定してください：

```env
OPENAI_API_KEY=sk-...    # OpenAI APIキー
SERPAPI_KEY=...         # SerpAPIキー（PDFやウェブ検索用）
# 必要に応じて他のキーを追加
```

---

**ローカルセットアップ（クイックスタート）**

```bash
cd "/Users/yutokumura/Desktop/Python/企業理解HOJO_model_v4"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

動作確認・起動:

```bash
streamlit run app.py --server.port 8511
```

ブラウザで `http://localhost:8511` を開いて操作します。

---

**Streamlit Cloud へデプロイする手順（概要）**

1. GitHub にリポジトリをプッシュ済みであること（例: `Yu10Kumura/hojo_model_company_understand`）。
2. https://share.streamlit.io/ にログインし "New app" を選択。
3. リポジトリ/ブランチ/ファイルパス（`app.py`）を選択してデプロイ。
4. Streamlit Cloud の「Secrets」に `OPENAI_API_KEY` と `SERPAPI_KEY` を設定。

Secretsは以下の形式で登録してください（UIでの入力）：

```toml
OPENAI_API_KEY = "sk-..."
SERPAPI_KEY = "..."
```

---

**ファイル構成（主要ファイル）**

- `app.py` - Streamlit エントリポイント
- `modules/openai_api.py` - OpenAI呼び出しロジック（モデル: `gpt-5-mini`）
- `modules/ir_extractor.py` - IR/PDF抽出とウェブ検索フォールバック
- `modules/serp_api.py` - SerpAPI 関連ユーティリティ
- `modules/logger.py` - ロギング（Streamlit Cloudの読み取り専用FS対応済み）
- `prompts/` - Step1/Step2のプロンプトテンプレート

---

**システム構成（アーキテクチャ）**

本アプリの主要コンポーネントとデータフローをテキストで示します。

- **Frontend（Streamlit UI）**: `app.py` がエントリポイント。ユーザーの会社名・求人情報を受け取り、分析をトリガーします。ローカル実行時はデフォルトで `8511` ポートを使用します。

- **IR / 情報取得層**:
	- `modules/serp_api.py`: SerpAPI を使った IR/PDF 検索と一般ウェブ検索（`search_general_info`）。
	- `modules/ir_extractor.py`: PDF（`pdfplumber`）やウェブ情報を抽出・照合し、財務・事業情報を構造化（`dict`）して返します。

- **LLM 呼び出し層**:
	- `modules/openai_api.py`: OpenAI SDK (`openai==2.8.1`) を用いて `gpt-5-mini` を呼び出します。Step1（生成）→ Step2（レビュー／拡充）の順に処理します。`max_completion_tokens=16000` を設定し、`temperature` はモデル側の制約に従い未指定です。

- **ロギング / モニタ**:
	- `modules/logger.py` で回転ログ（RotatingFileHandler）を使用。Streamlit Cloud のような読み取り専用環境ではファイルハンドラ生成に失敗した場合にスキップする安全処理があります。

- **プロンプト管理**:
	- `prompts/` フォルダ内に Step1/Step2 のテンプレートを配置します。プロンプトの変更は結果へ直接影響するため、バージョン管理を推奨します。

- **エクスポート / 永続化**:
	- 生成結果は JSON / Word（`python-docx`）等でエクスポート可能です。クラウド環境ではファイルシステムが非永続な場合があるため、S3 など外部ストレージへの保存を推奨します。

データフロー（簡易シーケンス）:

1. ユーザーが `app.py` で会社名・求人情報を入力
2. `ir_extractor` が IR/PDF を検索・抽出（失敗時はウェブ検索）
3. 構造化した企業情報を `openai_api.generate_step1_report` に渡す
4. Step1 出力を `generate_step2_report` でレビュー／拡充
5. 最終結果を画面表示・ファイルエクスポート

運用上のポイント:

- **トークンおよびコスト**: 長文生成はトークン消費が増えるため、利用頻度とコストを監視してください（使用モデルの価格に依存します）。
- **レート制限対策**: SerpAPI / OpenAI のレート制限に注意し、必要に応じてリトライ・バックオフを実装してください。
- **永続ストレージ**: Streamlit Cloud の場合はファイルが永続化されないことがあるため、出力は外部ストレージへ保管する運用を検討してください。

**よくあるトラブルと対処**

- OpenAI呼び出しで400エラー（Unsupported value: 'temperature'）が出る場合：
	- `gpt-5-mini` は `temperature` の任意指定をサポートしないため、`modules/openai_api.py` の呼び出しから `temperature` を削除しています。

- ログファイル作成でPermissionError/OSErrorが出る場合：
	- Streamlit Cloud等の読み取り専用環境ではファイルハンドラ作成が失敗することがあるため、`modules/logger.py` は失敗時にファイルログをスキップします。

- 生成結果が途中で切れる（出力切断）場合：
	- OpenAI APIのトークン上限・SDKの互換性を確認してください。推奨: `openai==2.8.1` 以降で `gpt-5-mini` の使用を行ってください。

---

**開発メモ / 今後の改善案**

- Step2以降の出力の安定化（長文出力のページネーションや分割取得）
- 日本語PDFの抽出精度向上（OCRや専用パーサの導入）
- 出力フォーマット（表・表組み）のより堅牢な生成

---

問題が発生したら `issues` を開くか、直接連絡してください。

