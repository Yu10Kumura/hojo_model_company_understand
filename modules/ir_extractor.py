"""
IR資料から財務データを抽出
"""
import requests
import io
import pdfplumber
from openai import OpenAI
import os
import json
from typing import Dict


def classify_company_type(company_name: str) -> str:
    """
    企業タイプを判定（上場/子会社/小規模など）
    
    Args:
        company_name: 企業名
        
    Returns:
        "listed": 上場企業
        "subsidiary": 子会社・関連会社
        "unknown": 不明
    """
    if not isinstance(company_name, str):
        company_name = str(company_name)
    
    # 上場企業の典型的なキーワード
    listed_keywords = ["株式会社", "ホールディングス", "グループ", "HD"]
    
    # 子会社・関連会社の典型的なキーワード
    subsidiary_keywords = ["CK", "システムズ", "ソリューションズ", "テクノロジーズ", 
                          "サービス", "エンジニアリング", "コンサルティング"]
    
    # 子会社パターンチェック（より厳密）
    for keyword in subsidiary_keywords:
        if keyword in company_name:
            return "subsidiary"
    
    # 上場企業パターンチェック
    for keyword in listed_keywords:
        if keyword in company_name:
            return "listed"
    
    return "unknown"


def strict_company_verification(pdf_text: str, target_company: str) -> bool:
    """
    より厳密な社名照合
    
    Args:
        pdf_text: PDFから抽出したテキスト
        target_company: 対象企業名
        
    Returns:
        True: 一致、False: 不一致
    """
    if not isinstance(pdf_text, str) or not isinstance(target_company, str):
        return False
    
    company_type = classify_company_type(target_company)
    
    # 完全一致チェック
    if target_company in pdf_text:
        return True
    
    # 子会社の場合は親会社名だけでは不可（厳格ルール）
    if company_type == "subsidiary":
        print(f"[IR Extractor] 子会社 '{target_company}' は完全一致のみ許可")
        return False
    
    # 上場企業の場合は部分一致も許可
    if company_type == "listed":
        # 企業名の主要部分を抽出して部分一致チェック
        main_name = target_company.replace("株式会社", "").replace("HD", "").strip()
        if main_name and len(main_name) > 2 and main_name in pdf_text:
            return True
    
    return False


def fetch_web_profile(company_name: str) -> Dict[str, str]:
    """
    IRが見つからない／照合失敗時のフォールバック: ウェブ検索で会社情報を取得
    
    Args:
        company_name: 企業名
    
    Returns:
        {
            "source": "web_search",
            "summary": "検索結果のスニペット集約",
            "data_quality": "partial_public"
        }
    """
    try:
        from modules.serp_api import search_general_info
        
        # 複数クエリで情報収集
        queries = [
            f"{company_name} 会社概要 事業内容",
            f"{company_name} 企業情報 売上",
            f"{company_name} ビジネス 事業"
        ]
        
        all_snippets = []
        for query in queries:
            snippets = search_general_info(query)
            if snippets:
                all_snippets.append(snippets)
                break  # 最初に成功したクエリで打ち切り（API呼び出し節約）
        
        if not all_snippets:
            return {
                "error": "web_search_no_results",
                "summary": "ウェブ検索で有用な公開情報が見つかりませんでした",
                "data_quality": "none"
            }
        
        # 検索結果をまとめる
        combined_text = "\n\n".join(all_snippets)
        summary = f"【ウェブ検索による企業情報（自動収集）】\n\n{combined_text[:8000]}"
        
        return {
            "source": "web_search",
            "summary": summary,
            "data_quality": "partial_public",
        }
    except Exception as e:
        return {
            "error": "web_search_failed",
            "summary": str(e)[:200],
            "data_quality": "error"
        }


def generate_industry_estimation(company_name: str, job_info: str = "") -> Dict[str, str]:
    """
    業界推定に基づく財務データ生成
    
    Args:
        company_name: 企業名
        job_info: 求人情報（業界推定用）
        
    Returns:
        推定財務データ
    """
    # IT・システム系の推定値
    if any(keyword in company_name.lower() or keyword in job_info.lower() 
           for keyword in ["システム", "ソリューション", "IT", "DX", "エンジニア", "SE"]):
        return {
            "売上高": "業界平均推定: 100-500億円",
            "営業利益率": "業界平均推定: 8-12パーセント",
            "自己資本比率": "業界平均推定: 40-60パーセント",
            "ROE": "業界平均推定: 10-15パーセント",
            "営業キャッシュフロー": "推定値",
            "主力事業セグメント": "ITソリューション事業: 推定75パーセント",
            "地域別売上構成": "国内中心: 推定80パーセント",
            "新規事業領域": "DX、クラウドサービス",
            "中期経営計画": "デジタル化推進",
            "成長戦略": "IT人材強化、新技術導入",
            "投資計画": "システム投資中心",
            "DX取り組み": "自社DX推進中",
            "市場シェア": "地域特化型",
            "強み": "専門技術、顧客密着",
            "_estimation_note": "子会社のため推定値を使用"
        }
    
    # 一般的な推定値
    return {
        "売上高": "推定値: 50-200億円",
        "営業利益率": "推定値: 5-10パーセント",
        "自己資本比率": "推定値: 30-50パーセント",
        "ROE": "推定値: 8-12パーセント",
        "営業キャッシュフロー": "推定値",
        "主力事業セグメント": "推定: 専門サービス事業",
        "地域別売上構成": "推定: 国内中心",
        "新規事業領域": "推定: サービス拡張",
        "中期経営計画": "推定: 安定成長",
        "成長戦略": "推定: 既存事業強化",
        "投資計画": "推定: 設備投資",
        "DX取り組み": "推定: 業務効率化",
        "市場シェア": "推定: 地域密着型",
        "強み": "推定: 専門性",
        "_estimation_note": "IR資料未発見のため推定値を使用"
    }


def safe_error_message(message: str) -> str:
    """
    エラーメッセージから危険な文字を人間が読める形に変換
    
    Args:
        message: 元のメッセージ
        
    Returns:
        安全なメッセージ
    """
    if not isinstance(message, str):
        message = str(message)
    
    # 危険な文字を人間が読める形に変換（エスケープではなく置換）
    safe_msg = message.replace('%', 'パーセント')
    safe_msg = safe_msg.replace('{', '（')
    safe_msg = safe_msg.replace('}', '）')
    
    return safe_msg


def get_financials_from_ir(company_name: str) -> Dict[str, str]:
    """
    メイン関数: 企業名からIR資料を取得→財務データ抽出
    フォールバック戦略付き（IR失敗時はウェブ検索で公開情報を収集）
    
    Args:
        company_name: 企業名
    
    Returns:
        {
            "売上高": "5.2兆円",
            "営業利益率": "8.5パーセント",
            "自己資本比率": "45.2パーセント"
        }
        or
        {"error": "エラーメッセージ", "use_estimation": True}
    """
    try:
        # 企業タイプ判定
        company_type = classify_company_type(company_name)
        print(f"[IR Extractor] 企業タイプ判定: {company_name} → {company_type}")
        
        # SerpAPIでIR資料PDF検索(別モジュール)
        from modules.serp_api import search_ir_pdf_url
        
        pdf_url = search_ir_pdf_url(company_name)
        ir_failed = False
        
        if not pdf_url:
            print(f"[IR Extractor] IR資料なし: '{company_name}'")
            ir_failed = True
        else:
            try:
                # PDF取得
                pdf_content = download_pdf(pdf_url)
                
                # テキスト抽出
                text = extract_text_from_pdf(pdf_content)
                
                if not text or len(text) < 100:
                    print(f"[IR Extractor] PDFテキスト抽出失敗: '{company_name}'")
                    ir_failed = True
                else:
                    # 厳密な企業名照合
                    if not strict_company_verification(text, company_name):
                        print(f"[IR Extractor] 企業照合失敗: '{company_name}' ≠ PDF内容")
                        ir_failed = True
            except Exception as e:
                print(f"[IR Extractor] PDF処理エラー: {str(e)[:100]}")
                ir_failed = True
        
        # IR処理失敗時のフォールバック: ウェブ検索
        if ir_failed:
            print(f"[IR Extractor] ウェブ検索フォールバックを実行: '{company_name}'")
            web_info = fetch_web_profile(company_name)
            
            if web_info.get("source") == "web_search":
                # ウェブ検索で情報が取得できた場合
                return {
                    "売上高": "情報不足（要確認）",
                    "営業利益率": "情報不足（要確認）",
                    "自己資本比率": "情報不足（要確認）",
                    "企業概要": web_info.get("summary", ""),
                    "情報ソース": "web_search（公開情報自動収集）",
                    "data_quality": web_info.get("data_quality", "partial_public")
                }
            else:
                # ウェブ検索も失敗した場合
                if company_type == "subsidiary":
                    print(f"[IR Extractor] 子会社 '{company_name}' → 推定値使用")
                    return {"error": "子会社のため独自IR資料なし", "use_estimation": True}
                return {"error": "IR資料もウェブ情報も見つかりませんでした"}
        
        # IR処理成功時の従来フロー（照合成功）
        # LLMで財務データ抽出(APIキーがない場合はスキップ)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {
                "error": "OpenAI APIキーが未設定のため、財務抽出はスキップしました"
            }
        
        # Step1: 基本財務データ抽出 (引数にcompany_nameを追加)
        financials = extract_financials_with_llm(text, company_name)
        
        # 【追加修正】社名不一致などでエラーが返ってきた場合はここで終了（詳細化をスキップ）
        if "error" in financials:
            print(f"[IR Extractor] 処理中断: {financials['error']}")
            if company_type == "subsidiary":
                return {"error": financials['error'], "use_estimation": True}
            return financials

        # Step2: 事業セグメント詳細化（基本抽出で不十分な場合）
        if financials and isinstance(financials, dict):
            segment_info = financials.get("主力事業セグメント", "")
            if "不明" in segment_info or len(segment_info) < 20:
                enhanced_segments = extract_detailed_segments(text, api_key)
                if enhanced_segments:
                    financials["主力事業セグメント"] = enhanced_segments
                    print("[IR Extractor] 事業セグメント詳細化完了")
        
        # 型チェック: 辞書であることを確認
        if not isinstance(financials, dict):
            type_name = str(type(financials).__name__)
            print("[IR Extractor ERROR] extract_financials_with_llm returned non-dict: " + type_name)
            return {"error": "財務データが辞書形式ではありません"}
        
        type_name = str(type(financials).__name__)
        keys_str = ", ".join(list(financials.keys()))
        print("[IR Extractor] Final financials type: " + type_name + ", keys: " + keys_str)
        return financials
        
        # LLMで財務データ抽出(APIキーがない場合はスキップ)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {
                "error": "OpenAI APIキーが未設定のため、財務抽出はスキップしました"
            }
        
        # Step1: 基本財務データ抽出 (引数にcompany_nameを追加)
        financials = extract_financials_with_llm(text, company_name)
        
        # 【追加修正】社名不一致などでエラーが返ってきた場合はここで終了（詳細化をスキップ）
        if "error" in financials:
            print(f"[IR Extractor] 処理中断: {financials['error']}")
            if company_type == "subsidiary":
                return {"error": financials['error'], "use_estimation": True}
            return financials

        # Step2: 事業セグメント詳細化（基本抽出で不十分な場合）
        if financials and isinstance(financials, dict):
            segment_info = financials.get("主力事業セグメント", "")
            if "不明" in segment_info or len(segment_info) < 20:
                enhanced_segments = extract_detailed_segments(text, api_key)
                if enhanced_segments:
                    financials["主力事業セグメント"] = enhanced_segments
                    print("[IR Extractor] 事業セグメント詳細化完了")
        
        # 型チェック: 辞書であることを確認
        if not isinstance(financials, dict):
            type_name = str(type(financials).__name__)
            print("[IR Extractor ERROR] extract_financials_with_llm returned non-dict: " + type_name)
            return {"error": "財務データが辞書形式ではありません"}
        
        type_name = str(type(financials).__name__)
        keys_str = ", ".join(list(financials.keys()))
        print("[IR Extractor] Final financials type: " + type_name + ", keys: " + keys_str)
        return financials
    
    except Exception as e:
        # 安全なエラーメッセージ作成
        error_type = type(e).__name__
        error_msg_raw = str(e)[:100]  # 最初100文字のみ
        safe_error_msg = safe_error_message(error_msg_raw)
        error_full = error_type + ": " + safe_error_msg
        
        print("[IR Extractor ERROR] 財務データ取得失敗: " + error_full)
        result = {"error": error_full}
        return result


def download_pdf(url: str) -> bytes:
    """
    PDFをダウンロード
    
    Args:
        url: PDF URL
    
    Returns:
        PDFバイナリデータ
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def extract_text_from_pdf(pdf_content: bytes) -> str:
    """
    PDFからテキスト抽出(最初の15ページ)
    
    Args:
        pdf_content: PDFバイナリ
    
    Returns:
        抽出テキスト
    """
    text = ""
    
    with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
        # 最初の15ページだけ処理(トークン制限対策)
        for page in pdf.pages[:15]:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"
    
    return text


def extract_financials_with_llm(text: str, company_name: str) -> Dict[str, str]:
    """
    GPT-5-miniで財務データを抽出
    
    Args:
        text: IR資料のテキスト
        company_name: 分析対象の企業名（追加）
    
    Returns:
        財務データ(JSON)
    """
    # トークン制限対策: 最初の6000文字のみ
    text_sample = text[:6000]
    
    # 【追加修正】プロンプト冒頭に社名照合命令を追加
    company_type = classify_company_type(company_name)
    
    prompt = """分析対象企業名: """ + company_name + """

【重要安全ガード: 社名照合】
提供されたテキストが「""" + company_name + """」の資料であることを確認してください。
企業タイプ: """ + company_type + """

照合ルール:
- subsidiary（子会社）の場合: 完全一致のみ許可。親会社名だけでは不可。
- listed（上場企業）の場合: 部分一致も許可。
- unknown（不明）の場合: 慎重に判定。

もし明らかに「全く別の企業」の資料である場合は、分析を行わず、以下のJSONのみを出力：
{"error": "対象外の企業の資料が検出されました"}

一致する場合は、以下の指示に従ってください。

IR資料から企業の重要情報を段階的に抽出してください。まず確実に見つけられる情報を重点的に探し、不明な項目は「不明」ではなく具体的な検索努力をしてください。

【第1段階: 必須財務情報(この段階で必ず発見してください)】
1. 売上高: 「売上高」「総売上」「Revenue」などのキーワードを探し、最新期の連結売上高を億円単位で記載
2. 営業利益率: 「営業利益」と「売上高」から計算、または直接「営業利益率」記載を探す
3. 自己資本比率: 「自己資本比率」「Equity Ratio」を探し、パーセント表記で記載

【第2段階: 追加財務指標】
4. ROE: 「ROE」「自己資本利益率」「Return on Equity」を探す
5. 営業キャッシュフロー: 「営業活動によるキャッシュフロー」「営業CF」を探す

【第3段階: 事業構造分析】
6. 主力事業セグメント: セグメント別売上や事業別業績表を探し、売上構成比とともに記載
7. 地域別売上構成: 「地域別」「国内外」「海外売上比率」などを探す
8. 新規事業領域: 「新規事業」「新分野」「新サービス」の記載を探す

【第4段階: 戦略・計画情報】
9. 中期経営計画: 「中期計画」「中期経営計画」「3年計画」「5年計画」の目標数値
10. 成長戦略: 「戦略」「重点施策」「成長ドライバー」を探す
11. 投資計画: 「設備投資」「投資予定」「CAPEX」の金額や計画
12. DX取り組み: 「DX」「デジタル化」「IT投資」「システム刷新」などの記載

【第5段階: 競争分析】
13. 市場シェア: 「シェア」「市場地位」「業界順位」などの数値
14. 強み: 「競争優位」「強み」「差別化」「特徴」などの記載

【重要な抽出指示】
- 「不明」は最後の手段として使用し、まず類似表現や関連データを探してください
- 数値は「〜〜億円」「〜〜パーセント」などの形式で正確に記載
- 連結決算を優先し、単体は避けてください
- 最新期（2024年度、2025年度）のデータを優先
- セグメント情報は「自動車事業: 4兆円（75パーセント）」のように具体的に記載
- 文書内を徹底的に検索し、関連キーワードでも探してください

【分析対象文書】
""" + text_sample + """

【出力JSON形式】
{
  "売上高": "具体的な金額（億円）",
  "営業利益率": "具体的なパーセント", 
  "自己資本比率": "具体的なパーセント",
  "ROE": "具体的なパーセント",
  "営業キャッシュフロー": "具体的な金額",
  "主力事業セグメント": "事業名と構成比",
  "地域別売上構成": "地域別の詳細",
  "新規事業領域": "新規分野の具体名",
  "中期経営計画": "計画内容と目標",
  "成長戦略": "戦略の要点",
  "投資計画": "投資額と内容", 
  "DX取り組み": "デジタル化の内容",
  "市場シェア": "シェア率と順位",
  "強み": "競争優位性"
}"""
    
    # クライアントを実行時に初期化（.env読み込み後に評価）
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)  # ここでキーが必須
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"},
        #temperature=0.1
    )
    
    result_text = response.choices[0].message.content
    
    # デバッグログ: LLM応答内容(raw)
    print("[IR Extractor] LLM Response (raw, first 200 chars): " + result_text[:200] + "...")
    
    # Markdownコードブロックのクリーニング
    result_text = result_text.strip()
    if result_text.startswith("```"):
        # ```json ... ``` 形式の除去
        lines = result_text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]  # 最初の```行を除去
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # 最後の```行を除去
        result_text = "\n".join(lines).strip()
        print("[IR Extractor] Removed Markdown code block wrapper")
    
    # デバッグログ: クリーニング後
    print("[IR Extractor] Cleaned response (first 200 chars): " + result_text[:200] + "...")
    
    try:
        financials_dict = json.loads(result_text)
        # 型チェック: 必ず辞書であることを確認
        if not isinstance(financials_dict, dict):
            type_name = str(type(financials_dict).__name__)
            print("[IR Extractor ERROR] LLM returned non-dict type: " + type_name)
            return {
                "売上高": "不明",
                "営業利益率": "不明",
                "自己資本比率": "不明"
            }
        # デバッグログ: 正常な辞書を取得
        keys_str = ", ".join(list(financials_dict.keys()))
        print("[IR Extractor] Parsed dict keys: " + keys_str)
        return financials_dict
    except json.JSONDecodeError as e:
        # エラーメッセージを安全に作成(値を含めない)
        error_type = type(e).__name__
        error_msg_short = str(e)[:100]  # 最初100文字のみ
        safe_msg = "[IR Extractor ERROR] JSON decode failed: " + error_type + ": " + error_msg_short
        print(safe_msg)
        return {
            "売上高": "不明",
            "営業利益率": "不明",
            "自己資本比率": "不明"
        }


def extract_detailed_segments(text: str, api_key: str) -> str:
    """
    事業セグメント情報に特化した二次抽出
    
    Args:
        text: IR資料の全文テキスト
        api_key: OpenAI API Key
    
    Returns:
        詳細な事業セグメント情報
    """
    # セグメント情報が記載されている可能性の高い部分を検索
    segment_keywords = [
        "セグメント", "事業別", "部門別", "分野別", "カテゴリー別",
        "自動車", "金融", "IT", "製造業", "小売", "不動産", "エネルギー",
        "segment", "business", "division"
    ]
    
    # キーワードを含む段落を抽出（前後の文脈も含める）
    relevant_text = ""
    text_lines = text.split("\n")
    
    for i, line in enumerate(text_lines):
        for keyword in segment_keywords:
            if keyword in line.lower() or keyword in line:
                # 該当行の前後5行を含める
                start_idx = max(0, i-5)
                end_idx = min(len(text_lines), i+6)
                segment_context = "\n".join(text_lines[start_idx:end_idx])
                relevant_text += segment_context + "\n\n"
                break
    
    # 関連テキストがない場合は元のテキストの一部を使用
    if len(relevant_text) < 100:
        relevant_text = text[:3000]
    
    prompt = f"""以下のIR資料から事業セグメント情報を詳細に抽出してください。

【最重要タスク】
事業別の売上高と構成比を具体的な数値で抽出してください。

【探索すべき情報】
- セグメント別売上高（億円単位）
- 各セグメントの売上構成比（パーセント）
- 主要な事業領域・分野名
- 各事業の成長率や前年比

【分析対象テキスト】
{relevant_text}

【出力形式】
「事業A: ○○○○億円（○○パーセント）、事業B: ○○○○億円（○○パーセント）」
の形式で、具体的な数値とともに記載してください。

見つからない場合のみ「不明」として回答してください。
"""
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-5-mini",  # 5-miniを利用
            messages=[{"role": "user", "content": prompt}],
            #temperature=0.1,
            # max_tokens=500
        )
        
        result = response.choices[0].message.content.strip()
        print(f"[IR Extractor] セグメント詳細化結果: {result[:100]}...")
        return result
        
    except Exception as e:
        print(f"[IR Extractor] セグメント詳細化エラー: {str(e)[:100]}")
        return "不明"