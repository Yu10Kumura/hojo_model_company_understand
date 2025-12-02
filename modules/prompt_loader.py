"""
プロンプトファイル読み込みモジュール

【重要】このモジュールはプロンプトを一切改変しない
YUTOさんが作成したプロンプトをそのまま読み込むだけ
"""
import os


def load_prompt(filename: str) -> str:
    """
    プロンプトファイルを読み込む
    
    Args:
        filename: ファイル名(例: "prompt_step1.txt")
    
    Returns:
        プロンプト文字列(1文字も変更していない)
    """
    # 現在のファイルのディレクトリから相対パスで解決
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    path = os.path.join(parent_dir, "prompts", filename)
    
    if not os.path.exists(path):
        raise FileNotFoundError(f"プロンプトファイルが見つかりません: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# 定数として読み込み
PROMPT_STEP1 = load_prompt("prompt_step1.txt")
PROMPT_STEP2 = load_prompt("prompt_step2.txt")
