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
    title="SmartReview AI Pro",
    description="AI口コミ生成システム - QRコード & 管理機能付き",
    version="5.0.0"
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

# セッション検証
def verify_admin_session(session_token: Optional[str] = Cookie(None)):
    if not session_token or session_token not in ADMIN_SESSIONS:
        return False
    session = ADMIN_SESSIONS[session_token]
    if datetime.now() > session["expires"]:
        del ADMIN_SESSIONS[session_token]
        return False
    return True

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

# HTMLインターフェース
HTML_INTERFACE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartReview AI Pro</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: rgba(255, 255, 255, 0.95);
            padding: 15px 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 24px;
            color: #333;
        }
        
        .nav-buttons {
            display: flex;
            gap: 10px;
        }
        
        .nav-btn {
            padding: 8px 20px;
            background: white;
            border: 2px solid #667eea;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
            color: #667eea;
            text-decoration: none;
        }
        
        .nav-btn:hover {
            background: #667eea;
            color: white;
        }
        
        .nav-btn.active {
            background: #667eea;
            color: white;
        }
        
        .main-container {
            margin-top: 80px;
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
        }
        
        .tab-container {
            display: none;
        }
        
        .tab-container.active {
            display: block;
        }
        
        .card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-bottom: 20px;
        }
        
        .store-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .store-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        
        .store-card:hover {
            transform: translateY(-5px);
        }
        
        .store-name {
            font-size: 20px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }
        
        .store-address {
            color: #666;
            font-size: 14px;
            margin-bottom: 15px;
        }
        
        .qr-code {
            text-align: center;
            margin: 20px 0;
        }
        
        .qr-code img {
            max-width: 200px;
            border: 2px solid #ddd;
            border-radius: 10px;
            padding: 10px;
            background: white;
        }
        
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        button:hover {
            transform: translateY(-2px);
        }
        
        .scanner-container {
            position: relative;
            width: 100%;
            max-width: 500px;
            margin: 0 auto;
        }
        
        #qr-reader {
            width: 100%;
            border-radius: 15px;
            overflow: hidden;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 10px;
            color: #555;
            font-weight: bold;
        }
        
        .stars {
            display: flex;
            gap: 5px;
            font-size: 40px;
            justify-content: center;
            margin-bottom: 10px;
        }
        
        .star {
            cursor: pointer;
            color: #e0e0e0;
            transition: all 0.2s;
        }
        
        .star:hover {
            transform: scale(1.2);
        }
        
        .star.active {
            color: #ffd700;
            animation: starPulse 0.3s ease;
        }
        
        @keyframes starPulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.3); }
            100% { transform: scale(1); }
        }
        
        .services {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .service-chip {
            padding: 10px 20px;
            background: #f0f0f0;
            border: 2px solid #ddd;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 14px;
        }
        
        .service-chip:hover {
            background: #e3f2fd;
            border-color: #2196f3;
        }
        
        .service-chip.selected {
            background: #2196f3;
            color: white;
            border-color: #2196f3;
        }
        
        textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 14px;
            font-family: inherit;
            resize: vertical;
            min-height: 100px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
        }
        
        .stat-number {
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 14px;
            opacity: 0.9;
        }
        
        .language-switcher {
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
            z-index: 1001;
        }
        
        .lang-btn {
            padding: 8px 15px;
            background: white;
            border: 2px solid #ddd;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }
        
        .lang-btn:hover {
            background: #f5f5f5;
        }
        
        .lang-btn.active {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
        
        @media (max-width: 768px) {
            .header {
                flex-direction: column;
                gap: 15px;
            }
            
            .store-grid {
                grid-template-columns: 1fr;
            }
            
            .language-switcher {
                position: static;
                margin-bottom: 20px;
                justify-content: center;
            }
        }
    </style>
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
</head>
<body>
    <div class="language-switcher">
        <button class="lang-btn active" data-lang="ja" onclick="switchLanguage('ja')">日本語</button>
        <button class="lang-btn" data-lang="en" onclick="switchLanguage('en')">English</button>
        <button class="lang-btn" data-lang="zh" onclick="switchLanguage('zh')">中文</button>
        <button class="lang-btn" data-lang="ko" onclick="switchLanguage('ko')">한국어</button>
    </div>
    
    <div class="header">
        <h1>🌟 SmartReview AI Pro</h1>
        <div class="nav-buttons">
            <button class="nav-btn active" onclick="showTab('stores')">店舗一覧</button>
            <button class="nav-btn" onclick="showTab('qr-scan')">QRスキャン</button>
            <button class="nav-btn" onclick="showTab('review')">レビュー作成</button>
            <button class="nav-btn" onclick="showTab('analytics')">分析</button>
            <a href="/admin" class="nav-btn">管理者</a>
        </div>
    </div>
    
    <div class="main-container">
        <!-- 店舗一覧タブ -->
        <div id="stores-tab" class="tab-container active">
            <div class="card">
                <h2>登録店舗一覧</h2>
                <div class="store-grid" id="storeGrid"></div>
            </div>
        </div>
        
        <!-- QRスキャンタブ -->
        <div id="qr-scan-tab" class="tab-container">
            <div class="card">
                <h2>QRコードスキャン</h2>
                <div class="scanner-container">
                    <div id="qr-reader"></div>
                </div>
                <div id="scan-result" style="margin-top: 20px; text-align: center;"></div>
            </div>
        </div>
        
        <!-- レビュー作成タブ -->
        <div id="review-tab" class="tab-container">
            <div class="card">
                <h2>レビュー作成</h2>
                <div id="selectedStore" style="margin-bottom: 20px;"></div>
                
                <div class="form-group">
                    <label>評価を選択してください</label>
                    <div class="stars" id="stars">
                        <span class="star" data-rating="1">⭐</span>
                        <span class="star" data-rating="2">⭐</span>
                        <span class="star" data-rating="3">⭐</span>
                        <span class="star" data-rating="4">⭐</span>
                        <span class="star" data-rating="5">⭐</span>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>ご利用されたサービス</label>
                    <div class="services" id="services"></div>
                </div>
                
                <div class="form-group">
                    <label>コメント（任意）</label>
                    <textarea id="userComment" placeholder="ご感想をお聞かせください..."></textarea>
                </div>
                
                <button onclick="generateReview()">AI口コミを生成</button>
                
                <div id="reviewResult" style="margin-top: 20px;"></div>
            </div>
        </div>
        
        <!-- 分析タブ -->
        <div id="analytics-tab" class="tab-container">
            <div class="card">
                <h2>統計情報</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number" id="totalStores">0</div>
                        <div class="stat-label">登録店舗数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" id="totalReviews">0</div>
                        <div class="stat-label">総レビュー数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" id="avgRating">0.0</div>
                        <div class="stat-label">平均評価</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" id="totalFeedbacks">0</div>
                        <div class="stat-label">フィードバック数</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>最近のレビュー</h2>
                <div id="recentReviews"></div>
            </div>
        </div>
    </div>
    
    <script>
        let selectedStore = null;
        let selectedRating = 0;
        let selectedServices = [];
        let currentLanguage = 'ja';
        let html5QrCode = null;
        
        // 初期化
        async function init() {
            await loadStores();
            await loadAnalytics();
            initStarRating();
        }
        
        // 店舗一覧読み込み
        async function loadStores() {
            try {
                const response = await fetch('/api/v1/stores');
                const stores = await response.json();
                
                const grid = document.getElementById('storeGrid');
                grid.innerHTML = '';
                
                stores.forEach(store => {
                    const card = document.createElement('div');
                    card.className = 'store-card';
                    card.innerHTML = `
                        <div class="store-name">${store.name}</div>
                        <div class="store-address">${store.address}</div>
                        <div class="qr-code">
                            <img src="/api/v1/stores/${store.store_id}/qr" alt="QR Code">
                        </div>
                        <button onclick="selectStore('${store.store_id}')">この店舗を選択</button>
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
                
                // 最近のレビュー表示
                const reviewsContainer = document.getElementById('recentReviews');
                reviewsContainer.innerHTML = '';
                
                if (data.recent_reviews && data.recent_reviews.length > 0) {
                    data.recent_reviews.forEach(review => {
                        const reviewDiv = document.createElement('div');
                        reviewDiv.style.marginBottom = '15px';
                        reviewDiv.style.padding = '15px';
                        reviewDiv.style.background = '#f5f5f5';
                        reviewDiv.style.borderRadius = '10px';
                        reviewDiv.innerHTML = `
                            <div style="font-weight: bold;">評価: ${'⭐'.repeat(review.rating)}</div>
                            <div style="margin-top: 5px;">${review.generated_text}</div>
                            <div style="margin-top: 5px; font-size: 12px; color: #666;">
                                ${new Date(review.created_at).toLocaleString()}
                            </div>
                        `;
                        reviewsContainer.appendChild(reviewDiv);
                    });
                } else {
                    reviewsContainer.innerHTML = '<p>まだレビューがありません</p>';
                }
            } catch (error) {
                console.error('Error loading analytics:', error);
            }
        }
        
        // タブ切り替え
        function showTab(tabName) {
            document.querySelectorAll('.tab-container').forEach(tab => {
                tab.classList.remove('active');
            });
            document.getElementById(tabName + '-tab').classList.add('active');
            
            document.querySelectorAll('.nav-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            
            if (tabName === 'qr-scan') {
                startQrScanner();
            } else if (html5QrCode) {
                html5QrCode.stop();
            }
        }
        
        // QRスキャナー開始
        function startQrScanner() {
            html5QrCode = new Html5Qrcode("qr-reader");
            
            Html5Qrcode.getCameras().then(devices => {
                if (devices && devices.length) {
                    const cameraId = devices[0].id;
                    html5QrCode.start(
                        cameraId,
                        {
                            fps: 10,
                            qrbox: { width: 250, height: 250 }
                        },
                        (decodedText, decodedResult) => {
                            onQrCodeScanned(decodedText);
                            html5QrCode.stop();
                        },
                        (errorMessage) => {
                            // QRコードが見つからない場合のエラー（無視）
                        }
                    ).catch((err) => {
                        console.error("Unable to start scanning:", err);
                    });
                }
            }).catch((err) => {
                console.error("Error getting cameras:", err);
                document.getElementById('scan-result').innerHTML = 
                    '<p style="color: red;">カメラへのアクセスが許可されていません</p>';
            });
        }
        
        // QRコードスキャン結果処理
        function onQrCodeScanned(url) {
            const storeIdMatch = url.match(/store\/([^\/]+)/);
            if (storeIdMatch) {
                selectStore(storeIdMatch[1]);
                showTab('review');
            }
        }
        
        // 店舗選択
        async function selectStore(storeId) {
            try {
                const response = await fetch(`/api/v1/stores/${storeId}`);
                selectedStore = await response.json();
                
                document.getElementById('selectedStore').innerHTML = `
                    <div style="background: #f5f5f5; padding: 15px; border-radius: 10px;">
                        <div style="font-weight: bold; font-size: 18px;">${selectedStore.name}</div>
                        <div style="color: #666; margin-top: 5px;">${selectedStore.address}</div>
                    </div>
                `;
                
                // サービス表示
                const servicesContainer = document.getElementById('services');
                servicesContainer.innerHTML = '';
                selectedStore.services.forEach(service => {
                    const chip = document.createElement('div');
                    chip.className = 'service-chip';
                    chip.dataset.service = service;
                    chip.textContent = service;
                    chip.onclick = () => toggleService(service);
                    servicesContainer.appendChild(chip);
                });
                
                showTab('review');
            } catch (error) {
                console.error('Error selecting store:', error);
            }
        }
        
        // サービス選択切り替え
        function toggleService(service) {
            const chip = event.target;
            if (selectedServices.includes(service)) {
                selectedServices = selectedServices.filter(s => s !== service);
                chip.classList.remove('selected');
            } else {
                selectedServices.push(service);
                chip.classList.add('selected');
            }
        }
        
        // 星評価初期化
        function initStarRating() {
            document.querySelectorAll('.star').forEach(star => {
                star.addEventListener('click', function() {
                    selectedRating = parseInt(this.dataset.rating);
                    updateStars();
                });
            });
        }
        
        function updateStars() {
            document.querySelectorAll('.star').forEach((star, index) => {
                star.classList.toggle('active', index < selectedRating);
            });
        }
        
        // レビュー生成
        async function generateReview() {
            if (!selectedStore || selectedRating === 0 || selectedServices.length === 0) {
                alert('店舗、評価、サービスを選択してください');
                return;
            }
            
            const requestData = {
                store_id: selectedStore.store_id,
                rating: selectedRating,
                services: selectedServices,
                user_comment: document.getElementById('userComment').value,
                language: currentLanguage
            };
            
            try {
                const response = await fetch('/api/v1/reviews/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(requestData)
                });
                
                const data = await response.json();
                
                document.getElementById('reviewResult').innerHTML = `
                    <div style="background: #f5f5f5; padding: 20px; border-radius: 10px; margin-top: 20px;">
                        <h3>生成された口コミ</h3>
                        <p style="margin-top: 10px; line-height: 1.8;">${data.generated_text}</p>
                        ${data.redirect_url ? `
                            <a href="${data.redirect_url}" target="_blank" 
                               style="display: inline-block; margin-top: 15px; padding: 10px 20px; 
                                      background: #4CAF50; color: white; border-radius: 20px; 
                                      text-decoration: none;">
                                外部サイトに投稿
                            </a>
                        ` : ''}
                    </div>
                `;
                
                // 分析データを更新
                await loadAnalytics();
            } catch (error) {
                console.error('Error generating review:', error);
                alert('エラーが発生しました');
            }
        }
        
        // 言語切替
        function switchLanguage(lang) {
            currentLanguage = lang;
            document.querySelectorAll('.lang-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.lang === lang);
            });
        }
        
        // 初期化実行
        init();
    </script>
</body>
</html>
"""

# 管理者ログインページ
ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>管理者ログイン - SmartReview AI</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .login-card {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 400px;
        }
        
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 30px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 10px;
            color: #555;
            font-weight: bold;
        }
        
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 16px;
        }
        
        button {
            width: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px;
            border-radius: 25px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }
        
        button:hover {
            transform: translateY(-2px);
        }
        
        .error {
            color: red;
            text-align: center;
            margin-top: 15px;
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

# ルートエンドポイント
@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_INTERFACE

# 管理者ログインページ
@app.get("/admin", response_class=HTMLResponse)
async def admin_login_page():
    return ADMIN_LOGIN_HTML

# 管理者ログイン処理
@app.post("/admin/login")
async def admin_login(password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        session_token = secrets.token_urlsafe(32)
        ADMIN_SESSIONS[session_token] = {
            "created_at": datetime.now(),
            "expires": datetime.now() + timedelta(hours=24)
        }
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_token", value=session_token, httponly=True)
        return response
    return HTMLResponse(ADMIN_LOGIN_HTML + '<div class="error">パスワードが正しくありません</div>')

# 管理者ログアウト
@app.get("/admin/logout")
async def admin_logout(session_token: Optional[str] = Cookie(None)):
    if session_token in ADMIN_SESSIONS:
        del ADMIN_SESSIONS[session_token]
    response = RedirectResponse(url="/")
    response.delete_cookie(key="session_token")
    return response

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
    # Base64デコードして画像として返す
    img_data = qr_image.split(',')[1]
    img_bytes = base64.b64decode(img_data)
    
    return Response(content=img_bytes, media_type="image/png")

# API: 店舗作成
@app.post("/api/v1/stores")
async def create_store(store: StoreCreate):
    store_id = f"store-{uuid.uuid4().hex[:8]}"
    qr_code = f"QR{len(STORES) + 1:03d}"
    
    new_store = {
        "store_id": store_id,
        "qr_code": qr_code,
        "name": store.name,
        "description": store.description,
        "address": store.address,
        "phone": store.phone,
        "services": store.services,
        "created_at": datetime.now().isoformat()
    }
    
    STORES[store_id] = new_store
    return new_store

# API: レビュー生成
@app.post("/api/v1/reviews/generate")
async def generate_review(request: ReviewRequest):
    if request.store_id not in STORES:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = STORES[request.store_id]
    services_text = "、".join(request.services)
    
    # ダミーレビュー生成（OpenAI API部分は簡略化）
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

# 店舗固有ページ
@app.get("/store/{store_id}", response_class=HTMLResponse)
async def store_page(store_id: str):
    if store_id not in STORES:
        return HTMLResponse("<h1>店舗が見つかりません</h1>")
    
    store = STORES[store_id]
    # 店舗固有のレビューページにリダイレクト
    return HTMLResponse(f"""
    <script>
        window.location.href = '/?store_id={store_id}';
    </script>
    """)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)