#!/bin/bash

# Firebase/Firestore セットアップスクリプト
PROJECT_ID="autosns-465900"
SERVICE_ACCOUNT_NAME="smartreview-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🔥 Firebase/Firestore セットアップ"
echo "=================================="

# 1. プロジェクトの設定
echo "📋 プロジェクトを設定中..."
gcloud config set project ${PROJECT_ID}

# 2. 必要なAPIの有効化
echo "🔧 必要なAPIを有効化中..."
gcloud services enable firestore.googleapis.com
gcloud services enable firebase.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# 3. Firestoreデータベースの作成（まだ作成されていない場合）
echo "💾 Firestoreデータベースを確認中..."
gcloud firestore databases create --region=us-central1 --type=firestore-native 2>/dev/null || echo "Firestoreは既に作成済みです"

# 4. サービスアカウントの作成（まだ存在しない場合）
echo "👤 サービスアカウントを設定中..."
gcloud iam service-accounts create ${SERVICE_ACCOUNT_NAME} \
    --display-name="SmartReview Service Account" 2>/dev/null || echo "サービスアカウントは既に存在します"

# 5. 必要な権限の付与
echo "🔐 権限を設定中..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/datastore.user"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/firebase.admin"

# 6. Cloud Run用の権限
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/run.invoker"

echo ""
echo "✅ セットアップ完了!"
echo "=================================="
echo ""
echo "📝 次のステップ:"
echo "  1. OPENAI_API_KEY環境変数を設定（オプション）:"
echo "     export OPENAI_API_KEY='your-api-key'"
echo ""
echo "  2. 管理者パスワードを設定（オプション）:"
echo "     export ADMIN_PASSWORD='your-secure-password'"
echo ""
echo "  3. デプロイスクリプトを実行:"
echo "     ./deploy_firestore.sh"
echo ""
echo "🔍 Firestore コンソール:"
echo "   https://console.firebase.google.com/project/${PROJECT_ID}/firestore"