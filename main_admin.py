from fastapi import FastAPI, HTTPException, Request, Cookie, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
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
import hashlib
import secrets

# 環境変数読み込み
load_dotenv()

app = FastAPI(
    title="SmartReview AI Admin System",
    description="AI口コミ生成システム - 管理者機能付き完全版",
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

# 管理者セッション管理（メモリ内）
ADMIN_SESSIONS = {}
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# メモリ内データベース（シンプル実装）
STORES = {
    "demo-store-001": {
        "store_id": "demo-store-001",
        "qr_code": "QR001",
        "name": "Beauty Salon SAKURA",
        "description": "最新の美容機器を完備した完全個室プライベートサロン",
        "address": "東京都渋谷区表参道1-2-3",
        "phone": "03-1234-5678",
        "services": ["ハイフ", "リフトアップ", "フェイシャル", "ボディケア", "脱毛"],
        "google_maps_place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
        "hotpepper_url": "https://beauty.hotpepper.jp/sample",
        "created_at": "2024-01-01T00:00:00"
    },
    "demo-store-002": {
        "store_id": "demo-store-002",
        "qr_code": "QR002",
        "name": "Nail Salon YUKI",
        "description": "トレンドを取り入れたデザインが得意なネイルサロン",
        "address": "東京都新宿区歌舞伎町2-1-5",
        "phone": "03-9876-5432",
        "services": ["ジェルネイル", "スカルプチュア", "ネイルアート", "ケア", "マツエク"],
        "google_maps_place_id": "ChIJN1t_tDeuEmsRUsoyG83frY5",
        "hotpepper_url": "https://beauty.hotpepper.jp/sample2",
        "created_at": "2024-01-01T00:00:00"
    },
    "demo-store-003": {
        "store_id": "demo-store-003",
        "qr_code": "QR003",
        "name": "Massage & Spa KAZE",
        "description": "リラクゼーションとボディケアの専門店",
        "address": "東京都港区六本木3-2-1",
        "phone": "03-5555-1234",
        "services": ["全身マッサージ", "アロマトリートメント", "リフレクソロジー", "ヘッドスパ", "痩身"],
        "google_maps_place_id": "ChIJN1t_tDeuEmsRUsoyG83frY6",
        "hotpepper_url": "https://beauty.hotpepper.jp/sample3",
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

class StoreCreateRequest(BaseModel):
    name: str
    description: str
    address: str
    phone: str
    services: List[str]
    google_maps_place_id: Optional[str] = ""
    hotpepper_url: Optional[str] = ""

class AdminLoginRequest(BaseModel):
    password: str

# 管理者認証
def verify_admin_session(admin_session: Optional[str] = Cookie(None)):
    if not admin_session or admin_session not in ADMIN_SESSIONS:
        raise HTTPException(status_code=401, detail="Admin authentication required")
    return admin_session

def get_admin_session(admin_session: Optional[str] = Cookie(None)):
    return admin_session if admin_session and admin_session in ADMIN_SESSIONS else None

# QRコード生成機能
def generate_qr_code(store_id: str, base_url: str) -> str:
    """QRコードを生成してBase64文字列として返す"""
    qr_url = f"{base_url}/store/{store_id}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # PIL ImageをBase64に変換
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"

# SEO最適化されたHTMLテンプレート
def get_seo_html(store_id: str = None, store_data: dict = None):
    # 店舗データの取得
    if store_id and store_id in STORES:
        store = STORES[store_id]
    elif store_data:
        store = store_data
    else:
        store = STORES["demo-store-001"]
    
    # SEO/MEO用のメタデータ
    page_title = f"{store['name']} - 口コミ・評価 | SmartReview AI"
    page_description = f"{store['name']}（{store['address']}）の口コミ・評価をAIで簡単作成。{', '.join(store['services'][:3])}など豊富なメニュー。表参道エリアの個室プライベートサロン。"
    page_keywords = f"表参道, 個室サロン, プライベートサロン, {store['name']}, {', '.join(store['services'])}, 口コミ, 評価, 美容"
    
    # 構造化データ（JSON-LD）
    structured_data = {
        "@context": "https://schema.org",
        "@type": "BeautySalon",
        "name": store['name'],
        "description": store['description'],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": store['address'],
            "addressLocality": "東京",
            "addressCountry": "JP"
        },
        "telephone": store.get('phone', ''),
        "url": f"https://smartreview-simple-208894137644.us-central1.run.app/store/{store['store_id']}",
        "serviceType": store['services'],
        "priceRange": "$$",
        "openingHours": "Mo-Su 10:00-20:00",
        "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.5",
            "reviewCount": len([r for r in REVIEWS if r.get('store_id') == store['store_id']]) or 1
        }
    }

    return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    
    <!-- SEO Meta Tags -->
    <title>{page_title}</title>
    <meta name="description" content="{page_description}">
    <meta name="keywords" content="{page_keywords}">
    <meta name="robots" content="index, follow">
    <meta name="author" content="SmartReview AI">
    
    <!-- Open Graph Tags -->
    <meta property="og:type" content="website">
    <meta property="og:title" content="{page_title}">
    <meta property="og:description" content="{page_description}">
    <meta property="og:url" content="https://smartreview-simple-208894137644.us-central1.run.app/store/{store['store_id']}">
    <meta property="og:site_name" content="SmartReview AI">
    <meta property="og:locale" content="ja_JP">
    
    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{page_title}">
    <meta name="twitter:description" content="{page_description}">
    
    <!-- Canonical URL -->
    <link rel="canonical" href="https://smartreview-simple-208894137644.us-central1.run.app/store/{store['store_id']}">
    
    <!-- Structured Data -->
    <script type="application/ld+json">
    {json.dumps(structured_data, ensure_ascii=False)}
    </script>
    
    <!-- QRコードスキャナー用ライブラリ -->
    <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
    <!-- QRコード生成用ライブラリ -->
    <script src="https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js"></script>
    
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        
        .language-switcher {{
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
            z-index: 1000;
        }}
        
        .lang-btn {{
            padding: 8px 15px;
            background: white;
            border: 2px solid #ddd;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }}
        
        .lang-btn:hover {{
            background: #f5f5f5;
        }}
        
        .lang-btn.active {{
            background: #667eea;
            color: white;
            border-color: #667eea;
        }}
        
        .admin-btn {{
            position: fixed;
            top: 20px;
            left: 20px;
            padding: 8px 15px;
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
            text-decoration: none;
        }}
        
        .admin-btn:hover {{
            background: #c82333;
        }}
        
        .container {{
            max-width: 500px;
            width: 100%;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        
        .nav-tabs {{
            display: flex;
            margin-bottom: 20px;
            border-radius: 10px;
            overflow: hidden;
            background: #f5f5f5;
        }}
        
        .nav-tab {{
            flex: 1;
            padding: 12px 8px;
            text-align: center;
            background: #f5f5f5;
            border: none;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: all 0.2s;
        }}
        
        .nav-tab.active {{
            background: #667eea;
            color: white;
        }}
        
        .tab-content {{
            display: none;
        }}
        
        .tab-content.active {{
            display: block;
        }}
        
        .qr-scanner-container {{
            text-align: center;
            margin: 20px 0;
        }}
        
        #qr-reader {{
            width: 100%;
            max-width: 400px;
            margin: 0 auto;
            border-radius: 10px;
            overflow: hidden;
        }}
        
        .store-selector {{
            margin-bottom: 20px;
        }}
        
        .store-selector select {{
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 14px;
            background: white;
        }}
        
        .qr-display {{
            text-align: center;
            margin: 20px 0;
        }}
        
        .qr-display img {{
            max-width: 200px;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        
        .analytics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        
        .analytics-card {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }}
        
        .analytics-number {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }}
        
        .analytics-label {{
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }}
        
        .review-history {{
            max-height: 300px;
            overflow-y: auto;
            margin-top: 20px;
        }}
        
        .review-item {{
            background: #f5f5f5;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
            position: relative;
        }}
        
        .review-rating {{
            color: #ffd700;
            font-size: 14px;
        }}
        
        .review-text {{
            font-size: 13px;
            color: #555;
            margin: 5px 0;
            line-height: 1.4;
        }}
        
        .review-date {{
            font-size: 11px;
            color: #999;
        }}
        
        .review-actions {{
            position: absolute;
            top: 10px;
            right: 10px;
            display: flex;
            gap: 5px;
        }}
        
        .btn-small {{
            padding: 4px 8px;
            font-size: 11px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }}
        
        .btn-edit {{
            background: #28a745;
            color: white;
        }}
        
        .btn-delete {{
            background: #dc3545;
            color: white;
        }}
        
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }}
        
        .modal-content {{
            background-color: #fefefe;
            margin: 5% auto;
            padding: 20px;
            border-radius: 10px;
            width: 90%;
            max-width: 500px;
            max-height: 80vh;
            overflow-y: auto;
        }}
        
        .close {{
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }}
        
        .close:hover {{
            color: black;
        }}
        
        .scanner-controls {{
            margin: 15px 0;
            text-align: center;
        }}
        
        .scanner-btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            margin: 0 5px;
            cursor: pointer;
        }}
        
        .hidden {{
            display: none;
        }}
        
        h1 {{
            text-align: center;
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }}
        
        h2 {{
            color: #333;
            margin-bottom: 15px;
            font-size: 20px;
        }}
        
        h3 {{
            color: #333;
            margin-bottom: 10px;
            font-size: 18px;
        }}
        
        h4 {{
            color: #333;
            margin-bottom: 10px;
            font-size: 16px;
        }}
        
        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }}
        
        .store-info {{
            background: #f5f5f5;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 25px;
        }}
        
        .store-name {{
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }}
        
        .store-address {{
            color: #666;
            font-size: 14px;
        }}
        
        .form-group {{
            margin-bottom: 20px;
        }}
        
        label {{
            display: block;
            margin-bottom: 10px;
            color: #555;
            font-weight: bold;
        }}
        
        .stars {{
            display: flex;
            gap: 5px;
            font-size: 40px;
            justify-content: center;
            margin-bottom: 10px;
        }}
        
        .star {{
            cursor: pointer;
            color: #e0e0e0;
            transition: all 0.2s;
            position: relative;
        }}
        
        .star:hover {{
            transform: scale(1.2);
        }}
        
        .star.active {{
            color: #ffd700;
            animation: starPulse 0.3s ease;
        }}
        
        .star.preview {{
            color: #ffed4e;
        }}
        
        @keyframes starPulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.3); }}
            100% {{ transform: scale(1); }}
        }}
        
        .rating-text {{
            text-align: center;
            color: #666;
            font-size: 16px;
            margin-top: 10px;
            font-weight: bold;
            min-height: 24px;
        }}
        
        .rating-text.rated-1 {{ color: #d32f2f; }}
        .rating-text.rated-2 {{ color: #f57c00; }}
        .rating-text.rated-3 {{ color: #fbc02d; }}
        .rating-text.rated-4 {{ color: #689f38; }}
        .rating-text.rated-5 {{ color: #388e3c; }}
        
        .services {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        
        .service-chip {{
            padding: 10px 20px;
            background: #f0f0f0;
            border: 2px solid #ddd;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 14px;
        }}
        
        .service-chip:hover {{
            background: #e3f2fd;
            border-color: #2196f3;
        }}
        
        .service-chip.selected {{
            background: #2196f3;
            color: white;
            border-color: #2196f3;
        }}
        
        textarea, input[type="text"], input[type="password"], input[type="email"] {{
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 14px;
            font-family: inherit;
            resize: vertical;
            min-height: 100px;
        }}
        
        input[type="text"], input[type="password"], input[type="email"] {{
            min-height: auto;
        }}
        
        textarea:focus, input:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
        button {{
            width: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }}
        
        .btn-secondary {{
            background: #6c757d;
        }}
        
        .btn-danger {{
            background: #dc3545;
        }}
        
        .btn-success {{
            background: #28a745;
        }}
        
        button:hover {{
            transform: translateY(-2px);
        }}
        
        button:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        
        .result {{
            margin-top: 20px;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 15px;
            border: 2px solid #e0e0e0;
            display: none;
        }}
        
        .result.show {{
            display: block;
        }}
        
        .result-title {{
            font-weight: bold;
            color: #333;
            margin-bottom: 15px;
            font-size: 18px;
        }}
        
        .generated-text {{
            color: #444;
            line-height: 1.8;
            white-space: pre-wrap;
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }}
        
        .platform-buttons {{
            display: grid;
            gap: 10px;
        }}
        
        .platform-button {{
            background: white;
            color: #333;
            border: 2px solid #ddd;
            padding: 12px 20px;
            border-radius: 10px;
            text-align: center;
            text-decoration: none;
            transition: all 0.2s;
            font-size: 14px;
        }}
        
        .platform-button:hover {{
            background: #f5f5f5;
            border-color: #667eea;
        }}
        
        .loading {{
            display: none;
            text-align: center;
            padding: 20px;
        }}
        
        .loading.show {{
            display: block;
        }}
        
        .spinner {{
            display: inline-block;
            width: 40px;
            height: 40px;
            border: 4px solid rgba(0,0,0,.1);
            border-radius: 50%;
            border-top-color: #667eea;
            animation: spin 1s ease-in-out infinite;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        .error {{
            background: #ffebee;
            color: #c62828;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            display: none;
        }}
        
        .error.show {{
            display: block;
        }}
        
        .success {{
            background: #e8f5e8;
            color: #2e7d32;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            display: none;
        }}
        
        .success.show {{
            display: block;
        }}
        
        .admin-login {{
            max-width: 300px;
            margin: 0 auto;
        }}
        
        .admin-dashboard {{
            max-width: 1200px;
        }}
        
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        
        .dashboard-card {{
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        
        .stats-overview {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
        }}
        
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        
        .data-table th,
        .data-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        
        .data-table th {{
            background: #f5f5f5;
            font-weight: bold;
        }}
        
        .data-table tr:hover {{
            background: #f9f9f9;
        }}
        
        /* モバイル対応 */
        @media (max-width: 768px) {{
            .container {{
                margin: 10px;
                padding: 20px;
                max-width: none;
            }}
            
            .language-switcher,
            .admin-btn {{
                position: relative;
                top: auto;
                right: auto;
                left: auto;
                margin-bottom: 15px;
            }}
            
            .nav-tab {{
                font-size: 12px;
                padding: 10px 5px;
            }}
            
            .stars {{
                font-size: 32px;
            }}
            
            .analytics-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .dashboard-grid {{
                grid-template-columns: 1fr;
            }}
            
            .stats-overview {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .data-table {{
                font-size: 12px;
            }}
            
            .data-table th,
            .data-table td {{
                padding: 8px 4px;
            }}
            
            .modal-content {{
                margin: 10% auto;
                width: 95%;
            }}
        }}
        
        @media (max-width: 480px) {{
            body {{
                padding: 10px;
            }}
            
            .container {{
                padding: 15px;
            }}
            
            h1 {{
                font-size: 24px;
            }}
            
            .stars {{
                font-size: 28px;
            }}
            
            .analytics-grid,
            .stats-overview {{
                grid-template-columns: 1fr;
            }}
            
            .nav-tab {{
                font-size: 11px;
                padding: 8px 3px;
            }}
        }}
    </style>
</head>
<body>
    <a href="/admin" class="admin-btn">管理者</a>
    
    <div class="language-switcher">
        <button class="lang-btn active" data-lang="ja" onclick="switchLanguage('ja')">日本語</button>
        <button class="lang-btn" data-lang="en" onclick="switchLanguage('en')">English</button>
        <button class="lang-btn" data-lang="zh" onclick="switchLanguage('zh')">中文</button>
        <button class="lang-btn" data-lang="ko" onclick="switchLanguage('ko')">한국어</button>
    </div>
    
    <div class="container">
        <h1>🌟 SmartReview AI</h1>
        <p class="subtitle" data-i18n="subtitle">AI口コミ生成システム</p>
        
        <!-- ナビゲーションタブ -->
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="switchTab('review')" data-i18n="tabReview">レビュー</button>
            <button class="nav-tab" onclick="switchTab('scanner')" data-i18n="tabScanner">QRスキャン</button>
            <button class="nav-tab" onclick="switchTab('management')" data-i18n="tabManagement">店舗管理</button>
            <button class="nav-tab" onclick="switchTab('analytics')" data-i18n="tabAnalytics">分析</button>
        </div>
        
        <!-- QRスキャナータブ -->
        <div id="scanner-tab" class="tab-content">
            <div class="qr-scanner-container">
                <h3 data-i18n="qrScanTitle">QRコードをスキャン</h3>
                <div id="qr-reader"></div>
                <div class="scanner-controls">
                    <button id="start-scan" class="scanner-btn" onclick="startScanner()" data-i18n="startScan">スキャン開始</button>
                    <button id="stop-scan" class="scanner-btn hidden" onclick="stopScanner()" data-i18n="stopScan">停止</button>
                </div>
                <p style="margin-top: 15px; color: #666; font-size: 14px;" data-i18n="scanInstructions">
                    QRコードをカメラに向けてスキャンしてください
                </p>
            </div>
        </div>
        
        <!-- 店舗管理タブ -->
        <div id="management-tab" class="tab-content">
            <h3 data-i18n="storeManagement">店舗管理</h3>
            
            <div class="store-selector">
                <label data-i18n="selectStore">店舗を選択</label>
                <select id="store-select" onchange="loadStoreInfo()">
                    <option value="">店舗を選択してください</option>
                </select>
            </div>
            
            <div id="qr-generator" class="hidden">
                <h4 data-i18n="qrCode">QRコード</h4>
                <div class="qr-display">
                    <img id="qr-image" alt="QR Code" />
                </div>
                <button onclick="downloadQR()" data-i18n="downloadQR">QRコードをダウンロード</button>
            </div>
        </div>
        
        <!-- 分析タブ -->
        <div id="analytics-tab" class="tab-content">
            <h3 data-i18n="analyticsTitle">分析ダッシュボード</h3>
            
            <div class="store-selector">
                <select id="analytics-store-select" onchange="loadAnalytics()">
                    <option value="">店舗を選択してください</option>
                </select>
            </div>
            
            <div id="analytics-data" class="hidden">
                <div class="analytics-grid">
                    <div class="analytics-card">
                        <div class="analytics-number" id="total-reviews">0</div>
                        <div class="analytics-label" data-i18n="totalReviews">総レビュー数</div>
                    </div>
                    <div class="analytics-card">
                        <div class="analytics-number" id="avg-rating">0.0</div>
                        <div class="analytics-label" data-i18n="avgRating">平均評価</div>
                    </div>
                    <div class="analytics-card">
                        <div class="analytics-number" id="total-feedbacks">0</div>
                        <div class="analytics-label" data-i18n="totalFeedbacks">フィードバック数</div>
                    </div>
                </div>
                
                <h4 data-i18n="recentReviews">最近のレビュー</h4>
                <div id="review-history" class="review-history"></div>
            </div>
        </div>
        
        <!-- レビュータブ -->
        <div id="review-tab" class="tab-content active">
        
        <div class="store-info">
            <div class="store-name">{store['name']}</div>
            <div class="store-address">{store['address']}</div>
        </div>
        
        <div class="form-group">
            <label data-i18n="selectRating">評価を選択してください</label>
            <div class="stars" id="stars">
                <span class="star" data-rating="1">⭐</span>
                <span class="star" data-rating="2">⭐</span>
                <span class="star" data-rating="3">⭐</span>
                <span class="star" data-rating="4">⭐</span>
                <span class="star" data-rating="5">⭐</span>
            </div>
            <div class="rating-text" id="ratingText">評価を選択してください</div>
        </div>
        
        <div class="form-group">
            <label data-i18n="selectService">ご利用されたサービス</label>
            <div class="services">
                {' '.join([f'<div class="service-chip" data-service="{service}">{service}</div>' for service in store['services']])}
            </div>
        </div>
        
        <div class="form-group">
            <label data-i18n="comment">コメント（任意）</label>
            <textarea id="userComment" placeholder="ご感想やご要望があればお聞かせください..." data-i18n-placeholder="commentPlaceholder"></textarea>
        </div>
        
        <button id="generateBtn" onclick="generateReview()" data-i18n="generateButton">
            AI口コミを生成
        </button>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p style="margin-top: 10px; color: #666;" data-i18n="generating">AI生成中...</p>
        </div>
        
        <div class="error" id="error"></div>
        <div class="success" id="success"></div>
        
        <div class="result" id="result">
            <div class="result-title" data-i18n="generatedReview">生成された口コミ</div>
            <div class="generated-text" id="generatedText"></div>
            <div class="platform-buttons" id="platformButtons"></div>
        </div>
        </div>
    </div>
    
    <!-- モーダル -->
    <div id="store-modal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h3 data-i18n="storeFound">店舗が見つかりました</h3>
            <div id="modal-store-info"></div>
            <button onclick="selectStore()" data-i18n="selectThisStore">この店舗を選択</button>
        </div>
    </div>
    
    <!-- レビュー編集モーダル -->
    <div id="edit-review-modal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeEditModal()">&times;</span>
            <h3>レビュー編集</h3>
            <div class="form-group">
                <label>レビュー内容:</label>
                <textarea id="edit-review-text" style="min-height: 150px;"></textarea>
            </div>
            <button onclick="saveReviewEdit()">保存</button>
            <button onclick="closeEditModal()" class="btn-secondary" style="margin-top: 10px;">キャンセル</button>
        </div>
    </div>
    
    <script>
        let selectedRating = 0;
        let selectedServices = [];
        let currentLanguage = 'ja';
        let currentStoreId = '{store['store_id']}';
        let qrScanner = null;
        let foundStore = null;
        let editingReviewId = null;
        
        // 多言語対応
        const translations = {{
            ja: {{
                subtitle: 'AI口コミ生成システム',
                selectRating: '評価を選択してください',
                selectService: 'ご利用されたサービス',
                comment: 'コメント（任意）',
                commentPlaceholder: 'ご感想やご要望があればお聞かせください...',
                generateButton: 'AI口コミを生成',
                generating: 'AI生成中...',
                generatedReview: '生成された口コミ',
                ratingTexts: [
                    '評価を選択してください',
                    '⭐ 改善が必要',
                    '⭐⭐ やや不満',
                    '⭐⭐⭐ 普通',
                    '⭐⭐⭐⭐ 良い',
                    '⭐⭐⭐⭐⭐ 素晴らしい！'
                ],
                errorRating: '評価を選択してください',
                errorService: 'サービスを選択してください',
                errorCommunication: '通信エラーが発生しました',
                googleMaps: 'Google マップに投稿',
                hotpepper: 'HotPepper Beautyに投稿',
                feedbackSent: 'フィードバックとして送信しました',
                tabReview: 'レビュー',
                tabScanner: 'QRスキャン',
                tabManagement: '店舗管理',
                tabAnalytics: '分析',
                qrScanTitle: 'QRコードをスキャン',
                startScan: 'スキャン開始',
                stopScan: '停止',
                scanInstructions: 'QRコードをカメラに向けてスキャンしてください',
                storeManagement: '店舗管理',
                selectStore: '店舗を選択',
                qrCode: 'QRコード',
                downloadQR: 'QRコードをダウンロード',
                analyticsTitle: '分析ダッシュボード',
                totalReviews: '総レビュー数',
                avgRating: '平均評価',
                totalFeedbacks: 'フィードバック数',
                recentReviews: '最近のレビュー',
                storeFound: '店舗が見つかりました',
                selectThisStore: 'この店舗を選択'
            }},
            en: {{
                subtitle: 'AI Review Generation System',
                selectRating: 'Please select a rating',
                selectService: 'Services used',
                comment: 'Comment (optional)',
                commentPlaceholder: 'Please share your thoughts or feedback...',
                generateButton: 'Generate AI Review',
                generating: 'Generating...',
                generatedReview: 'Generated Review',
                ratingTexts: [
                    'Please select a rating',
                    '⭐ Needs improvement',
                    '⭐⭐ Somewhat dissatisfied',
                    '⭐⭐⭐ Average',
                    '⭐⭐⭐⭐ Good',
                    '⭐⭐⭐⭐⭐ Excellent!'
                ],
                errorRating: 'Please select a rating',
                errorService: 'Please select a service',
                errorCommunication: 'Communication error occurred',
                googleMaps: 'Post to Google Maps',
                hotpepper: 'Post to HotPepper Beauty',
                feedbackSent: 'Sent as feedback',
                tabReview: 'Review',
                tabScanner: 'QR Scan',
                tabManagement: 'Store Management',
                tabAnalytics: 'Analytics',
                qrScanTitle: 'Scan QR Code',
                startScan: 'Start Scan',
                stopScan: 'Stop',
                scanInstructions: 'Point your camera at the QR code to scan',
                storeManagement: 'Store Management',
                selectStore: 'Select Store',
                qrCode: 'QR Code',
                downloadQR: 'Download QR Code',
                analyticsTitle: 'Analytics Dashboard',
                totalReviews: 'Total Reviews',
                avgRating: 'Average Rating',
                totalFeedbacks: 'Total Feedbacks',
                recentReviews: 'Recent Reviews',
                storeFound: 'Store Found',
                selectThisStore: 'Select This Store'
            }},
            zh: {{
                subtitle: 'AI评论生成系统',
                selectRating: '请选择评分',
                selectService: '使用的服务',
                comment: '评论（可选）',
                commentPlaceholder: '请分享您的想法或反馈...',
                generateButton: '生成AI评论',
                generating: '生成中...',
                generatedReview: '生成的评论',
                ratingTexts: [
                    '请选择评分',
                    '⭐ 需要改进',
                    '⭐⭐ 略有不满',
                    '⭐⭐⭐ 一般',
                    '⭐⭐⭐⭐ 良好',
                    '⭐⭐⭐⭐⭐ 优秀！'
                ],
                errorRating: '请选择评分',
                errorService: '请选择服务',
                errorCommunication: '发生通信错误',
                googleMaps: '发布到谷歌地图',
                hotpepper: '发布到HotPepper Beauty',
                feedbackSent: '已作为反馈发送',
                tabReview: '评论',
                tabScanner: '二维码扫描',
                tabManagement: '店铺管理',
                tabAnalytics: '分析',
                qrScanTitle: '扫描二维码',
                startScan: '开始扫描',
                stopScan: '停止',
                scanInstructions: '将相机对准二维码进行扫描',
                storeManagement: '店铺管理',
                selectStore: '选择店铺',
                qrCode: '二维码',
                downloadQR: '下载二维码',
                analyticsTitle: '分析仪表板',
                totalReviews: '总评论数',
                avgRating: '平均评分',
                totalFeedbacks: '总反馈数',
                recentReviews: '最近评论',
                storeFound: '找到店铺',
                selectThisStore: '选择此店铺'
            }},
            ko: {{
                subtitle: 'AI 리뷰 생성 시스템',
                selectRating: '평점을 선택해주세요',
                selectService: '이용하신 서비스',
                comment: '코멘트 (선택사항)',
                commentPlaceholder: '의견이나 피드백을 공유해주세요...',
                generateButton: 'AI 리뷰 생성',
                generating: '생성 중...',
                generatedReview: '생성된 리뷰',
                ratingTexts: [
                    '평점을 선택해주세요',
                    '⭐ 개선 필요',
                    '⭐⭐ 다소 불만족',
                    '⭐⭐⭐ 보통',
                    '⭐⭐⭐⭐ 좋음',
                    '⭐⭐⭐⭐⭐ 훌륭함!'
                ],
                errorRating: '평점을 선택해주세요',
                errorService: '서비스를 선택해주세요',
                errorCommunication: '통신 오류가 발생했습니다',
                googleMaps: '구글 지도에 게시',
                hotpepper: 'HotPepper Beauty에 게시',
                feedbackSent: '피드백으로 전송됨',
                tabReview: '리뷰',
                tabScanner: 'QR 스캔',
                tabManagement: '매장 관리',
                tabAnalytics: '분석',
                qrScanTitle: 'QR 코드 스캔',
                startScan: '스캔 시작',
                stopScan: '정지',
                scanInstructions: '카메라를 QR 코드에 향하게 하여 스캔하세요',
                storeManagement: '매장 관리',
                selectStore: '매장 선택',
                qrCode: 'QR 코드',
                downloadQR: 'QR 코드 다운로드',
                analyticsTitle: '분석 대시보드',
                totalReviews: '총 리뷰 수',
                avgRating: '평균 평점',
                totalFeedbacks: '총 피드백 수',
                recentReviews: '최근 리뷰',
                storeFound: '매장을 찾았습니다',
                selectThisStore: '이 매장 선택'
            }}
        }};
        
        function switchLanguage(lang) {{
            currentLanguage = lang;
            
            // Update language buttons
            document.querySelectorAll('.lang-btn').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.lang === lang);
            }});
            
            // Update text content
            document.querySelectorAll('[data-i18n]').forEach(element => {{
                const key = element.getAttribute('data-i18n');
                if (translations[lang][key]) {{
                    element.textContent = translations[lang][key];
                }}
            }});
            
            // Update placeholders
            document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {{
                const key = element.getAttribute('data-i18n-placeholder');
                if (translations[lang][key]) {{
                    element.placeholder = translations[lang][key];
                }}
            }});
            
            // Update rating text
            updateRatingText();
        }}
        
        function updateRatingText() {{
            const ratingTextEl = document.getElementById('ratingText');
            if (ratingTextEl) {{
                ratingTextEl.textContent = translations[currentLanguage].ratingTexts[selectedRating];
                ratingTextEl.className = 'rating-text' + (selectedRating > 0 ? ' rated-' + selectedRating : '');
            }}
        }}
        
        // 星評価の設定
        document.querySelectorAll('.star').forEach(star => {{
            star.addEventListener('mouseenter', function() {{
                const rating = parseInt(this.dataset.rating);
                document.querySelectorAll('.star').forEach((s, index) => {{
                    s.classList.toggle('preview', index < rating);
                }});
            }});
            
            star.addEventListener('mouseleave', function() {{
                document.querySelectorAll('.star').forEach(s => {{
                    s.classList.remove('preview');
                }});
            }});
            
            star.addEventListener('click', function() {{
                selectedRating = parseInt(this.dataset.rating);
                updateStars();
                updateRatingText();
            }});
        }});
        
        function updateStars() {{
            document.querySelectorAll('.star').forEach((star, index) => {{
                star.classList.toggle('active', index < selectedRating);
            }});
        }}
        
        // サービス選択
        document.querySelectorAll('.service-chip').forEach(chip => {{
            chip.addEventListener('click', function() {{
                const service = this.dataset.service;
                if (selectedServices.includes(service)) {{
                    selectedServices = selectedServices.filter(s => s !== service);
                    this.classList.remove('selected');
                }} else {{
                    selectedServices.push(service);
                    this.classList.add('selected');
                }}
            }});
        }});
        
        async function generateReview() {{
            // バリデーション
            if (selectedRating === 0) {{
                showError(translations[currentLanguage].errorRating);
                return;
            }}
            
            if (selectedServices.length === 0) {{
                showError(translations[currentLanguage].errorService);
                return;
            }}
            
            // UI更新
            document.getElementById('generateBtn').disabled = true;
            document.getElementById('loading').classList.add('show');
            document.getElementById('result').classList.remove('show');
            document.getElementById('error').classList.remove('show');
            
            const requestData = {{
                store_id: currentStoreId,
                rating: selectedRating,
                services: selectedServices,
                user_comment: document.getElementById('userComment').value,
                language: currentLanguage
            }};
            
            try {{
                const response = await fetch('/api/v1/reviews/generate', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify(requestData)
                }});
                
                const data = await response.json();
                
                if (response.ok) {{
                    showResult(data);
                }} else {{
                    showError('Error: ' + (data.detail || 'Unknown error'));
                }}
            }} catch (error) {{
                showError(translations[currentLanguage].errorCommunication);
            }} finally {{
                document.getElementById('generateBtn').disabled = false;
                document.getElementById('loading').classList.remove('show');
            }}
        }}
        
        function showResult(data) {{
            document.getElementById('generatedText').textContent = data.generated_text;
            
            // プラットフォームボタンの生成
            const buttonsContainer = document.getElementById('platformButtons');
            buttonsContainer.innerHTML = '';
            
            if (selectedRating >= 4) {{
                // 高評価の場合は外部プラットフォームへ
                const platforms = [
                    {{ name: translations[currentLanguage].googleMaps, url: 'https://maps.google.com' }},
                    {{ name: translations[currentLanguage].hotpepper, url: 'https://beauty.hotpepper.jp' }}
                ];
                
                platforms.forEach(platform => {{
                    const button = document.createElement('a');
                    button.className = 'platform-button';
                    button.href = platform.url;
                    button.target = '_blank';
                    button.textContent = platform.name;
                    buttonsContainer.appendChild(button);
                }});
            }} else {{
                // 低評価の場合は内部フィードバック
                const button = document.createElement('div');
                button.className = 'platform-button';
                button.style.background = '#fff3cd';
                button.style.borderColor = '#ffc107';
                button.textContent = translations[currentLanguage].feedbackSent;
                buttonsContainer.appendChild(button);
            }}
            
            document.getElementById('result').classList.add('show');
        }}
        
        function showError(message) {{
            const errorDiv = document.getElementById('error');
            errorDiv.textContent = message;
            errorDiv.classList.add('show');
            setTimeout(() => {{
                errorDiv.classList.remove('show');
            }}, 5000);
        }}
        
        function showSuccess(message) {{
            const successDiv = document.getElementById('success');
            successDiv.textContent = message;
            successDiv.classList.add('show');
            setTimeout(() => {{
                successDiv.classList.remove('show');
            }}, 5000);
        }}
        
        // タブ切り替え
        function switchTab(tabName) {{
            // すべてのタブを非アクティブに
            document.querySelectorAll('.nav-tab').forEach(tab => {{
                tab.classList.remove('active');
            }});
            document.querySelectorAll('.tab-content').forEach(content => {{
                content.classList.remove('active');
            }});
            
            // 選択されたタブをアクティブに
            event.target.classList.add('active');
            document.getElementById(tabName + '-tab').classList.add('active');
            
            // 初期化
            if (tabName === 'management') {{
                loadStoreList();
            }} else if (tabName === 'analytics') {{
                loadStoreListForAnalytics();
            }} else if (tabName === 'scanner') {{
                // QRスキャナーは手動で開始
            }}
        }}
        
        // QRスキャナー機能
        function startScanner() {{
            const config = {{
                fps: 10,
                qrbox: {{ width: 250, height: 250 }},
                rememberLastUsedCamera: true
            }};
            
            qrScanner = new Html5Qrcode("qr-reader");
            
            qrScanner.start(
                {{ facingMode: "environment" }},
                config,
                qrCodeSuccessCallback,
                qrCodeErrorCallback
            ).then(() => {{
                document.getElementById('start-scan').classList.add('hidden');
                document.getElementById('stop-scan').classList.remove('hidden');
            }}).catch(err => {{
                console.log('Error starting scanner:', err);
                showError('カメラの起動に失敗しました');
            }});
        }}
        
        function stopScanner() {{
            if (qrScanner) {{
                qrScanner.stop().then(() => {{
                    document.getElementById('start-scan').classList.remove('hidden');
                    document.getElementById('stop-scan').classList.add('hidden');
                }}).catch(err => {{
                    console.log('Error stopping scanner:', err);
                }});
            }}
        }}
        
        function qrCodeSuccessCallback(decodedText, decodedResult) {{
            console.log('QR Code detected:', decodedText);
            
            // QRコードからstore_idを抽出
            try {{
                const url = new URL(decodedText);
                const pathParts = url.pathname.split('/');
                const storeId = pathParts[pathParts.length - 1];
                
                // 店舗情報を取得
                fetch(`/api/v1/stores/${{storeId}}`)
                    .then(response => response.json())
                    .then(store => {{
                        foundStore = store;
                        showStoreModal(store);
                        stopScanner();
                    }})
                    .catch(error => {{
                        console.error('Error:', error);
                        showError('店舗情報の取得に失敗しました');
                    }});
            }} catch (error) {{
                showError('無効なQRコードです');
            }}
        }}
        
        function qrCodeErrorCallback(errorMessage) {{
            // QRコード読み取りエラー（通常は無視）
        }}
        
        function showStoreModal(store) {{
            const modalInfo = document.getElementById('modal-store-info');
            modalInfo.innerHTML = `
                <div class="store-info">
                    <div class="store-name">${{store.name}}</div>
                    <div class="store-address">${{store.address}}</div>
                    <div style="margin-top: 10px; color: #666;">${{store.description}}</div>
                </div>
            `;
            document.getElementById('store-modal').style.display = 'block';
        }}
        
        function closeModal() {{
            document.getElementById('store-modal').style.display = 'none';
        }}
        
        function selectStore() {{
            if (foundStore) {{
                currentStoreId = foundStore.store_id;
                
                // 店舗情報を更新
                document.querySelector('.store-name').textContent = foundStore.name;
                document.querySelector('.store-address').textContent = foundStore.address;
                
                // サービスリストを更新
                updateServicesList(foundStore.services);
                
                closeModal();
                switchTab('review');
            }}
        }}
        
        function updateServicesList(services) {{
            const servicesContainer = document.querySelector('.services');
            servicesContainer.innerHTML = '';
            
            services.forEach(service => {{
                const chip = document.createElement('div');
                chip.className = 'service-chip';
                chip.dataset.service = service;
                chip.textContent = service;
                chip.addEventListener('click', function() {{
                    const service = this.dataset.service;
                    if (selectedServices.includes(service)) {{
                        selectedServices = selectedServices.filter(s => s !== service);
                        this.classList.remove('selected');
                    }} else {{
                        selectedServices.push(service);
                        this.classList.add('selected');
                    }}
                }});
                servicesContainer.appendChild(chip);
            }});
        }}
        
        // 店舗管理機能
        async function loadStoreList() {{
            try {{
                const response = await fetch('/api/v1/stores');
                const stores = await response.json();
                
                const select = document.getElementById('store-select');
                select.innerHTML = '<option value="">店舗を選択してください</option>';
                
                stores.forEach(store => {{
                    const option = document.createElement('option');
                    option.value = store.store_id;
                    option.textContent = store.name;
                    select.appendChild(option);
                }});
            }} catch (error) {{
                console.error('Error loading stores:', error);
            }}
        }}
        
        async function loadStoreInfo() {{
            const storeId = document.getElementById('store-select').value;
            if (!storeId) {{
                document.getElementById('qr-generator').classList.add('hidden');
                return;
            }}
            
            try {{
                const response = await fetch(`/api/v1/stores/${{storeId}}/qr`);
                const data = await response.json();
                
                document.getElementById('qr-image').src = data.qr_image;
                document.getElementById('qr-generator').classList.remove('hidden');
            }} catch (error) {{
                console.error('Error loading QR code:', error);
            }}
        }}
        
        function downloadQR() {{
            const img = document.getElementById('qr-image');
            const link = document.createElement('a');
            link.download = 'qr-code.png';
            link.href = img.src;
            link.click();
        }}
        
        // 分析機能
        async function loadStoreListForAnalytics() {{
            try {{
                const response = await fetch('/api/v1/stores');
                const stores = await response.json();
                
                const select = document.getElementById('analytics-store-select');
                select.innerHTML = '<option value="">店舗を選択してください</option>';
                
                stores.forEach(store => {{
                    const option = document.createElement('option');
                    option.value = store.store_id;
                    option.textContent = store.name;
                    select.appendChild(option);
                }});
            }} catch (error) {{
                console.error('Error loading stores:', error);
            }}
        }}
        
        async function loadAnalytics() {{
            const storeId = document.getElementById('analytics-store-select').value;
            if (!storeId) {{
                document.getElementById('analytics-data').classList.add('hidden');
                return;
            }}
            
            try {{
                const response = await fetch(`/api/v1/stores/${{storeId}}/analytics`);
                const data = await response.json();
                
                document.getElementById('total-reviews').textContent = data.total_reviews;
                document.getElementById('avg-rating').textContent = data.average_rating;
                document.getElementById('total-feedbacks').textContent = data.total_feedbacks;
                
                // レビュー履歴表示
                const historyContainer = document.getElementById('review-history');
                historyContainer.innerHTML = '';
                
                data.recent_reviews.forEach(review => {{
                    const item = document.createElement('div');
                    item.className = 'review-item';
                    
                    const stars = '⭐'.repeat(review.rating);
                    const date = new Date(review.created_at).toLocaleDateString();
                    
                    item.innerHTML = `
                        <div class="review-actions">
                            <button class="btn-small btn-edit" onclick="editReview('${{review.review_id}}', '${{review.generated_text.replace(/'/g, "\\'")}}')">編集</button>
                            <button class="btn-small btn-delete" onclick="deleteReview('${{review.review_id}}')">削除</button>
                        </div>
                        <div class="review-rating">${{stars}} (${{review.rating}}/5)</div>
                        <div class="review-text">${{review.generated_text.substring(0, 100)}}...</div>
                        <div class="review-date">${{date}} | ${{review.services.join(', ')}}</div>
                    `;
                    
                    historyContainer.appendChild(item);
                }});
                
                document.getElementById('analytics-data').classList.remove('hidden');
            }} catch (error) {{
                console.error('Error loading analytics:', error);
            }}
        }}
        
        // レビュー編集・削除機能
        function editReview(reviewId, reviewText) {{
            editingReviewId = reviewId;
            document.getElementById('edit-review-text').value = reviewText;
            document.getElementById('edit-review-modal').style.display = 'block';
        }}
        
        function closeEditModal() {{
            document.getElementById('edit-review-modal').style.display = 'none';
            editingReviewId = null;
        }}
        
        async function saveReviewEdit() {{
            if (!editingReviewId) return;
            
            const newText = document.getElementById('edit-review-text').value;
            
            try {{
                const response = await fetch(`/api/v1/admin/reviews/${{editingReviewId}}`, {{
                    method: 'PUT',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{ generated_text: newText }})
                }});
                
                if (response.ok) {{
                    showSuccess('レビューを更新しました');
                    closeEditModal();
                    loadAnalytics(); // リフレッシュ
                }} else {{
                    showError('更新に失敗しました');
                }}
            }} catch (error) {{
                showError('通信エラーが発生しました');
            }}
        }}
        
        async function deleteReview(reviewId) {{
            if (!confirm('このレビューを削除しますか？')) return;
            
            try {{
                const response = await fetch(`/api/v1/admin/reviews/${{reviewId}}`, {{
                    method: 'DELETE'
                }});
                
                if (response.ok) {{
                    showSuccess('レビューを削除しました');
                    loadAnalytics(); // リフレッシュ
                }} else {{
                    showError('削除に失敗しました');
                }}
            }} catch (error) {{
                showError('通信エラーが発生しました');
            }}
        }}
        
        // ページ読み込み時の初期化
        window.addEventListener('load', function() {{
            // デフォルト店舗の情報を読み込む
            loadStoreListForAnalytics();
        }});
        
        // モーダル外クリックで閉じる
        window.onclick = function(event) {{
            const storeModal = document.getElementById('store-modal');
            const editModal = document.getElementById('edit-review-modal');
            
            if (event.target == storeModal) {{
                storeModal.style.display = 'none';
            }}
            if (event.target == editModal) {{
                editModal.style.display = 'none';
            }}
        }}
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
    <title>SmartReview AI - 管理者ログイン</title>
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
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .login-container {
            max-width: 400px;
            width: 100%;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .form-group {
            margin-bottom: 20px;
            text-align: left;
        }
        
        label {
            display: block;
            margin-bottom: 10px;
            color: #555;
            font-weight: bold;
        }
        
        input[type="password"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 14px;
            font-family: inherit;
        }
        
        input[type="password"]:focus {
            outline: none;
            border-color: #667eea;
        }
        
        button {
            width: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        button:hover {
            transform: translateY(-2px);
        }
        
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            display: none;
        }
        
        .error.show {
            display: block;
        }
        
        .back-link {
            display: inline-block;
            margin-top: 20px;
            color: #667eea;
            text-decoration: none;
            font-size: 14px;
        }
        
        .back-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>🔐 管理者ログイン</h1>
        <p class="subtitle">SmartReview AI 管理システム</p>
        
        <form onsubmit="return handleLogin(event)">
            <div class="form-group">
                <label for="password">パスワード:</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <button type="submit" id="loginBtn">ログイン</button>
        </form>
        
        <div class="error" id="error"></div>
        
        <a href="/" class="back-link">← トップページに戻る</a>
    </div>
    
    <script>
        async function handleLogin(event) {
            event.preventDefault();
            
            const password = document.getElementById('password').value;
            const loginBtn = document.getElementById('loginBtn');
            const errorDiv = document.getElementById('error');
            
            loginBtn.disabled = true;
            errorDiv.classList.remove('show');
            
            try {
                const response = await fetch('/admin/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ password: password })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    window.location.href = '/admin/dashboard';
                } else {
                    errorDiv.textContent = data.detail || 'ログインに失敗しました';
                    errorDiv.classList.add('show');
                }
            } catch (error) {
                errorDiv.textContent = '通信エラーが発生しました';
                errorDiv.classList.add('show');
            } finally {
                loginBtn.disabled = false;
            }
            
            return false;
        }
    </script>
</body>
</html>
"""

# ルートエンドポイント - SEO最適化されたHTMLインターフェース
@app.get("/", response_class=HTMLResponse)
async def root():
    return get_seo_html()

# 店舗固有のレビューページ
@app.get("/store/{store_id}", response_class=HTMLResponse)
async def store_review_page(store_id: str):
    if store_id not in STORES:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = STORES[store_id]
    return get_seo_html(store_id, store)

# 管理者ログインページ
@app.get("/admin", response_class=HTMLResponse)
async def admin_login():
    return ADMIN_LOGIN_HTML

# 管理者ログイン処理
@app.post("/admin/login")
async def admin_login_post(request: AdminLoginRequest):
    if request.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # セッションIDを生成
    session_id = secrets.token_urlsafe(32)
    ADMIN_SESSIONS[session_id] = {
        "created_at": datetime.now(),
        "last_access": datetime.now()
    }
    
    # レスポンスにクッキーを設定
    response = {"message": "Login successful", "redirect": "/admin/dashboard"}
    response_obj = RedirectResponse(url="/admin/dashboard", status_code=302)
    response_obj.set_cookie(
        key="admin_session",
        value=session_id,
        max_age=3600 * 24,  # 24時間
        httponly=True,
        secure=False,  # HTTPSでない場合はFalse
        samesite="lax"
    )
    return response_obj

# 管理者ログアウト
@app.get("/admin/logout")
async def admin_logout(admin_session: str = Depends(get_admin_session)):
    if admin_session and admin_session in ADMIN_SESSIONS:
        del ADMIN_SESSIONS[admin_session]
    
    response = RedirectResponse(url="/admin", status_code=302)
    response.delete_cookie("admin_session")
    return response

# 管理者ダッシュボードページ
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(admin_session: str = Depends(verify_admin_session)):
    return ADMIN_DASHBOARD_HTML

# ヘルスチェック
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "SmartReview AI Admin System",
        "version": "5.0.0",
        "timestamp": datetime.now().isoformat()
    }

# 店舗一覧取得
@app.get("/api/v1/stores")
async def get_stores():
    return list(STORES.values())

# 店舗情報取得
@app.get("/api/v1/stores/qr/{qr_code}")
async def get_store_by_qr(qr_code: str):
    for store in STORES.values():
        if store["qr_code"] == qr_code:
            return store
    raise HTTPException(status_code=404, detail="Store not found")

@app.get("/api/v1/stores/{store_id}")
async def get_store(store_id: str):
    if store_id not in STORES:
        raise HTTPException(status_code=404, detail="Store not found")
    return STORES[store_id]

# QRコード生成
@app.get("/api/v1/stores/{store_id}/qr")
async def get_store_qr(store_id: str, request: Request):
    if store_id not in STORES:
        raise HTTPException(status_code=404, detail="Store not found")
    
    # リクエストからベースURLを取得
    base_url = str(request.base_url).rstrip('/')
    
    qr_image = generate_qr_code(store_id, base_url)
    
    return {
        "store_id": store_id,
        "qr_image": qr_image,
        "qr_url": f"{base_url}/store/{store_id}"
    }

# 店舗作成
@app.post("/api/v1/stores")
async def create_store(request: StoreCreateRequest):
    store_id = f"store-{uuid.uuid4().hex[:8]}"
    qr_code = f"QR{len(STORES) + 1:03d}"
    
    store = {
        "store_id": store_id,
        "qr_code": qr_code,
        "name": request.name,
        "description": request.description,
        "address": request.address,
        "phone": request.phone,
        "services": request.services,
        "google_maps_place_id": request.google_maps_place_id,
        "hotpepper_url": request.hotpepper_url,
        "created_at": datetime.now().isoformat()
    }
    
    STORES[store_id] = store
    
    return {
        "store_id": store_id,
        "message": "Store created successfully",
        "store": store
    }

# AI口コミ生成
@app.post("/api/v1/reviews/generate")
async def generate_review(request: ReviewRequest):
    # 店舗確認
    if request.store_id not in STORES:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = STORES[request.store_id]
    
    # 言語別のプロンプト設定
    lang_prompts = {
        "ja": {
            "system": "あなたは口コミライターです。表参道エリアの美容サロンの口コミを自然で魅力的に書きます。",
            "tone_positive": "ポジティブで感謝の気持ちを込めた",
            "tone_constructive": "建設的で改善提案を含む",
            "platform_external": "Google マップやHotPepper Beauty",
            "platform_internal": "店舗への直接フィードバック",
            "template": """以下の条件で{platform}用の口コミを生成してください：

店舗名: {store_name}
住所: {address}
評価: {rating}星
利用サービス: {services}
ユーザーコメント: {user_comment}

トーン: {tone}
文字数: 150-200文字程度
必須キーワード: 表参道、{services}、個室、プライベートサロン

SEO/MEO対策として以下を含めてください：
- 表参道駅からのアクセス情報
- 個室・プライベート感の強調
- 具体的なサービス名

口コミ文章のみを日本語で出力してください："""
        },
        "en": {
            "system": "You are a review writer specializing in beauty salons in Omotesando area.",
            "tone_positive": "positive and grateful",
            "tone_constructive": "constructive with improvement suggestions",
            "platform_external": "Google Maps or HotPepper Beauty",
            "platform_internal": "direct feedback to the store",
            "template": """Generate a review for {platform} with the following conditions:

Store Name: {store_name}
Address: {address}
Rating: {rating} stars
Services Used: {services}
User Comment: {user_comment}

Tone: {tone}
Length: Around 100-150 words
Keywords: Omotesando, {services}, private room, private salon

Please output only the review text in English:"""
        },
        "zh": {
            "system": "你是一位专门为表参道美容沙龙撰写评论的作者。",
            "tone_positive": "积极且充满感激",
            "tone_constructive": "建设性的改进建议",
            "platform_external": "谷歌地图或HotPepper Beauty",
            "platform_internal": "直接反馈给店铺",
            "template": """请根据以下条件生成{platform}的评论：

店铺名称：{store_name}
地址：{address}
评分：{rating}星
使用服务：{services}
用户评论：{user_comment}

语气：{tone}
字数：100-150字左右
关键词：表参道、{services}、私人房间、私人沙龙

请仅用中文输出评论内容："""
        },
        "ko": {
            "system": "당신은 오모테산도 지역 미용 살롱 전문 리뷰 작성자입니다.",
            "tone_positive": "긍정적이고 감사한",
            "tone_constructive": "건설적이고 개선 제안이 포함된",
            "platform_external": "구글 지도나 HotPepper Beauty",
            "platform_internal": "매장에 직접 피드백",
            "template": """{platform}용 리뷰를 다음 조건으로 생성해주세요:

매장명: {store_name}
주소: {address}
평점: {rating}점
이용 서비스: {services}
사용자 코멘트: {user_comment}

어조: {tone}
글자 수: 100-150자 정도
키워드: 오모테산도, {services}, 개인실, 프라이빗 살롱

한국어로 리뷰 내용만 출력해주세요:"""
        }
    }
    
    # デフォルトは日本語
    if request.language not in lang_prompts:
        request.language = "ja"
    
    lang_config = lang_prompts[request.language]
    services_text = ", ".join(request.services)
    
    if request.rating >= 4:
        tone = lang_config["tone_positive"]
        platform = lang_config["platform_external"]
    else:
        tone = lang_config["tone_constructive"]
        platform = lang_config["platform_internal"]
    
    prompt = lang_config["template"].format(
        platform=platform,
        store_name=store['name'],
        address=store['address'],
        rating=request.rating,
        services=services_text,
        user_comment=request.user_comment if request.user_comment else 'N/A',
        tone=tone
    )
    
    try:
        # OpenAI API呼び出し
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": lang_config["system"]},
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.7
        )
        
        generated_text = response.choices[0].message.content.strip()
        
    except Exception as e:
        # OpenAI APIが使えない場合はダミーテキスト（多言語対応）
        dummy_texts = {
            "ja": f"""
{store['name']}で{services_text}を体験しました。
表参道駅から徒歩5分の好立地にある完全個室のプライベートサロンです。
{'とても満足しています。' if request.rating >= 4 else '改善の余地があると感じました。'}
スタッフの対応も{'素晴らしく、' if request.rating >= 4 else ''}
また利用したいと思います。表参道エリアでは珍しい完全個室制で、プライバシーが保たれた空間で施術を受けることができます。
""",
            "en": f"""
I experienced {services_text} at {store['name']}.
It's a private salon with private rooms, just 5 minutes walk from Omotesando station.
{'I am very satisfied.' if request.rating >= 4 else 'I felt there was room for improvement.'}
The staff service was {'excellent and ' if request.rating >= 4 else ''}
I would like to visit again.
""",
            "zh": f"""
我在{store['name']}体验了{services_text}。
这是一家位于表参道站步行5分钟的完全私人包间沙龙。
{'非常满意。' if request.rating >= 4 else '感觉还有改进的空间。'}
工作人员的服务{'非常好，' if request.rating >= 4 else ''}
我想再次使用。
""",
            "ko": f"""
{store['name']}에서 {services_text}를 체험했습니다.
오모테산도역에서 도보 5분 거리의 완전 개인실 프라이빗 살롱입니다.
{'매우 만족합니다.' if request.rating >= 4 else '개선의 여지가 있다고 느꼈습니다.'}
직원의 대응도 {'훌륭했고 ' if request.rating >= 4 else ''}
다시 이용하고 싶습니다.
"""
        }
        generated_text = dummy_texts.get(request.language, dummy_texts["ja"]).strip()
    
    # レビューを保存
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

# フィードバック送信
@app.post("/api/v1/feedbacks")
async def submit_feedback(request: FeedbackRequest):
    feedback_id = str(uuid.uuid4())
    feedback = {
        "feedback_id": feedback_id,
        "store_id": request.store_id,
        "rating": request.rating,
        "services": request.services,
        "comment": request.comment,
        "improvement_areas": request.improvement_areas,
        "created_at": datetime.now().isoformat()
    }
    FEEDBACKS.append(feedback)
    
    return {
        "feedback_id": feedback_id,
        "status": "received",
        "message": "フィードバックありがとうございます"
    }

# 統計情報取得
@app.get("/api/v1/stores/{store_id}/analytics")
async def get_store_analytics(store_id: str):
    if store_id not in STORES:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store_reviews = [r for r in REVIEWS if r["store_id"] == store_id]
    store_feedbacks = [f for f in FEEDBACKS if f["store_id"] == store_id]
    
    if not store_reviews:
        avg_rating = 0
    else:
        avg_rating = sum(r["rating"] for r in store_reviews) / len(store_reviews)
    
    return {
        "store_id": store_id,
        "total_reviews": len(store_reviews),
        "total_feedbacks": len(store_feedbacks),
        "average_rating": round(avg_rating, 2),
        "recent_reviews": store_reviews[-5:] if store_reviews else []
    }

# 管理者API - 統計情報
@app.get("/api/v1/admin/stats")
async def get_admin_stats(admin_session: str = Depends(verify_admin_session)):
    total_reviews = len(REVIEWS)
    total_feedbacks = len(FEEDBACKS)
    total_stores = len(STORES)
    
    if total_reviews > 0:
        avg_rating = sum(r["rating"] for r in REVIEWS) / total_reviews
    else:
        avg_rating = 0
    
    return {
        "total_stores": total_stores,
        "total_reviews": total_reviews,
        "total_feedbacks": total_feedbacks,
        "average_rating": round(avg_rating, 1)
    }

# 管理者API - レビュー一覧
@app.get("/api/v1/admin/reviews")
async def get_admin_reviews(
    admin_session: str = Depends(verify_admin_session),
    store_id: Optional[str] = None
):
    if store_id:
        return [r for r in REVIEWS if r["store_id"] == store_id]
    return REVIEWS

# 管理者API - レビュー編集
@app.put("/api/v1/admin/reviews/{review_id}")
async def update_review(
    review_id: str,
    update_data: dict,
    admin_session: str = Depends(verify_admin_session)
):
    for review in REVIEWS:
        if review["review_id"] == review_id:
            if "generated_text" in update_data:
                review["generated_text"] = update_data["generated_text"]
            review["updated_at"] = datetime.now().isoformat()
            return {"message": "Review updated successfully"}
    
    raise HTTPException(status_code=404, detail="Review not found")

# 管理者API - レビュー削除
@app.delete("/api/v1/admin/reviews/{review_id}")
async def delete_review(
    review_id: str,
    admin_session: str = Depends(verify_admin_session)
):
    global REVIEWS
    REVIEWS = [r for r in REVIEWS if r["review_id"] != review_id]
    return {"message": "Review deleted successfully"}

# 管理者API - フィードバック一覧
@app.get("/api/v1/admin/feedbacks")
async def get_admin_feedbacks(
    admin_session: str = Depends(verify_admin_session),
    store_id: Optional[str] = None
):
    if store_id:
        return [f for f in FEEDBACKS if f["store_id"] == store_id]
    return FEEDBACKS

# 管理者API - フィードバック詳細
@app.get("/api/v1/admin/feedbacks/{feedback_id}")
async def get_feedback_detail(
    feedback_id: str,
    admin_session: str = Depends(verify_admin_session)
):
    for feedback in FEEDBACKS:
        if feedback["feedback_id"] == feedback_id:
            return feedback
    
    raise HTTPException(status_code=404, detail="Feedback not found")

# 管理者API - フィードバック削除
@app.delete("/api/v1/admin/feedbacks/{feedback_id}")
async def delete_feedback(
    feedback_id: str,
    admin_session: str = Depends(verify_admin_session)
):
    global FEEDBACKS
    FEEDBACKS = [f for f in FEEDBACKS if f["feedback_id"] != feedback_id]
    return {"message": "Feedback deleted successfully"}

# OpenAI APIテスト
@app.get("/api/v1/test-openai")
async def test_openai():
    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "こんにちは。これはテストです。"}
            ],
            max_tokens=50
        )
        return {
            "status": "success",
            "message": "OpenAI API is working",
            "response": response.choices[0].message.content
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "hint": "Please check your OPENAI_API_KEY environment variable"
        }

# セッション管理のクリーンアップ（24時間以上古いセッションを削除）
def cleanup_sessions():
    current_time = datetime.now()
    expired_sessions = []
    
    for session_id, session_data in ADMIN_SESSIONS.items():
        if (current_time - session_data["created_at"]).total_seconds() > 86400:  # 24時間
            expired_sessions.append(session_id)
    
    for session_id in expired_sessions:
        del ADMIN_SESSIONS[session_id]

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    
    # 定期的なセッションクリーンアップを設定（実際の本番環境では別の方法を推奨）
    import threading
    import time
    
    def periodic_cleanup():
        while True:
            time.sleep(3600)  # 1時間ごとにクリーンアップ
            cleanup_sessions()
    
    cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()
    
    uvicorn.run(app, host="0.0.0.0", port=port)

# 管理者ダッシュボードページ
ADMIN_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartReview AI - 管理者ダッシュボード</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            background: #f5f6fa;
            min-height: 100vh;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .header-content {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 {
            font-size: 24px;
        }
        
        .header-actions {
            display: flex;
            gap: 15px;
        }
        
        .btn-header {
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            text-decoration: none;
            font-size: 14px;
            transition: background 0.2s;
        }
        
        .btn-header:hover {
            background: rgba(255,255,255,0.3);
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 30px 20px;
        }
        
        .stats-overview {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            text-align: center;
        }
        
        .stat-number {
            font-size: 36px;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 16px;
            color: #666;
        }
        
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        
        .dashboard-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .card-title {
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }
        
        .data-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .data-table th,
        .data-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        
        .data-table th {
            background: #f8f9fa;
            font-weight: bold;
            color: #555;
        }
        
        .data-table tr:hover {
            background: #f8f9fa;
        }
        
        .rating-stars {
            color: #ffd700;
        }
        
        .btn-small {
            padding: 6px 12px;
            font-size: 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin: 0 2px;
        }
        
        .btn-edit {
            background: #28a745;
            color: white;
        }
        
        .btn-delete {
            background: #dc3545;
            color: white;
        }
        
        .btn-view {
            background: #17a2b8;
            color: white;
        }
        
        .store-selector {
            margin-bottom: 20px;
        }
        
        .store-selector select {
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            background: white;
            font-size: 14px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .spinner {
            display: inline-block;
            width: 40px;
            height: 40px;
            border: 4px solid rgba(0,0,0,.1);
            border-radius: 50%;
            border-top-color: #667eea;
            animation: spin 1s ease-in-out infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        
        .modal-content {
            background-color: white;
            margin: 5% auto;
            padding: 30px;
            border-radius: 15px;
            width: 90%;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        
        .close:hover {
            color: black;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
            color: #555;
        }
        
        textarea, input[type="text"] {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            font-family: inherit;
        }
        
        textarea {
            min-height: 120px;
            resize: vertical;
        }
        
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            margin-right: 10px;
        }
        
        button:hover {
            background: #5a6fd8;
        }
        
        .btn-secondary {
            background: #6c757d;
        }
        
        .btn-secondary:hover {
            background: #5a6268;
        }
        
        .alert {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .alert-danger {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .chart-container {
            height: 300px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666;
            font-style: italic;
        }
        
        /* モバイル対応 */
        @media (max-width: 768px) {
            .header-content {
                flex-direction: column;
                gap: 15px;
                text-align: center;
            }
            
            .stats-overview {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
            
            .data-table {
                font-size: 12px;
            }
            
            .data-table th,
            .data-table td {
                padding: 8px 4px;
            }
            
            .modal-content {
                margin: 10% auto;
                width: 95%;
                padding: 20px;
            }
        }
        
        @media (max-width: 480px) {
            .stats-overview {
                grid-template-columns: 1fr;
            }
            
            .container {
                padding: 20px 10px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <h1>🛠️ SmartReview AI 管理者ダッシュボード</h1>
            <div class="header-actions">
                <a href="/" class="btn-header">サイトを表示</a>
                <a href="/admin/logout" class="btn-header">ログアウト</a>
            </div>
        </div>
    </div>
    
    <div class="container">
        <!-- 統計概要 -->
        <div class="stats-overview">
            <div class="stat-card">
                <div class="stat-number" id="total-stores">0</div>
                <div class="stat-label">総店舗数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="total-reviews">0</div>
                <div class="stat-label">総レビュー数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="total-feedbacks">0</div>
                <div class="stat-label">総フィードバック数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="avg-rating">0.0</div>
                <div class="stat-label">全体平均評価</div>
            </div>
        </div>
        
        <!-- ダッシュボードグリッド -->
        <div class="dashboard-grid">
            <!-- 店舗管理 -->
            <div class="dashboard-card">
                <div class="card-header">
                    <h3 class="card-title">店舗管理</h3>
                </div>
                <div id="stores-loading" class="loading">
                    <div class="spinner"></div>
                    <p>読み込み中...</p>
                </div>
                <div id="stores-content" style="display: none;">
                    <table class="data-table" id="stores-table">
                        <thead>
                            <tr>
                                <th>店舗名</th>
                                <th>レビュー数</th>
                                <th>平均評価</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
            
            <!-- レビュー管理 -->
            <div class="dashboard-card">
                <div class="card-header">
                    <h3 class="card-title">レビュー管理</h3>
                </div>
                <div class="store-selector">
                    <label>店舗を選択:</label>
                    <select id="review-store-select" onchange="loadReviews()">
                        <option value="">全店舗</option>
                    </select>
                </div>
                <div id="reviews-loading" class="loading">
                    <div class="spinner"></div>
                    <p>読み込み中...</p>
                </div>
                <div id="reviews-content" style="display: none;">
                    <table class="data-table" id="reviews-table">
                        <thead>
                            <tr>
                                <th>日時</th>
                                <th>評価</th>
                                <th>レビュー</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
            
            <!-- フィードバック管理 -->
            <div class="dashboard-card">
                <div class="card-header">
                    <h3 class="card-title">フィードバック管理</h3>
                </div>
                <div class="store-selector">
                    <label>店舗を選択:</label>
                    <select id="feedback-store-select" onchange="loadFeedbacks()">
                        <option value="">全店舗</option>
                    </select>
                </div>
                <div id="feedbacks-loading" class="loading">
                    <div class="spinner"></div>
                    <p>読み込み中...</p>
                </div>
                <div id="feedbacks-content" style="display: none;">
                    <table class="data-table" id="feedbacks-table">
                        <thead>
                            <tr>
                                <th>日時</th>
                                <th>評価</th>
                                <th>コメント</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            </div>
            
            <!-- 分析チャート -->
            <div class="dashboard-card">
                <div class="card-header">
                    <h3 class="card-title">評価分析</h3>
                </div>
                <div class="chart-container">
                    <p>チャート機能は将来のバージョンで実装予定</p>
                </div>
            </div>
        </div>
    </div>
    
    <!-- レビュー編集モーダル -->
    <div id="edit-review-modal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeEditModal()">&times;</span>
            <h3>レビュー編集</h3>
            <div id="edit-alert"></div>
            <div class="form-group">
                <label>レビュー内容:</label>
                <textarea id="edit-review-text"></textarea>
            </div>
            <button onclick="saveReviewEdit()">保存</button>
            <button onclick="closeEditModal()" class="btn-secondary">キャンセル</button>
        </div>
    </div>
    
    <!-- フィードバック詳細モーダル -->
    <div id="feedback-detail-modal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeFeedbackModal()">&times;</span>
            <h3>フィードバック詳細</h3>
            <div id="feedback-detail-content"></div>
            <button onclick="closeFeedbackModal()" class="btn-secondary">閉じる</button>
        </div>
    </div>
    
    <script>
        let currentEditingReviewId = null;
        
        // 初期化
        document.addEventListener('DOMContentLoaded', function() {
            loadDashboardData();
        });
        
        // ダッシュボードデータの読み込み
        async function loadDashboardData() {
            try {
                // 統計データの読み込み
                const statsResponse = await fetch('/api/v1/admin/stats');
                const stats = await statsResponse.json();
                
                document.getElementById('total-stores').textContent = stats.total_stores;
                document.getElementById('total-reviews').textContent = stats.total_reviews;
                document.getElementById('total-feedbacks').textContent = stats.total_feedbacks;
                document.getElementById('avg-rating').textContent = stats.average_rating;
                
                // 各セクションのデータ読み込み
                await Promise.all([
                    loadStores(),
                    loadStoreSelectors(),
                    loadReviews(),
                    loadFeedbacks()
                ]);
            } catch (error) {
                console.error('Error loading dashboard:', error);
            }
        }
        
        // 店舗一覧の読み込み
        async function loadStores() {
            try {
                const response = await fetch('/api/v1/stores');
                const stores = await response.json();
                
                const tbody = document.querySelector('#stores-table tbody');
                tbody.innerHTML = '';
                
                for (const store of stores) {
                    const analyticsResponse = await fetch(`/api/v1/stores/${store.store_id}/analytics`);
                    const analytics = await analyticsResponse.json();
                    
                    const row = tbody.insertRow();
                    row.innerHTML = `
                        <td>${store.name}</td>
                        <td>${analytics.total_reviews}</td>
                        <td class="rating-stars">${'⭐'.repeat(Math.round(analytics.average_rating))} ${analytics.average_rating}</td>
                        <td>
                            <button class="btn-small btn-view" onclick="viewStore('${store.store_id}')">詳細</button>
                        </td>
                    `;
                }
                
                document.getElementById('stores-loading').style.display = 'none';
                document.getElementById('stores-content').style.display = 'block';
            } catch (error) {
                console.error('Error loading stores:', error);
            }
        }
        
        // 店舗セレクタの読み込み
        async function loadStoreSelectors() {
            try {
                const response = await fetch('/api/v1/stores');
                const stores = await response.json();
                
                const selectors = ['review-store-select', 'feedback-store-select'];
                selectors.forEach(selectorId => {
                    const select = document.getElementById(selectorId);
                    select.innerHTML = '<option value="">全店舗</option>';
                    
                    stores.forEach(store => {
                        const option = document.createElement('option');
                        option.value = store.store_id;
                        option.textContent = store.name;
                        select.appendChild(option);
                    });
                });
            } catch (error) {
                console.error('Error loading store selectors:', error);
            }
        }
        
        // レビュー一覧の読み込み
        async function loadReviews() {
            try {
                const storeId = document.getElementById('review-store-select').value;
                const url = storeId ? `/api/v1/admin/reviews?store_id=${storeId}` : '/api/v1/admin/reviews';
                
                const response = await fetch(url);
                const reviews = await response.json();
                
                const tbody = document.querySelector('#reviews-table tbody');
                tbody.innerHTML = '';
                
                reviews.forEach(review => {
                    const row = tbody.insertRow();
                    const date = new Date(review.created_at).toLocaleDateString();
                    const truncatedText = review.generated_text.substring(0, 50) + '...';
                    
                    row.innerHTML = `
                        <td>${date}</td>
                        <td class="rating-stars">${'⭐'.repeat(review.rating)}</td>
                        <td>${truncatedText}</td>
                        <td>
                            <button class="btn-small btn-edit" onclick="editReview('${review.review_id}', '${review.generated_text.replace(/'/g, "\\'")}')">編集</button>
                            <button class="btn-small btn-delete" onclick="deleteReview('${review.review_id}')">削除</button>
                        </td>
                    `;
                });
                
                document.getElementById('reviews-loading').style.display = 'none';
                document.getElementById('reviews-content').style.display = 'block';
            } catch (error) {
                console.error('Error loading reviews:', error);
            }
        }
        
        // フィードバック一覧の読み込み
        async function loadFeedbacks() {
            try {
                const storeId = document.getElementById('feedback-store-select').value;
                const url = storeId ? `/api/v1/admin/feedbacks?store_id=${storeId}` : '/api/v1/admin/feedbacks';
                
                const response = await fetch(url);
                const feedbacks = await response.json();
                
                const tbody = document.querySelector('#feedbacks-table tbody');
                tbody.innerHTML = '';
                
                feedbacks.forEach(feedback => {
                    const row = tbody.insertRow();
                    const date = new Date(feedback.created_at).toLocaleDateString();
                    const truncatedComment = feedback.comment.substring(0, 50) + '...';
                    
                    row.innerHTML = `
                        <td>${date}</td>
                        <td class="rating-stars">${'⭐'.repeat(feedback.rating)}</td>
                        <td>${truncatedComment}</td>
                        <td>
                            <button class="btn-small btn-view" onclick="viewFeedback('${feedback.feedback_id}')">詳細</button>
                            <button class="btn-small btn-delete" onclick="deleteFeedback('${feedback.feedback_id}')">削除</button>
                        </td>
                    `;
                });
                
                document.getElementById('feedbacks-loading').style.display = 'none';
                document.getElementById('feedbacks-content').style.display = 'block';
            } catch (error) {
                console.error('Error loading feedbacks:', error);
            }
        }
        
        // レビュー編集
        function editReview(reviewId, reviewText) {
            currentEditingReviewId = reviewId;
            document.getElementById('edit-review-text').value = reviewText;
            document.getElementById('edit-alert').innerHTML = '';
            document.getElementById('edit-review-modal').style.display = 'block';
        }
        
        function closeEditModal() {
            document.getElementById('edit-review-modal').style.display = 'none';
            currentEditingReviewId = null;
        }
        
        async function saveReviewEdit() {
            if (!currentEditingReviewId) return;
            
            const newText = document.getElementById('edit-review-text').value;
            const alertDiv = document.getElementById('edit-alert');
            
            try {
                const response = await fetch(`/api/v1/admin/reviews/${currentEditingReviewId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ generated_text: newText })
                });
                
                if (response.ok) {
                    alertDiv.innerHTML = '<div class="alert alert-success">レビューを更新しました</div>';
                    setTimeout(() => {
                        closeEditModal();
                        loadReviews();
                    }, 1500);
                } else {
                    alertDiv.innerHTML = '<div class="alert alert-danger">更新に失敗しました</div>';
                }
            } catch (error) {
                alertDiv.innerHTML = '<div class="alert alert-danger">通信エラーが発生しました</div>';
            }
        }
        
        // レビュー削除
        async function deleteReview(reviewId) {
            if (!confirm('このレビューを削除しますか？')) return;
            
            try {
                const response = await fetch(`/api/v1/admin/reviews/${reviewId}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    loadReviews();
                    loadDashboardData(); // 統計を更新
                } else {
                    alert('削除に失敗しました');
                }
            } catch (error) {
                alert('通信エラーが発生しました');
            }
        }
        
        // フィードバック詳細表示
        async function viewFeedback(feedbackId) {
            try {
                const response = await fetch(`/api/v1/admin/feedbacks/${feedbackId}`);
                const feedback = await response.json();
                
                const content = document.getElementById('feedback-detail-content');
                content.innerHTML = `
                    <div class="form-group">
                        <label>評価:</label>
                        <div class="rating-stars">${'⭐'.repeat(feedback.rating)} (${feedback.rating}/5)</div>
                    </div>
                    <div class="form-group">
                        <label>サービス:</label>
                        <div>${feedback.services.join(', ')}</div>
                    </div>
                    <div class="form-group">
                        <label>コメント:</label>
                        <div>${feedback.comment}</div>
                    </div>
                    <div class="form-group">
                        <label>改善点:</label>
                        <div>${feedback.improvement_areas.join(', ') || 'なし'}</div>
                    </div>
                    <div class="form-group">
                        <label>投稿日時:</label>
                        <div>${new Date(feedback.created_at).toLocaleString()}</div>
                    </div>
                `;
                
                document.getElementById('feedback-detail-modal').style.display = 'block';
            } catch (error) {
                alert('フィードバック詳細の取得に失敗しました');
            }
        }
        
        function closeFeedbackModal() {
            document.getElementById('feedback-detail-modal').style.display = 'none';
        }
        
        // フィードバック削除
        async function deleteFeedback(feedbackId) {
            if (!confirm('このフィードバックを削除しますか？')) return;
            
            try {
                const response = await fetch(`/api/v1/admin/feedbacks/${feedbackId}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    loadFeedbacks();
                    loadDashboardData(); // 統計を更新
                } else {
                    alert('削除に失敗しました');
                }
            } catch (error) {
                alert('通信エラーが発生しました');
            }
        }
        
        // 店舗詳細表示
        function viewStore(storeId) {
            window.open(`/store/${storeId}`, '_blank');
        }
        
        // モーダル外クリックで閉じる
        window.onclick = function(event) {
            const editModal = document.getElementById('edit-review-modal');
            const feedbackModal = document.getElementById('feedback-detail-modal');
            
            if (event.target == editModal) {
                closeEditModal();
            }
            if (event.target == feedbackModal) {
                closeFeedbackModal();
            }
        }
    </script>
</body>
</html>
"""

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "1", "content": "\u73fe\u5728\u306emain.py\u3068main_v2.py\u3092\u5206\u6790\u3057\u3001\u65e2\u5b58\u6a5f\u80fd\u3092\u7406\u89e3\u3059\u308b", "status": "completed"}, {"id": "2", "content": "\u7ba1\u7406\u8005\u8a8d\u8a3c\u6a5f\u80fd\u3092\u5b9f\u88c5\uff08\u30bb\u30c3\u30b7\u30e7\u30f3\u7ba1\u7406\u3001\u30d1\u30b9\u30ef\u30fc\u30c9\u8a8d\u8a3c\uff09", "status": "completed"}, {"id": "3", "content": "\u7ba1\u7406\u8005\u30c0\u30c3\u30b7\u30e5\u30dc\u30fc\u30c9\u3092\u5b9f\u88c5\uff08\u7d71\u8a08\u8868\u793a\u3001\u30ec\u30d3\u30e5\u30fc\u7ba1\u7406\u3001\u30d5\u30a3\u30fc\u30c9\u30d0\u30c3\u30af\u7ba1\u7406\uff09", "status": "completed"}, {"id": "4", "content": "SEO/MEO\u6700\u9069\u5316\u3092\u5b9f\u88c5\uff08\u69cb\u9020\u5316\u30c7\u30fc\u30bf\u3001Open Graph\u3001Twitter Card\u3001\u30e1\u30bf\u30bf\u30b0\uff09", "status": "completed"}, {"id": "5", "content": "HTML\u30c6\u30f3\u30d7\u30ec\u30fc\u30c8\u306b\u30e2\u30d0\u30a4\u30eb\u5bfe\u5fdc\u3068\u30ec\u30b9\u30dd\u30f3\u30b7\u30d6\u30c7\u30b6\u30a4\u30f3\u3092\u9069\u7528", "status": "completed"}, {"id": "6", "content": "main_admin.py\u30d5\u30a1\u30a4\u30eb\u3092\u4f5c\u6210\u3057\u3001\u5168\u6a5f\u80fd\u3092\u7d71\u5408", "status": "in_progress"}]