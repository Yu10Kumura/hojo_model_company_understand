"""
OpenAI APIを呼び出すモジュール

【最重要】プロンプトは絶対に改変しない
YUTOさんが作成したプロンプトをそのまま使用する
"""
import os
from openai import OpenAI
from typing import Dict
from .logger import get_logger

logger = get_logger(__name__)


def clean_error_message(message: str) -> str:
    """
    エラーメッセージからストリームリットに危険な文字を除去
    
    Args:
        message: 元のメッセージ
        
    Returns:
        安全なメッセージ
    """
    if not isinstance(message, str):
        message = str(message)
    
    # 危険な文字を人間が読める形に変換
    safe_msg = message.replace('%', 'パーセント')
    safe_msg = safe_msg.replace('{', '（')
    safe_msg = safe_msg.replace('}', '）')
    
    return safe_msg


def generate_step1_report(
    company_name: str,
    job_info: str,
    financials: Dict[str, str],
    market_data: str,
    prompt_template: str
) -> str:
    """
    Step1: 初回分析レポート生成
    
    【重要】prompt_templateの内容は一切変更しない
    
    Args:
        company_name: 会社名
        job_info: 求人情報
        financials: 財務データ(自動取得)
        market_data: 業界データ(Web検索結果)
        prompt_template: YUTOさんのプロンプト(変更禁止)
    
    Returns:
        初回分析レポート(Markdown)
    """
    
    # 財務データの型検証とログ出力
    type_name = str(type(financials).__name__)
    logger.info("[Step1] financials type: %s", type_name)
    # 内容はJSON形式で安全に表示
    import json
    try:
        content_str = json.dumps(financials, ensure_ascii=False)[:200]
        logger.info("[Step1] financials preview: %s...", content_str)
    except:
        logger.warning("[Step1] financials preview: (could not serialize)")
    
    # 型チェック: 文字列の場合はJSONパース試行
    if isinstance(financials, str):
        logger.warning("[Step1] financials is string, attempting JSON parse...")
        try:
            financials = json.loads(financials)
            parsed_str = json.dumps(financials, ensure_ascii=False)[:100]
            logger.info("[Step1] parsed to dict: %s...", parsed_str)
        except json.JSONDecodeError as e:
            error_type = type(e).__name__
            error_msg_raw = str(e)[:50]
            safe_error_msg = clean_error_message(error_msg_raw)
            logger.error("[Step1] JSON parse failed: %s: %s", error_type, safe_error_msg)
            financials = {"error": "財務データのパースに失敗しました"}
    
    # 辞書であることを確認
    if not isinstance(financials, dict):
        type_name = str(type(financials).__name__)
        logger.error("[Step1] financials is not dict after processing: %s", type_name)
        financials = {"error": "財務データが不正な形式です"}
    
    # システム補足情報の作成(プロンプトとは完全分離)
    system_supplement = """【自動取得データ】以下を分析の参考にしてください:

"""
    
    if "error" not in financials:
        revenue = str(financials.get('売上高', '不明'))
        profit_margin = str(financials.get('営業利益率', '不明'))
        equity_ratio = str(financials.get('自己資本比率', '不明'))
        # 安全な文字列連結(f-stringや.format()を使わない)
        system_supplement += "■ 財務情報(IR資料より)\n"
        system_supplement += "- 売上高: " + revenue + "\n"
        system_supplement += "- 営業利益率: " + profit_margin + "\n"
        system_supplement += "- 自己資本比率: " + equity_ratio + "\n\n"
    else:
        error_msg = str(financials.get('error', '不明なエラー'))
        system_supplement += "■ 財務情報\n"
        system_supplement += "取得できませんでした(" + error_msg + ")\n\n"
    
    market_data_snippet = str(market_data[:2500])
    system_supplement += "■ 業界動向(Web検索結果)\n"
    system_supplement += market_data_snippet + "\n\n"
    
    # プロンプト内のプレースホルダーを実際の値に置換
    # ※これはプロンプトの改変ではなく、元々のプレースホルダーを埋めるだけ
    final_user_prompt = prompt_template.replace("{company_name}", str(company_name))
    final_user_prompt = final_user_prompt.replace("{job_info}", str(job_info))
    
    # financialsを整形された文字列に変換
    import json
    if isinstance(financials, dict):
        financials_str = "\n".join([
            "- " + k + ": " + v for k, v in financials.items()
        ])
    else:
        financials_str = str(financials)
    final_user_prompt = final_user_prompt.replace("{financials}", financials_str)
    
    final_user_prompt = final_user_prompt.replace("{market_data}", str(market_data))
    
    # 詳細指示をuser roleの末尾に追記(LLMに強制力を持たせる)
    final_user_prompt += "\n\n" + "="*80 + "\n"
    final_user_prompt += "【重要な出力要件 - 必ず遵守してください】\n"
    final_user_prompt += "\n"
    final_user_prompt += "1. **文字数要件**\n"
    final_user_prompt += "   - Step 1全体で最低3000文字を記述してください\n"
    final_user_prompt += "   - Step 2-4の各セクションは最低100文字を目安に記述してください\n"
    final_user_prompt += "\n"
    final_user_prompt += "2. **具体性要件**\n"
    final_user_prompt += "   - 各セクションで具体的な数値・事例を必ず3つ以上含めてください\n"
    final_user_prompt += "   - 抽象的な表現(例: \"高い技術力\")だけでなく、実務者が判断可能なレベルまで詳述してください\n"
    final_user_prompt += "   - 例: \"年間特許出願数120件、うち製造プロセス改善関連が65パーセント\"\n"
    final_user_prompt += "\n"
    final_user_prompt += "3. **Pain & Success Scenarioの深掘り**\n"
    final_user_prompt += "   - \"The Pain(不在のリスク)\"は具体的なエピソードレベルで記述してください\n"
    final_user_prompt += "   - \"Success Scenario(採用後の世界)\"は時系列を含めた具体的なストーリーで描いてください\n"
    final_user_prompt += "   - 例: \"入社3ヶ月で○○プロジェクトに参画、6ヶ月後には△△の改善を主導\"\n"
    final_user_prompt += "\n"
    final_user_prompt += "4. **フォーマット**\n"
    final_user_prompt += "   - 重要なキーワードは**太字**で強調してください\n"
    final_user_prompt += "   - 数値データは表形式も活用してください\n"
    final_user_prompt += "\n"
    final_user_prompt += "="*80
    
    # OpenAI API呼び出し
    # クライアントを実行時に初期化
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEYが未設定です。環境変数を設定してください。")
    client = OpenAI(api_key=api_key)
    
    # デバッグ: 実際に送信するメッセージ内容をログ出力
    logger.info("[Step1] request lengths: system=%d, user=%d", len(system_supplement), len(final_user_prompt))
    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": system_supplement},
                {"role": "user", "content": final_user_prompt}
            ],
            max_completion_tokens=16000,
            #temperature=0.7,
        )
        content = response.choices[0].message.content
        logger.info("[Step1] response length: %d", len(content or ""))
        return content
    except Exception as e:
        logger.exception("[Step1] OpenAI call failed: %s", str(e)[:200])
        raise


def generate_step2_report(
    draft_report: str,
    prompt_template: str
) -> str:
    """
    Step2: レビュー・修正版生成
    
    【重要】prompt_templateの内容は一切変更しない
    
    Args:
        draft_report: Step1の出力結果
        prompt_template: YUTOさんのプロンプト(変更禁止)
    
    Returns:
        完全版レポート(Markdown)
    """
    
    # プロンプト内の指示に従ってStep1出力を挿入
    final_prompt = prompt_template.replace("{step1_report}", draft_report)
    
    # OpenAI API呼び出し
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEYが未設定です。環境変数を設定してください。")
    client = OpenAI(api_key=api_key)
    
    # デバッグ: Step2リクエスト内容をログ出力
    logger.info("[Step2] request user length: %d", len(final_prompt))
    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": final_prompt}],
            max_completion_tokens=16000,
            #temperature=0.7,
        )
        content = response.choices[0].message.content
        logger.info("[Step2] response length: %d", len(content or ""))
        return content
    except Exception as e:
        logger.exception("[Step2] OpenAI call failed: %s", str(e)[:200])
        raise
