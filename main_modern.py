from fastapi import FastAPI, HTTPException, Request, Cookie, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import os
import openai
from dotenv import load_dotenv
import json
import uuid
import qrcode
import io
import base64
from PIL import Image
import secrets

# 環境変数読み込み
load_dotenv()

app = FastAPI(
    title="SmartReview AI",
    description="AI口コミ生成システム - モダンUI版",
    version="6.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 管理者セッション管理
ADMIN_SESSIONS = {}
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# メモリ内データベース
STORES = {
    "demo-store-001": {
        "store_id": "demo-store-001",
        "qr_code": "QR001",
        "name": "Beauty Salon SAKURA",
        "description": "最新の美容機器を完備した完全個室プライベートサロン",
        "address": "東京都渋谷区表参道1-2-3",
        "phone": "03-1234-5678",
        "services": ["ハイフ", "リフトアップ", "フェイシャル", "ボディケア", "脱毛"],
        "created_at": "2024-01-01T00:00:00"
    },
    "demo-store-002": {
        "store_id": "demo-store-002", 
        "qr_code": "QR002",
        "name": "Healing Spa MIYABI",
        "description": "都会の喧騒を忘れる癒しの空間",
        "address": "東京都港区南青山3-4-5",
        "phone": "03-9876-5432",
        "services": ["アロマトリートメント", "ホットストーン", "リフレクソロジー"],
        "created_at": "2024-01-01T00:00:00"
    },
    "demo-store-003": {
        "store_id": "demo-store-003",
        "qr_code": "QR003",
        "name": "Medical Beauty Clinic AZURE",
        "description": "医療レベルの美容施術を提供",
        "address": "東京都新宿区西新宿5-6-7",
        "phone": "03-5555-7777",
        "services": ["医療脱毛", "ボトックス", "ヒアルロン酸注入", "レーザー治療"],
        "created_at": "2024-01-01T00:00:00"
    }
}

REVIEWS = []
FEEDBACKS = []

# Pydanticモデル
class ReviewRequest(BaseModel):
    store_id: str
    rating: int
    services: List[str]
    user_comment: Optional[str] = ""
    language: str = "ja"

class FeedbackRequest(BaseModel):
    store_id: str
    rating: int
    services: List[str]
    comment: str
    improvement_areas: Optional[List[str]] = []

class StoreCreate(BaseModel):
    name: str
    description: str
    address: str
    phone: str
    services: List[str]

# QRコード生成
def generate_qr_code(store_id: str) -> str:
    base_url = os.getenv("BASE_URL", "https://smartreview-simple-208894137644.us-central1.run.app")
    url = f"{base_url}/store/{store_id}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

# HTMLインターフェース（モダンUI）
HTML_INTERFACE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartReview AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Noto Sans JP', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f8f9fa;
            min-height: 100vh;
        }
        
        /* ヘッダー */
        .header {
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            position: sticky;
            top: 0;
            z-index: 1000;
        }
        
        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            color: #1a1a1a;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .logo-icon {
            font-size: 1.8rem;
        }
        
        /* ナビゲーション */
        .nav-tabs {
            display: flex;
            gap: 0.5rem;
        }
        
        .nav-tab {
            padding: 0.75rem 1.5rem;
            background: transparent;
            border: none;
            color: #6c757d;
            font-size: 0.95rem;
            font-weight: 500;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        
        .nav-tab:hover {
            background: #f1f3f5;
        }
        
        .nav-tab.active {
            background: #6366f1;
            color: white;
        }
        
        /* 言語切替 */
        .lang-switcher {
            display: flex;
            gap: 0.25rem;
            background: #f1f3f5;
            padding: 0.25rem;
            border-radius: 8px;
        }
        
        .lang-btn {
            padding: 0.5rem 1rem;
            background: transparent;
            border: none;
            color: #6c757d;
            font-size: 0.875rem;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.2s;
        }
        
        .lang-btn:hover {
            background: white;
        }
        
        .lang-btn.active {
            background: white;
            color: #6366f1;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        /* メインコンテンツ */
        .main-content {
            max-width: 1400px;
            margin: 2rem auto;
            padding: 0 2rem;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
            animation: fadeIn 0.3s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        /* カード */
        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            padding: 2rem;
            margin-bottom: 2rem;
        }
        
        .card-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 1.5rem;
        }
        
        /* 店舗グリッド */
        .stores-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 1.5rem;
        }
        
        .store-card {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
            cursor: pointer;
        }
        
        .store-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.12);
        }
        
        .store-header {
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            color: white;
            padding: 1.5rem;
        }
        
        .store-name {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        
        .store-address {
            font-size: 0.875rem;
            opacity: 0.9;
        }
        
        .store-body {
            padding: 1.5rem;
        }
        
        .qr-container {
            display: flex;
            justify-content: center;
            margin: 1rem 0;
        }
        
        .qr-code {
            width: 150px;
            height: 150px;
            padding: 10px;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
        }
        
        /* ボタン */
        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }
        
        .btn-primary {
            background: #6366f1;
            color: white;
        }
        
        .btn-primary:hover {
            background: #5558e3;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }
        
        .btn-secondary {
            background: #f1f3f5;
            color: #495057;
        }
        
        .btn-secondary:hover {
            background: #e9ecef;
        }
        
        .btn-block {
            width: 100%;
        }
        
        /* フォーム要素 */
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        .form-label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
            color: #495057;
            font-size: 0.95rem;
        }
        
        .form-control {
            width: 100%;
            padding: 0.75rem 1rem;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            font-size: 0.95rem;
            transition: all 0.2s;
        }
        
        .form-control:focus {
            outline: none;
            border-color: #6366f1;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        
        textarea.form-control {
            resize: vertical;
            min-height: 100px;
            font-family: inherit;
        }
        
        /* 星評価 */
        .star-rating {
            display: flex;
            gap: 0.5rem;
            justify-content: center;
            font-size: 2.5rem;
            margin: 1rem 0;
        }
        
        .star {
            cursor: pointer;
            color: #e9ecef;
            transition: all 0.2s;
        }
        
        .star:hover {
            color: #fbbf24;
            transform: scale(1.1);
        }
        
        .star.active {
            color: #fbbf24;
            animation: pulse 0.3s ease;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.2); }
            100% { transform: scale(1); }
        }
        
        .rating-text {
            text-align: center;
            color: #6c757d;
            margin-top: 0.5rem;
            font-size: 0.95rem;
        }
        
        /* サービスチップ */
        .services-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
        }
        
        .service-chip {
            padding: 0.5rem 1rem;
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 20px;
            color: #495057;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .service-chip:hover {
            border-color: #6366f1;
            background: #f8f9ff;
        }
        
        .service-chip.selected {
            background: #6366f1;
            color: white;
            border-color: #6366f1;
        }
        
        /* 統計カード */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border-left: 4px solid #6366f1;
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: #1a1a1a;
            margin-bottom: 0.5rem;
        }
        
        .stat-label {
            color: #6c757d;
            font-size: 0.875rem;
        }
        
        /* QRスキャナー */
        .scanner-container {
            max-width: 500px;
            margin: 0 auto;
            text-align: center;
        }
        
        #qr-reader {
            border-radius: 12px;
            overflow: hidden;
            margin: 1rem 0;
        }
        
        /* レビュー結果 */
        .review-result {
            background: #f8f9ff;
            border: 1px solid #e8e9ff;
            border-radius: 12px;
            padding: 1.5rem;
            margin-top: 1.5rem;
        }
        
        .review-text {
            color: #495057;
            line-height: 1.8;
            margin-bottom: 1rem;
        }
        
        /* レスポンシブ */
        @media (max-width: 768px) {
            .header-content {
                flex-direction: column;
                gap: 1rem;
                padding: 1rem;
            }
            
            .nav-tabs {
                width: 100%;
                justify-content: center;
                flex-wrap: wrap;
            }
            
            .nav-tab {
                padding: 0.5rem 1rem;
                font-size: 0.875rem;
            }
            
            .stores-grid {
                grid-template-columns: 1fr;
            }
            
            .main-content {
                padding: 0 1rem;
            }
            
            .lang-switcher {
                justify-content: center;
            }
        }
        
        /* ローディング */
        .loading {
            display: none;
            text-align: center;
            padding: 2rem;
        }
        
        .loading.show {
            display: block;
        }
        
        .spinner {
            display: inline-block;
            width: 50px;
            height: 50px;
            border: 3px solid #f3f4f6;
            border-top-color: #6366f1;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
</head>
<body>
    <!-- ヘッダー -->
    <header class="header">
        <div class="header-content">
            <div class="logo">
                <span class="logo-icon">✨</span>
                <span>SmartReview AI</span>
            </div>
            
            <nav class="nav-tabs">
                <button class="nav-tab active" onclick="showTab('stores')">店舗一覧</button>
                <button class="nav-tab" onclick="showTab('qr-scan')">QRスキャン</button>
                <button class="nav-tab" onclick="showTab('review')">レビュー作成</button>
                <button class="nav-tab" onclick="showTab('analytics')">分析</button>
                <button class="nav-tab" onclick="window.location.href='/admin'">管理者</button>
            </nav>
            
            <div class="lang-switcher">
                <button class="lang-btn active" data-lang="ja" onclick="setLanguage('ja')">日本語</button>
                <button class="lang-btn" data-lang="en" onclick="setLanguage('en')">EN</button>
                <button class="lang-btn" data-lang="zh" onclick="setLanguage('zh')">中文</button>
                <button class="lang-btn" data-lang="ko" onclick="setLanguage('ko')">한국어</button>
            </div>
        </div>
    </header>
    
    <!-- メインコンテンツ -->
    <main class="main-content">
        <!-- 店舗一覧タブ -->
        <div id="stores-tab" class="tab-content active">
            <div class="card">
                <h2 class="card-title">登録店舗一覧</h2>
                <div class="stores-grid" id="storesGrid"></div>
            </div>
        </div>
        
        <!-- QRスキャンタブ -->
        <div id="qr-scan-tab" class="tab-content">
            <div class="card">
                <h2 class="card-title">QRコードスキャン</h2>
                <div class="scanner-container">
                    <p style="color: #6c757d; margin-bottom: 1rem;">カメラで店舗のQRコードをスキャンしてください</p>
                    <div id="qr-reader"></div>
                    <div id="scanResult" style="margin-top: 1rem;"></div>
                </div>
            </div>
        </div>
        
        <!-- レビュー作成タブ -->
        <div id="review-tab" class="tab-content">
            <div class="card">
                <h2 class="card-title">レビュー作成</h2>
                
                <div id="selectedStore" style="margin-bottom: 2rem;"></div>
                
                <div class="form-group">
                    <label class="form-label" id="ratingLabel">評価を選択してください</label>
                    <div class="star-rating">
                        <span class="star" data-rating="1">★</span>
                        <span class="star" data-rating="2">★</span>
                        <span class="star" data-rating="3">★</span>
                        <span class="star" data-rating="4">★</span>
                        <span class="star" data-rating="5">★</span>
                    </div>
                    <div class="rating-text" id="ratingText">評価を選択してください</div>
                </div>
                
                <div class="form-group">
                    <label class="form-label" id="serviceLabel">ご利用されたサービス</label>
                    <div class="services-grid" id="servicesGrid"></div>
                </div>
                
                <div class="form-group">
                    <label class="form-label" id="commentLabel">コメント（任意）</label>
                    <textarea class="form-control" id="userComment" placeholder="ご感想をお聞かせください..."></textarea>
                </div>
                
                <button class="btn btn-primary btn-block" id="generateBtn" onclick="generateReview()">
                    AI口コミを生成
                </button>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p style="margin-top: 1rem; color: #6c757d;" id="loadingText">AI生成中...</p>
                </div>
                
                <div id="reviewResult"></div>
            </div>
        </div>
        
        <!-- 分析タブ -->
        <div id="analytics-tab" class="tab-content">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="totalStores">0</div>
                    <div class="stat-label">登録店舗数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="totalReviews">0</div>
                    <div class="stat-label">総レビュー数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="avgRating">0.0</div>
                    <div class="stat-label">平均評価</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="totalFeedbacks">0</div>
                    <div class="stat-label">フィードバック数</div>
                </div>
            </div>
            
            <div class="card">
                <h2 class="card-title">最近のレビュー</h2>
                <div id="recentReviews"></div>
            </div>
        </div>
    </main>
    
    <script>
        let selectedStore = null;
        let selectedRating = 0;
        let selectedServices = [];
        let currentLanguage = 'ja';
        let html5QrCode = null;
        
        // 多言語対応テキスト
        const translations = {
            ja: {
                // ナビゲーション
                nav_stores: '店舗一覧',
                nav_qrscan: 'QRスキャン',
                nav_review: 'レビュー作成',
                nav_analytics: '分析',
                nav_admin: '管理者',
                // ページタイトル
                stores_title: '登録店舗一覧',
                qrscan_title: 'QRコードスキャン',
                review_title: 'レビュー作成',
                analytics_title: '統計情報',
                select_store_btn: 'この店舗を選択',
                start_scan_btn: 'スキャン開始',
                stop_scan_btn: 'スキャン停止',
                // フォームラベル
                ratingLabel: '評価を選択してください',
                serviceLabel: 'ご利用されたサービス',
                commentLabel: 'コメント（任意）',
                commentPlaceholder: 'ご感想をお聞かせください...',
                generateBtn: 'AI口コミを生成',
                loadingText: 'AI生成中...',
                selectRating: '評価を選択してください',
                ratingTexts: [
                    '改善が必要',
                    'やや不満',
                    '普通',
                    '満足',
                    '大変満足'
                ],
                // エラーメッセージ
                storeNotSelected: '店舗を選択してください',
                ratingNotSelected: '評価を選択してください',
                reviewGenerated: 'AI口コミが生成されました！',
                error: 'エラーが発生しました',
                // 統計ラベル
                total_stores: '登録店舗数',
                total_reviews: '総レビュー数',
                avg_rating: '平均評価',
                total_feedbacks: 'フィードバック数',
                recent_reviews: '最近のレビュー'
            },
            en: {
                // Navigation
                nav_stores: 'Store List',
                nav_qrscan: 'QR Scan',
                nav_review: 'Create Review',
                nav_analytics: 'Analytics',
                nav_admin: 'Admin',
                // Page titles
                stores_title: 'Registered Stores',
                qrscan_title: 'QR Code Scanner',
                review_title: 'Create Review',
                analytics_title: 'Statistics',
                select_store_btn: 'Select This Store',
                start_scan_btn: 'Start Scan',
                stop_scan_btn: 'Stop Scan',
                // Form labels
                ratingLabel: 'Please select a rating',
                serviceLabel: 'Service used',
                commentLabel: 'Comment (optional)',
                commentPlaceholder: 'Please share your thoughts...',
                generateBtn: 'Generate AI Review',
                loadingText: 'Generating AI review...',
                selectRating: 'Please select a rating',
                ratingTexts: [
                    'Needs improvement',
                    'Somewhat dissatisfied',
                    'Average',
                    'Satisfied',
                    'Very satisfied'
                ],
                // Error messages
                storeNotSelected: 'Please select a store',
                ratingNotSelected: 'Please select a rating',
                reviewGenerated: 'AI review generated!',
                error: 'An error occurred',
                // Statistics labels
                total_stores: 'Total Stores',
                total_reviews: 'Total Reviews',
                avg_rating: 'Average Rating',
                total_feedbacks: 'Total Feedbacks',
                recent_reviews: 'Recent Reviews'
            },
            zh: {
                // 导航
                nav_stores: '店铺列表',
                nav_qrscan: 'QR扫描',
                nav_review: '创建评价',
                nav_analytics: '统计',
                nav_admin: '管理员',
                // 页面标题
                stores_title: '注册店铺',
                qrscan_title: 'QR码扫描器',
                review_title: '创建评价',
                analytics_title: '统计信息',
                select_store_btn: '选择此店铺',
                start_scan_btn: '开始扫描',
                stop_scan_btn: '停止扫描',
                // 表单标签
                ratingLabel: '请选择评分',
                serviceLabel: '使用的服务',
                commentLabel: '评论（可选）',
                commentPlaceholder: '请分享您的想法...',
                generateBtn: '生成AI评价',
                loadingText: '正在生成AI评价...',
                selectRating: '请选择评分',
                ratingTexts: [
                    '需要改进',
                    '有点不满意',
                    '一般',
                    '满意',
                    '非常满意'
                ],
                // 错误消息
                storeNotSelected: '请选择店铺',
                ratingNotSelected: '请选择评分',
                reviewGenerated: 'AI评价生成成功！',
                error: '发生错误',
                // 统计标签
                total_stores: '店铺总数',
                total_reviews: '评价总数',
                avg_rating: '平均评分',
                total_feedbacks: '反馈总数',
                recent_reviews: '最近评价'
            },
            ko: {
                // 네비게이션
                nav_stores: '매장 목록',
                nav_qrscan: 'QR 스캔',
                nav_review: '리뷰 작성',
                nav_analytics: '통계',
                nav_admin: '관리자',
                // 페이지 타이틀
                stores_title: '등록된 매장',
                qrscan_title: 'QR 코드 스캐너',
                review_title: '리뷰 작성',
                analytics_title: '통계 정보',
                select_store_btn: '이 매장 선택',
                start_scan_btn: '스캔 시작',
                stop_scan_btn: '스캔 중지',
                // 폼 라벨
                ratingLabel: '평가를 선택해주세요',
                serviceLabel: '이용하신 서비스',
                commentLabel: '코멘트 (선택사항)',
                commentPlaceholder: '의견을 공유해주세요...',
                generateBtn: 'AI 리뷰 생성',
                loadingText: 'AI 리뷰 생성 중...',
                selectRating: '평가를 선택해주세요',
                ratingTexts: [
                    '개선 필요',
                    '약간 불만족',
                    '보통',
                    '만족',
                    '매우 만족'
                ],
                // 에러 메시지
                storeNotSelected: '매장을 선택해주세요',
                ratingNotSelected: '평가를 선택해주세요',
                reviewGenerated: 'AI 리뷰가 생성되었습니다!',
                error: '오류가 발생했습니다',
                // 통계 라벨
                total_stores: '매장 수',
                total_reviews: '총 리뷰 수',
                avg_rating: '평균 평가',
                total_feedbacks: '총 피드백 수',
                recent_reviews: '최근 리뷰'
            }
        };
        
        // ナビゲーションテキストを更新
        function updateNavigationText(lang) {
            const t = translations[lang];
            const navButtons = document.querySelectorAll('.nav-tab');
            if (navButtons[0]) navButtons[0].textContent = t.nav_stores;
            if (navButtons[1]) navButtons[1].textContent = t.nav_qrscan;
            if (navButtons[2]) navButtons[2].textContent = t.nav_review;
            if (navButtons[3]) navButtons[3].textContent = t.nav_analytics;
            if (navButtons[4]) navButtons[4].textContent = t.nav_admin;
        }
        
        // すべてのページテキストを更新
        function updateAllTexts(lang) {
            const t = translations[lang];
            
            // カードタイトルを更新
            const cardTitles = document.querySelectorAll('.card-title');
            cardTitles.forEach((title, index) => {
                const titleText = title.textContent;
                if (titleText.includes('店舗') || titleText.includes('Store') || titleText.includes('店铺') || titleText.includes('매장')) {
                    title.textContent = t.stores_title;
                } else if (titleText.includes('QR') || titleText.includes('스캔')) {
                    title.textContent = t.qrscan_title;
                } else if (titleText.includes('レビュー') || titleText.includes('Review') || titleText.includes('评价') || titleText.includes('리뷰')) {
                    title.textContent = t.review_title;
                } else if (titleText.includes('統計') || titleText.includes('Analytics') || titleText.includes('统计') || titleText.includes('통계')) {
                    title.textContent = t.analytics_title;
                }
            });
            
            // ボタンテキストを更新
            const storeButtons = document.querySelectorAll('.store-card button');
            storeButtons.forEach(btn => {
                btn.textContent = t.select_store_btn;
            });
            
            // 統計ラベルを更新
            const statLabels = document.querySelectorAll('.stat-label');
            if (statLabels[0]) statLabels[0].textContent = t.total_stores;
            if (statLabels[1]) statLabels[1].textContent = t.total_reviews;
            if (statLabels[2]) statLabels[2].textContent = t.avg_rating;
            if (statLabels[3]) statLabels[3].textContent = t.total_feedbacks;
            
            // 最近のレビューのタイトルを更新
            const recentReviewsTitle = document.querySelector('#analytics-tab .card:last-child .card-title');
            if (recentReviewsTitle) {
                recentReviewsTitle.textContent = t.recent_reviews;
            }
        }
        
        // 言語設定
        function setLanguage(lang) {
            currentLanguage = lang;
            
            // 右上の言語ボタンのアクティブ状態を更新
            document.querySelectorAll('.lang-btn').forEach(btn => {
                btn.classList.remove('active');
                if (btn.dataset.lang === lang) {
                    btn.classList.add('active');
                }
            });
            
            // テキストを更新
            const t = translations[lang];
            
            // ナビゲーションタブのテキストを更新
            updateNavigationText(lang);
            
            // レビューフォームのテキストを更新
            if (document.getElementById('ratingLabel')) {
                document.getElementById('ratingLabel').textContent = t.ratingLabel;
            }
            if (document.getElementById('serviceLabel')) {
                document.getElementById('serviceLabel').textContent = t.serviceLabel;
            }
            if (document.getElementById('commentLabel')) {
                document.getElementById('commentLabel').textContent = t.commentLabel;
            }
            if (document.getElementById('userComment')) {
                document.getElementById('userComment').placeholder = t.commentPlaceholder;
            }
            if (document.getElementById('generateBtn')) {
                document.getElementById('generateBtn').textContent = t.generateBtn;
            }
            if (document.getElementById('loadingText')) {
                document.getElementById('loadingText').textContent = t.loadingText;
            }
            
            // 評価テキストを更新
            updateRatingText();
            
            // ページタイトルやその他のテキストも更新
            updateAllTexts(lang);
        }
        
        // 初期化
        async function init() {
            await loadStores();
            await loadAnalytics();
            setupStarRating();
        }
        
        // 店舗読み込み
        async function loadStores() {
            try {
                const response = await fetch('/api/v1/stores');
                const stores = await response.json();
                
                const grid = document.getElementById('storesGrid');
                grid.innerHTML = '';
                
                stores.forEach(store => {
                    const card = document.createElement('div');
                    card.className = 'store-card';
                    card.onclick = () => selectStore(store.store_id);
                    card.innerHTML = `
                        <div class="store-header">
                            <div class="store-name">${store.name}</div>
                            <div class="store-address">${store.address}</div>
                        </div>
                        <div class="store-body">
                            <div class="qr-container">
                                <img class="qr-code" src="/api/v1/stores/${store.store_id}/qr" alt="QR Code">
                            </div>
                            <button class="btn btn-primary btn-block" onclick="selectStore('${store.store_id}'); event.stopPropagation();">
                                この店舗を選択
                            </button>
                        </div>
                    `;
                    grid.appendChild(card);
                });
                
                document.getElementById('totalStores').textContent = stores.length;
            } catch (error) {
                console.error('Error loading stores:', error);
            }
        }
        
        // 分析データ読み込み
        async function loadAnalytics() {
            try {
                const response = await fetch('/api/v1/admin/analytics');
                const data = await response.json();
                
                document.getElementById('totalReviews').textContent = data.total_reviews;
                document.getElementById('avgRating').textContent = data.average_rating.toFixed(1);
                document.getElementById('totalFeedbacks').textContent = data.total_feedbacks;
                
                const reviewsContainer = document.getElementById('recentReviews');
                if (data.recent_reviews && data.recent_reviews.length > 0) {
                    reviewsContainer.innerHTML = data.recent_reviews.map(review => `
                        <div style="padding: 1rem; background: #f8f9fa; border-radius: 8px; margin-bottom: 1rem;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                                <div style="color: #fbbf24;">${'★'.repeat(review.rating)}</div>
                                <div style="font-size: 0.875rem; color: #6c757d;">
                                    ${new Date(review.created_at).toLocaleDateString('ja-JP')}
                                </div>
                            </div>
                            <div style="color: #495057; line-height: 1.6;">
                                ${review.generated_text}
                            </div>
                        </div>
                    `).join('');
                } else {
                    reviewsContainer.innerHTML = '<p style="text-align: center; color: #6c757d;">まだレビューがありません</p>';
                }
            } catch (error) {
                console.error('Error loading analytics:', error);
            }
        }
        
        // タブ切り替え
        function showTab(tabName) {
            // タブコンテンツ切り替え
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.getElementById(tabName + '-tab').classList.add('active');
            
            // ナビゲーション更新
            document.querySelectorAll('.nav-tab').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            
            // QRスキャナー管理
            if (tabName === 'qr-scan') {
                startQrScanner();
            } else if (html5QrCode) {
                html5QrCode.stop().catch(err => console.log(err));
            }
        }
        
        // QRスキャナー開始
        function startQrScanner() {
            html5QrCode = new Html5Qrcode("qr-reader");
            
            Html5Qrcode.getCameras().then(devices => {
                if (devices && devices.length) {
                    html5QrCode.start(
                        devices[0].id,
                        {
                            fps: 10,
                            qrbox: { width: 250, height: 250 }
                        },
                        (decodedText) => {
                            onQrCodeScanned(decodedText);
                            html5QrCode.stop();
                        },
                        () => {} // エラーは無視
                    );
                }
            }).catch(err => {
                document.getElementById('scanResult').innerHTML = 
                    '<p style="color: #dc3545;">カメラへのアクセスが許可されていません</p>';
            });
        }
        
        // QRコードスキャン処理
        function onQrCodeScanned(url) {
            const match = url.match(/store\/([^\/]+)/);
            if (match) {
                selectStore(match[1]);
                showTab('review');
            }
        }
        
        // 店舗選択
        async function selectStore(storeId) {
            try {
                const response = await fetch(`/api/v1/stores/${storeId}`);
                selectedStore = await response.json();
                
                // レビュータブに移動
                document.querySelectorAll('.tab-content').forEach(tab => {
                    tab.classList.remove('active');
                });
                document.getElementById('review-tab').classList.add('active');
                
                document.querySelectorAll('.nav-tab').forEach(btn => {
                    btn.classList.remove('active');
                });
                document.querySelectorAll('.nav-tab')[2].classList.add('active');
                
                // 店舗情報表示
                document.getElementById('selectedStore').innerHTML = `
                    <div style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 1.5rem; border-radius: 12px;">
                        <div style="font-size: 1.25rem; font-weight: 600;">${selectedStore.name}</div>
                        <div style="margin-top: 0.5rem; opacity: 0.9;">${selectedStore.address}</div>
                    </div>
                `;
                
                // サービス表示
                const servicesGrid = document.getElementById('servicesGrid');
                servicesGrid.innerHTML = '';
                selectedStore.services.forEach(service => {
                    const chip = document.createElement('div');
                    chip.className = 'service-chip';
                    chip.dataset.service = service;
                    chip.textContent = service;
                    chip.onclick = () => toggleService(service, chip);
                    servicesGrid.appendChild(chip);
                });
            } catch (error) {
                console.error('Error selecting store:', error);
            }
        }
        
        // サービス選択
        function toggleService(service, element) {
            if (selectedServices.includes(service)) {
                selectedServices = selectedServices.filter(s => s !== service);
                element.classList.remove('selected');
            } else {
                selectedServices.push(service);
                element.classList.add('selected');
            }
        }
        
        // 星評価設定
        function setupStarRating() {
            document.querySelectorAll('.star').forEach(star => {
                star.addEventListener('click', function() {
                    selectedRating = parseInt(this.dataset.rating);
                    updateStars();
                    updateRatingText();
                });
            });
        }
        
        function updateStars() {
            document.querySelectorAll('.star').forEach((star, index) => {
                star.classList.toggle('active', index < selectedRating);
            });
        }
        
        function updateRatingText() {
            const t = translations[currentLanguage];
            if (selectedRating === 0) {
                document.getElementById('ratingText').textContent = t.selectRating;
            } else {
                document.getElementById('ratingText').textContent = t.ratingTexts[selectedRating - 1];
            }
        }
        
        // レビュー生成
        async function generateReview() {
            if (!selectedStore || selectedRating === 0 || selectedServices.length === 0) {
                alert('店舗、評価、サービスを選択してください');
                return;
            }
            
            document.getElementById('loading').classList.add('show');
            
            try {
                const response = await fetch('/api/v1/reviews/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        store_id: selectedStore.store_id,
                        rating: selectedRating,
                        services: selectedServices,
                        user_comment: document.getElementById('userComment').value,
                        language: currentLanguage
                    })
                });
                
                const data = await response.json();
                
                document.getElementById('reviewResult').innerHTML = `
                    <div class="review-result">
                        <h3 style="margin-bottom: 1rem;">生成された口コミ</h3>
                        <div class="review-text">${data.generated_text}</div>
                        ${data.redirect_url ? `
                            <a href="${data.redirect_url}" target="_blank" class="btn btn-primary">
                                外部サイトに投稿
                            </a>
                        ` : ''}
                    </div>
                `;
                
                await loadAnalytics();
            } catch (error) {
                const t = translations[currentLanguage];
                alert(t.error);
            } finally {
                document.getElementById('loading').classList.remove('show');
            }
        }
        
        // 言語切替
        function switchLanguage(lang) {
            currentLanguage = lang;
            document.querySelectorAll('.lang-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.lang === lang);
            });
        }
        
        // 初期化
        init();
    </script>
</body>
</html>
"""

# ルートエンドポイント
@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_INTERFACE

# API: 店舗一覧
@app.get("/api/v1/stores")
async def get_stores():
    return list(STORES.values())

# API: 店舗詳細
@app.get("/api/v1/stores/{store_id}")
async def get_store(store_id: str):
    if store_id not in STORES:
        raise HTTPException(status_code=404, detail="Store not found")
    return STORES[store_id]

# API: QRコード生成
@app.get("/api/v1/stores/{store_id}/qr")
async def get_store_qr(store_id: str):
    if store_id not in STORES:
        raise HTTPException(status_code=404, detail="Store not found")
    
    qr_image = generate_qr_code(store_id)
    img_data = qr_image.split(',')[1]
    img_bytes = base64.b64decode(img_data)
    
    return Response(content=img_bytes, media_type="image/png")

# API: レビュー生成
@app.post("/api/v1/reviews/generate")
async def generate_review(request: ReviewRequest):
    if request.store_id not in STORES:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = STORES[request.store_id]
    services_text = "、".join(request.services)
    
    # OpenAI APIを使用する場合はここに実装
    # 今回はダミーレスポンス
    if request.rating >= 4:
        generated_text = f"""
{store['name']}で{services_text}を体験しました。
スタッフの対応が素晴らしく、技術も確かでした。
{store['address']}という立地も便利で、また利用したいと思います。
特に{request.services[0]}の効果に満足しています。
"""
    else:
        generated_text = f"""
{store['name']}で{services_text}を利用しました。
サービス自体は悪くありませんでしたが、改善の余地があると感じました。
もう少し{request.services[0]}の質を向上させていただければと思います。
"""
    
    # レビュー保存
    review_id = str(uuid.uuid4())
    review = {
        "review_id": review_id,
        "store_id": request.store_id,
        "rating": request.rating,
        "services": request.services,
        "user_comment": request.user_comment,
        "generated_text": generated_text,
        "language": request.language,
        "created_at": datetime.now().isoformat()
    }
    REVIEWS.append(review)
    
    return {
        "review_id": review_id,
        "generated_text": generated_text,
        "rating": request.rating,
        "redirect_url": "https://maps.google.com" if request.rating >= 4 else None
    }

# API: 管理者用分析データ
@app.get("/api/v1/admin/analytics")
async def get_admin_analytics():
    total_reviews = len(REVIEWS)
    total_feedbacks = len(FEEDBACKS)
    
    if total_reviews > 0:
        avg_rating = sum(r["rating"] for r in REVIEWS) / total_reviews
    else:
        avg_rating = 0
    
    return {
        "total_stores": len(STORES),
        "total_reviews": total_reviews,
        "total_feedbacks": total_feedbacks,
        "average_rating": round(avg_rating, 2),
        "recent_reviews": REVIEWS[-5:] if REVIEWS else []
    }

# 管理者ページ
@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>管理者ログイン</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: #f8f9fa;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .login-card {
                background: white;
                padding: 2rem;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                width: 100%;
                max-width: 400px;
            }
            h1 {
                text-align: center;
                color: #1a1a1a;
                margin-bottom: 2rem;
            }
            .form-group {
                margin-bottom: 1.5rem;
            }
            label {
                display: block;
                margin-bottom: 0.5rem;
                color: #495057;
                font-weight: 500;
            }
            input {
                width: 100%;
                padding: 0.75rem;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                font-size: 1rem;
            }
            button {
                width: 100%;
                padding: 0.75rem;
                background: #6366f1;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 1rem;
                font-weight: 500;
                cursor: pointer;
            }
            button:hover {
                background: #5558e3;
            }
        </style>
    </head>
    <body>
        <div class="login-card">
            <h1>🔐 管理者ログイン</h1>
            <form method="POST" action="/admin/login">
                <div class="form-group">
                    <label for="password">パスワード</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit">ログイン</button>
            </form>
        </div>
    </body>
    </html>
    """

# 店舗ページ
@app.get("/store/{store_id}", response_class=HTMLResponse)
async def store_page(store_id: str):
    return HTMLResponse(f"""
    <script>
        window.location.href = '/?store_id={store_id}';
    </script>
    """)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)