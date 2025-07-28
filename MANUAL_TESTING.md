# 手動動作確認ガイド

## 1. 準備

### データベースとサンプルデータの準備
```bash
# テーブル作成
python create_tables.py

# サンプルデータ挿入
python insert_sample_data.py
```

### サーバー起動
```bash
# 方法1: スクリプトで起動
python run_server.py

# 方法2: uvicornで直接起動
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 2. APIドキュメント確認

サーバー起動後、ブラウザでアクセス：
- **Swagger UI**: http://127.0.0.1:8000/api/v1/docs
- **ReDoc**: http://127.0.0.1:8000/api/v1/redoc

## 3. 基本的なテスト

### ヘルスチェック
```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health
```

### ユーザー登録
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/users/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com", 
    "password": "Test123!@#",
    "full_name": "Test User"
  }'
```

### ログイン
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "Test123!@#"
  }'
```

レスポンスから `access_token` を保存してください。

### 管理者ログイン（サンプルデータを挿入済みの場合）
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "Admin123!@#"
  }'
```

### 認証が必要なAPIのテスト
```bash
# 現在のユーザー情報取得
curl -X GET "http://127.0.0.1:8000/api/v1/users/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# ユーザー一覧取得（管理者権限）
curl -X GET "http://127.0.0.1:8000/api/v1/users/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 4. 自動テストスクリプト

統合的なテストを実行：
```bash
python manual_test.py
```

このスクリプトは以下をテストします：
- ヘルスチェック
- ユーザー登録
- ログイン
- 保護されたエンドポイント
- トークンリフレッシュ

## 5. サンプルデータ

挿入されるサンプルデータ：

### カテゴリー
- `01` - システム操作
- `02` - 業務プロセス  
- `03` - 技術情報

### 記事
- `SYS001` - システムログイン方法
- `BIZ001` - 申請プロセスの流れ
- `TECH001` - APIの使用方法

### ユーザー
- `admin` / `Admin123!@#` - 管理者権限

## 6. トラブルシューティング

### サーバーが起動しない場合
1. `.env` ファイルが存在することを確認
2. 必要なパッケージがインストールされていることを確認：
   ```bash
   pip install -r requirements.txt
   ```

### データベースエラーの場合
1. テーブルが作成されていることを確認：
   ```bash
   python create_tables.py
   ```

### 認証エラーの場合
1. 正しいユーザー名・パスワードを使用していることを確認
2. トークンが正しく設定されていることを確認

## 7. 現在実装済みの機能

✅ **実装済み**
- ユーザー登録・認証
- JWT トークン認証
- ユーザー管理
- カテゴリー管理（基本機能）
- 記事参照サービス（基本機能）
- データベース設計
- キャッシュシステム（Redis + フォールバック）

🔄 **部分実装**
- 記事管理API
- カテゴリー管理API

❌ **未実装**
- 修正案管理・ワークフロー
- 承認プロセス
- 通知システム
- 外部システム連携（SWEET, CTStage）