# SmartReview AI - Firebase/Firestore連携版

## 概要
SmartReview AIのFirebase/Firestore連携版です。データの永続化とスケーラビリティを実現します。

## 主な機能
- ✅ **データ永続化**: Firestoreによる永続的なデータ保存
- ✅ **リアルタイム同期**: 複数インスタンス間でのデータ同期
- ✅ **スケーラビリティ**: 自動スケーリング対応
- ✅ **バックアップ**: 自動バックアップ機能
- ✅ **QRコード生成**: 各店舗用のQRコード自動生成
- ✅ **多言語対応**: 日本語、英語、中国語、韓国語
- ✅ **管理者ダッシュボード**: 店舗・レビュー管理

## アーキテクチャ

```
┌─────────────────┐
│   ユーザー       │
└────────┬────────┘
         │
    ┌────▼────┐
    │Cloud Run│
    └────┬────┘
         │
   ┌─────▼─────┐
   │ Firestore │
   └───────────┘
```

## セットアップ

### 1. 前提条件
- Google Cloud SDK インストール済み
- Docker インストール済み
- Google Cloudプロジェクト作成済み

### 2. 初期設定
```bash
# 権限設定
chmod +x setup_firebase.sh
chmod +x deploy_firestore.sh

# Firebase/Firestoreセットアップ
./setup_firebase.sh
```

### 3. 環境変数設定
```bash
# OpenAI API Key（オプション）
export OPENAI_API_KEY='your-openai-api-key'

# 管理者パスワード（オプション）
export ADMIN_PASSWORD='your-secure-password'
```

### 4. デプロイ
```bash
./deploy_firestore.sh
```

## データ構造

### Stores Collection
```json
{
  "store_id": "demo-store-001",
  "name": "Beauty Salon SAKURA",
  "description": "説明文",
  "address": "住所",
  "phone": "電話番号",
  "services": ["サービス1", "サービス2"],
  "created_at": "2024-01-01T00:00:00",
  "total_reviews": 10,
  "last_review_at": "2024-01-10T00:00:00"
}
```

### Reviews Collection
```json
{
  "review_id": "uuid",
  "store_id": "demo-store-001",
  "store_name": "Beauty Salon SAKURA",
  "product": "サービス名",
  "user_name": "ユーザー名",
  "content": "レビュー内容",
  "improvement_points": ["改善点1", "改善点2"],
  "language": "ja",
  "created_at": "2024-01-01T00:00:00",
  "rating": 5
}
```

## API エンドポイント

### 公開エンドポイント
- `GET /` - メインページ（店舗一覧）
- `GET /store/{store_id}` - 店舗別口コミ投稿ページ
- `POST /api/review` - レビュー生成API
- `GET /api/stores` - 店舗一覧API
- `GET /api/store/{store_id}` - 店舗詳細API

### 管理者エンドポイント
- `GET /admin/login` - 管理者ログインページ
- `POST /api/admin/login` - ログインAPI
- `GET /admin/dashboard` - ダッシュボード
- `GET /admin/store/{store_id}` - 店舗管理ページ
- `POST /api/admin/store` - 新規店舗作成API
- `GET /admin/logout` - ログアウト

## モニタリング

### Firestoreコンソール
```
https://console.firebase.google.com/project/autosns-465900/firestore
```

### Cloud Runコンソール
```
https://console.cloud.google.com/run?project=autosns-465900
```

## トラブルシューティング

### Firestore接続エラー
```bash
# サービスアカウントの権限確認
gcloud projects get-iam-policy autosns-465900 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:smartreview-sa@autosns-465900.iam.gserviceaccount.com"
```

### デプロイエラー
```bash
# ログ確認
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=smartreview-firestore" --limit 50
```

## コスト最適化

### Firestoreの料金
- 読み取り: $0.06 / 100,000ドキュメント
- 書き込み: $0.18 / 100,000ドキュメント
- ストレージ: $0.18 / GB

### 最適化のヒント
1. インデックスを適切に設定
2. 不要なフィールドを削除
3. バッチ処理を活用
4. キャッシュを有効化

## セキュリティ

### Firestoreセキュリティルール
現在はサーバーサイドアクセスのみ。必要に応じてセキュリティルールを設定：

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // 読み取りは全て許可
    match /{document=**} {
      allow read: if true;
      // 書き込みは認証済みユーザーのみ
      allow write: if request.auth != null;
    }
  }
}
```

## 今後の拡張

- [ ] ユーザー認証システム
- [ ] レビューの編集・削除機能
- [ ] 画像アップロード機能
- [ ] メール通知システム
- [ ] 分析ダッシュボード強化
- [ ] A/Bテスト機能