#!/bin/bash

# プロジェクトIDと設定
PROJECT_ID="autosns-465900"
SERVICE_NAME="smartreview-firestore"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🔥 Firebase/Firestore連携版デプロイメントスクリプト"
echo "================================================"

# 1. Dockerイメージのビルド
echo "📦 Dockerイメージをビルド中..."
docker build -t ${IMAGE_NAME} .

# 2. コンテナレジストリにプッシュ
echo "⬆️  イメージをプッシュ中..."
docker push ${IMAGE_NAME}

# 3. Cloud Runにデプロイ（環境変数設定付き）
echo "🚀 Cloud Runにデプロイ中..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0 \
    --set-env-vars "BASE_URL=https://${SERVICE_NAME}-208894137644.${REGION}.run.app" \
    --set-env-vars "ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}" \
    --set-env-vars "OPENAI_API_KEY=${OPENAI_API_KEY}" \
    --set-env-vars "FIREBASE_PROJECT_ID=${PROJECT_ID}" \
    --service-account "smartreview-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# 4. サービスURLの取得と表示
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')

echo ""
echo "✅ デプロイ完了!"
echo "================================================"
echo "🌐 サービスURL: ${SERVICE_URL}"
echo "🔐 管理画面: ${SERVICE_URL}/admin/login"
echo "📱 QRコード生成: ${SERVICE_URL}/admin/dashboard"
echo ""
echo "📋 Firebase/Firestoreの特徴:"
echo "  - データの永続化"
echo "  - リアルタイムデータ同期"
echo "  - スケーラブルなNoSQLデータベース"
echo "  - 自動バックアップ"
echo ""
echo "⚙️  必要な設定:"
echo "  1. Firebaseプロジェクトでアプリを有効化"
echo "  2. サービスアカウントに適切な権限を付与"
echo "  3. 環境変数でOPENAI_API_KEYを設定（オプション）"