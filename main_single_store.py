from fastapi import FastAPI, HTTPException, Request, Cookie, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, RedirectResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
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
    description="AI口コミ生成システム - 単一店舗版",
    version="7.0.0"
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

# 単一店舗データ（設定から編集可能）
STORE = {
    "store_id": "main-store",
    "name": "Beauty Salon SAKURA",
    "description": "最新の美容機器を完備した完全個室プライベートサロン",
    "address": "東京都渋谷区表参道1-2-3",
    "phone": "03-1234-5678",
    "services": ["ハイフ", "リフトアップ", "フェイシャル", "ボディケア", "脱毛"],
    "google_review_url": "",
    "created_at": datetime.now().isoformat()
}

REVIEWS = []

# Pydanticモデル
class ReviewRequest(BaseModel):
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
    google_review_url: Optional[str] = ""

# QRコード生成
def generate_qr_code() -> str:
    base_url = os.getenv("BASE_URL", "https://smartreview-simple-208894137644.us-central1.run.app")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(base_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{img_str}"

# メインページHTML
def get_main_html():
    return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{STORE['name']} - レビュー</title>
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
            max-width: 600px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .logo {{
            font-size: 1.25rem;
            font-weight: 700;
            color: #333;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .logo-icon {{
            font-size: 1.5rem;
        }}

        .lang-switcher {{
            display: flex;
            gap: 0.25rem;
            background: #f1f3f5;
            padding: 0.25rem;
            border-radius: 8px;
        }}

        .lang-btn {{
            padding: 0.4rem 0.8rem;
            background: transparent;
            border: none;
            color: #6c757d;
            font-size: 0.8rem;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.2s;
        }}

        .lang-btn:hover {{
            background: white;
        }}

        .lang-btn.active {{
            background: white;
            color: #6366f1;
            font-weight: 500;
        }}

        .main-content {{
            max-width: 600px;
            margin: 0 auto;
            padding: 1.5rem;
        }}

        .store-card {{
            background: white;
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 1.5rem;
        }}

        .store-name {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #333;
            margin-bottom: 0.5rem;
        }}

        .store-description {{
            color: #666;
            font-size: 0.95rem;
            line-height: 1.6;
            margin-bottom: 1rem;
        }}

        .store-info {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            color: #555;
            font-size: 0.9rem;
        }}

        .store-info-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .card {{
            background: white;
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 1.5rem;
        }}

        .card-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: #333;
            margin-bottom: 1.5rem;
            text-align: center;
        }}

        .form-group {{
            margin-bottom: 1.5rem;
        }}

        .form-label {{
            display: block;
            font-weight: 500;
            color: #555;
            margin-bottom: 0.75rem;
            font-size: 0.95rem;
        }}

        /* 星評価 */
        .star-rating {{
            display: flex;
            gap: 0.5rem;
            justify-content: center;
            font-size: 2.5rem;
            margin: 1rem 0;
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
            margin-top: 0.5rem;
        }}

        /* サービス選択 */
        .services-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}

        .service-chip {{
            padding: 0.5rem 1rem;
            background: #f1f3f5;
            border: 2px solid transparent;
            border-radius: 20px;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s;
            color: #555;
        }}

        .service-chip:hover {{
            background: #e9ecef;
        }}

        .service-chip.selected {{
            background: #6366f1;
            color: white;
            border-color: #6366f1;
        }}

        /* テキストエリア */
        textarea {{
            width: 100%;
            padding: 0.75rem 1rem;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            font-size: 0.95rem;
            font-family: inherit;
            resize: vertical;
            min-height: 100px;
            transition: border-color 0.2s;
        }}

        textarea:focus {{
            outline: none;
            border-color: #6366f1;
        }}

        /* ボタン */
        .btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.875rem 1.5rem;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
        }}

        .btn-primary {{
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: white;
            width: 100%;
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

        /* ローディング */
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

        /* 結果表示 */
        .result {{
            display: none;
            margin-top: 1.5rem;
        }}

        .result.show {{
            display: block;
        }}

        .result-card {{
            background: linear-gradient(135deg, #f8f9ff 0%, #f0f4ff 100%);
            border: 1px solid #e0e7ff;
            border-radius: 12px;
            padding: 1.5rem;
        }}

        .result-title {{
            font-weight: 600;
            color: #4f46e5;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .result-text {{
            background: white;
            padding: 1rem;
            border-radius: 8px;
            line-height: 1.8;
            color: #333;
            white-space: pre-wrap;
            font-size: 0.95rem;
        }}

        .copy-btn {{
            margin-top: 1rem;
            padding: 0.75rem 1.5rem;
            background: white;
            border: 1px solid #6366f1;
            color: #6366f1;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.2s;
        }}

        .copy-btn:hover {{
            background: #6366f1;
            color: white;
        }}

        /* 設定リンク */
        .settings-link {{
            text-align: center;
            margin-top: 2rem;
            padding-top: 1.5rem;
            border-top: 1px solid #e9ecef;
        }}

        .settings-link a {{
            color: #6c757d;
            text-decoration: none;
            font-size: 0.9rem;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .settings-link a:hover {{
            color: #6366f1;
        }}

        /* レスポンシブ */
        @media (max-width: 480px) {{
            .header-content {{
                padding: 0;
            }}

            .main-content {{
                padding: 1rem;
            }}

            .store-name {{
                font-size: 1.25rem;
            }}

            .star-rating {{
                font-size: 2rem;
            }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <div class="logo">
                <span class="logo-icon">✨</span>
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
        <!-- 店舗情報 -->
        <div class="store-card">
            <h1 class="store-name">{STORE['name']}</h1>
            <p class="store-description">{STORE['description']}</p>
            <div class="store-info">
                <div class="store-info-item">
                    <span>📍</span>
                    <span>{STORE['address']}</span>
                </div>
                <div class="store-info-item">
                    <span>📞</span>
                    <span>{STORE['phone']}</span>
                </div>
            </div>
        </div>

        <!-- レビューフォーム -->
        <div class="card">
            <h2 class="card-title" id="formTitle">口コミを作成</h2>

            <div class="form-group">
                <label class="form-label" id="ratingLabel">評価を選択してください</label>
                <div class="star-rating">
                    <span class="star" data-rating="1">★</span>
                    <span class="star" data-rating="2">★</span>
                    <span class="star" data-rating="3">★</span>
                    <span class="star" data-rating="4">★</span>
                    <span class="star" data-rating="5">★</span>
                </div>
                <div class="rating-text" id="ratingText">タップして評価</div>
            </div>

            <div class="form-group">
                <label class="form-label" id="serviceLabel">ご利用されたサービス</label>
                <div class="services-grid" id="servicesGrid">
                    {''.join([f'<div class="service-chip" data-service="{s}">{s}</div>' for s in STORE['services']])}
                </div>
            </div>

            <div class="form-group">
                <label class="form-label" id="commentLabel">コメント（任意）</label>
                <textarea id="userComment" placeholder="ご感想をお聞かせください..."></textarea>
            </div>

            <button class="btn btn-primary" id="generateBtn" onclick="generateReview()">
                AI口コミを生成
            </button>

            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p style="margin-top: 1rem; color: #6c757d;" id="loadingText">AI生成中...</p>
            </div>

            <div class="result" id="result">
                <div class="result-card">
                    <div class="result-title">
                        <span>✅</span>
                        <span id="resultTitle">口コミが生成されました！</span>
                    </div>
                    <div class="result-text" id="resultText"></div>
                    <button class="copy-btn" onclick="copyReview()" id="copyBtn">📋 コピーする</button>
                </div>
            </div>
        </div>

        <div class="settings-link">
            <a href="/settings">⚙️ <span id="settingsText">設定</span></a>
        </div>
    </main>

    <script>
        let currentLanguage = 'ja';
        let selectedRating = 0;
        let selectedServices = [];

        // 多言語対応テキスト
        const translations = {{
            ja: {{
                formTitle: '口コミを作成',
                ratingLabel: '評価を選択してください',
                ratingText: 'タップして評価',
                ratingTexts: ['改善が必要', 'やや不満', '普通', '満足', '大変満足'],
                serviceLabel: 'ご利用されたサービス',
                commentLabel: 'コメント（任意）',
                commentPlaceholder: 'ご感想をお聞かせください...',
                generateBtn: 'AI口コミを生成',
                loadingText: 'AI生成中...',
                resultTitle: '口コミが生成されました！',
                copyBtn: '📋 コピーする',
                copied: '✅ コピーしました！',
                settings: '設定',
                error: 'エラーが発生しました',
                selectRating: '評価を選択してください',
                selectService: 'サービスを選択してください'
            }},
            en: {{
                formTitle: 'Create Review',
                ratingLabel: 'Please select a rating',
                ratingText: 'Tap to rate',
                ratingTexts: ['Needs improvement', 'Somewhat dissatisfied', 'Average', 'Satisfied', 'Very satisfied'],
                serviceLabel: 'Service used',
                commentLabel: 'Comment (optional)',
                commentPlaceholder: 'Please share your thoughts...',
                generateBtn: 'Generate AI Review',
                loadingText: 'Generating...',
                resultTitle: 'Review generated!',
                copyBtn: '📋 Copy',
                copied: '✅ Copied!',
                settings: 'Settings',
                error: 'An error occurred',
                selectRating: 'Please select a rating',
                selectService: 'Please select a service'
            }},
            zh: {{
                formTitle: '创建评价',
                ratingLabel: '请选择评分',
                ratingText: '点击评分',
                ratingTexts: ['需要改进', '有点不满意', '一般', '满意', '非常满意'],
                serviceLabel: '使用的服务',
                commentLabel: '评论（可选）',
                commentPlaceholder: '请分享您的想法...',
                generateBtn: '生成AI评价',
                loadingText: '正在生成...',
                resultTitle: '评价生成成功！',
                copyBtn: '📋 复制',
                copied: '✅ 已复制！',
                settings: '设置',
                error: '发生错误',
                selectRating: '请选择评分',
                selectService: '请选择服务'
            }},
            ko: {{
                formTitle: '리뷰 작성',
                ratingLabel: '평가를 선택해주세요',
                ratingText: '탭하여 평가',
                ratingTexts: ['개선 필요', '약간 불만족', '보통', '만족', '매우 만족'],
                serviceLabel: '이용하신 서비스',
                commentLabel: '코멘트 (선택사항)',
                commentPlaceholder: '의견을 공유해주세요...',
                generateBtn: 'AI 리뷰 생성',
                loadingText: '생성 중...',
                resultTitle: '리뷰가 생성되었습니다!',
                copyBtn: '📋 복사',
                copied: '✅ 복사됨!',
                settings: '설정',
                error: '오류가 발생했습니다',
                selectRating: '평가를 선택해주세요',
                selectService: '서비스를 선택해주세요'
            }}
        }};

        function setLanguage(lang) {{
            currentLanguage = lang;
            const t = translations[lang];

            // ボタンのアクティブ状態を更新
            document.querySelectorAll('.lang-btn').forEach(btn => {{
                btn.classList.remove('active');
                if (btn.dataset.lang === lang) btn.classList.add('active');
            }});

            // テキストを更新
            document.getElementById('formTitle').textContent = t.formTitle;
            document.getElementById('ratingLabel').textContent = t.ratingLabel;
            document.getElementById('serviceLabel').textContent = t.serviceLabel;
            document.getElementById('commentLabel').textContent = t.commentLabel;
            document.getElementById('userComment').placeholder = t.commentPlaceholder;
            document.getElementById('generateBtn').textContent = t.generateBtn;
            document.getElementById('loadingText').textContent = t.loadingText;
            document.getElementById('resultTitle').textContent = t.resultTitle;
            document.getElementById('copyBtn').textContent = t.copyBtn;
            document.getElementById('settingsText').textContent = t.settings;

            updateRatingText();
        }}

        function updateRatingText() {{
            const t = translations[currentLanguage];
            if (selectedRating === 0) {{
                document.getElementById('ratingText').textContent = t.ratingText;
            }} else {{
                document.getElementById('ratingText').textContent = t.ratingTexts[selectedRating - 1];
            }}
        }}

        // 星評価の設定
        document.querySelectorAll('.star').forEach(star => {{
            star.addEventListener('click', function() {{
                selectedRating = parseInt(this.dataset.rating);
                document.querySelectorAll('.star').forEach((s, index) => {{
                    s.classList.toggle('active', index < selectedRating);
                }});
                updateRatingText();
            }});
        }});

        // サービス選択
        document.querySelectorAll('.service-chip').forEach(chip => {{
            chip.addEventListener('click', function() {{
                this.classList.toggle('selected');
                const service = this.dataset.service;
                if (this.classList.contains('selected')) {{
                    selectedServices.push(service);
                }} else {{
                    selectedServices = selectedServices.filter(s => s !== service);
                }}
            }});
        }});

        async function generateReview() {{
            const t = translations[currentLanguage];

            if (selectedRating === 0) {{
                alert(t.selectRating);
                return;
            }}
            if (selectedServices.length === 0) {{
                alert(t.selectService);
                return;
            }}

            document.getElementById('loading').classList.add('show');
            document.getElementById('result').classList.remove('show');
            document.getElementById('generateBtn').disabled = true;

            try {{
                const response = await fetch('/api/review', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        rating: selectedRating,
                        services: selectedServices,
                        user_comment: document.getElementById('userComment').value,
                        language: currentLanguage
                    }})
                }});

                const data = await response.json();

                document.getElementById('resultText').textContent = data.generated_text;
                document.getElementById('result').classList.add('show');
            }} catch (error) {{
                alert(t.error);
            }} finally {{
                document.getElementById('loading').classList.remove('show');
                document.getElementById('generateBtn').disabled = false;
            }}
        }}

        function copyReview() {{
            const text = document.getElementById('resultText').textContent;
            navigator.clipboard.writeText(text).then(() => {{
                const btn = document.getElementById('copyBtn');
                const t = translations[currentLanguage];
                btn.textContent = t.copied;
                setTimeout(() => {{
                    btn.textContent = t.copyBtn;
                }}, 2000);
            }});
        }}
    </script>
</body>
</html>
"""

# 設定ページHTML
def get_settings_html(is_admin: bool = False):
    services_value = "\\n".join(STORE['services'])

    return f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>設定 - SmartReview AI</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Noto Sans JP', sans-serif;
            background: #f8f9fa;
            min-height: 100vh;
        }}

        .header {{
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.08);
            padding: 1rem 1.5rem;
        }}

        .header-content {{
            max-width: 600px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .back-link {{
            color: #6366f1;
            text-decoration: none;
            font-size: 0.95rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .back-link:hover {{
            text-decoration: underline;
        }}

        .page-title {{
            font-size: 1.25rem;
            font-weight: 600;
            color: #333;
        }}

        .main-content {{
            max-width: 600px;
            margin: 0 auto;
            padding: 1.5rem;
        }}

        .card {{
            background: white;
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            margin-bottom: 1.5rem;
        }}

        .card-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: #333;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .form-group {{
            margin-bottom: 1.25rem;
        }}

        .form-label {{
            display: block;
            font-weight: 500;
            color: #555;
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
        }}

        input, textarea {{
            width: 100%;
            padding: 0.75rem 1rem;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            font-size: 0.95rem;
            font-family: inherit;
            transition: border-color 0.2s;
        }}

        input:focus, textarea:focus {{
            outline: none;
            border-color: #6366f1;
        }}

        textarea {{
            min-height: 100px;
            resize: vertical;
        }}

        .help-text {{
            font-size: 0.8rem;
            color: #6c757d;
            margin-top: 0.25rem;
        }}

        .btn {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.875rem 1.5rem;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
        }}

        .btn-primary {{
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: white;
            width: 100%;
        }}

        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
        }}

        .qr-section {{
            text-align: center;
            padding: 1.5rem;
        }}

        .qr-code {{
            max-width: 200px;
            margin: 1rem auto;
        }}

        .qr-code img {{
            width: 100%;
            border-radius: 8px;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
            margin-bottom: 1rem;
        }}

        .stat-card {{
            background: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
        }}

        .stat-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #6366f1;
        }}

        .stat-label {{
            font-size: 0.8rem;
            color: #6c757d;
            margin-top: 0.25rem;
        }}

        .login-form {{
            text-align: center;
            padding: 2rem;
        }}

        .login-form input {{
            margin-bottom: 1rem;
        }}

        .success-message {{
            background: #d4edda;
            color: #155724;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            text-align: center;
            display: none;
        }}

        .success-message.show {{
            display: block;
        }}
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
        {'<div class="success-message" id="successMessage">保存しました！</div>' if is_admin else ''}

        {f'''
        <!-- QRコード -->
        <div class="card">
            <h2 class="card-title">📱 QRコード</h2>
            <div class="qr-section">
                <p style="color: #666; font-size: 0.9rem; margin-bottom: 1rem;">お客様にこのQRコードをスキャンしてもらうとレビューページが開きます</p>
                <div class="qr-code">
                    <img src="{generate_qr_code()}" alt="QR Code">
                </div>
            </div>
        </div>

        <!-- 統計 -->
        <div class="card">
            <h2 class="card-title">📊 統計</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{len(REVIEWS)}</div>
                    <div class="stat-label">総レビュー数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{sum(r.get("rating", 0) for r in REVIEWS) / len(REVIEWS) if REVIEWS else 0:.1f}</div>
                    <div class="stat-label">平均評価</div>
                </div>
            </div>
        </div>

        <!-- 店舗情報編集 -->
        <div class="card">
            <h2 class="card-title">🏪 店舗情報</h2>
            <form id="storeForm" onsubmit="saveStore(event)">
                <div class="form-group">
                    <label class="form-label">店舗名</label>
                    <input type="text" id="storeName" value="{STORE['name']}" required>
                </div>

                <div class="form-group">
                    <label class="form-label">説明</label>
                    <textarea id="storeDescription">{STORE['description']}</textarea>
                </div>

                <div class="form-group">
                    <label class="form-label">住所</label>
                    <input type="text" id="storeAddress" value="{STORE['address']}">
                </div>

                <div class="form-group">
                    <label class="form-label">電話番号</label>
                    <input type="text" id="storePhone" value="{STORE['phone']}">
                </div>

                <div class="form-group">
                    <label class="form-label">サービス一覧</label>
                    <textarea id="storeServices" placeholder="1行に1つずつ入力">{services_value}</textarea>
                    <p class="help-text">1行に1つずつサービス名を入力してください</p>
                </div>

                <div class="form-group">
                    <label class="form-label">Google口コミURL（任意）</label>
                    <input type="text" id="googleReviewUrl" value="{STORE.get('google_review_url', '')}" placeholder="https://g.page/...">
                    <p class="help-text">入力するとレビュー生成後にGoogleへの投稿リンクが表示されます</p>
                </div>

                <button type="submit" class="btn btn-primary">保存する</button>
            </form>
        </div>

        <div class="card">
            <h2 class="card-title">🔐 ログアウト</h2>
            <a href="/settings/logout" class="btn btn-primary" style="background: #dc3545;">ログアウト</a>
        </div>
        ''' if is_admin else f'''
        <!-- ログインフォーム -->
        <div class="card">
            <h2 class="card-title">🔐 管理者ログイン</h2>
            <div class="login-form">
                <p style="color: #666; margin-bottom: 1.5rem;">店舗情報を編集するにはログインしてください</p>
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

            const response = await fetch('/api/login', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ password }})
            }});

            if (response.ok) {{
                window.location.reload();
            }} else {{
                alert('パスワードが正しくありません');
            }}
        }}

        async function saveStore(e) {{
            e.preventDefault();

            const services = document.getElementById('storeServices').value
                .split('\\n')
                .map(s => s.trim())
                .filter(s => s.length > 0);

            const data = {{
                name: document.getElementById('storeName').value,
                description: document.getElementById('storeDescription').value,
                address: document.getElementById('storeAddress').value,
                phone: document.getElementById('storePhone').value,
                services: services,
                google_review_url: document.getElementById('googleReviewUrl').value
            }};

            const response = await fetch('/api/store', {{
                method: 'PUT',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(data)
            }});

            if (response.ok) {{
                document.getElementById('successMessage').classList.add('show');
                setTimeout(() => {{
                    document.getElementById('successMessage').classList.remove('show');
                }}, 3000);
            }} else {{
                alert('保存に失敗しました');
            }}
        }}
    </script>
</body>
</html>
"""

# ルート
@app.get("/", response_class=HTMLResponse)
async def home():
    return get_main_html()

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(session_id: Optional[str] = Cookie(None)):
    is_admin = session_id and session_id in ADMIN_SESSIONS
    return get_settings_html(is_admin)

@app.get("/settings/logout")
async def logout(response: Response):
    response.delete_cookie(key="session_id")
    return RedirectResponse(url="/settings", status_code=303)

@app.post("/api/login")
async def login(request: Request, response: Response):
    data = await request.json()
    if data.get("password") == ADMIN_PASSWORD:
        session_id = secrets.token_urlsafe(32)
        ADMIN_SESSIONS[session_id] = {"created_at": datetime.now().isoformat()}
        response.set_cookie(key="session_id", value=session_id, max_age=3600, httponly=True)
        return {"status": "success"}
    raise HTTPException(status_code=401, detail="Invalid password")

@app.put("/api/store")
async def update_store(store_data: StoreUpdate, session_id: Optional[str] = Cookie(None)):
    if not session_id or session_id not in ADMIN_SESSIONS:
        raise HTTPException(status_code=401, detail="Unauthorized")

    global STORE
    STORE.update({
        "name": store_data.name,
        "description": store_data.description,
        "address": store_data.address,
        "phone": store_data.phone,
        "services": store_data.services,
        "google_review_url": store_data.google_review_url or ""
    })

    return {"status": "success"}

@app.get("/api/store")
async def get_store():
    return STORE

@app.post("/api/review")
async def generate_review(review: ReviewRequest):
    services_text = "、".join(review.services) if review.language in ["ja", "zh"] else ", ".join(review.services)

    # 言語別のレビューテンプレート
    if review.language == "en":
        if review.rating >= 4:
            generated_text = f"""I experienced {services_text} at {STORE['name']}.

The staff were wonderful and very professional. The service quality exceeded my expectations.

I especially felt the effects of {review.services[0]} and am very satisfied with the results.

The location at {STORE['address']} is also very convenient. I would definitely recommend this place!"""
        else:
            generated_text = f"""I tried {services_text} at {STORE['name']}.

The service was decent, but there's room for improvement. I hope the quality of {review.services[0]} can be enhanced.

The staff were polite, but I felt the experience could be better."""

    elif review.language == "zh":
        if review.rating >= 4:
            generated_text = f"""在{STORE['name']}体验了{services_text}。

工作人员非常专业，服务质量超出了我的期望。

特别是{review.services[0]}的效果非常明显，我对结果非常满意。

位于{STORE['address']}的位置也很方便。强烈推荐！"""
        else:
            generated_text = f"""在{STORE['name']}尝试了{services_text}。

服务还可以，但还有改进的空间。希望{review.services[0]}的质量能够提升。

工作人员态度不错，但整体体验可以更好。"""

    elif review.language == "ko":
        if review.rating >= 4:
            generated_text = f"""{STORE['name']}에서 {services_text}를 체험했습니다.

직원분들이 정말 친절하고 전문적이었습니다. 서비스 품질이 기대 이상이었어요.

특히 {review.services[0]}의 효과를 확실히 느낄 수 있어서 매우 만족합니다.

{STORE['address']}에 위치해 있어 접근성도 좋습니다. 강력 추천합니다!"""
        else:
            generated_text = f"""{STORE['name']}에서 {services_text}를 이용했습니다.

서비스는 괜찮았지만 개선의 여지가 있다고 생각합니다. {review.services[0]}의 품질이 더 좋아지면 좋겠습니다.

직원분들은 친절했지만 전체적인 경험은 더 나아질 수 있을 것 같습니다."""

    else:  # Japanese (default)
        if review.rating >= 4:
            generated_text = f"""{STORE['name']}で{services_text}を体験しました。

スタッフの方々がとても親切で、施術も丁寧でした。サービスの質が期待以上で大変満足しています。

特に{review.services[0]}の効果を実感でき、とても嬉しいです。

{STORE['address']}というアクセスの良さも魅力的です。ぜひまた利用したいと思います！"""
        else:
            generated_text = f"""{STORE['name']}で{services_text}を利用しました。

サービス自体は悪くありませんでしたが、改善の余地があると感じました。
特に{review.services[0]}については、もう少し質を向上させていただければと思います。

スタッフの対応は丁寧でしたが、全体的にはもう少し改善を期待します。"""

    # レビューを保存
    review_data = {
        "id": str(uuid.uuid4()),
        "rating": review.rating,
        "services": review.services,
        "user_comment": review.user_comment,
        "language": review.language,
        "generated_text": generated_text,
        "created_at": datetime.now().isoformat()
    }
    REVIEWS.append(review_data)

    return {
        "generated_text": generated_text,
        "google_review_url": STORE.get("google_review_url", "")
    }

@app.get("/api/qr")
async def get_qr_code():
    return {"qr_code": generate_qr_code()}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
