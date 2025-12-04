"""
SmartReview AI - マルチプラットフォーム対応版
PostgreSQL + SQLAlchemy によるデータ永続化対応
"""
from fastapi import FastAPI, HTTPException, Request, Cookie, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
import json
import qrcode
import io
import base64
from PIL import Image
import secrets

# Database imports
from database import get_db, init_db, SessionLocal
from models import Store, Review, AdminSession, DEFAULT_STORE_DATA

# 環境変数読み込み
load_dotenv()

app = FastAPI(
    title="SmartReview AI",
    description="AI口コミ生成システム - マルチプラットフォーム対応版（DB永続化）",
    version="9.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 環境変数
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or "admin123"
print(f"[STARTUP] ADMIN_PASSWORD configured: {'*' * len(ADMIN_PASSWORD)}")


# アプリ起動時にDBを初期化
@app.on_event("startup")
def startup_event():
    """アプリ起動時にDB初期化とSeedデータ投入"""
    print("[STARTUP] Initializing database...")
    init_db()

    # Seedデータの投入（店舗が存在しない場合）
    db = SessionLocal()
    try:
        store = db.query(Store).filter(Store.store_id == "main-store").first()
        if not store:
            print("[STARTUP] Creating default store...")
            store = Store(**DEFAULT_STORE_DATA)
            db.add(store)
            db.commit()
            print("[STARTUP] Default store created successfully")
        else:
            print(f"[STARTUP] Store found: {store.name}")
    finally:
        db.close()


# Pydanticモデル
class ReviewRequest(BaseModel):
    platform: str
    rating: int
    services: List[str]
    user_comment: Optional[str] = ""
    language: str = "ja"


class StoreUpdate(BaseModel):
    name: str
    description: str
    address: str
    phone: str
    services: List[str]
    platform_urls: Dict[str, str]


# ヘルパー関数
def get_store(db: Session) -> Store:
    """店舗情報を取得（存在しない場合は作成）"""
    store = db.query(Store).filter(Store.store_id == "main-store").first()
    if not store:
        store = Store(**DEFAULT_STORE_DATA)
        db.add(store)
        db.commit()
        db.refresh(store)
    return store


def get_store_dict(db: Session) -> dict:
    """店舗情報を辞書形式で取得"""
    store = get_store(db)
    return store.to_dict()


def validate_session(db: Session, session_id: Optional[str]) -> bool:
    """セッションの有効性を確認"""
    if not session_id:
        return False
    session = db.query(AdminSession).filter(AdminSession.token == session_id).first()
    if session and session.is_valid():
        return True
    # 期限切れセッションを削除
    if session:
        db.delete(session)
        db.commit()
    return False


def get_review_stats(db: Session) -> dict:
    """レビュー統計を取得"""
    reviews = db.query(Review).all()
    total = len(reviews)
    avg_rating = sum(r.rating for r in reviews) / total if total > 0 else 0
    return {"total": total, "avg_rating": avg_rating}


# QRコード生成
def generate_qr_code() -> str:
    base_url = os.getenv("BASE_URL", "https://smartreview-simple-208894137644.us-central1.run.app")
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(base_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"


# メインページHTML
def get_main_html(store_data: dict):
    services_json = json.dumps(store_data['services'], ensure_ascii=False)
    platform_urls_json = json.dumps(store_data['platform_urls'], ensure_ascii=False)

    return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{store_data['name']} - レビュー投稿</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Noto Sans JP', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #f8f9fa;
            min-height: 100vh;
        }}

        .header {{
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            padding: 1rem 1.5rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }}

        .header-content {{
            max-width: 500px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .logo {{
            font-size: 1.1rem;
            font-weight: 700;
            color: #333;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .lang-switcher {{
            display: flex;
            gap: 0.25rem;
            background: #f1f3f5;
            padding: 0.2rem;
            border-radius: 6px;
        }}

        .lang-btn {{
            padding: 0.35rem 0.6rem;
            background: transparent;
            border: none;
            color: #6c757d;
            font-size: 0.75rem;
            cursor: pointer;
            border-radius: 4px;
            transition: all 0.2s;
        }}

        .lang-btn.active {{
            background: white;
            color: #6366f1;
            font-weight: 500;
        }}

        .main-content {{
            max-width: 500px;
            margin: 0 auto;
            padding: 1.5rem;
        }}

        .step-indicator {{
            display: flex;
            justify-content: center;
            gap: 0.5rem;
            margin-bottom: 1.5rem;
        }}

        .step-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #dee2e6;
            transition: all 0.3s;
        }}

        .step-dot.active {{
            background: #6366f1;
            transform: scale(1.2);
        }}

        .step-dot.completed {{
            background: #10b981;
        }}

        .card {{
            background: white;
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 1rem;
        }}

        .card-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: #333;
            margin-bottom: 1rem;
            text-align: center;
        }}

        .card-subtitle {{
            font-size: 0.9rem;
            color: #6c757d;
            text-align: center;
            margin-bottom: 1.5rem;
        }}

        .step-content {{
            display: none;
        }}

        .step-content.active {{
            display: block;
            animation: fadeIn 0.3s ease;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .platform-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.75rem;
        }}

        .platform-card {{
            padding: 1rem;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            background: white;
        }}

        .platform-card:hover {{
            border-color: #6366f1;
            background: #f8f9ff;
        }}

        .platform-card.selected {{
            border-color: #6366f1;
            background: linear-gradient(135deg, #f8f9ff 0%, #eef2ff 100%);
        }}

        .platform-card.disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}

        .platform-icon {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}

        .platform-name {{
            font-size: 0.85rem;
            font-weight: 500;
            color: #333;
        }}

        .platform-status {{
            font-size: 0.7rem;
            color: #6c757d;
            margin-top: 0.25rem;
        }}

        .star-rating {{
            display: flex;
            gap: 0.5rem;
            justify-content: center;
            font-size: 2.5rem;
            margin: 1.5rem 0;
        }}

        .star {{
            cursor: pointer;
            color: #e9ecef;
            transition: all 0.2s;
        }}

        .star:hover,
        .star.active {{
            color: #ffc107;
            transform: scale(1.1);
        }}

        .rating-text {{
            text-align: center;
            color: #6c757d;
            font-size: 0.9rem;
        }}

        .services-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            justify-content: center;
        }}

        .service-chip {{
            padding: 0.5rem 1rem;
            background: #f1f3f5;
            border: 2px solid transparent;
            border-radius: 20px;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s;
            color: #555;
        }}

        .service-chip.selected {{
            background: #6366f1;
            color: white;
        }}

        .form-group {{
            margin-bottom: 1rem;
        }}

        .form-label {{
            display: block;
            font-weight: 500;
            color: #555;
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
        }}

        textarea {{
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            font-size: 0.9rem;
            font-family: inherit;
            resize: vertical;
            min-height: 80px;
        }}

        textarea:focus {{
            outline: none;
            border-color: #6366f1;
        }}

        .btn-group {{
            display: flex;
            gap: 0.75rem;
            margin-top: 1.5rem;
        }}

        .btn {{
            flex: 1;
            padding: 0.875rem 1rem;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            text-align: center;
        }}

        .btn-primary {{
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: white;
        }}

        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
        }}

        .btn-primary:disabled {{
            background: #adb5bd;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }}

        .btn-secondary {{
            background: #f1f3f5;
            color: #495057;
        }}

        .btn-secondary:hover {{
            background: #e9ecef;
        }}

        .btn-full {{
            width: 100%;
        }}

        .loading {{
            display: none;
            text-align: center;
            padding: 2rem;
        }}

        .loading.show {{
            display: block;
        }}

        .spinner {{
            display: inline-block;
            width: 40px;
            height: 40px;
            border: 3px solid #f3f4f6;
            border-top-color: #6366f1;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}

        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}

        .result-card {{
            background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%);
            border: 1px solid #86efac;
            border-radius: 12px;
            padding: 1.25rem;
            margin-bottom: 1rem;
        }}

        .result-header {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 1rem;
            color: #166534;
            font-weight: 600;
        }}

        .result-text {{
            background: white;
            padding: 1rem;
            border-radius: 8px;
            line-height: 1.7;
            color: #333;
            white-space: pre-wrap;
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }}

        .action-buttons {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}

        .post-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            padding: 1rem;
            border-radius: 10px;
            font-size: 0.95rem;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s;
        }}

        .post-btn.google {{
            background: #4285f4;
            color: white;
        }}

        .post-btn.hotpepper {{
            background: #ff6b6b;
            color: white;
        }}

        .post-btn.booking {{
            background: #003580;
            color: white;
        }}

        .post-btn.tripadvisor {{
            background: #00af87;
            color: white;
        }}

        .post-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}

        .copy-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            padding: 0.875rem;
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            color: #495057;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.2s;
        }}

        .copy-btn:hover {{
            background: #f8f9fa;
            border-color: #6366f1;
            color: #6366f1;
        }}

        .settings-link {{
            text-align: center;
            margin-top: 1.5rem;
        }}

        .settings-link a {{
            color: #6c757d;
            text-decoration: none;
            font-size: 0.85rem;
        }}

        .settings-link a:hover {{
            color: #6366f1;
        }}

        .hint {{
            background: #fff3cd;
            border-radius: 8px;
            padding: 0.75rem 1rem;
            font-size: 0.8rem;
            color: #856404;
            margin-top: 1rem;
            display: flex;
            align-items: flex-start;
            gap: 0.5rem;
        }}

        .hint-icon {{
            font-size: 1rem;
        }}

        @media (max-width: 480px) {{
            .main-content {{
                padding: 1rem;
            }}

            .star-rating {{
                font-size: 2rem;
            }}

            .platform-grid {{
                grid-template-columns: 1fr 1fr;
            }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <div class="logo">
                <span>✨</span>
                <span>SmartReview</span>
            </div>
            <div class="lang-switcher">
                <button class="lang-btn active" data-lang="ja" onclick="setLanguage('ja')">日本語</button>
                <button class="lang-btn" data-lang="en" onclick="setLanguage('en')">EN</button>
                <button class="lang-btn" data-lang="zh" onclick="setLanguage('zh')">中文</button>
                <button class="lang-btn" data-lang="ko" onclick="setLanguage('ko')">한국어</button>
            </div>
        </div>
    </header>

    <main class="main-content">
        <div class="step-indicator">
            <div class="step-dot active" data-step="1"></div>
            <div class="step-dot" data-step="2"></div>
            <div class="step-dot" data-step="3"></div>
            <div class="step-dot" data-step="4"></div>
        </div>

        <div class="step-content active" id="step1">
            <div class="card">
                <h2 class="card-title" id="step1Title">投稿先を選択</h2>
                <p class="card-subtitle" id="step1Subtitle">口コミを投稿するサイトを選んでください</p>

                <div class="platform-grid" id="platformGrid"></div>

                <div class="btn-group">
                    <button class="btn btn-primary btn-full" id="step1Next" onclick="nextStep()" disabled>
                        次へ
                    </button>
                </div>
            </div>
        </div>

        <div class="step-content" id="step2">
            <div class="card">
                <h2 class="card-title" id="step2Title">評価を選択</h2>
                <p class="card-subtitle" id="step2Subtitle">お店の評価を星で選んでください</p>

                <div class="star-rating">
                    <span class="star" data-rating="1">★</span>
                    <span class="star" data-rating="2">★</span>
                    <span class="star" data-rating="3">★</span>
                    <span class="star" data-rating="4">★</span>
                    <span class="star" data-rating="5">★</span>
                </div>
                <div class="rating-text" id="ratingText">タップして評価</div>

                <div class="btn-group">
                    <button class="btn btn-secondary" onclick="prevStep()">戻る</button>
                    <button class="btn btn-primary" id="step2Next" onclick="nextStep()" disabled>次へ</button>
                </div>
            </div>
        </div>

        <div class="step-content" id="step3">
            <div class="card">
                <h2 class="card-title" id="step3Title">詳細を教えてください</h2>

                <div class="form-group">
                    <label class="form-label" id="serviceLabel">利用したサービス</label>
                    <div class="services-grid" id="servicesGrid"></div>
                </div>

                <div class="form-group">
                    <label class="form-label" id="commentLabel">コメント（任意）</label>
                    <textarea id="userComment" placeholder="良かった点や気になった点など"></textarea>
                </div>

                <div class="btn-group">
                    <button class="btn btn-secondary" onclick="prevStep()">戻る</button>
                    <button class="btn btn-primary" id="generateBtn" onclick="generateReview()">口コミを生成</button>
                </div>
            </div>
        </div>

        <div class="step-content" id="step4">
            <div class="card">
                <div class="result-card">
                    <div class="result-header">
                        <span>✅</span>
                        <span id="resultTitle">口コミが完成しました！</span>
                    </div>
                    <div class="result-text" id="resultText"></div>
                    <button class="copy-btn" onclick="copyReview()">
                        <span>📋</span>
                        <span id="copyBtnText">コピーする</span>
                    </button>
                </div>

                <div class="action-buttons" id="actionButtons"></div>

                <div class="hint" id="postHint">
                    <span class="hint-icon">💡</span>
                    <span id="hintText">上のボタンをタップすると投稿ページが開きます。コピーした口コミを貼り付けてください。</span>
                </div>

                <div class="btn-group" style="margin-top: 1.5rem;">
                    <button class="btn btn-secondary btn-full" onclick="resetForm()">
                        新しい口コミを作成
                    </button>
                </div>
            </div>
        </div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p style="margin-top: 1rem; color: #6c757d;" id="loadingText">AIが口コミを生成中...</p>
        </div>

        <div class="settings-link">
            <a href="/settings">⚙️ 設定</a>
        </div>
    </main>

    <script>
        const storeData = {{
            name: "{store_data['name']}",
            services: {services_json},
            platformUrls: {platform_urls_json}
        }};

        let currentStep = 1;
        let currentLanguage = 'ja';
        let selectedPlatform = null;
        let selectedRating = 0;
        let selectedServices = [];

        const platforms = {{
            google: {{ name: 'Google Maps', icon: '🗺️', color: '#4285f4' }},
            hotpepper: {{ name: 'ホットペッパー', icon: '💇', color: '#ff6b6b' }},
            booking: {{ name: 'Booking.com', icon: '🏨', color: '#003580' }},
            tripadvisor: {{ name: 'TripAdvisor', icon: '🦉', color: '#00af87' }}
        }};

        const translations = {{
            ja: {{
                step1Title: '投稿先を選択',
                step1Subtitle: '口コミを投稿するサイトを選んでください',
                step2Title: '評価を選択',
                step2Subtitle: 'お店の評価を星で選んでください',
                step3Title: '詳細を教えてください',
                serviceLabel: '利用したサービス',
                commentLabel: 'コメント（任意）',
                commentPlaceholder: '良かった点や気になった点など',
                next: '次へ',
                back: '戻る',
                generate: '口コミを生成',
                loading: 'AIが口コミを生成中...',
                resultTitle: '口コミが完成しました！',
                copyBtn: 'コピーする',
                copied: 'コピーしました！',
                postTo: 'に投稿する',
                hint: '上のボタンをタップすると投稿ページが開きます。コピーした口コミを貼り付けてください。',
                newReview: '新しい口コミを作成',
                notConfigured: '未設定',
                ratingTexts: ['改善が必要', 'やや不満', '普通', '満足', '大変満足'],
                tapToRate: 'タップして評価'
            }},
            en: {{
                step1Title: 'Select Platform',
                step1Subtitle: 'Choose where to post your review',
                step2Title: 'Rate Your Experience',
                step2Subtitle: 'Select a star rating',
                step3Title: 'Tell Us More',
                serviceLabel: 'Services Used',
                commentLabel: 'Comment (Optional)',
                commentPlaceholder: 'What did you like or notice?',
                next: 'Next',
                back: 'Back',
                generate: 'Generate Review',
                loading: 'AI is generating your review...',
                resultTitle: 'Your review is ready!',
                copyBtn: 'Copy',
                copied: 'Copied!',
                postTo: 'Post to ',
                hint: 'Tap the button above to open the review page. Paste your copied review there.',
                newReview: 'Create New Review',
                notConfigured: 'Not set',
                ratingTexts: ['Needs improvement', 'Somewhat dissatisfied', 'Average', 'Satisfied', 'Very satisfied'],
                tapToRate: 'Tap to rate'
            }},
            zh: {{
                step1Title: '选择平台',
                step1Subtitle: '选择您要发布评价的网站',
                step2Title: '选择评分',
                step2Subtitle: '请为店铺打分',
                step3Title: '详细信息',
                serviceLabel: '使用的服务',
                commentLabel: '评论（可选）',
                commentPlaceholder: '您喜欢什么或注意到什么？',
                next: '下一步',
                back: '返回',
                generate: '生成评价',
                loading: 'AI正在生成评价...',
                resultTitle: '评价已生成！',
                copyBtn: '复制',
                copied: '已复制！',
                postTo: '发布到 ',
                hint: '点击上方按钮打开评价页面，粘贴您复制的评价。',
                newReview: '创建新评价',
                notConfigured: '未设置',
                ratingTexts: ['需要改进', '有点不满意', '一般', '满意', '非常满意'],
                tapToRate: '点击评分'
            }},
            ko: {{
                step1Title: '플랫폼 선택',
                step1Subtitle: '리뷰를 게시할 사이트를 선택하세요',
                step2Title: '평가 선택',
                step2Subtitle: '별점을 선택해주세요',
                step3Title: '자세한 정보',
                serviceLabel: '이용한 서비스',
                commentLabel: '코멘트 (선택사항)',
                commentPlaceholder: '좋았던 점이나 느낀 점을 적어주세요',
                next: '다음',
                back: '이전',
                generate: '리뷰 생성',
                loading: 'AI가 리뷰를 생성 중...',
                resultTitle: '리뷰가 완성되었습니다!',
                copyBtn: '복사',
                copied: '복사됨!',
                postTo: '에 게시',
                hint: '위 버튼을 탭하면 리뷰 페이지가 열립니다. 복사한 리뷰를 붙여넣으세요.',
                newReview: '새 리뷰 작성',
                notConfigured: '미설정',
                ratingTexts: ['개선 필요', '약간 불만족', '보통', '만족', '매우 만족'],
                tapToRate: '탭하여 평가'
            }}
        }};

        function init() {{
            renderPlatforms();
            renderServices();
            setupStarRating();
        }}

        function renderPlatforms() {{
            const grid = document.getElementById('platformGrid');
            grid.innerHTML = '';

            Object.entries(platforms).forEach(([key, platform]) => {{
                const url = storeData.platformUrls[key];
                const isConfigured = url && url.length > 0;
                const t = translations[currentLanguage];

                const card = document.createElement('div');
                card.className = 'platform-card' + (isConfigured ? '' : ' disabled');
                card.dataset.platform = key;
                card.innerHTML = `
                    <div class="platform-icon">${{platform.icon}}</div>
                    <div class="platform-name">${{platform.name}}</div>
                    <div class="platform-status">${{isConfigured ? '✓' : t.notConfigured}}</div>
                `;

                if (isConfigured) {{
                    card.onclick = () => selectPlatform(key);
                }}

                grid.appendChild(card);
            }});
        }}

        function renderServices() {{
            const grid = document.getElementById('servicesGrid');
            grid.innerHTML = '';

            storeData.services.forEach(service => {{
                const chip = document.createElement('div');
                chip.className = 'service-chip';
                chip.dataset.service = service;
                chip.textContent = service;
                chip.onclick = () => toggleService(service, chip);
                grid.appendChild(chip);
            }});
        }}

        function setupStarRating() {{
            document.querySelectorAll('.star').forEach(star => {{
                star.addEventListener('click', function() {{
                    selectedRating = parseInt(this.dataset.rating);
                    updateStars();
                    updateRatingText();
                    document.getElementById('step2Next').disabled = false;
                }});
            }});
        }}

        function updateStars() {{
            document.querySelectorAll('.star').forEach((star, index) => {{
                star.classList.toggle('active', index < selectedRating);
            }});
        }}

        function updateRatingText() {{
            const t = translations[currentLanguage];
            const text = selectedRating > 0 ? t.ratingTexts[selectedRating - 1] : t.tapToRate;
            document.getElementById('ratingText').textContent = text;
        }}

        function selectPlatform(platform) {{
            selectedPlatform = platform;
            document.querySelectorAll('.platform-card').forEach(card => {{
                card.classList.toggle('selected', card.dataset.platform === platform);
            }});
            document.getElementById('step1Next').disabled = false;
        }}

        function toggleService(service, chip) {{
            chip.classList.toggle('selected');
            if (chip.classList.contains('selected')) {{
                selectedServices.push(service);
            }} else {{
                selectedServices = selectedServices.filter(s => s !== service);
            }}
        }}

        function nextStep() {{
            if (currentStep < 4) {{
                currentStep++;
                updateStepUI();
            }}
        }}

        function prevStep() {{
            if (currentStep > 1) {{
                currentStep--;
                updateStepUI();
            }}
        }}

        function updateStepUI() {{
            document.querySelectorAll('.step-content').forEach((content, index) => {{
                content.classList.toggle('active', index + 1 === currentStep);
            }});

            document.querySelectorAll('.step-dot').forEach((dot, index) => {{
                dot.classList.remove('active', 'completed');
                if (index + 1 === currentStep) {{
                    dot.classList.add('active');
                }} else if (index + 1 < currentStep) {{
                    dot.classList.add('completed');
                }}
            }});
        }}

        async function generateReview() {{
            const t = translations[currentLanguage];

            document.getElementById('step3').classList.remove('active');
            document.getElementById('loading').classList.add('show');

            try {{
                const response = await fetch('/api/review', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        platform: selectedPlatform,
                        rating: selectedRating,
                        services: selectedServices.length > 0 ? selectedServices : storeData.services.slice(0, 1),
                        user_comment: document.getElementById('userComment').value,
                        language: currentLanguage
                    }})
                }});

                const data = await response.json();

                document.getElementById('resultText').textContent = data.generated_text;
                renderActionButtons();

                document.getElementById('loading').classList.remove('show');
                currentStep = 4;
                updateStepUI();

            }} catch (error) {{
                alert(t.error || 'Error occurred');
                document.getElementById('loading').classList.remove('show');
                document.getElementById('step3').classList.add('active');
            }}
        }}

        function renderActionButtons() {{
            const container = document.getElementById('actionButtons');
            const t = translations[currentLanguage];
            const platform = platforms[selectedPlatform];
            const url = storeData.platformUrls[selectedPlatform];

            container.innerHTML = `
                <a href="${{url}}" target="_blank" class="post-btn ${{selectedPlatform}}">
                    <span>${{platform.icon}}</span>
                    <span>${{platform.name}}${{t.postTo}}</span>
                </a>
            `;
        }}

        function copyReview() {{
            const text = document.getElementById('resultText').textContent;
            const t = translations[currentLanguage];

            navigator.clipboard.writeText(text).then(() => {{
                const btn = document.getElementById('copyBtnText');
                btn.textContent = t.copied;
                setTimeout(() => {{
                    btn.textContent = t.copyBtn;
                }}, 2000);
            }});
        }}

        function resetForm() {{
            currentStep = 1;
            selectedPlatform = null;
            selectedRating = 0;
            selectedServices = [];

            document.querySelectorAll('.platform-card').forEach(c => c.classList.remove('selected'));
            document.querySelectorAll('.star').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.service-chip').forEach(c => c.classList.remove('selected'));
            document.getElementById('userComment').value = '';
            document.getElementById('step1Next').disabled = true;
            document.getElementById('step2Next').disabled = true;

            updateStepUI();
            updateRatingText();
        }}

        function setLanguage(lang) {{
            currentLanguage = lang;
            const t = translations[lang];

            document.querySelectorAll('.lang-btn').forEach(btn => {{
                btn.classList.toggle('active', btn.dataset.lang === lang);
            }});

            document.getElementById('step1Title').textContent = t.step1Title;
            document.getElementById('step1Subtitle').textContent = t.step1Subtitle;
            document.getElementById('step2Title').textContent = t.step2Title;
            document.getElementById('step2Subtitle').textContent = t.step2Subtitle;
            document.getElementById('step3Title').textContent = t.step3Title;
            document.getElementById('serviceLabel').textContent = t.serviceLabel;
            document.getElementById('commentLabel').textContent = t.commentLabel;
            document.getElementById('userComment').placeholder = t.commentPlaceholder;
            document.getElementById('step1Next').textContent = t.next;
            document.getElementById('step2Next').textContent = t.next;
            document.getElementById('generateBtn').textContent = t.generate;
            document.getElementById('loadingText').textContent = t.loading;
            document.getElementById('resultTitle').textContent = t.resultTitle;
            document.getElementById('copyBtnText').textContent = t.copyBtn;
            document.getElementById('hintText').textContent = t.hint;

            document.querySelectorAll('.btn-secondary').forEach(btn => {{
                if (btn.textContent.match(/戻る|Back|返回|이전/)) {{
                    btn.textContent = t.back;
                }}
                if (btn.textContent.match(/新しい|Create|创建|새/)) {{
                    btn.textContent = t.newReview;
                }}
            }});

            updateRatingText();
            renderPlatforms();
        }}

        init();
    </script>
</body>
</html>
"""


# 設定ページHTML
def get_settings_html(is_admin: bool, store_data: dict, stats: dict):
    services_value = "\n".join(store_data.get('services', []))

    return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>設定 - SmartReview AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Noto Sans JP', sans-serif; background: #f8f9fa; min-height: 100vh; }}
        .header {{ background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.08); padding: 1rem 1.5rem; }}
        .header-content {{ max-width: 600px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }}
        .back-link {{ color: #6366f1; text-decoration: none; font-size: 0.95rem; }}
        .page-title {{ font-size: 1.25rem; font-weight: 600; color: #333; }}
        .main-content {{ max-width: 600px; margin: 0 auto; padding: 1.5rem; }}
        .card {{ background: white; border-radius: 16px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 1.5rem; }}
        .card-title {{ font-size: 1.1rem; font-weight: 600; color: #333; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 0.5rem; }}
        .form-group {{ margin-bottom: 1.25rem; }}
        .form-label {{ display: block; font-weight: 500; color: #555; margin-bottom: 0.5rem; font-size: 0.9rem; }}
        input, textarea {{ width: 100%; padding: 0.75rem 1rem; border: 1px solid #dee2e6; border-radius: 8px; font-size: 0.95rem; font-family: inherit; }}
        input:focus, textarea:focus {{ outline: none; border-color: #6366f1; }}
        textarea {{ min-height: 100px; resize: vertical; }}
        .help-text {{ font-size: 0.8rem; color: #6c757d; margin-top: 0.25rem; }}
        .btn {{ display: inline-flex; align-items: center; justify-content: center; padding: 0.875rem 1.5rem; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: all 0.2s; text-decoration: none; }}
        .btn-primary {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; width: 100%; }}
        .btn-primary:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4); }}
        .qr-section {{ text-align: center; padding: 1.5rem; }}
        .qr-code img {{ max-width: 200px; border-radius: 8px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-bottom: 1rem; }}
        .stat-card {{ background: #f8f9fa; padding: 1rem; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 1.5rem; font-weight: 700; color: #6366f1; }}
        .stat-label {{ font-size: 0.8rem; color: #6c757d; margin-top: 0.25rem; }}
        .platform-input {{ margin-bottom: 1rem; }}
        .platform-label {{ display: flex; align-items: center; gap: 0.5rem; font-weight: 500; color: #555; margin-bottom: 0.5rem; font-size: 0.9rem; }}
        .success-message {{ background: #d4edda; color: #155724; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; text-align: center; display: none; font-weight: 500; animation: fadeIn 0.3s ease; }}
        .success-message.show {{ display: block; }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(-10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .login-form {{ text-align: center; padding: 2rem; }}
        .login-form input {{ margin-bottom: 1rem; }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <a href="/" class="back-link">← 戻る</a>
            <h1 class="page-title">設定</h1>
            <div style="width: 60px;"></div>
        </div>
    </header>

    <main class="main-content">
        <div class="success-message" id="successMessage">✅ 保存しました！</div>

        {f'''
        <div class="card">
            <h2 class="card-title">📱 QRコード</h2>
            <div class="qr-section">
                <p style="color: #666; font-size: 0.9rem; margin-bottom: 1rem;">お客様にスキャンしてもらうとレビューページが開きます</p>
                <div class="qr-code">
                    <img src="{generate_qr_code()}" alt="QR Code">
                </div>
            </div>
        </div>

        <div class="card">
            <h2 class="card-title">📊 統計</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{stats["total"]}</div>
                    <div class="stat-label">総レビュー数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{stats["avg_rating"]:.1f}</div>
                    <div class="stat-label">平均評価</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2 class="card-title">🏪 店舗情報</h2>
            <form id="storeForm" onsubmit="saveStore(event)">
                <div class="form-group">
                    <label class="form-label">店舗名</label>
                    <input type="text" id="storeName" value="{store_data['name']}" required>
                </div>
                <div class="form-group">
                    <label class="form-label">説明</label>
                    <textarea id="storeDescription">{store_data['description']}</textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">住所</label>
                    <input type="text" id="storeAddress" value="{store_data['address']}">
                </div>
                <div class="form-group">
                    <label class="form-label">電話番号</label>
                    <input type="text" id="storePhone" value="{store_data['phone']}">
                </div>
                <div class="form-group">
                    <label class="form-label">サービス一覧</label>
                    <textarea id="storeServices" placeholder="1行に1つずつ入力">{services_value}</textarea>
                    <p class="help-text">1行に1つずつサービス名を入力</p>
                </div>
                <button type="submit" class="btn btn-primary">保存する</button>
            </form>
        </div>

        <div class="card">
            <h2 class="card-title">🔗 投稿先URL</h2>
            <form id="platformForm" onsubmit="savePlatforms(event)">
                <div class="platform-input">
                    <label class="platform-label">🗺️ Google Maps</label>
                    <input type="text" id="urlGoogle" value="{store_data['platform_urls'].get('google', '')}" placeholder="https://g.page/...">
                    <p class="help-text">Google マイビジネスの口コミURL（https://は自動補完されます）</p>
                </div>
                <div class="platform-input">
                    <label class="platform-label">💇 ホットペッパービューティー</label>
                    <input type="text" id="urlHotpepper" value="{store_data['platform_urls'].get('hotpepper', '')}" placeholder="https://beauty.hotpepper.jp/...">
                </div>
                <div class="platform-input">
                    <label class="platform-label">🏨 Booking.com</label>
                    <input type="text" id="urlBooking" value="{store_data['platform_urls'].get('booking', '')}" placeholder="https://www.booking.com/...">
                </div>
                <div class="platform-input">
                    <label class="platform-label">🦉 TripAdvisor</label>
                    <input type="text" id="urlTripadvisor" value="{store_data['platform_urls'].get('tripadvisor', '')}" placeholder="https://www.tripadvisor.jp/...">
                </div>
                <button type="submit" class="btn btn-primary">保存する</button>
            </form>
        </div>

        <div class="card">
            <h2 class="card-title">🔐 ログアウト</h2>
            <a href="/settings/logout" class="btn btn-primary" style="background: #dc3545;">ログアウト</a>
        </div>
        ''' if is_admin else '''
        <div class="card">
            <h2 class="card-title">🔐 管理者ログイン</h2>
            <div class="login-form">
                <p style="color: #666; margin-bottom: 1.5rem;">設定を編集するにはログインしてください</p>
                <form onsubmit="login(event)">
                    <input type="password" id="password" placeholder="パスワード" required>
                    <button type="submit" class="btn btn-primary">ログイン</button>
                </form>
            </div>
        </div>
        '''}
    </main>

    <script>
        async function login(e) {{
            e.preventDefault();
            const password = document.getElementById('password').value;
            try {{
                const response = await fetch('/api/login', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ password: password }}),
                    credentials: 'same-origin'
                }});
                if (response.ok) {{
                    window.location.reload();
                }} else {{
                    alert('パスワードが正しくありません');
                }}
            }} catch (error) {{
                alert('ログインエラー: ' + error.message);
            }}
        }}

        function normalizeUrl(url) {{
            if (!url || url.trim() === '') return '';
            url = url.trim();
            if (url && !url.startsWith('http://') && !url.startsWith('https://')) {{
                return 'https://' + url;
            }}
            return url;
        }}

        async function saveStore(e) {{
            e.preventDefault();
            const services = document.getElementById('storeServices').value.split('\\n').map(s => s.trim()).filter(s => s);

            const googleUrl = normalizeUrl(document.getElementById('urlGoogle').value);
            const hotpepperUrl = normalizeUrl(document.getElementById('urlHotpepper').value);
            const bookingUrl = normalizeUrl(document.getElementById('urlBooking').value);
            const tripadvisorUrl = normalizeUrl(document.getElementById('urlTripadvisor').value);

            document.getElementById('urlGoogle').value = googleUrl;
            document.getElementById('urlHotpepper').value = hotpepperUrl;
            document.getElementById('urlBooking').value = bookingUrl;
            document.getElementById('urlTripadvisor').value = tripadvisorUrl;

            const response = await fetch('/api/store', {{
                method: 'PUT',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    name: document.getElementById('storeName').value,
                    description: document.getElementById('storeDescription').value,
                    address: document.getElementById('storeAddress').value,
                    phone: document.getElementById('storePhone').value,
                    services: services,
                    platform_urls: {{
                        google: googleUrl,
                        hotpepper: hotpepperUrl,
                        booking: bookingUrl,
                        tripadvisor: tripadvisorUrl
                    }}
                }})
            }});
            if (response.ok) {{
                document.getElementById('successMessage').classList.add('show');
                setTimeout(() => document.getElementById('successMessage').classList.remove('show'), 3000);
            }}
        }}

        async function savePlatforms(e) {{
            e.preventDefault();
            await saveStore({{ preventDefault: () => {{}} }});
        }}
    </script>
</body>
</html>
"""


# ================== API Routes ==================

@app.get("/", response_class=HTMLResponse)
async def home(db: Session = Depends(get_db)):
    store_data = get_store_dict(db)
    return get_main_html(store_data)


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    session_id: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    is_admin = validate_session(db, session_id)
    store_data = get_store_dict(db)
    stats = get_review_stats(db)
    print(f"[DEBUG] Settings page - is_admin: {is_admin}")
    return get_settings_html(is_admin, store_data, stats)


@app.get("/settings/logout")
async def logout(response: Response, db: Session = Depends(get_db), session_id: Optional[str] = Cookie(None)):
    if session_id:
        # DBからセッション削除
        session = db.query(AdminSession).filter(AdminSession.token == session_id).first()
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(key="session_id")
    return RedirectResponse(url="/settings", status_code=303)


@app.post("/api/login")
async def login(request: Request, response: Response, db: Session = Depends(get_db)):
    data = await request.json()
    input_password = data.get("password", "")

    if input_password == ADMIN_PASSWORD:
        # 新しいセッションをDBに保存
        token = secrets.token_urlsafe(32)
        session = AdminSession.create_session(token)
        db.add(session)
        db.commit()

        response.set_cookie(
            key="session_id",
            value=token,
            max_age=3600,
            httponly=True,
            samesite="lax"
        )
        print(f"[DEBUG] Login success - Session: {token[:8]}...")
        return {"status": "success"}

    print(f"[DEBUG] Login failed")
    raise HTTPException(status_code=401, detail="Invalid password")


@app.put("/api/store")
async def update_store(
    store_data: StoreUpdate,
    session_id: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    if not validate_session(db, session_id):
        raise HTTPException(status_code=401, detail="Unauthorized")

    store = get_store(db)
    store.name = store_data.name
    store.description = store_data.description
    store.address = store_data.address
    store.phone = store_data.phone
    store.services = store_data.services
    store.platform_urls = store_data.platform_urls
    store.updated_at = datetime.utcnow()

    db.commit()
    print(f"[DEBUG] Store updated: {store.name}")
    return {"status": "success"}


@app.get("/api/store")
async def api_get_store(db: Session = Depends(get_db)):
    return get_store_dict(db)


@app.post("/api/review")
async def generate_review(review: ReviewRequest, db: Session = Depends(get_db)):
    store = get_store(db)
    store_dict = store.to_dict()

    platform = review.platform
    services_text = "、".join(review.services) if review.language in ["ja", "zh"] else ", ".join(review.services)

    # レビュー生成ロジック（テンプレートベース）
    if review.language == "en":
        if review.rating >= 4:
            if platform == "tripadvisor":
                generated_text = f"""Excellent experience at {store_dict['name']}!

I visited for {services_text} and was thoroughly impressed. The staff were professional and attentive throughout my visit.

The facility was clean and well-maintained. Located at {store_dict['address']}, it's easily accessible.

What stood out:
• Outstanding {review.services[0]} service
• Friendly and knowledgeable staff
• Clean and comfortable environment

Highly recommended for anyone looking for quality {review.services[0]}!"""
            elif platform == "booking":
                generated_text = f"""Great stay! The {services_text} exceeded my expectations.

Pros:
+ Professional staff
+ Excellent {review.services[0]}
+ Great location at {store_dict['address']}

Would definitely return!"""
            else:
                generated_text = f"""Had an amazing experience at {store_dict['name']}!

The {services_text} was fantastic. Staff were super friendly and professional.

Definitely coming back! ⭐"""
        else:
            generated_text = f"""Visited {store_dict['name']} for {services_text}.

The service was okay but there's room for improvement. The {review.services[0]} could be better.

Location is convenient at {store_dict['address']}."""

    elif review.language == "zh":
        if review.rating >= 4:
            generated_text = f"""在{store_dict['name']}体验了{services_text}，非常满意！

工作人员专业又热情，{review.services[0]}效果很棒。

店铺位于{store_dict['address']}，交通很方便。

强烈推荐！下次一定会再来！"""
        else:
            generated_text = f"""去{store_dict['name']}体验了{services_text}。

服务还可以，但{review.services[0]}还有提升空间。

位置在{store_dict['address']}，交通便利。"""

    elif review.language == "ko":
        if review.rating >= 4:
            generated_text = f"""{store_dict['name']}에서 {services_text} 받았는데 정말 좋았어요!

직원분들이 친절하고 전문적이에요. 특히 {review.services[0]}가 마음에 들었습니다.

위치도 {store_dict['address']}라서 찾아가기 쉬워요.

꼭 다시 방문하고 싶습니다! 추천해요 ⭐"""
        else:
            generated_text = f"""{store_dict['name']}에서 {services_text} 이용했습니다.

서비스는 괜찮았지만 {review.services[0]}는 개선이 필요할 것 같아요.

위치는 {store_dict['address']}로 접근성이 좋습니다."""

    else:  # Japanese
        if review.rating >= 4:
            if platform == "hotpepper":
                generated_text = f"""{store_dict['name']}で{services_text}を受けました♪

スタッフさんがとても丁寧で、カウンセリングもしっかりしてくれました。
{review.services[0]}の効果を実感できて大満足です！

店内も清潔で落ち着いた雰囲気でした。
{store_dict['address']}でアクセスも良いので、また通いたいと思います。

おすすめです♡"""
            elif platform == "tripadvisor":
                generated_text = f"""【{store_dict['name']}】{services_text}体験レポート

■良かった点
・{review.services[0]}の技術が高い
・スタッフの対応が丁寧
・清潔感のある店内
・{store_dict['address']}でアクセス良好

■総評
期待以上のサービスでした。特に{review.services[0]}は他店と比べても質が高いと感じました。

また利用したいと思います。"""
            else:
                generated_text = f"""{store_dict['name']}で{services_text}を体験しました！

スタッフさんの対応が丁寧で、{review.services[0]}の効果もしっかり実感できました。

{store_dict['address']}という好立地で通いやすいです。

また行きたいと思います！おすすめです⭐"""
        else:
            generated_text = f"""{store_dict['name']}で{services_text}を利用しました。

サービス自体は悪くありませんでしたが、{review.services[0]}についてはもう少し改善を期待します。

{store_dict['address']}で場所は便利です。"""

    # レビューをDBに保存
    new_review = Review(
        store_id=store.store_id,
        platform=platform,
        rating=review.rating,
        services=review.services,
        user_comment=review.user_comment,
        generated_text=generated_text,
        language=review.language
    )
    db.add(new_review)
    db.commit()
    print(f"[DEBUG] Review saved: {new_review.id}")

    return {
        "generated_text": generated_text,
        "platform_url": store_dict["platform_urls"].get(platform, "")
    }


# ヘルスチェックエンドポイント
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Coolify/Kubernetes用ヘルスチェック"""
    from sqlalchemy import text
    try:
        # DBへの疎通確認
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
