import logging
import os
from logging.handlers import RotatingFileHandler


def get_logger(name: str = "analysis", log_path: str = "logs/analysis.log") -> logging.Logger:
    """
    ローテーション付きのファイルロガーを返す。
    - ログは `logs/analysis.log` に出力（ローカル環境のみ）
    - 1MBでローテーション、バックアップ3世代
    - 既存ロガーがあれば再利用
    - Streamlit Cloud等の読み取り専用環境ではコンソールのみに出力
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # ファイルハンドラー（エラー時はスキップ）
    try:
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    except (OSError, PermissionError):
        # Streamlit Cloud等の読み取り専用環境ではファイル出力をスキップ
        pass

    # コンソールハンドラー（常に追加）
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    return logger
