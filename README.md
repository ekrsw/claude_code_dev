# Knowledge Revision Management System

既存ナレッジに対する修正案の提出、承認、管理を行うPython APIシステム

## 技術スタック

- Python 3.12+
- FastAPI 0.115.12
- PostgreSQL (asyncpg)
- Redis 3.0.504
- SQLAlchemy 2.0.40
- JWT認証

## セットアップ

### 1. 仮想環境の作成

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 3. 環境変数の設定

```bash
cp .env.example .env
# .envファイルを編集して適切な値を設定
```

### 4. データベースのセットアップ

PostgreSQLデータベースを作成し、.envファイルのDATABASE_URLを設定してください。

```bash
# データベースマイグレーションの実行
alembic upgrade head
```

### 5. Redisのセットアップ

Redisサーバーを起動し、.envファイルのREDIS_URLを設定してください。

### 6. アプリケーションの起動

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API ドキュメント

アプリケーション起動後、以下のURLでAPIドキュメントを確認できます：

- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

## テスト

```bash
# 全テストの実行
pytest

# カバレッジ付きでテスト実行
pytest --cov=app --cov-report=html
```

## プロジェクト構造

```
.
├── app/
│   ├── api/              # APIエンドポイント
│   ├── core/             # 設定、セキュリティ
│   ├── services/         # ビジネスロジック
│   ├── repositories/     # データアクセス層
│   ├── models/           # SQLAlchemyモデル
│   ├── schemas/          # Pydanticスキーマ
│   └── utils/            # ユーティリティ
├── alembic/              # DBマイグレーション
├── tests/                # テストコード
├── .env.example          # 環境変数サンプル
├── requirements.txt      # 依存関係
└── README.md            # このファイル
```

## ロール権限

- **一般ユーザー**: 修正案の作成・提出
- **スーパーバイザー (SV)**: 修正案の承認・編集
- **承認者**: 修正案の承認・却下・編集
- **管理者**: 全権限

## 主な機能

1. **ユーザー管理**
   - 登録・認証
   - プロファイル管理

2. **修正案管理**
   - 修正案の作成・編集
   - 差分表示
   - ワークフロー管理

3. **承認ワークフロー**
   - レビュー依頼
   - 承認・却下
   - 修正指示

## 開発ガイドライン

- コードフォーマット: Black
- リンティング: Ruff
- 型チェック: mypy
- テストカバレッジ: 80%以上

## ライセンス

[ライセンス情報を記載]