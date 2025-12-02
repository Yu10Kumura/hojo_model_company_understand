"""
Streamlitメインアプリケーション

【重要】YUTOさんのプロンプトは一切改変しない
"""
import streamlit as st
import os
from datetime import datetime
from io import BytesIO
from dotenv import load_dotenv

# 自作モジュール
from modules.ir_extractor import get_financials_from_ir
from modules.serp_api import search_market_data, extract_industry_keyword
from modules.openai_api import generate_step1_report, generate_step2_report
from modules.prompt_loader import PROMPT_STEP1, PROMPT_STEP2
from modules.export import export_to_json, export_to_word, export_to_pdf
from modules.logger import get_logger

logger = get_logger(__name__)


def safe_streamlit_message(text: str) -> str:
    """
    Streamlitメッセージ関数で安全に表示するための簡素な処理
    ※ ir_extractorで既に危険な文字は置換済みのため、ここではシンプルなチェックのみ
    
    Args:
        text: 表示したい文字列
    
    Returns:
        安全な文字列
    """
    if not isinstance(text, str):
        text = str(text)
    
    # 念のため、残った危険な文字をシンプルに処理
    if '%' in text or '{' in text or '}' in text:
        # 残った危険文字を削除
        text = text.replace('%', '').replace('{', '').replace('}', '')
    
    return text

# 環境変数読み込み
load_dotenv()

# ページ設定
st.set_page_config(
    page_title="採用戦略分析ジェネレーター",
    page_icon="📊",
    layout="wide"
)


def main():
    """メイン関数"""
    st.title("📊 採用戦略分析ジェネレーター")
    st.markdown("---")

    # キー状態表示（安全なマスキング）
    def mask(v: str) -> str:
        if not v:
            return "未設定"
        return v[:4] + "****" + v[-4:]

    openai_key = os.getenv("OPENAI_API_KEY")
    serpapi_key = os.getenv("SERPAPI_KEY")
    with st.expander("🔐 環境変数ステータス", expanded=False):
        st.write("OpenAI API Key:", "✅" if openai_key else "❌", mask(openai_key or ""))
        st.write("SerpAPI Key:", "✅" if serpapi_key else "❌", mask(serpapi_key or ""))
        st.caption("キーはマスク表示。再設定した場合はアプリ再起動が必要です。")

    # セッション状態の初期化
    if "analysis_done" not in st.session_state:
        st.session_state.analysis_done = False
    if "final_report" not in st.session_state:
        st.session_state.final_report = ""
    if "company_name" not in st.session_state:
        st.session_state.company_name = ""
    if "job_info" not in st.session_state:
        st.session_state.job_info = ""

    # 入力フォーム
    with st.form("input_form", clear_on_submit=False):
        st.subheader("📝 入力情報")

        company_name = st.text_input(
            "会社名 *",
            value=st.session_state.get("company_name", ""),
            key="company_name_input",
            placeholder="例: 三菱電機",
            help="分析対象の会社名を入力してください"
        )

        job_info = st.text_area(
            "求人情報 *",
            value=st.session_state.get("job_info", ""),
            key="job_info_input", 
            height=300,
            placeholder="""職種: 
業務内容: 
必須スキル: 
歓迎スキル: 
勤務地: 
年収: 
その他: """,
            help="求人票の内容を貼り付けてください(最低50文字)"
        )

        submitted = st.form_submit_button("🚀 分析を開始する", type="primary")

    if submitted:
        # セッション状態を更新
        st.session_state.company_name = company_name
        st.session_state.job_info = job_info
        
        # バリデーション
        if not company_name or len(company_name) < 2:
            st.error("⚠️ 会社名を正しく入力してください")
            return

        if not job_info or len(job_info) < 50:
            st.error("⚠️ 求人情報が短すぎます(最低50文字)")
            return

        # キー未設定時の早期警告
        if not openai_key:
            st.error("❌ OPENAI_API_KEY が未設定です。`.env` に設定後、再起動してください。")
            return
        if not serpapi_key:
            st.warning("⚠️ SERPAPI_KEY 未設定: 業界/IR検索が利用できず一部精度が低下します。続行は可能です。")

        # 分析実行
        run_analysis(company_name, job_info)

    # 結果表示
    if st.session_state.analysis_done:
        display_results()


def run_analysis(company_name: str, job_info: str):
    """分析処理のメイン関数"""
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        # Step 0-1: 財務データ取得
        status_text.text("🔄 財務データ取得中(IR検索)...")
        progress_bar.progress(10)
        financials = get_financials_from_ir(company_name)

        if "error" in financials:
            # フォールバック戦略: 推定値使用
            if financials.get("use_estimation"):
                st.info("💡 子会社のため業界推定値を使用します")
                # 業界推定値を生成
                from modules.ir_extractor import generate_industry_estimation
                financials = generate_industry_estimation(company_name, job_info)
                st.success("✅ 財務データ（推定値）取得完了")
                with st.expander("📊 取得した財務データ（推定値）"):
                    st.json(financials)
                    st.caption("⚠️ この企業は子会社のため、業界平均に基づく推定値を使用しています")
            else:
                # 通常のエラー処理
                error_msg = str(financials.get('error', '不明なエラー'))
                safe_warning_text = safe_streamlit_message("⚠️ 財務データ取得失敗: " + error_msg)
                st.warning(safe_warning_text)
                st.info("💡 分析は継続しますが、財務情報は含まれません")
        else:
            st.success("✅ 財務データ取得完了")
            with st.expander("📊 取得した財務データ"):
                st.json(financials)

        # Step 0-2: 業界データ取得
        status_text.text("🔄 業界データ取得中(Web検索)...")
        progress_bar.progress(30)
        industry_keyword = extract_industry_keyword(job_info)
        market_data = search_market_data(industry_keyword)
        st.success("✅ 業界データ取得完了(キーワード: " + str(industry_keyword) + ")")

        # Step 1: 初回分析
        status_text.text("🔄 Step 1: 初回分析生成中...")
        progress_bar.progress(50)
        draft_report = generate_step1_report(
            company_name=company_name,
            job_info=job_info,
            financials=financials,
            market_data=market_data,
            prompt_template=PROMPT_STEP1
        )
        # デバッグ: Step1の出力長とプレビュー
        try:
            step1_len = len(draft_report or "")
        except Exception:
            step1_len = 0
        logger.info("[UI] Step1 length: %d (company=%s)", step1_len, company_name)
        st.caption(f"Step1出力サイズ: {step1_len} 文字")
        with st.expander("🧪 Step1 生出力プレビュー(デバッグ)", expanded=False):
            st.text((draft_report or "")[:1200])

        # 最低限のガード: 極端に短い場合はStep2へ送らず停止
        if step1_len < 300:
            st.error("⚠️ Step1の出力が想定より短い/空です。入力内容やAPIレスポンスを確認してください。")
            progress_bar.progress(65)
            return
        st.success("✅ Step 1 完了")
        progress_bar.progress(70)

        # Step 2: レビュー・修正
        status_text.text("🔄 Step 2: レビュー・修正中...")
        final_report = generate_step2_report(
            draft_report=draft_report,
            prompt_template=PROMPT_STEP2
        )

        # デバッグ: Step2の出力長とプレビュー
        try:
            step2_len = len(final_report or "")
        except Exception:
            step2_len = 0
        logger.info("[UI] Step2 length: %d (company=%s)", step2_len, company_name)
        st.caption(f"Step2出力サイズ: {step2_len} 文字")
        with st.expander("🧪 Step2 生出力プレビュー(デバッグ)", expanded=False):
            st.text((final_report or "")[:1200])

        progress_bar.progress(100)
        status_text.text("✅ 分析完了!")
        st.session_state.final_report = final_report
        st.session_state.company_name = company_name
        st.session_state.analysis_done = True
        st.success("🎉 分析が完了しました!")
        st.balloons()

    except Exception as e:
        error_msg = str(e)[:200]  # 最初200文字のみで安全化
        safe_error_msg = safe_streamlit_message("❌ エラーが発生しました: " + error_msg)
        st.error(safe_error_msg)
        st.session_state.analysis_done = False


def display_results():
    """結果表示(1画面完結)"""
    st.markdown("---")
    st.subheader("📄 分析結果")

    company_name = st.session_state.company_name
    final_report = st.session_state.final_report

    # ダウンロードボタン (PDF削除版)
    col1, col2 = st.columns(2)
    
    with col1:
        json_data = export_to_json(company_name, final_report)
        st.download_button(
            label="📥 JSON",
            data=json_data,
            file_name=f"{company_name}_分析_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json"
        )

    with col2:
        doc = export_to_word(company_name, final_report)
        bio = BytesIO()
        doc.save(bio)
        st.download_button(
            label="📄 Word",
            data=bio.getvalue(),
            file_name=f"{company_name}_分析_{datetime.now().strftime('%Y%m%d_%H%M')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    # PDF出力は日本語フォント配置が必要なため一時的に無効化
    # with col3:
    #     pdf_data = export_to_pdf(company_name, final_report)
    #     st.download_button(
    #         label="📕 PDF",
    #         data=pdf_data,
    #         file_name=f"{company_name}_分析_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
    #         mime="application/pdf"
    #     )

    st.markdown("---")
    st.markdown(final_report, unsafe_allow_html=False)
    st.markdown("---")

    if st.button("🔄 新しい分析を開始"):
        st.session_state.analysis_done = False
        st.rerun()


if __name__ == "__main__":
    main()
