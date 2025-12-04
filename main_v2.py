from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
import openai
from dotenv import load_dotenv
import json
import uuid

# 環境変数読み込み
load_dotenv()

app = FastAPI(
    title="SmartReview AI API",
    description="AI口コミ生成システム - Cloud Run単体実装版",
    version="4.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# HTMLインターフェース（Cloud Run単体で動作）
HTML_INTERFACE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartReview AI</title>
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
        
        .language-switcher {
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
            z-index: 1000;
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
        
        .container {
            max-width: 500px;
            width: 100%;
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        
        h1 {
            text-align: center;
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .store-info {
            background: #f5f5f5;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 25px;
        }
        
        .store-name {
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }
        
        .store-address {
            color: #666;
            font-size: 14px;
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
            position: relative;
        }
        
        .star:hover {
            transform: scale(1.2);
        }
        
        .star.active {
            color: #ffd700;
            animation: starPulse 0.3s ease;
        }
        
        .star.preview {
            color: #ffed4e;
        }
        
        @keyframes starPulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.3); }
            100% { transform: scale(1); }
        }
        
        .rating-text {
            text-align: center;
            color: #666;
            font-size: 16px;
            margin-top: 10px;
            font-weight: bold;
            min-height: 24px;
        }
        
        .rating-text.rated-1 { color: #d32f2f; }
        .rating-text.rated-2 { color: #f57c00; }
        .rating-text.rated-3 { color: #fbc02d; }
        .rating-text.rated-4 { color: #689f38; }
        .rating-text.rated-5 { color: #388e3c; }
        
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
        
        textarea:focus {
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
        
        .result {
            margin-top: 20px;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 15px;
            border: 2px solid #e0e0e0;
            display: none;
        }
        
        .result.show {
            display: block;
        }
        
        .result-title {
            font-weight: bold;
            color: #333;
            margin-bottom: 15px;
            font-size: 18px;
        }
        
        .generated-text {
            color: #444;
            line-height: 1.8;
            white-space: pre-wrap;
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }
        
        .platform-buttons {
            display: grid;
            gap: 10px;
        }
        
        .platform-button {
            background: white;
            color: #333;
            border: 2px solid #ddd;
            padding: 12px 20px;
            border-radius: 10px;
            text-align: center;
            text-decoration: none;
            transition: all 0.2s;
            font-size: 14px;
        }
        
        .platform-button:hover {
            background: #f5f5f5;
            border-color: #667eea;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .loading.show {
            display: block;
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
    </style>
</head>
<body>
    <div class="language-switcher">
        <button class="lang-btn active" data-lang="ja" onclick="switchLanguage('ja')">日本語</button>
        <button class="lang-btn" data-lang="en" onclick="switchLanguage('en')">English</button>
        <button class="lang-btn" data-lang="zh" onclick="switchLanguage('zh')">中文</button>
        <button class="lang-btn" data-lang="ko" onclick="switchLanguage('ko')">한국어</button>
    </div>
    
    <div class="container">
        <h1>🌟 SmartReview AI</h1>
        <p class="subtitle" data-i18n="subtitle">AI口コミ生成システム</p>
        
        <div class="store-info">
            <div class="store-name">Beauty Salon SAKURA</div>
            <div class="store-address">東京都渋谷区表参道1-2-3</div>
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
                <div class="service-chip" data-service="ハイフ">ハイフ</div>
                <div class="service-chip" data-service="リフトアップ">リフトアップ</div>
                <div class="service-chip" data-service="フェイシャル">フェイシャル</div>
                <div class="service-chip" data-service="ボディケア">ボディケア</div>
                <div class="service-chip" data-service="脱毛">脱毛</div>
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
        
        <div class="result" id="result">
            <div class="result-title" data-i18n="generatedReview">生成された口コミ</div>
            <div class="generated-text" id="generatedText"></div>
            <div class="platform-buttons" id="platformButtons"></div>
        </div>
    </div>
    
    <script>
        let selectedRating = 0;
        let selectedServices = [];
        let currentLanguage = 'ja';
        
        // 多言語対応
        const translations = {
            ja: {
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
                feedbackSent: 'フィードバックとして送信しました'
            },
            en: {
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
                feedbackSent: 'Sent as feedback'
            },
            zh: {
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
                feedbackSent: '已作为反馈发送'
            },
            ko: {
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
                feedbackSent: '피드백으로 전송됨'
            }
        };
        
        function switchLanguage(lang) {
            currentLanguage = lang;
            
            // Update language buttons
            document.querySelectorAll('.lang-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.lang === lang);
            });
            
            // Update text content
            document.querySelectorAll('[data-i18n]').forEach(element => {
                const key = element.getAttribute('data-i18n');
                if (translations[lang][key]) {
                    element.textContent = translations[lang][key];
                }
            });
            
            // Update placeholders
            document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
                const key = element.getAttribute('data-i18n-placeholder');
                if (translations[lang][key]) {
                    element.placeholder = translations[lang][key];
                }
            });
            
            // Update rating text
            updateRatingText();
        }
        
        function updateRatingText() {
            const ratingTextEl = document.getElementById('ratingText');
            if (ratingTextEl) {
                ratingTextEl.textContent = translations[currentLanguage].ratingTexts[selectedRating];
                ratingTextEl.className = 'rating-text' + (selectedRating > 0 ? ' rated-' + selectedRating : '');
            }
        }
        
        // 星評価の設定
        document.querySelectorAll('.star').forEach(star => {
            star.addEventListener('mouseenter', function() {
                const rating = parseInt(this.dataset.rating);
                document.querySelectorAll('.star').forEach((s, index) => {
                    s.classList.toggle('preview', index < rating);
                });
            });
            
            star.addEventListener('mouseleave', function() {
                document.querySelectorAll('.star').forEach(s => {
                    s.classList.remove('preview');
                });
            });
            
            star.addEventListener('click', function() {
                selectedRating = parseInt(this.dataset.rating);
                updateStars();
                updateRatingText();
            });
        });
        
        function updateStars() {
            document.querySelectorAll('.star').forEach((star, index) => {
                star.classList.toggle('active', index < selectedRating);
            });
        }
        
        // サービス選択
        document.querySelectorAll('.service-chip').forEach(chip => {
            chip.addEventListener('click', function() {
                const service = this.dataset.service;
                if (selectedServices.includes(service)) {
                    selectedServices = selectedServices.filter(s => s !== service);
                    this.classList.remove('selected');
                } else {
                    selectedServices.push(service);
                    this.classList.add('selected');
                }
            });
        });
        
        async function generateReview() {
            // バリデーション
            if (selectedRating === 0) {
                showError(translations[currentLanguage].errorRating);
                return;
            }
            
            if (selectedServices.length === 0) {
                showError(translations[currentLanguage].errorService);
                return;
            }
            
            // UI更新
            document.getElementById('generateBtn').disabled = true;
            document.getElementById('loading').classList.add('show');
            document.getElementById('result').classList.remove('show');
            document.getElementById('error').classList.remove('show');
            
            const requestData = {
                store_id: "demo-store-001",
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
                
                if (response.ok) {
                    showResult(data);
                } else {
                    showError('Error: ' + (data.detail || 'Unknown error'));
                }
            } catch (error) {
                showError(translations[currentLanguage].errorCommunication);
            } finally {
                document.getElementById('generateBtn').disabled = false;
                document.getElementById('loading').classList.remove('show');
            }
        }
        
        function showResult(data) {
            document.getElementById('generatedText').textContent = data.generated_text;
            
            // プラットフォームボタンの生成
            const buttonsContainer = document.getElementById('platformButtons');
            buttonsContainer.innerHTML = '';
            
            if (selectedRating >= 4) {
                // 高評価の場合は外部プラットフォームへ
                const platforms = [
                    { name: translations[currentLanguage].googleMaps, url: 'https://maps.google.com' },
                    { name: translations[currentLanguage].hotpepper, url: 'https://beauty.hotpepper.jp' }
                ];
                
                platforms.forEach(platform => {
                    const button = document.createElement('a');
                    button.className = 'platform-button';
                    button.href = platform.url;
                    button.target = '_blank';
                    button.textContent = platform.name;
                    buttonsContainer.appendChild(button);
                });
            } else {
                // 低評価の場合は内部フィードバック
                const button = document.createElement('div');
                button.className = 'platform-button';
                button.style.background = '#fff3cd';
                button.style.borderColor = '#ffc107';
                button.textContent = translations[currentLanguage].feedbackSent;
                buttonsContainer.appendChild(button);
            }
            
            document.getElementById('result').classList.add('show');
        }
        
        function showError(message) {
            const errorDiv = document.getElementById('error');
            errorDiv.textContent = message;
            errorDiv.classList.add('show');
            setTimeout(() => {
                errorDiv.classList.remove('show');
            }, 5000);
        }
    </script>
</body>
</html>
"""

# ルートエンドポイント - HTMLインターフェース
@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_INTERFACE

# ヘルスチェック
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "SmartReview AI API",
        "version": "4.0.0",
        "timestamp": datetime.now().isoformat()
    }

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
            "system": "あなたは口コミライターです。",
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
キーワード: 表参道、{services}、個室、プライベートサロン

口コミ文章のみを日本語で出力してください："""
        },
        "en": {
            "system": "You are a review writer.",
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
            "system": "你是一位评论撰写者。",
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
            "system": "당신은 리뷰 작성자입니다.",
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
また利用したいと思います。
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)