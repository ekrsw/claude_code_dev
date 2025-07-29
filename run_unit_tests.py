#!/usr/bin/env python
"""
単体テスト実行スクリプト

カバレッジ測定付きで単体テストを実行します。
"""
import sys
import subprocess
import os


def run_unit_tests():
    """単体テストを実行"""
    print("=== 単体テスト実行開始 ===")
    
    # 現在のディレクトリを確認
    current_dir = os.getcwd()
    print(f"実行ディレクトリ: {current_dir}")
    
    # テストコマンドを構築
    test_commands = [
        # 単体テストのみ実行（カバレッジ付き）
        [
            "python", "-m", "pytest",
            "tests/unit/",
            "-v",
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-fail-under=80",
            "--tb=short"
        ],
        
        # 個別サービステスト（詳細出力）
        [
            "python", "-m", "pytest",
            "tests/unit/services/test_auth_service.py",
            "-v", "-s"
        ]
    ]
    
    success_count = 0
    
    for i, cmd in enumerate(test_commands, 1):
        print(f"\n--- テストコマンド {i}/{len(test_commands)} ---")
        print(f"実行コマンド: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分のタイムアウト
            )
            
            print("STDOUT:")
            print(result.stdout)
            
            if result.stderr:
                print("STDERR:")
                print(result.stderr)
            
            if result.returncode == 0:
                print(f"[OK] テストコマンド {i} 成功")
                success_count += 1
            else:
                print(f"[ERROR] テストコマンド {i} 失敗 (戻り値: {result.returncode})")
                
        except subprocess.TimeoutExpired:
            print(f"[TIMEOUT] テストコマンド {i} タイムアウト")
        except Exception as e:
            print(f"[ERROR] テストコマンド {i} 実行エラー: {e}")
    
    print(f"\n=== テスト実行完了 ===")
    print(f"成功: {success_count}/{len(test_commands)}")
    
    # カバレッジレポートの場所を表示
    html_report_path = os.path.join(current_dir, "htmlcov", "index.html")
    if os.path.exists(html_report_path):
        print(f"[REPORT] HTMLカバレッジレポート: {html_report_path}")
    
    return success_count == len(test_commands)


def check_prerequisites():
    """前提条件をチェック"""
    print("=== 前提条件チェック ===")
    
    # Pythonモジュールの存在確認
    required_modules = [
        "pytest",
        "pytest_asyncio",
        "pytest_cov",
        "httpx"
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module.replace('-', '_'))
            print(f"[OK] {module}: OK")
        except ImportError:
            print(f"[ERROR] {module}: 見つかりません")
            missing_modules.append(module)
    
    # テストディレクトリの存在確認
    test_dirs = [
        "tests/unit",
        "tests/unit/services"
    ]
    
    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            print(f"[OK] {test_dir}: OK")
        else:
            print(f"[ERROR] {test_dir}: 見つかりません")
    
    if missing_modules:
        print(f"\n[WARNING] 不足モジュール: {', '.join(missing_modules)}")
        print("以下のコマンドでインストールしてください:")
        print(f"pip install {' '.join(missing_modules)}")
        return False
    
    return True


def main():
    """メイン関数"""
    print("Task 3.1: 単体テストの実行")
    print("=" * 50)
    
    # 前提条件チェック
    if not check_prerequisites():
        print("[ERROR] 前提条件が満たされていません")
        return 1
    
    # 単体テスト実行
    if run_unit_tests():
        print("[SUCCESS] すべてのテストが成功しました！")
        return 0
    else:
        print("[ERROR] 一部のテストが失敗しました")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)