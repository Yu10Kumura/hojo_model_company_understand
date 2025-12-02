"""SerpAPIで業界データ・IR資料を取得 (改良版)

改良点:
 - APIキー未設定時の早期メッセージ
 - 業界データ検索結果の空判定改善
 - IR PDF検索: クエリを増強し多段試行 + 拡張フィルタ
 - デバッグ用環境変数 `DEBUG_SERPAPI=1` で内部状態簡易出力
"""
import os
from typing import Optional, List, Dict, Any


def _debug(msg: str):
    # 常にログ出力(Streamlitログで確認可能)
    print("[SerpAPI DEBUG] " + str(msg))


def search_market_data(industry_keyword: str) -> str:
    """業界規模・トレンドデータを検索 (上位有機結果のスニペット集約)"""
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return "SerpAPIキー未設定のため検索をスキップしました。"

    query_variants = [
        f"{industry_keyword} 市場規模 2024 日本",
        f"{industry_keyword} 成長率 2024",
        f"{industry_keyword} トレンド 2024",
    ]

    try:
        from serpapi.google_search import GoogleSearch  # 正しいインポートパス
    except ImportError:
        try:
            from serpapi import GoogleSearch  # 旧バージョン互換
        except ImportError as e:
            _debug(f"ImportError GoogleSearch: {e}")
            return "SerpAPIクライアントのインポートに失敗したため検索をスキップしました。再インストール例: `pip install --force-reinstall google-search-results`"
    snippets: List[str] = []

    for q in query_variants:
        params = {
            "q": q,
            "location": "Japan",
            "hl": "ja",
            "gl": "jp",
            "num": 5,
            "api_key": api_key,
        }
        try:
            _debug("market search query='" + str(q) + "'")
            results = GoogleSearch(params).get_dict()
            _debug("Results keys: " + str(list(results.keys())))
            organic = results.get('organic_results', [])
            _debug("organic_results count: " + str(len(organic)))
            
            # 最初の結果の詳細をログ出力
            if organic:
                first = organic[0]
                title_sample = str(first.get('title', 'N/A'))[:50]
                has_snippet = bool(first.get('snippet'))
                _debug("First result sample - title: " + title_sample + ", snippet exists: " + str(has_snippet))
            else:
                _debug("WARNING: No organic_results returned. Full response keys: " + str(list(results.keys())))
                # エラー情報があればログ出力
                if 'error' in results:
                    error_val = str(results.get('error', ''))[:100]
                    _debug("API Error: " + error_val)
        except Exception as e:
            error_msg = str(e)[:100]
            _debug("market search error: " + error_msg)
            continue

        for result in results.get("organic_results", [])[:5]:
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            if snippet:
                snippets.append("【" + str(title) + "】\n" + str(snippet))
        if len(snippets) >= 5:  # 十分取得できたら打ち切り
            break

    if not snippets:
        return "業界データが見つかりませんでした。"
    return "\n\n".join(snippets)


def search_ir_pdf_url(company_name: str) -> Optional[str]:
    """IR関連PDF(決算説明資料/有価証券報告書/統合報告書等)のURLを探索 - 段階的検索強化版"""
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        _debug("SerpAPI key missing; abort IR pdf search")
        return None

    # Step1: 基本検索クエリ（従来通り）
    basic_queries = [
        f"{company_name} 決算説明資料 pdf",
        f"{company_name} 決算短信 pdf",
        f"{company_name} 有価証券報告書 pdf",
        f"{company_name} 統合報告書 pdf",
        f"{company_name} IR 資料 pdf",
        f"{company_name} annual report pdf",
    ]
    
    # Step2: 企業名のバリエーション対応
    company_variants = [company_name]
    if "株式会社" in company_name:
        company_variants.append(company_name.replace("株式会社", ""))
    if "ホールディングス" in company_name:
        company_variants.append(company_name.replace("ホールディングス", "HD"))
        company_variants.append(company_name.replace("ホールディングス", ""))
    
    # Step3: 拡張検索クエリ
    enhanced_queries = []
    for variant in company_variants:
        enhanced_queries.extend([
            f'site:ir.{variant.lower().replace(" ", "").replace("株式会社", "")}.co.jp filetype:pdf',
            f'{variant} "investor relations" pdf 2024',
            f'{variant} "決算" pdf 2024',
            f'{variant} "財務情報" pdf',
            f'{variant} "業績" pdf site:co.jp',
        ])
    
    all_queries = basic_queries + enhanced_queries

    # PDFリンクフィルタ条件（強化版）
    def is_ir_pdf(link: str) -> bool:
        lowered = link.lower()
        return (
            lowered.endswith('.pdf') and (
                'ir' in lowered or
                'investor' in lowered or
                'finance' in lowered or
                'report' in lowered or
                'settlement' in lowered or
                'yuuka' in lowered or
                'kessan' in lowered or
                'earnings' in lowered or
                'financial' in lowered or
                'disclosure' in lowered
            )
        )

    try:
        from serpapi.google_search import GoogleSearch
    except ImportError:
        try:
            from serpapi import GoogleSearch
        except ImportError as e:
            error_msg = str(e)[:100]
            _debug("ImportError GoogleSearch: " + error_msg)
            return None
    
    # 段階的検索実行
    for i, q in enumerate(all_queries):
        params = {
            "q": q,
            "location": "Japan",
            "hl": "ja",
            "gl": "jp",
            "num": 15,  # 検索結果数を増加
            "api_key": api_key,
        }
        try:
            _debug(f"IR pdf search query {i+1}/{len(all_queries)}='{str(q)}'")
            results = GoogleSearch(params).get_dict()
        except Exception as e:
            error_msg = str(e)[:100]
            _debug("IR pdf search error: " + error_msg)
            continue

        # 結果を優先度付きで評価
        pdf_candidates = []
        for result in results.get("organic_results", []):
            link = result.get("link", "")
            title = result.get("title", "")
            
            if is_ir_pdf(link):
                # PDF の関連度スコアリング
                score = 0
                if company_name.replace("株式会社", "") in title:
                    score += 10
                if any(kw in title.lower() for kw in ["決算", "ir", "investor", "financial"]):
                    score += 5
                if "2024" in title or "2023" in title:
                    score += 3
                
                pdf_candidates.append((link, score, title))
        
        # スコア順にソートして最適なPDFを選択
        if pdf_candidates:
            pdf_candidates.sort(key=lambda x: x[1], reverse=True)
            best_pdf = pdf_candidates[0][0]
            best_title = pdf_candidates[0][2]
            _debug(f"Found IR PDF (score: {pdf_candidates[0][1]}): {best_title[:50]} -> {str(best_pdf)}")
            return best_pdf

    _debug("No IR PDF found after enhanced queries")
    return None


def extract_industry_keyword(job_info: str) -> str:
    """
    求人情報から業界キーワードをLLMで判定
    
    Args:
        job_info: 求人情報テキスト
    
    Returns:
        業界キーワード
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        _debug("OpenAI key missing; fallback to keyword matching")
        return _extract_industry_keyword_fallback(job_info)
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        prompt = f"""以下の求人情報から、該当する業界を1つだけ選んで業界名のみを回答してください。
選択肢以外の回答は絶対にしないでください。

【選択肢】
- 防衛産業
- 自動車産業
- 製薬産業
- 金融業界
- IT業界
- 製造業
- 不動産業界
- 小売業界
- エネルギー業界
- 食品業界
- 物流業界
- 建設業界
- メディア業界
- その他

【求人情報】
{job_info[:800]}

【回答形式】業界名のみ(例: 自動車産業)"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.3
        )
        industry = response.choices[0].message.content.strip()
        _debug("LLM industry classification: " + str(industry))
        return industry if industry else "市場動向"
        
    except Exception as e:
        error_msg = str(e)[:100]
        _debug("LLM industry classification failed: " + error_msg)
        return _extract_industry_keyword_fallback(job_info)


def _extract_industry_keyword_fallback(job_info: str) -> str:
    """LLM失敗時のフォールバック: キーワードマッチング"""
    industry_keywords = {
        "防衛産業": ["防衛", "レーダー", "ミサイル", "衛星", "航空宇宙"],
        "自動車産業": ["自動車", "EV", "ADAS", "電動化", "モビリティ"],
        "製薬産業": ["製薬", "医薬品", "創薬", "バイオ"],
        "金融業界": ["金融", "銀行", "保険", "フィンテック"],
        "IT業界": ["IT", "ソフトウェア", "システム開発", "SaaS"],
        "製造業": ["製造", "工場", "生産", "FA"],
    }
    
    for industry, keywords in industry_keywords.items():
        if any(kw in job_info for kw in keywords):
            return industry
    
    return "市場動向"


def search_general_info(query: str) -> str:
    """
    汎用ウェブ検索（IR資料が見つからない場合のフォールバック）
    
    Args:
        query: 検索クエリ（例: "企業名 会社概要 事業内容"）
    
    Returns:
        検索結果のスニペット集約テキスト
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        _debug("SerpAPI key missing; abort general search")
        return ""
    
    try:
        from serpapi.google_search import GoogleSearch
    except ImportError:
        try:
            from serpapi import GoogleSearch
        except ImportError as e:
            _debug(f"ImportError GoogleSearch: {str(e)[:100]}")
            return ""
    
    params = {
        "q": query,
        "location": "Japan",
        "hl": "ja",
        "gl": "jp",
        "num": 10,
        "api_key": api_key,
    }
    
    try:
        _debug(f"General web search query='{query}'")
        results = GoogleSearch(params).get_dict()
        organic = results.get("organic_results", [])
        _debug(f"General search results count: {len(organic)}")
        
        snippets = []
        for result in organic[:10]:
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            if snippet:
                snippets.append(f"【{title}】\n{snippet}\n出典: {link}")
        
        if not snippets:
            return ""
        
        return "\n\n".join(snippets)
        
    except Exception as e:
        _debug(f"General search error: {str(e)[:100]}")
        return ""
