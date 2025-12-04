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
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import FieldFilter

# 環境変数読み込み
load_dotenv()

app = FastAPI(
    title="SmartReview AI",
    description="AI口コミ生成システム - Firestore連携版",
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

# Firebase初期化をスキップしてFirestoreを直接使用
try:
    # Cloud Run環境では認証は自動的に処理される
    if not firebase_admin._apps:
        # プロジェクトIDのみ指定して初期化
        firebase_admin.initialize_app(options={
            'projectId': os.getenv("FIREBASE_PROJECT_ID", "autosns-465900")
        })
    
    # Firestoreクライアント
    db = firestore.client()
except Exception as e:
    print(f"Firebase initialization warning: {e}")
    # Firebaseが初期化できない場合はメモリストレージを使用
    db = None

# 管理者セッション管理
ADMIN_SESSIONS = {}
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# データモデル
class ReviewInput(BaseModel):
    store_id: str
    product: str
    user_name: str
    improvement_points: List[str] = []
    language: str = "ja"

class ReviewResponse(BaseModel):
    review_id: str
    content: str
    created_at: str
    language: str
    store_name: str
    product: str

class LoginRequest(BaseModel):
    password: str

class StoreInfo(BaseModel):
    store_id: str
    name: str
    description: str
    address: str
    phone: str
    services: List[str]

# 初期データ投入関数
async def initialize_sample_data():
    stores_ref = db.collection('stores')
    
    # サンプル店舗データ
    sample_stores = [
        {
            "store_id": "demo-store-001",
            "qr_code": "QR001",
            "name": "Beauty Salon SAKURA",
            "description": "最新の美容機器を完備した完全個室プライベートサロン",
            "address": "東京都渋谷区表参道1-2-3",
            "phone": "03-1234-5678",
            "services": ["ハイフ", "リフトアップ", "フェイシャル", "ボディケア", "脱毛"],
            "created_at": datetime.now().isoformat()
        },
        {
            "store_id": "demo-store-002",
            "qr_code": "QR002",
            "name": "Aesthetic Clinic Rose",
            "description": "医療とエステの融合による最先端美容クリニック",
            "address": "東京都港区南青山2-3-4",
            "phone": "03-2345-6789",
            "services": ["医療脱毛", "シミ取り", "ボトックス", "ヒアルロン酸", "ダーマペン"],
            "created_at": datetime.now().isoformat()
        },
        {
            "store_id": "demo-store-003",
            "qr_code": "QR003",
            "name": "Total Beauty LILY",
            "description": "トータルビューティーを実現するラグジュアリーサロン",
            "address": "東京都新宿区西新宿3-4-5",
            "phone": "03-3456-7890",
            "services": ["痩身", "小顔矯正", "美肌治療", "アンチエイジング", "ブライダルエステ"],
            "created_at": datetime.now().isoformat()
        }
    ]
    
    # 既存データチェックして、なければ投入
    for store_data in sample_stores:
        doc_ref = stores_ref.document(store_data["store_id"])
        doc = doc_ref.get()
        if not doc.exists:
            doc_ref.set(store_data)
            print(f"初期化: 店舗 {store_data['name']} を作成しました")

# OpenAI API設定
openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_ai_review(product: str, user_name: str, improvement_points: List[str], store_name: str, language: str = "ja") -> str:
    if not openai.api_key:
        # APIキーがない場合のフォールバック
        if language == "ja":
            improvements = "、".join(improvement_points) if improvement_points else "特になし"
            return f"""
{store_name}で{product}を体験させていただきました。

施術はとても丁寧で、スタッフの方の対応も親切でした。
{product}の効果を実感でき、大変満足しています。

改善点: {improvements}

また利用させていただきたいと思います。
ありがとうございました！

{user_name}
            """.strip()
        elif language == "en":
            improvements = ", ".join(improvement_points) if improvement_points else "None"
            return f"""
I experienced {product} at {store_name}.

The treatment was very careful and the staff were kind.
I could feel the effects of {product} and am very satisfied.

Points for improvement: {improvements}

I would like to use the service again.
Thank you!

{user_name}
            """.strip()
        elif language == "zh":
            improvements = "、".join(improvement_points) if improvement_points else "无"
            return f"""
在{store_name}体验了{product}。

服务非常细致，工作人员的态度也很亲切。
能够感受到{product}的效果，非常满意。

改进建议：{improvements}

希望下次还能来。
谢谢！

{user_name}
            """.strip()
        elif language == "ko":
            improvements = ", ".join(improvement_points) if improvement_points else "없음"
            return f"""
{store_name}에서 {product}를 체험했습니다.

시술은 매우 정성스러웠고 직원분들의 대응도 친절했습니다.
{product}의 효과를 실감할 수 있어 매우 만족합니다.

개선점: {improvements}

또 이용하고 싶습니다.
감사합니다!

{user_name}
            """.strip()
    
    # OpenAI API使用
    try:
        # 言語別のプロンプト設定
        prompts = {
            "ja": f"""
あなたは{store_name}で{product}を体験した{user_name}という顧客です。
以下の改善要望を含めて、自然で信頼性の高い口コミを日本語で作成してください：
改善要望: {', '.join(improvement_points) if improvement_points else '特になし'}

口コミは以下の要素を含めてください：
1. 施術・サービスの感想
2. スタッフの対応
3. 効果の実感
4. 改善要望（あれば）
5. 総合的な満足度

300文字程度で、自然な日本語で記載してください。
            """,
            "en": f"""
You are a customer named {user_name} who experienced {product} at {store_name}.
Create a natural and trustworthy review in English including these improvement requests:
Improvements: {', '.join(improvement_points) if improvement_points else 'None'}

Include these elements:
1. Impressions of the treatment/service
2. Staff response
3. Effectiveness
4. Improvement requests (if any)
5. Overall satisfaction

Write in about 100 words in natural English.
            """,
            "zh": f"""
你是在{store_name}体验了{product}的顾客{user_name}。
请用中文撰写一份自然可信的评价，包含以下改进建议：
改进建议：{', '.join(improvement_points) if improvement_points else '无'}

包含以下要素：
1. 服务体验感受
2. 员工态度
3. 效果实感
4. 改进建议（如有）
5. 整体满意度

用大约150字的自然中文撰写。
            """,
            "ko": f"""
당신은 {store_name}에서 {product}를 체험한 {user_name}이라는 고객입니다.
다음 개선 요청사항을 포함하여 자연스럽고 신뢰할 수 있는 리뷰를 한국어로 작성해주세요:
개선사항: {', '.join(improvement_points) if improvement_points else '없음'}

다음 요소를 포함해주세요:
1. 시술/서비스 감상
2. 직원 응대
3. 효과 실감
4. 개선 요청사항(있다면)
5. 전반적인 만족도

자연스러운 한국어로 150자 정도로 작성해주세요.
            """
        }
        
        client = openai.OpenAI(api_key=openai.api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates authentic customer reviews."},
                {"role": "user", "content": prompts.get(language, prompts["ja"])}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI API エラー: {e}")
        # エラー時はフォールバック処理
        return generate_ai_review(product, user_name, improvement_points, store_name, language)

def generate_qr_code(store_id: str) -> str:
    """店舗IDからQRコードを生成"""
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
    
    # Base64エンコード
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

@app.on_event("startup")
async def startup_event():
    """アプリ起動時の初期化処理"""
    await initialize_sample_data()

@app.get("/", response_class=HTMLResponse)
async def read_root(session_id: Optional[str] = Cookie(None)):
    """メインページ（店舗選択）"""
    is_admin = session_id and session_id in ADMIN_SESSIONS
    
    # Firestoreから店舗一覧を取得
    stores_ref = db.collection('stores')
    stores_docs = stores_ref.stream()
    stores_html = ""
    
    for doc in stores_docs:
        store = doc.to_dict()
        services = ", ".join(store.get('services', []))
        stores_html += f"""
        <div class="store-card">
            <div class="store-header">
                <h3 class="store-name">{store['name']}</h3>
                <span class="store-id">ID: {store['store_id']}</span>
            </div>
            <p class="store-description">{store.get('description', '')}</p>
            <div class="store-info">
                <p><i class="icon">📍</i> {store.get('address', '')}</p>
                <p><i class="icon">📞</i> {store.get('phone', '')}</p>
                <p><i class="icon">✨</i> {services}</p>
            </div>
            <div class="store-actions">
                <a href="/store/{store['store_id']}" class="btn btn-primary">口コミを投稿</a>
                {"<a href='/admin/store/" + store['store_id'] + "' class='btn btn-secondary'>管理画面</a>' if is_admin else ''}
            </div>
        </div>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SmartReview AI - 店舗選択</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Noto Sans JP', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            
            .header {{
                text-align: center;
                color: white;
                margin-bottom: 40px;
                padding: 20px;
            }}
            
            .header h1 {{
                font-size: 2.5rem;
                font-weight: 700;
                margin-bottom: 10px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
            }}
            
            .header p {{
                font-size: 1.1rem;
                opacity: 0.95;
            }}
            
            .admin-badge {{
                display: inline-block;
                background: rgba(255,255,255,0.2);
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                margin-top: 10px;
                font-size: 0.9rem;
            }}
            
            .stores-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                gap: 25px;
                margin-bottom: 30px;
            }}
            
            .store-card {{
                background: white;
                border-radius: 15px;
                padding: 25px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                transition: transform 0.3s, box-shadow 0.3s;
            }}
            
            .store-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 15px 40px rgba(0,0,0,0.15);
            }}
            
            .store-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 15px;
            }}
            
            .store-name {{
                font-size: 1.3rem;
                font-weight: 600;
                color: #333;
            }}
            
            .store-id {{
                font-size: 0.85rem;
                color: #666;
                background: #f0f0f0;
                padding: 3px 8px;
                border-radius: 5px;
            }}
            
            .store-description {{
                color: #666;
                margin-bottom: 15px;
                line-height: 1.5;
            }}
            
            .store-info {{
                border-top: 1px solid #eee;
                padding-top: 15px;
                margin-bottom: 20px;
            }}
            
            .store-info p {{
                color: #555;
                margin-bottom: 8px;
                font-size: 0.95rem;
                display: flex;
                align-items: center;
            }}
            
            .icon {{
                margin-right: 8px;
                font-style: normal;
            }}
            
            .store-actions {{
                display: flex;
                gap: 10px;
            }}
            
            .btn {{
                flex: 1;
                padding: 12px 20px;
                border: none;
                border-radius: 8px;
                font-size: 0.95rem;
                font-weight: 500;
                text-decoration: none;
                text-align: center;
                cursor: pointer;
                transition: all 0.3s;
            }}
            
            .btn-primary {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            
            .btn-primary:hover {{
                transform: scale(1.02);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }}
            
            .btn-secondary {{
                background: #f0f0f0;
                color: #333;
            }}
            
            .btn-secondary:hover {{
                background: #e0e0e0;
            }}
            
            .login-section {{
                text-align: center;
                margin-top: 40px;
            }}
            
            .login-btn {{
                background: rgba(255,255,255,0.2);
                color: white;
                border: 2px solid white;
                padding: 10px 30px;
                border-radius: 25px;
                text-decoration: none;
                display: inline-block;
                transition: all 0.3s;
            }}
            
            .login-btn:hover {{
                background: white;
                color: #667eea;
            }}
            
            @media (max-width: 768px) {{
                .header h1 {{
                    font-size: 2rem;
                }}
                
                .stores-grid {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>SmartReview AI</h1>
                <p>AIが生成する自然な口コミで、お店の評判を向上</p>
                {'<span class="admin-badge">🔐 管理者モード</span>' if is_admin else ''}
            </div>
            
            <div class="stores-grid">
                {stores_html}
            </div>
            
            {f'''
            <div class="login-section">
                <a href="/admin/logout" class="login-btn">ログアウト</a>
            </div>
            ''' if is_admin else f'''
            <div class="login-section">
                <a href="/admin/login" class="login-btn">管理者ログイン</a>
            </div>
            '''}
        </div>
    </body>
    </html>
    """
    return html

@app.get("/store/{store_id}", response_class=HTMLResponse)
async def store_page(store_id: str):
    """店舗ごとの口コミ投稿ページ"""
    # Firestoreから店舗情報を取得
    store_ref = db.collection('stores').document(store_id)
    store_doc = store_ref.get()
    
    if not store_doc.exists:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = store_doc.to_dict()
    services_options = "".join([f'<option value="{s}">{s}</option>' for s in store.get('services', [])])
    
    html = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{store['name']} - 口コミ投稿</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Noto Sans JP', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: #f8f9fa;
                min-height: 100vh;
            }}
            
            .header {{
                background: white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.08);
                padding: 20px;
                margin-bottom: 30px;
            }}
            
            .container {{
                max-width: 800px;
                margin: 0 auto;
                padding: 0 20px;
            }}
            
            .header h1 {{
                font-size: 1.8rem;
                font-weight: 700;
                color: #333;
                margin-bottom: 5px;
            }}
            
            .header p {{
                color: #666;
                font-size: 0.95rem;
            }}
            
            .back-link {{
                display: inline-block;
                color: #667eea;
                text-decoration: none;
                margin-bottom: 10px;
                font-size: 0.9rem;
                transition: color 0.3s;
            }}
            
            .back-link:hover {{
                color: #764ba2;
            }}
            
            .store-info {{
                background: white;
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                margin-bottom: 30px;
            }}
            
            .store-info h2 {{
                font-size: 1.5rem;
                color: #333;
                margin-bottom: 10px;
            }}
            
            .store-details {{
                color: #666;
                line-height: 1.6;
            }}
            
            .form-card {{
                background: white;
                border-radius: 12px;
                padding: 30px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }}
            
            .form-title {{
                font-size: 1.3rem;
                font-weight: 600;
                color: #333;
                margin-bottom: 25px;
                text-align: center;
            }}
            
            .form-group {{
                margin-bottom: 20px;
            }}
            
            label {{
                display: block;
                color: #555;
                font-weight: 500;
                margin-bottom: 8px;
                font-size: 0.95rem;
            }}
            
            input, select, textarea {{
                width: 100%;
                padding: 12px 15px;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 0.95rem;
                font-family: inherit;
                transition: border-color 0.3s, box-shadow 0.3s;
            }}
            
            input:focus, select:focus, textarea:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            
            textarea {{
                resize: vertical;
                min-height: 100px;
            }}
            
            .language-tabs {{
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                border-bottom: 2px solid #eee;
            }}
            
            .lang-tab {{
                padding: 10px 20px;
                background: none;
                border: none;
                color: #666;
                cursor: pointer;
                font-size: 0.95rem;
                font-weight: 500;
                transition: all 0.3s;
                border-bottom: 2px solid transparent;
                margin-bottom: -2px;
            }}
            
            .lang-tab:hover {{
                color: #333;
            }}
            
            .lang-tab.active {{
                color: #667eea;
                border-bottom-color: #667eea;
            }}
            
            .improvement-chips {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 10px;
            }}
            
            .chip {{
                padding: 8px 15px;
                background: #f0f0f0;
                border-radius: 20px;
                font-size: 0.9rem;
                color: #555;
                cursor: pointer;
                transition: all 0.3s;
                border: 2px solid transparent;
            }}
            
            .chip:hover {{
                background: #e0e0e0;
            }}
            
            .chip.selected {{
                background: #667eea;
                color: white;
                border-color: #667eea;
            }}
            
            .btn-submit {{
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.3s, box-shadow 0.3s;
            }}
            
            .btn-submit:hover {{
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
            }}
            
            .btn-submit:disabled {{
                background: #ccc;
                cursor: not-allowed;
                transform: none;
            }}
            
            #result {{
                margin-top: 30px;
                padding: 20px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                display: none;
            }}
            
            #result.show {{
                display: block;
            }}
            
            .success {{
                color: #28a745;
                font-weight: 500;
                margin-bottom: 15px;
            }}
            
            .error {{
                color: #dc3545;
                font-weight: 500;
            }}
            
            .review-content {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                white-space: pre-wrap;
                line-height: 1.6;
            }}
            
            @media (max-width: 768px) {{
                .container {{
                    padding: 0 15px;
                }}
                
                .form-card {{
                    padding: 20px;
                }}
                
                .language-tabs {{
                    flex-wrap: wrap;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="container">
                <a href="/" class="back-link">← 店舗一覧に戻る</a>
                <h1>SmartReview AI</h1>
                <p>AIが生成する自然な口コミで、お店の評判を向上</p>
            </div>
        </div>
        
        <div class="container">
            <div class="store-info">
                <h2>{store['name']}</h2>
                <div class="store-details">
                    <p>{store.get('description', '')}</p>
                    <p>📍 {store.get('address', '')}</p>
                    <p>📞 {store.get('phone', '')}</p>
                </div>
            </div>
            
            <div class="form-card">
                <h2 class="form-title">口コミを投稿</h2>
                
                <div class="language-tabs">
                    <button class="lang-tab active" onclick="setLanguage('ja')">日本語</button>
                    <button class="lang-tab" onclick="setLanguage('en')">English</button>
                    <button class="lang-tab" onclick="setLanguage('zh')">中文</button>
                    <button class="lang-tab" onclick="setLanguage('ko')">한국어</button>
                </div>
                
                <form id="reviewForm">
                    <input type="hidden" id="store_id" value="{store_id}">
                    <input type="hidden" id="language" value="ja">
                    
                    <div class="form-group">
                        <label for="user_name">お名前</label>
                        <input type="text" id="user_name" name="user_name" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="product">利用したサービス</label>
                        <select id="product" name="product" required>
                            <option value="">選択してください</option>
                            {services_options}
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>改善してほしい点（任意）</label>
                        <div class="improvement-chips">
                            <div class="chip" data-value="待ち時間">待ち時間</div>
                            <div class="chip" data-value="接客">接客</div>
                            <div class="chip" data-value="清潔感">清潔感</div>
                            <div class="chip" data-value="料金">料金</div>
                            <div class="chip" data-value="予約システム">予約システム</div>
                        </div>
                    </div>
                    
                    <button type="submit" class="btn-submit">AI口コミを生成</button>
                </form>
                
                <div id="result"></div>
            </div>
        </div>
        
        <script>
            let currentLanguage = 'ja';
            let selectedImprovements = [];
            
            function setLanguage(lang) {{
                currentLanguage = lang;
                document.getElementById('language').value = lang;
                
                // タブの切り替え
                document.querySelectorAll('.lang-tab').forEach(tab => {{
                    tab.classList.remove('active');
                }});
                event.target.classList.add('active');
                
                // ラベルの更新
                const labels = {{
                    ja: {{
                        name: 'お名前',
                        service: '利用したサービス',
                        improvements: '改善してほしい点（任意）',
                        submit: 'AI口コミを生成'
                    }},
                    en: {{
                        name: 'Your Name',
                        service: 'Service Used',
                        improvements: 'Points for Improvement (Optional)',
                        submit: 'Generate AI Review'
                    }},
                    zh: {{
                        name: '您的姓名',
                        service: '使用的服务',
                        improvements: '改进建议（可选）',
                        submit: '生成AI评价'
                    }},
                    ko: {{
                        name: '성함',
                        service: '이용한 서비스',
                        improvements: '개선 요청사항 (선택)',
                        submit: 'AI 리뷰 생성'
                    }}
                }};
                
                document.querySelector('label[for="user_name"]').textContent = labels[lang].name;
                document.querySelector('label[for="product"]').textContent = labels[lang].service;
                document.querySelectorAll('label')[2].textContent = labels[lang].improvements;
                document.querySelector('.btn-submit').textContent = labels[lang].submit;
            }}
            
            // 改善点チップのクリック処理
            document.querySelectorAll('.chip').forEach(chip => {{
                chip.addEventListener('click', function() {{
                    this.classList.toggle('selected');
                    const value = this.getAttribute('data-value');
                    if (this.classList.contains('selected')) {{
                        selectedImprovements.push(value);
                    }} else {{
                        selectedImprovements = selectedImprovements.filter(item => item !== value);
                    }}
                }});
            }});
            
            document.getElementById('reviewForm').addEventListener('submit', async function(e) {{
                e.preventDefault();
                
                const submitBtn = document.querySelector('.btn-submit');
                submitBtn.disabled = true;
                submitBtn.textContent = '生成中...';
                
                const formData = {{
                    store_id: document.getElementById('store_id').value,
                    user_name: document.getElementById('user_name').value,
                    product: document.getElementById('product').value,
                    improvement_points: selectedImprovements,
                    language: currentLanguage
                }};
                
                try {{
                    const response = await fetch('/api/review', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify(formData)
                    }});
                    
                    const data = await response.json();
                    const resultDiv = document.getElementById('result');
                    
                    if (response.ok) {{
                        resultDiv.innerHTML = `
                            <div class="success">✅ 口コミが生成されました！</div>
                            <div class="review-content">${{data.content}}</div>
                        `;
                        resultDiv.classList.add('show');
                        
                        // フォームをリセット
                        document.getElementById('reviewForm').reset();
                        selectedImprovements = [];
                        document.querySelectorAll('.chip').forEach(chip => {{
                            chip.classList.remove('selected');
                        }});
                    }} else {{
                        resultDiv.innerHTML = '<div class="error">エラーが発生しました。もう一度お試しください。</div>';
                        resultDiv.classList.add('show');
                    }}
                }} catch (error) {{
                    console.error('Error:', error);
                    document.getElementById('result').innerHTML = '<div class="error">エラーが発生しました。もう一度お試しください。</div>';
                    document.getElementById('result').classList.add('show');
                }} finally {{
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'AI口コミを生成';
                }}
            }});
        </script>
    </body>
    </html>
    """
    return html

@app.post("/api/review", response_model=ReviewResponse)
async def create_review(review_input: ReviewInput):
    """口コミ生成API"""
    # Firestoreから店舗情報を取得
    store_ref = db.collection('stores').document(review_input.store_id)
    store_doc = store_ref.get()
    
    if not store_doc.exists:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = store_doc.to_dict()
    
    # AI口コミ生成
    review_content = generate_ai_review(
        product=review_input.product,
        user_name=review_input.user_name,
        improvement_points=review_input.improvement_points,
        store_name=store['name'],
        language=review_input.language
    )
    
    # Firestoreに保存
    review_id = str(uuid.uuid4())
    review_data = {
        "review_id": review_id,
        "store_id": review_input.store_id,
        "store_name": store['name'],
        "product": review_input.product,
        "user_name": review_input.user_name,
        "content": review_content,
        "improvement_points": review_input.improvement_points,
        "language": review_input.language,
        "created_at": datetime.now().isoformat(),
        "rating": 5  # デフォルト評価
    }
    
    # レビューを保存
    reviews_ref = db.collection('reviews')
    reviews_ref.document(review_id).set(review_data)
    
    # 店舗の統計情報を更新
    store_ref.update({
        'total_reviews': firestore.Increment(1),
        'last_review_at': datetime.now().isoformat()
    })
    
    return ReviewResponse(
        review_id=review_id,
        content=review_content,
        created_at=review_data["created_at"],
        language=review_input.language,
        store_name=store['name'],
        product=review_input.product
    )

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login():
    """管理者ログインページ"""
    html = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>管理者ログイン - SmartReview AI</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap" rel="stylesheet">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Noto Sans JP', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            
            .login-container {
                background: white;
                border-radius: 15px;
                padding: 40px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                width: 100%;
                max-width: 400px;
            }
            
            h1 {
                font-size: 1.8rem;
                color: #333;
                margin-bottom: 10px;
                text-align: center;
            }
            
            p {
                color: #666;
                text-align: center;
                margin-bottom: 30px;
            }
            
            .form-group {
                margin-bottom: 20px;
            }
            
            label {
                display: block;
                color: #555;
                font-weight: 500;
                margin-bottom: 8px;
            }
            
            input {
                width: 100%;
                padding: 12px 15px;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 1rem;
                transition: border-color 0.3s;
            }
            
            input:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }
            
            button {
                width: 100%;
                padding: 14px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 1rem;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.3s, box-shadow 0.3s;
            }
            
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
            }
            
            .back-link {
                display: block;
                text-align: center;
                color: #667eea;
                text-decoration: none;
                margin-top: 20px;
                font-size: 0.9rem;
            }
            
            .back-link:hover {
                color: #764ba2;
            }
            
            .error {
                color: #dc3545;
                text-align: center;
                margin-bottom: 20px;
                display: none;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>管理者ログイン</h1>
            <p>管理画面にアクセスするにはパスワードを入力してください</p>
            
            <div class="error" id="error">パスワードが正しくありません</div>
            
            <form id="loginForm">
                <div class="form-group">
                    <label for="password">パスワード</label>
                    <input type="password" id="password" name="password" required autofocus>
                </div>
                <button type="submit">ログイン</button>
            </form>
            
            <a href="/" class="back-link">← トップに戻る</a>
        </div>
        
        <script>
            document.getElementById('loginForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                
                const password = document.getElementById('password').value;
                
                try {
                    const response = await fetch('/api/admin/login', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ password })
                    });
                    
                    if (response.ok) {
                        window.location.href = '/admin/dashboard';
                    } else {
                        document.getElementById('error').style.display = 'block';
                    }
                } catch (error) {
                    console.error('Error:', error);
                    document.getElementById('error').style.display = 'block';
                }
            });
        </script>
    </body>
    </html>
    """
    return html

@app.post("/api/admin/login")
async def admin_login_api(request: LoginRequest, response: Response):
    """管理者ログインAPI"""
    if request.password == ADMIN_PASSWORD:
        session_id = secrets.token_urlsafe(32)
        ADMIN_SESSIONS[session_id] = {
            "created_at": datetime.now().isoformat()
        }
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=3600,  # 1時間
            httponly=True,
            samesite="lax"
        )
        return {"status": "success"}
    else:
        raise HTTPException(status_code=401, detail="Invalid password")

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(session_id: Optional[str] = Cookie(None)):
    """管理者ダッシュボード"""
    if not session_id or session_id not in ADMIN_SESSIONS:
        return RedirectResponse(url="/admin/login", status_code=303)
    
    # Firestoreから統計情報を取得
    stores_ref = db.collection('stores')
    reviews_ref = db.collection('reviews')
    
    total_stores = len(list(stores_ref.stream()))
    total_reviews = len(list(reviews_ref.stream()))
    
    # 最新のレビューを取得
    recent_reviews = reviews_ref.order_by('created_at', direction=firestore.Query.DESCENDING).limit(5).stream()
    
    reviews_html = ""
    for doc in recent_reviews:
        review = doc.to_dict()
        reviews_html += f"""
        <div class="review-item">
            <div class="review-header">
                <span class="reviewer">{review.get('user_name', 'Unknown')}</span>
                <span class="review-date">{review.get('created_at', '')[:10]}</span>
            </div>
            <div class="review-store">{review.get('store_name', '')} - {review.get('product', '')}</div>
            <div class="review-text">{review.get('content', '')[:100]}...</div>
        </div>
        """
    
    # 店舗一覧とQRコード
    stores_html = ""
    for doc in stores_ref.stream():
        store = doc.to_dict()
        qr_code = generate_qr_code(store['store_id'])
        stores_html += f"""
        <div class="store-item">
            <h3>{store['name']}</h3>
            <p>ID: {store['store_id']}</p>
            <img src="{qr_code}" alt="QR Code" style="width: 150px; height: 150px;">
            <div class="store-actions">
                <a href="/admin/store/{store['store_id']}" class="btn">詳細表示</a>
            </div>
        </div>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>管理者ダッシュボード - SmartReview AI</title>
        <link href="https://fonts.googleapis.com/css2+family=Noto+Sans+JP:wght@300;400;500;700&display=swap" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Noto Sans JP', sans-serif;
                background: #f5f6fa;
                min-height: 100vh;
            }}
            
            .header {{
                background: white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.08);
                padding: 20px;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            
            .header-content {{
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            h1 {{
                font-size: 1.8rem;
                color: #333;
            }}
            
            .logout-btn {{
                background: #dc3545;
                color: white;
                padding: 8px 20px;
                border-radius: 5px;
                text-decoration: none;
                font-size: 0.9rem;
            }}
            
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }}
            
            .stat-card {{
                background: white;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }}
            
            .stat-value {{
                font-size: 2rem;
                font-weight: 700;
                color: #667eea;
                margin-bottom: 5px;
            }}
            
            .stat-label {{
                color: #666;
                font-size: 0.9rem;
            }}
            
            .section {{
                margin-top: 40px;
            }}
            
            .section-title {{
                font-size: 1.3rem;
                color: #333;
                margin-bottom: 20px;
            }}
            
            .stores-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 20px;
            }}
            
            .store-item {{
                background: white;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                text-align: center;
            }}
            
            .store-item h3 {{
                font-size: 1.1rem;
                color: #333;
                margin-bottom: 10px;
            }}
            
            .store-item p {{
                color: #666;
                font-size: 0.85rem;
                margin-bottom: 15px;
            }}
            
            .store-actions {{
                margin-top: 15px;
            }}
            
            .btn {{
                background: #667eea;
                color: white;
                padding: 8px 20px;
                border-radius: 5px;
                text-decoration: none;
                font-size: 0.9rem;
                display: inline-block;
            }}
            
            .reviews-list {{
                background: white;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }}
            
            .review-item {{
                padding: 15px;
                border-bottom: 1px solid #eee;
            }}
            
            .review-item:last-child {{
                border-bottom: none;
            }}
            
            .review-header {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 5px;
            }}
            
            .reviewer {{
                font-weight: 600;
                color: #333;
            }}
            
            .review-date {{
                color: #999;
                font-size: 0.85rem;
            }}
            
            .review-store {{
                color: #667eea;
                font-size: 0.9rem;
                margin-bottom: 5px;
            }}
            
            .review-text {{
                color: #666;
                font-size: 0.9rem;
                line-height: 1.4;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="container">
                <div class="header-content">
                    <h1>管理者ダッシュボード</h1>
                    <a href="/admin/logout" class="logout-btn">ログアウト</a>
                </div>
            </div>
        </div>
        
        <div class="container">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{total_stores}</div>
                    <div class="stat-label">登録店舗数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{total_reviews}</div>
                    <div class="stat-label">総レビュー数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">5.0</div>
                    <div class="stat-label">平均評価</div>
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">店舗一覧とQRコード</h2>
                <div class="stores-grid">
                    {stores_html}
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">最新のレビュー</h2>
                <div class="reviews-list">
                    {reviews_html if reviews_html else '<p style="text-align: center; color: #999;">まだレビューがありません</p>'}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

@app.get("/admin/store/{store_id}", response_class=HTMLResponse)
async def admin_store_detail(store_id: str, session_id: Optional[str] = Cookie(None)):
    """店舗詳細管理ページ"""
    if not session_id or session_id not in ADMIN_SESSIONS:
        return RedirectResponse(url="/admin/login", status_code=303)
    
    # Firestoreから店舗情報を取得
    store_ref = db.collection('stores').document(store_id)
    store_doc = store_ref.get()
    
    if not store_doc.exists:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = store_doc.to_dict()
    
    # この店舗のレビューを取得
    reviews_ref = db.collection('reviews')
    store_reviews = reviews_ref.where(filter=FieldFilter('store_id', '==', store_id)).order_by('created_at', direction=firestore.Query.DESCENDING).stream()
    
    reviews_html = ""
    review_count = 0
    for doc in store_reviews:
        review = doc.to_dict()
        review_count += 1
        reviews_html += f"""
        <div class="review-card">
            <div class="review-header">
                <div class="review-user">
                    <strong>{review.get('user_name', 'Unknown')}</strong>
                    <span class="review-product">- {review.get('product', '')}</span>
                </div>
                <div class="review-meta">
                    <span class="review-lang">{review.get('language', 'ja').upper()}</span>
                    <span class="review-date">{review.get('created_at', '')[:10]}</span>
                </div>
            </div>
            <div class="review-content">{review.get('content', '')}</div>
            {f'<div class="review-improvements">改善要望: {", ".join(review.get("improvement_points", []))}</div>' if review.get("improvement_points") else ''}
        </div>
        """
    
    qr_code = generate_qr_code(store_id)
    
    html = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{store['name']} - 管理画面</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Noto Sans JP', sans-serif;
                background: #f5f6fa;
                min-height: 100vh;
            }}
            
            .header {{
                background: white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.08);
                padding: 20px;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            
            .back-link {{
                display: inline-block;
                color: #667eea;
                text-decoration: none;
                margin-bottom: 10px;
                font-size: 0.9rem;
            }}
            
            .back-link:hover {{
                color: #764ba2;
            }}
            
            h1 {{
                font-size: 1.8rem;
                color: #333;
            }}
            
            .store-info {{
                background: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                margin-top: 20px;
                display: grid;
                grid-template-columns: 1fr 200px;
                gap: 30px;
            }}
            
            .store-details h2 {{
                font-size: 1.5rem;
                color: #333;
                margin-bottom: 15px;
            }}
            
            .store-meta {{
                color: #666;
                line-height: 1.8;
                margin-bottom: 20px;
            }}
            
            .services {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
            }}
            
            .service-tag {{
                background: #667eea;
                color: white;
                padding: 5px 12px;
                border-radius: 15px;
                font-size: 0.85rem;
            }}
            
            .qr-section {{
                text-align: center;
            }}
            
            .qr-section h3 {{
                font-size: 1rem;
                color: #333;
                margin-bottom: 10px;
            }}
            
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 15px;
                margin-top: 30px;
            }}
            
            .stat {{
                text-align: center;
            }}
            
            .stat-value {{
                font-size: 2rem;
                font-weight: 700;
                color: #667eea;
            }}
            
            .stat-label {{
                color: #666;
                font-size: 0.9rem;
            }}
            
            .reviews-section {{
                margin-top: 40px;
            }}
            
            .section-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
            }}
            
            .section-title {{
                font-size: 1.3rem;
                color: #333;
            }}
            
            .review-card {{
                background: white;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                margin-bottom: 15px;
            }}
            
            .review-header {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 15px;
            }}
            
            .review-user strong {{
                color: #333;
                font-size: 1rem;
            }}
            
            .review-product {{
                color: #666;
                font-size: 0.9rem;
            }}
            
            .review-meta {{
                display: flex;
                gap: 10px;
                align-items: center;
            }}
            
            .review-lang {{
                background: #f0f0f0;
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 0.75rem;
                font-weight: 600;
                color: #666;
            }}
            
            .review-date {{
                color: #999;
                font-size: 0.85rem;
            }}
            
            .review-content {{
                color: #444;
                line-height: 1.6;
                white-space: pre-wrap;
            }}
            
            .review-improvements {{
                margin-top: 10px;
                padding-top: 10px;
                border-top: 1px solid #eee;
                color: #666;
                font-size: 0.9rem;
            }}
            
            .no-reviews {{
                text-align: center;
                color: #999;
                padding: 40px;
                background: white;
                border-radius: 10px;
            }}
            
            @media (max-width: 768px) {{
                .store-info {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="container">
                <a href="/admin/dashboard" class="back-link">← ダッシュボードに戻る</a>
                <h1>店舗管理: {store['name']}</h1>
            </div>
        </div>
        
        <div class="container">
            <div class="store-info">
                <div class="store-details">
                    <h2>{store['name']}</h2>
                    <div class="store-meta">
                        <p><strong>店舗ID:</strong> {store['store_id']}</p>
                        <p><strong>説明:</strong> {store.get('description', '')}</p>
                        <p><strong>住所:</strong> {store.get('address', '')}</p>
                        <p><strong>電話:</strong> {store.get('phone', '')}</p>
                    </div>
                    <div>
                        <strong>提供サービス:</strong>
                        <div class="services">
                            {''.join([f'<span class="service-tag">{s}</span>' for s in store.get('services', [])])}
                        </div>
                    </div>
                    
                    <div class="stats">
                        <div class="stat">
                            <div class="stat-value">{review_count}</div>
                            <div class="stat-label">レビュー数</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">5.0</div>
                            <div class="stat-label">平均評価</div>
                        </div>
                        <div class="stat">
                            <div class="stat-value">100%</div>
                            <div class="stat-label">満足度</div>
                        </div>
                    </div>
                </div>
                
                <div class="qr-section">
                    <h3>QRコード</h3>
                    <img src="{qr_code}" alt="QR Code" style="width: 200px; height: 200px;">
                    <p style="margin-top: 10px; font-size: 0.85rem; color: #666;">スキャンして口コミ投稿ページへ</p>
                </div>
            </div>
            
            <div class="reviews-section">
                <div class="section-header">
                    <h2 class="section-title">レビュー一覧 ({review_count}件)</h2>
                </div>
                
                {reviews_html if reviews_html else '<div class="no-reviews">まだレビューがありません</div>'}
            </div>
        </div>
    </body>
    </html>
    """
    return html

@app.get("/admin/logout")
async def admin_logout(response: Response):
    """管理者ログアウト"""
    response.delete_cookie(key="session_id")
    return RedirectResponse(url="/", status_code=303)

@app.get("/api/stores")
async def get_stores():
    """店舗一覧取得API"""
    stores_ref = db.collection('stores')
    stores_docs = stores_ref.stream()
    
    stores = []
    for doc in stores_docs:
        store = doc.to_dict()
        stores.append({
            "store_id": store.get("store_id"),
            "name": store.get("name"),
            "description": store.get("description"),
            "services": store.get("services", [])
        })
    
    return {"stores": stores}

@app.get("/api/store/{store_id}")
async def get_store(store_id: str):
    """店舗情報取得API"""
    store_ref = db.collection('stores').document(store_id)
    store_doc = store_ref.get()
    
    if not store_doc.exists:
        raise HTTPException(status_code=404, detail="Store not found")
    
    store = store_doc.to_dict()
    
    # レビュー数を取得
    reviews_ref = db.collection('reviews')
    store_reviews = reviews_ref.where(filter=FieldFilter('store_id', '==', store_id)).stream()
    review_count = len(list(store_reviews))
    
    return {
        "store_id": store.get("store_id"),
        "name": store.get("name"),
        "description": store.get("description"),
        "address": store.get("address"),
        "phone": store.get("phone"),
        "services": store.get("services", []),
        "review_count": review_count,
        "qr_code": generate_qr_code(store_id)
    }

@app.post("/api/admin/store", response_model=StoreInfo)
async def create_store(store_info: StoreInfo, session_id: Optional[str] = Cookie(None)):
    """新規店舗作成API"""
    if not session_id or session_id not in ADMIN_SESSIONS:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Firestoreに店舗を作成
    store_data = {
        "store_id": store_info.store_id,
        "qr_code": f"QR{store_info.store_id[-3:]}",
        "name": store_info.name,
        "description": store_info.description,
        "address": store_info.address,
        "phone": store_info.phone,
        "services": store_info.services,
        "created_at": datetime.now().isoformat(),
        "total_reviews": 0,
        "last_review_at": None
    }
    
    # 保存
    stores_ref = db.collection('stores')
    stores_ref.document(store_info.store_id).set(store_data)
    
    return store_info

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)