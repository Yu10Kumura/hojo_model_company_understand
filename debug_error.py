#!/usr/bin/env python3
"""
財務データエラーの真因を特定するためのテストスクリプト
"""
import sys
sys.path.insert(0, '.')

try:
    from modules.ir_extractor import get_financials_from_ir
    
    # テスト実行
    print("=== 財務データ取得テスト開始 ===")
    company_name = "ホンダ"
    
    print(f"テスト対象: {company_name}")
    result = get_financials_from_ir(company_name)
    
    print("\n=== 結果の詳細分析 ===")
    print(f"result type: {type(result)}")
    print(f"result repr: {repr(result)}")
    
    if isinstance(result, dict):
        print(f"keys: {list(result.keys())}")
        
        if 'error' in result:
            error_val = result['error']
            print(f"\nerror value type: {type(error_val)}")
            print(f"error value repr: {repr(error_val)}")
            print(f"error value str(): {str(error_val)}")
            print(f"error value contains open brace: {'{' in str(error_val)}")
            print(f"error value contains close brace: {'}' in str(error_val)}")
            
            # 問題となる文字列結合をテスト
            try:
                warning_text = "⚠️ 財務データ取得失敗: " + str(error_val)
                print(f"\n✅ 安全な文字列結合成功: {repr(warning_text)}")
            except Exception as e:
                print(f"\n❌ 文字列結合でエラー: {e}")
            
            # f-stringテストも実行
            try:
                dangerous_text = f"⚠️ 財務データ取得失敗: {error_val}"
                print(f"\n✅ f-string成功: {repr(dangerous_text)}")
            except Exception as e:
                print(f"\n❌ f-stringでエラー: {e}")
                print(f"エラー詳細: {repr(e)}")
    
    print("\n=== テスト完了 ===")
    
except Exception as e:
    print(f"❌ テスト実行エラー: {e}")
    import traceback
    traceback.print_exc()