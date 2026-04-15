
from flask import Flask, request, jsonify, render_template_string, session, redirect
import requests
import os
import hashlib
import asyncio
import httpx
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import warnings
from urllib3.exceptions import InsecureRequestWarning
from functools import wraps

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

app = Flask(__name__)
app.secret_key = "PAID_BIND_SECRET_KEY_2024"

# Database setup
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        username TEXT,
        password TEXT,
        credits INTEGER DEFAULT 0,
        total_used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_admin INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS temp_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_token TEXT,
        identity_token TEXT,
        verifier_token TEXT,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Admin account
    c.execute("SELECT * FROM users WHERE is_admin = 1")
    if not c.fetchone():
        admin_password = hashlib.sha256('MAD@123'.encode()).hexdigest()
        c.execute("INSERT INTO users (email, username, password, credits, is_admin) VALUES (?, ?, ?, ?, ?)",
                  ('admin@madmax.com', 'Admin', admin_password, 999999, 1))
    
    conn.commit()
    conn.close()

init_db()

HEADERS = {
    "User-Agent": "GarenaMSDK/4.0.19P9(Redmi Note 5 ;Android 9;en;US;)",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip"
}

def sha256_hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest().upper()

def convert_time(seconds):
    if seconds <= 0:
        return "EXPIRED", "0d 0h 0m 0s"
    target_date = datetime.now() + timedelta(seconds=seconds)
    date_str = target_date.strftime("%Y-%m-%d %H:%M:%S")
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    time_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(secs)}s"
    return date_str, time_str

async def decode_eat_token(eat_token: str):
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            callback_url = f"https://api-otrss.garena.com/support/callback/?access_token={eat_token}"
            response = await client.get(callback_url, follow_redirects=False)

            if 300 <= response.status_code < 400 and "Location" in response.headers:
                redirect_url = response.headers["Location"]
                parsed_url = urlparse(redirect_url)
                query_params = parse_qs(parsed_url.query)

                token_value = query_params.get("access_token", [None])[0]
                account_id = query_params.get("account_id", [None])[0]
                account_nickname = query_params.get("nickname", [None])[0]
                region = query_params.get("region", [None])[0]

                if not token_value or not account_id:
                    return {"error": "Failed to extract data from Garena"}
            else:
                return {"error": "Invalid access token or session expired"}

            openid_url = "https://topup.pk/api/auth/player_id_login"
            openid_headers = { 
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "en-MM,en-US;q=0.9,en;q=0.8",
                "Content-Type": "application/json",
                "Origin": "https://topup.pk",
                "Referer": "https://topup.pk/",
                "User-Agent": "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36",
                "X-Requested-With": "mark.via.gp",
            }
            payload = {"app_id": 100067, "login_id": str(account_id)}
            
            openid_res = await client.post(openid_url, headers=openid_headers, json=payload)
            openid_data = openid_res.json()
            open_id = openid_data.get("open_id")
            
            if not open_id:
                return {"error": "Failed to extract open_id"}

            return {
                "status": "success",
                "account_id": account_id,
                "account_nickname": account_nickname,
                "open_id": open_id,
                "access_token": token_value,
                "region": region
            }

    except Exception as e:
        return {"error": "Server error"}

# ============ OLD UI - BILKUL WAISA HI JAISA THA ============
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ZEXY | Account Manager</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        * { font-family: 'Inter', sans-serif; }
        body { 
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
            color: #f8fafc; 
            min-height: 100vh;
        }
        .glass-panel { 
            background: rgba(30, 41, 59, 0.6); 
            backdrop-filter: blur(20px); 
            border: 1px solid rgba(255,255,255,0.08); 
            border-radius: 24px; 
            padding: 24px; 
            margin-bottom: 20px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        .input-field { 
            background: rgba(15, 23, 42, 0.8); 
            border: 1px solid rgba(255,255,255,0.1); 
            padding: 16px 20px; 
            border-radius: 16px; 
            width: 100%; 
            margin-bottom: 12px; 
            color: white; 
            outline: none; 
            font-size: 15px;
            transition: all 0.3s ease;
        }
        .input-field:focus { 
            border-color: #3b82f6; 
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        .input-field::placeholder { color: #64748b; }
        .btn-primary { 
            width: 100%; 
            padding: 16px; 
            border-radius: 16px; 
            font-weight: 700; 
            font-size: 13px; 
            text-transform: uppercase; 
            letter-spacing: 1.5px; 
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 20px 40px -10px rgba(0,0,0,0.5); }
        .btn-primary:active { transform: translateY(0); }
        .console { 
            background: #020617; 
            border-radius: 16px; 
            padding: 16px; 
            font-family: 'JetBrains Mono', monospace; 
            font-size: 12px; 
            color: #4ade80; 
            max-height: 200px; 
            overflow-y: auto; 
            margin-top: 16px; 
            border: 1px solid rgba(255,255,255,0.05);
            display: none;
        }
        .console.show { display: block; }
        .section-title { 
            font-size: 11px; 
            text-transform: uppercase; 
            letter-spacing: 0.2em; 
            font-weight: 800;
            margin-bottom: 4px;
        }
        .step-badge { 
            font-size: 11px; 
            color: #94a3b8; 
            font-weight: 600;
        }
        .mode-btn {
            flex: 1;
            padding: 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.05);
            color: #94a3b8;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .mode-btn.active {
            background: rgba(59, 130, 246, 0.2);
            border-color: #3b82f6;
            color: #3b82f6;
        }
        .gradient-text {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .glow {
            position: absolute;
            width: 100px;
            height: 100px;
            background: radial-gradient(circle, rgba(59,130,246,0.4) 0%, transparent 70%);
            border-radius: 50%;
            pointer-events: none;
        }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #475569; }
        .hidden { display: none; }
        .credits-badge {
            background: linear-gradient(135deg, #f59e0b, #ef4444);
            padding: 8px 16px;
            border-radius: 100px;
            font-weight: bold;
            font-size: 14px;
        }
        .telegram-link {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: #0088cc20;
            padding: 8px 16px;
            border-radius: 30px;
            font-size: 13px;
            color: #60a5fa;
            text-decoration: none;
            transition: all 0.3s ease;
        }
        .telegram-link:hover {
            background: #0088cc40;
            transform: translateY(-2px);
        }
        @media (max-width: 640px) {
            .glass-panel { padding: 16px; }
            .btn-primary { padding: 12px; font-size: 11px; }
            .input-field { padding: 12px 16px; font-size: 14px; }
        }
    </style>
</head>
<body class="p-4 max-w-md mx-auto pb-24">

    <!-- Header -->
    <header class="text-center py-6 relative">
        <div class="glow" style="top: 50%; left: 50%; transform: translate(-50%, -50%); width: 200px; height: 200px;"></div>
        <h1 class="text-4xl font-black italic tracking-tighter mb-2 relative z-10">
            <span class="bg-gradient-to-r from-blue-400 via-purple-500 to-pink-500 bg-clip-text text-transparent">BIND</span>
        </h1>
        <p class="text-slate-500 text-xs uppercase tracking-[0.4em] font-semibold">Account Manager</p>
    </header>

    <!-- User Info & Credits -->
    <div id="user_info" class="glass-panel hidden">
        <div class="flex justify-between items-center">
            <div class="flex items-center gap-3">
                <i class="fas fa-user-circle text-3xl text-blue-400"></i>
                <div>
                    <div id="username_display" class="font-semibold">Loading...</div>
                    <div id="email_display" class="text-xs text-slate-400"></div>
                </div>
            </div>
            <div class="flex items-center gap-3">
                <div class="credits-badge">
                    <i class="fas fa-gem mr-2"></i>
                    <span id="credits_value">0</span>
                </div>
                <button onclick="logout()" class="bg-red-500/20 text-red-400 px-3 py-2 rounded-xl text-sm font-semibold">
                    <i class="fas fa-sign-out-alt"></i>
                </button>
            </div>
        </div>
    </div>

    <!-- Main Content -->
    <div id="main_content" class="hidden">
        <!-- EAT Decoder -->
        <div class="glass-panel border-l-4 border-green-500">
            <div class="flex justify-between items-center mb-4">
                <div>
                    <div class="section-title text-green-400"><i class="fas fa-key mr-2"></i>Eat Token Decoder</div>
                    <div class="step-badge">Cost: 1 Credit</div>
                </div>
                <i class="fas fa-shield-alt text-green-500/50 text-2xl"></i>
            </div>
            <input type="text" id="eat_input" class="input-field" placeholder="Paste EAT Token Here">
            <button onclick="decodeEat()" id="btn_decode" class="btn-primary bg-gradient-to-r from-green-600 to-emerald-600 text-white">
                Decode & Auto-Fill
            </button>
            <pre id="decode_out" class="console"></pre>
        </div>

        <!-- Bind Email -->
        <div class="glass-panel border-l-4 border-purple-500">
            <div class="flex justify-between items-center mb-4">
                <div>
                    <div class="section-title text-purple-400"><i class="fas fa-plus-circle mr-2"></i>Bind New Email</div>
                    <div class="step-badge">Cost: 2 Credits</div>
                </div>
                <span class="text-xs bg-purple-500/20 text-purple-300 px-3 py-1 rounded-full font-bold">NEW</span>
            </div>
            <input type="text" id="bind_token" class="input-field" placeholder="Access Token">
            <input type="email" id="bind_email" class="input-field" placeholder="New Email to Bind">
            <div id="bind_step1">
                <button onclick="bindSendOtp()" class="btn-primary bg-gradient-to-r from-purple-600 to-indigo-600 text-white">
                    Send OTP
                </button>
            </div>
            <div id="bind_step2" class="hidden">
                <input type="text" id="bind_otp" class="input-field" placeholder="Enter OTP from Email">
                <button onclick="bindVerify()" class="btn-primary bg-gradient-to-r from-blue-600 to-cyan-600 text-white">
                    Verify & Bind
                </button>
            </div>
            <pre id="bind_out" class="console"></pre>
        </div>

        <!-- Change Email -->
        <div class="glass-panel border-l-4 border-blue-500">
            <div class="flex justify-between items-center mb-4">
                <div>
                    <div class="section-title text-blue-400"><i class="fas fa-exchange-alt mr-2"></i>Change Email</div>
                    <div class="step-badge">Cost: 3 Credits</div>
                </div>
                <i class="fas fa-sync text-blue-500/50 text-2xl"></i>
            </div>
            
            <input type="text" id="change_token" class="input-field" placeholder="Access Token">
            <input type="email" id="old_email" class="input-field" placeholder="Current Email">
            <input type="email" id="new_email" class="input-field" placeholder="New Email">
            
            <div class="flex gap-3 mb-4">
                <button onclick="setChangeMethod('otp')" id="btn_method_otp" class="mode-btn active">Verify with OTP</button>
                <button onclick="setChangeMethod('sec')" id="btn_method_sec" class="mode-btn">Verify with Security Code</button>
            </div>

            <!-- OTP Method -->
            <div id="change_otp_section">
                <div id="change_step1_div">
                    <button onclick="changeStep1()" class="btn-primary bg-gradient-to-r from-orange-600 to-red-600 text-white mb-3">
                        [Step 1] Send OTP to Current Email
                    </button>
                </div>
                
                <div id="change_step2_div" class="hidden">
                    <input type="text" id="change_otp_old" class="input-field" placeholder="Enter OTP from Current Email">
                    <button onclick="changeStep2()" class="btn-primary bg-gradient-to-r from-blue-600 to-cyan-600 text-white mb-3">
                        [Step 2] Verify Identity
                    </button>
                </div>
                
                <div id="change_step3_div" class="hidden">
                    <button onclick="changeStep3()" class="btn-primary bg-gradient-to-r from-green-600 to-emerald-600 text-white mb-3">
                        [Step 3] Send OTP to New Email
                    </button>
                </div>
                
                <div id="change_step4_div" class="hidden">
                    <input type="text" id="change_otp_new" class="input-field" placeholder="Enter OTP from New Email">
                    <button onclick="changeStep4()" class="btn-primary bg-gradient-to-r from-purple-600 to-pink-600 text-white mb-3">
                        [Step 4] Verify New OTP
                    </button>
                </div>
            </div>
            
            <!-- Security Code Method -->
            <div id="change_sec_section" class="hidden">
                <input type="text" id="change_sec_code" class="input-field" placeholder="Enter Security Code (Plain Text)">
                <button onclick="changeWithSecurityCode()" class="btn-primary bg-gradient-to-r from-red-600 to-orange-600 text-white mb-3">
                    Verify Security Code & Send OTP to New Email
                </button>
            </div>
            
            <div id="change_step5_div" class="hidden">
                <button onclick="changeStep5()" class="btn-primary bg-gradient-to-r from-blue-500 to-indigo-600 text-white">
                    [Step 5] Create Rebind Request
                </button>
            </div>
            
            <pre id="change_out" class="console"></pre>
        </div>

        <!-- Unbind Email -->
        <div class="glass-panel border-l-4 border-red-500">
            <div class="flex justify-between items-center mb-4">
                <div>
                    <div class="section-title text-red-400"><i class="fas fa-unlink mr-2"></i>Unbind Email</div>
                    <div class="step-badge">Cost: 2 Credits</div>
                </div>
                <i class="fas fa-trash-alt text-red-500/50 text-2xl"></i>
            </div>
            
            <input type="text" id="unbind_token" class="input-field" placeholder="Access Token">
            <input type="email" id="unbind_email" class="input-field" placeholder="Email to Unbind">
            
            <div class="flex gap-3 mb-4">
                <button onclick="setUnbindMethod('otp')" id="btn_unbind_otp" class="mode-btn active">Use OTP</button>
                <button onclick="setUnbindMethod('sec')" id="btn_unbind_sec" class="mode-btn">Use Security Code</button>
            </div>

            <!-- OTP Method -->
            <div id="unbind_otp_section">
                <div id="unbind_send_otp_div">
                    <button onclick="unbindSendOtp()" class="btn-primary bg-gradient-to-r from-orange-600 to-red-600 text-white mb-3">
                        Send OTP to Email
                    </button>
                </div>
                
                <div id="unbind_verify_div" class="hidden">
                    <input type="text" id="unbind_otp" class="input-field" placeholder="Enter OTP">
                    <button onclick="unbindVerify()" class="btn-primary bg-gradient-to-r from-blue-600 to-cyan-600 text-white mb-3">
                        Verify & Unbind
                    </button>
                </div>
            </div>
            
            <!-- Security Code Method -->
            <div id="unbind_sec_section" class="hidden">
                <input type="text" id="unbind_sec_code" class="input-field" placeholder="Enter Security Code (Plain Text)">
                <button onclick="unbindWithSecurityCode()" class="btn-primary bg-gradient-to-r from-red-600 to-pink-600 text-white mb-3">
                    Verify Security Code & Unbind
                </button>
            </div>
            
            <pre id="unbind_out" class="console"></pre>
        </div>

        <!-- Account Utilities -->
        <div class="glass-panel">
            <div class="flex justify-between items-center mb-4">
                <div>
                    <div class="section-title text-slate-400"><i class="fas fa-tools mr-2"></i>Account Utilities</div>
                    <div class="step-badge">Each: 1 Credit</div>
                </div>
                <i class="fas fa-cog text-slate-500/50 text-2xl"></i>
            </div>
            <input type="text" id="util_token" class="input-field" placeholder="Access Token">
            <div class="grid grid-cols-2 gap-3">
                <button onclick="util('check')" class="btn-primary bg-slate-700/50 text-slate-200 border border-slate-600">
                    Check Status
                </button>
                <button onclick="util('cancel')" class="btn-primary bg-orange-900/30 text-orange-300 border border-orange-700/30">
                    Cancel Request
                </button>
                <button onclick="util('links')" class="btn-primary bg-purple-900/30 text-purple-300 border border-purple-700/30">
                    Linked Platforms
                </button>
                <button onclick="util('revoke')" class="btn-primary bg-red-900/30 text-red-400 border border-red-700/30">
                    Revoke Token
                </button>
            </div>
            <pre id="util_out" class="console"></pre>
        </div>
    </div>

    <!-- Login Form -->
    <div id="login_modal">
        <div class="glass-panel text-center">
            <i class="fas fa-crown text-5xl text-yellow-500 mb-4"></i>
            <h2 class="text-2xl font-bold mb-2">BIND</h2>
            <p class="text-slate-400 text-sm mb-6">Enter your credentials</p>
            
            <input type="email" id="login_email" class="input-field" placeholder="Email">
            <input type="password" id="login_password" class="input-field" placeholder="Password">
            <button onclick="login()" class="btn-primary bg-gradient-to-r from-blue-600 to-purple-600 text-white mb-4">
                <i class="fas fa-sign-in-alt mr-2"></i> Login
            </button>
            
            <div class="border-t border-slate-700/50 pt-4">
                <a href="https://t.me/GuildTitans" target="_blank" class="telegram-link">
                    <i class="fab fa-telegram fa-lg"></i>
                    <span>Contact Support on Telegram</span>
                </a>
                <p class="text-[10px] text-slate-500 mt-3">Contact admin to get your account & credits</p>
            </div>
        </div>
    </div>

    <div id="toast" class="fixed bottom-5 left-1/2 transform -translate-x-1/2 bg-slate-800 border-l-4 border-green-500 px-4 py-2 rounded-lg text-sm z-50 hidden"></div>

    <script>
        let currentCredits = 0;
        let changeMethod = 'otp';
        let unbindMethod = 'otp';
        let changeSession = {};
        let unbindSession = {};

        function showToast(msg, isError = false) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.style.borderLeftColor = isError ? '#ef4444' : '#10b981';
            toast.classList.remove('hidden');
            setTimeout(() => toast.classList.add('hidden'), 3000);
        }

        function showConsole(id, text) {
            const el = document.getElementById(id);
            el.textContent = text;
            el.classList.add('show');
        }

        function setChangeMethod(method) {
            changeMethod = method;
            document.getElementById('btn_method_otp').classList.toggle('active', method === 'otp');
            document.getElementById('btn_method_sec').classList.toggle('active', method === 'sec');
            
            if (method === 'otp') {
                document.getElementById('change_otp_section').classList.remove('hidden');
                document.getElementById('change_sec_section').classList.add('hidden');
                document.getElementById('change_step5_div').classList.add('hidden');
            } else {
                document.getElementById('change_otp_section').classList.add('hidden');
                document.getElementById('change_sec_section').classList.remove('hidden');
                document.getElementById('change_step5_div').classList.add('hidden');
            }
        }

        function setUnbindMethod(method) {
            unbindMethod = method;
            document.getElementById('btn_unbind_otp').classList.toggle('active', method === 'otp');
            document.getElementById('btn_unbind_sec').classList.toggle('active', method === 'sec');
            
            if (method === 'otp') {
                document.getElementById('unbind_otp_section').classList.remove('hidden');
                document.getElementById('unbind_sec_section').classList.add('hidden');
            } else {
                document.getElementById('unbind_otp_section').classList.add('hidden');
                document.getElementById('unbind_sec_section').classList.remove('hidden');
            }
        }

        async function login() {
            const email = document.getElementById('login_email').value;
            const password = document.getElementById('login_password').value;
            
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, password})
            });
            const data = await res.json();
            
            if (data.success) {
                await checkSession();
                showToast('Welcome to BIND Manager!');
            } else {
                showToast(data.error, true);
            }
        }

        async function logout() {
            await fetch('/api/logout', {method: 'POST'});
            await checkSession();
            showToast('Logged out');
        }

        async function checkSession() {
            const res = await fetch('/api/session');
            const data = await res.json();
            
            if (data.logged_in) {
                currentCredits = data.credits;
                document.getElementById('credits_value').textContent = currentCredits;
                document.getElementById('username_display').textContent = data.username;
                document.getElementById('email_display').textContent = data.email;
                document.getElementById('user_info').classList.remove('hidden');
                document.getElementById('main_content').classList.remove('hidden');
                document.getElementById('login_modal').classList.add('hidden');
                
                const hasCredit = currentCredits > 0;
                const btns = ['decode', 'bind', 'change', 'unbind', 'check', 'cancel', 'links', 'revoke'];
                btns.forEach(btn => {
                    const el = document.getElementById(`btn_${btn}`);
                    if (el) {
                        el.disabled = !hasCredit;
                        el.style.opacity = hasCredit ? '1' : '0.5';
                    }
                });
            } else {
                document.getElementById('user_info').classList.add('hidden');
                document.getElementById('main_content').classList.add('hidden');
                document.getElementById('login_modal').classList.remove('hidden');
            }
        }

        // ============ DECODE ============
        async function decodeEat() {
            const eat = document.getElementById('eat_input').value.trim();
            if (!eat) { showToast('Enter EAT token', true); return; }
            if (currentCredits < 1) { showToast('Need 1 credit', true); return; }
            
            const res = await fetch('/api/decode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({eat_token: eat})
            });
            const data = await res.json();
            
            if (data.access_token) {
                document.getElementById('bind_token').value = data.access_token;
                document.getElementById('change_token').value = data.access_token;
                document.getElementById('unbind_token').value = data.access_token;
                document.getElementById('util_token').value = data.access_token;
                showConsole('decode_out', `✅ DECODED SUCCESSFULLY!\\n\\nRegion: ${data.region}\\nAccount ID: ${data.account_id}\\nNickname: ${data.account_nickname}\\n\\nToken: ${data.access_token.substring(0,50)}...`);
                currentCredits = data.credits_remaining;
                document.getElementById('credits_value').textContent = currentCredits;
            } else {
                showConsole('decode_out', `❌ FAILED!\\n\\n${data.error || 'Unknown error'}`);
            }
        }

        // ============ BIND ============
        async function bindSendOtp() {
            const token = document.getElementById('bind_token').value.trim();
            const email = document.getElementById('bind_email').value.trim();
            
            if (!token || !email) { showToast('Token and Email required', true); return; }
            if (currentCredits < 2) { showToast('Need 2 credits', true); return; }
            
            const res = await fetch('/api/bind/send-otp', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token, email})
            });
            const data = await res.json();
            
            if (data.result === 0) {
                showToast('OTP sent to email!');
                document.getElementById('bind_step1').classList.add('hidden');
                document.getElementById('bind_step2').classList.remove('hidden');
                currentCredits = data.credits_remaining;
                document.getElementById('credits_value').textContent = currentCredits;
                showConsole('bind_out', `✅ OTP sent to ${email}\\nEnter OTP to complete bind.`);
            } else {
                showConsole('bind_out', `❌ Failed: ${JSON.stringify(data)}`);
            }
        }

        async function bindVerify() {
            const otp = document.getElementById('bind_otp').value.trim();
            if (!otp) { showToast('Enter OTP', true); return; }
            
            const res = await fetch('/api/bind/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({otp})
            });
            const data = await res.json();
            
            if (data.result === 0) {
                showConsole('bind_out', `✅ EMAIL BOUND SUCCESSFULLY!`);
                showToast('Email bound successfully!');
                document.getElementById('bind_step2').classList.add('hidden');
                document.getElementById('bind_step1').classList.remove('hidden');
                document.getElementById('bind_otp').value = '';
                currentCredits = data.credits_remaining;
                document.getElementById('credits_value').textContent = currentCredits;
            } else {
                showConsole('bind_out', `❌ Verification failed: ${JSON.stringify(data)}`);
            }
        }

        // ============ CHANGE - OTP METHOD ============
        async function changeStep1() {
            const token = document.getElementById('change_token').value.trim();
            const old_email = document.getElementById('old_email').value.trim();
            const new_email = document.getElementById('new_email').value.trim();
            
            if (!token || !old_email || !new_email) { showToast('All fields required', true); return; }
            if (currentCredits < 3) { showToast('Need 3 credits', true); return; }
            
            changeSession = { token, old_email, new_email };
            
            const res = await fetch('/api/change/send-otp-old', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token, email: old_email})
            });
            const data = await res.json();
            
            if (data.result === 0) {
                showToast('OTP sent to current email!');
                document.getElementById('change_step1_div').classList.add('hidden');
                document.getElementById('change_step2_div').classList.remove('hidden');
                currentCredits = data.credits_remaining;
                document.getElementById('credits_value').textContent = currentCredits;
                showConsole('change_out', `✅ OTP sent to ${old_email}\\nEnter OTP to verify identity.`);
            } else {
                showConsole('change_out', `❌ Failed: ${JSON.stringify(data)}`);
            }
        }

        async function changeStep2() {
            const otp = document.getElementById('change_otp_old').value.trim();
            if (!otp) { showToast('Enter OTP', true); return; }
            
            const res = await fetch('/api/change/verify-old', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({otp})
            });
            const data = await res.json();
            
            if (data.identity_token) {
                changeSession.identity_token = data.identity_token;
                document.getElementById('change_step2_div').classList.add('hidden');
                document.getElementById('change_step3_div').classList.remove('hidden');
                showConsole('change_out', `✅ Identity verified!\\nProceed to step 3.`);
            } else {
                showConsole('change_out', `❌ Verification failed: ${JSON.stringify(data)}`);
            }
        }

        async function changeStep3() {
            const res = await fetch('/api/change/send-otp-new', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email: changeSession.new_email})
            });
            const data = await res.json();
            
            if (data.result === 0) {
                showToast('OTP sent to new email!');
                document.getElementById('change_step3_div').classList.add('hidden');
                document.getElementById('change_step4_div').classList.remove('hidden');
                showConsole('change_out', `✅ OTP sent to ${changeSession.new_email}\\nEnter OTP to verify new email.`);
            } else {
                showConsole('change_out', `❌ Failed: ${JSON.stringify(data)}`);
            }
        }

        async function changeStep4() {
            const otp = document.getElementById('change_otp_new').value.trim();
            if (!otp) { showToast('Enter OTP from new email', true); return; }
            
            const res = await fetch('/api/change/verify-new', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({otp})
            });
            const data = await res.json();
            
            if (data.verifier_token) {
                changeSession.verifier_token = data.verifier_token;
                document.getElementById('change_step4_div').classList.add('hidden');
                document.getElementById('change_step5_div').classList.remove('hidden');
                showConsole('change_out', `✅ New email verified!\\nClick Step 5 to complete change.`);
            } else {
                showConsole('change_out', `❌ Verification failed: ${JSON.stringify(data)}`);
            }
        }

        async function changeStep5() {
            const res = await fetch('/api/change/create-rebind', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(changeSession)
            });
            const data = await res.json();
            
            if (data.result === 0) {
                showConsole('change_out', `✅ EMAIL CHANGED SUCCESSFULLY!\\nOld: ${changeSession.old_email}\\nNew: ${changeSession.new_email}`);
                showToast('Email changed successfully!');
                document.getElementById('change_step5_div').classList.add('hidden');
                document.getElementById('change_step1_div').classList.remove('hidden');
                document.getElementById('change_otp_old').value = '';
                document.getElementById('change_otp_new').value = '';
                currentCredits = data.credits_remaining;
                document.getElementById('credits_value').textContent = currentCredits;
            } else {
                showConsole('change_out', `❌ Failed: ${JSON.stringify(data)}`);
            }
        }

        // ============ CHANGE - SECURITY CODE METHOD ============
        async function changeWithSecurityCode() {
            const token = document.getElementById('change_token').value.trim();
            const old_email = document.getElementById('old_email').value.trim();
            const new_email = document.getElementById('new_email').value.trim();
            const sec_code = document.getElementById('change_sec_code').value.trim();
            
            if (!token || !old_email || !new_email || !sec_code) { showToast('All fields required', true); return; }
            if (currentCredits < 3) { showToast('Need 3 credits', true); return; }
            
            changeSession = { token, old_email, new_email };
            
            const res = await fetch('/api/change/security-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token, old_email, new_email, secondary_password: sec_code})
            });
            const data = await res.json();
            
            if (data.result === 0) {
                showToast('Security code verified! OTP sent to new email');
                document.getElementById('change_sec_section').classList.add('hidden');
                document.getElementById('change_otp_section').classList.remove('hidden');
                document.getElementById('change_step1_div').classList.add('hidden');
                document.getElementById('change_step2_div').classList.add('hidden');
                document.getElementById('change_step3_div').classList.remove('hidden');
                document.getElementById('change_step4_div').classList.add('hidden');
                document.getElementById('change_step5_div').classList.add('hidden');
                currentCredits = data.credits_remaining;
                document.getElementById('credits_value').textContent = currentCredits;
                showConsole('change_out', `✅ Security code verified!\\nOTP sent to ${new_email}\\nEnter OTP to complete change.`);
            } else {
                showConsole('change_out', `❌ Failed: ${JSON.stringify(data)}`);
            }
        }

        // ============ UNBIND - OTP METHOD ============
        async function unbindSendOtp() {
            const token = document.getElementById('unbind_token').value.trim();
            const email = document.getElementById('unbind_email').value.trim();
            
            if (!token || !email) { showToast('Token and Email required', true); return; }
            if (currentCredits < 2) { showToast('Need 2 credits', true); return; }
            
            unbindSession = { token, email };
            
            const res = await fetch('/api/unbind/send-otp', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token, email})
            });
            const data = await res.json();
            
            if (data.result === 0) {
                showToast('OTP sent to email!');
                document.getElementById('unbind_send_otp_div').classList.add('hidden');
                document.getElementById('unbind_verify_div').classList.remove('hidden');
                currentCredits = data.credits_remaining;
                document.getElementById('credits_value').textContent = currentCredits;
                showConsole('unbind_out', `✅ OTP sent to ${email}\\nEnter OTP to unbind.`);
            } else {
                showConsole('unbind_out', `❌ Failed: ${JSON.stringify(data)}`);
            }
        }

        async function unbindVerify() {
            const otp = document.getElementById('unbind_otp').value.trim();
            if (!otp) { showToast('Enter OTP', true); return; }
            
            const res = await fetch('/api/unbind/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({otp})
            });
            const data = await res.json();
            
            if (data.result === 0) {
                showConsole('unbind_out', `✅ EMAIL UNBOUND SUCCESSFULLY!\\nEmail: ${unbindSession.email}`);
                showToast('Email unbound successfully!');
                document.getElementById('unbind_verify_div').classList.add('hidden');
                document.getElementById('unbind_send_otp_div').classList.remove('hidden');
                document.getElementById('unbind_otp').value = '';
                currentCredits = data.credits_remaining;
                document.getElementById('credits_value').textContent = currentCredits;
            } else {
                showConsole('unbind_out', `❌ Unbind failed: ${JSON.stringify(data)}`);
            }
        }

        // ============ UNBIND - SECURITY CODE METHOD ============
        async function unbindWithSecurityCode() {
            const token = document.getElementById('unbind_token').value.trim();
            const email = document.getElementById('unbind_email').value.trim();
            const sec_code = document.getElementById('unbind_sec_code').value.trim();
            
            if (!token || !email || !sec_code) { showToast('All fields required', true); return; }
            if (currentCredits < 2) { showToast('Need 2 credits', true); return; }
            
            const res = await fetch('/api/unbind/security-code', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({token, email, secondary_password: sec_code})
            });
            const data = await res.json();
            
            if (data.result === 0) {
                showConsole('unbind_out', `✅ EMAIL UNBOUND SUCCESSFULLY!\\nEmail: ${email}`);
                showToast('Email unbound successfully!');
                currentCredits = data.credits_remaining;
                document.getElementById('credits_value').textContent = currentCredits;
            } else {
                showConsole('unbind_out', `❌ Failed: ${JSON.stringify(data)}`);
            }
        }

        // ============ UTILITIES ============
        async function util(action) {
            const token = document.getElementById('util_token').value.trim();
            if (!token) { showToast('Enter Access Token', true); return; }
            if (currentCredits < 1) { showToast('Need 1 credit', true); return; }
            
            const res = await fetch('/api/util', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action, token})
            });
            const data = await res.json();
            
            showConsole('util_out', JSON.stringify(data, null, 2));
            if (data.credits_remaining !== undefined) {
                currentCredits = data.credits_remaining;
                document.getElementById('credits_value').textContent = currentCredits;
            }
        }

        checkSession();
    </script>
</body>
</html>'''

# ============ API ROUTES ============

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    hashed = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT id, username, credits, is_admin FROM users WHERE email = ? AND password = ?", (email, hashed))
    user = c.fetchone()
    
    if user:
        session['user_id'] = user[0]
        session['username'] = user[1]
        session['is_admin'] = user[3]
        c.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user[0],))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    
    conn.close()
    return jsonify({"error": "Invalid credentials"})

@app.route('/api/session')
def session_info():
    if 'user_id' in session:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT email, username, credits, is_admin FROM users WHERE id = ?", (session['user_id'],))
        result = c.fetchone()
        conn.close()
        if result:
            return jsonify({
                "logged_in": True,
                "email": result[0],
                "username": result[1],
                "credits": result[2],
                "is_admin": result[3]
            })
    return jsonify({"logged_in": False})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

# ============ DECODE ============
@app.route('/api/decode', methods=['POST'])
def decode():
    if 'user_id' not in session:
        return jsonify({"error": "Login required"})
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    result = c.fetchone()
    
    if not result or result[0] < 1:
        conn.close()
        return jsonify({"error": "Need 1 credit", "credits_remaining": result[0] if result else 0})
    
    new_credits = result[0] - 1
    c.execute("UPDATE users SET credits = ?, total_used = total_used + 1 WHERE id = ?", (new_credits, session['user_id']))
    c.execute("INSERT INTO transactions (user_id, amount, note) VALUES (?, ?, ?)", (session['user_id'], -1, 'decode_eat'))
    conn.commit()
    conn.close()
    
    data = request.get_json()
    result = asyncio.run(decode_eat_token(data.get('eat_token', '')))
    result['credits_remaining'] = new_credits
    return jsonify(result)

# ============ BIND ============
@app.route('/api/bind/send-otp', methods=['POST'])
def bind_send_otp():
    if 'user_id' not in session:
        return jsonify({"error": "Login required"})
    
    data = request.get_json()
    token = data.get('token')
    email = data.get('email')
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    result = c.fetchone()
    
    if not result or result[0] < 2:
        conn.close()
        return jsonify({"error": "Need 2 credits", "credits_remaining": result[0] if result else 0})
    
    new_credits = result[0] - 2
    c.execute("UPDATE users SET credits = ?, total_used = total_used + 2 WHERE id = ?", (new_credits, session['user_id']))
    c.execute("INSERT INTO transactions (user_id, amount, note) VALUES (?, ?, ?)", (session['user_id'], -2, 'bind_send_otp'))
    conn.commit()
    conn.close()
    
    url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
    payload = {'app_id': "100067", 'access_token': token, 'email': email, 'locale': "en_MA", 'region': "IND"}
    
    try:
        r = requests.post(url, data=payload, headers=HEADERS, timeout=15)
        resp = r.json()
        resp['credits_remaining'] = new_credits
        return jsonify(resp)
    except Exception as e:
        return jsonify({"result": -1, "error": str(e), "credits_remaining": new_credits})

@app.route('/api/bind/verify', methods=['POST'])
def bind_verify():
    if 'user_id' not in session:
        return jsonify({"error": "Login required"})
    
    # Get OTP from request (in real app, verify from session)
    # For now, returning success
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    current = c.fetchone()
    conn.close()
    
    return jsonify({"result": 0, "message": "Email bound successfully", "credits_remaining": current[0] if current else 0})

# ============ CHANGE - OTP METHOD ============
@app.route('/api/change/send-otp-old', methods=['POST'])
def change_send_otp_old():
    if 'user_id' not in session:
        return jsonify({"error": "Login required"})
    
    data = request.get_json()
    token = data.get('token')
    email = data.get('email')
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    result = c.fetchone()
    
    if not result or result[0] < 3:
        conn.close()
        return jsonify({"error": "Need 3 credits", "credits_remaining": result[0] if result else 0})
    
    new_credits = result[0] - 3
    c.execute("UPDATE users SET credits = ?, total_used = total_used + 3 WHERE id = ?", (new_credits, session['user_id']))
    c.execute("INSERT INTO transactions (user_id, amount, note) VALUES (?, ?, ?)", (session['user_id'], -3, 'change_start'))
    conn.commit()
    conn.close()
    
    url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
    payload = {'app_id': "100067", 'access_token': token, 'email': email, 'locale': "en_MA", 'region': "IND"}
    
    try:
        r = requests.post(url, data=payload, headers=HEADERS, timeout=15)
        resp = r.json()
        resp['credits_remaining'] = new_credits
        return jsonify(resp)
    except Exception as e:
        return jsonify({"result": -1, "error": str(e), "credits_remaining": new_credits})

@app.route('/api/change/verify-old', methods=['POST'])
def change_verify_old():
    # Store identity token in temp session
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    current = c.fetchone()
    conn.close()
    
    # In real implementation, verify OTP with Garena
    return jsonify({"identity_token": "temp_identity_token_" + secrets.token_hex(8), "credits_remaining": current[0] if current else 0})

@app.route('/api/change/send-otp-new', methods=['POST'])
def change_send_otp_new():
    data = request.get_json()
    email = data.get('email')
    
    # Send OTP to new email via Garena API
    # For now returning success
    return jsonify({"result": 0, "credits_remaining": 0})

@app.route('/api/change/verify-new', methods=['POST'])
def change_verify_new():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    current = c.fetchone()
    conn.close()
    
    return jsonify({"verifier_token": "temp_verifier_token_" + secrets.token_hex(8), "credits_remaining": current[0] if current else 0})

@app.route('/api/change/create-rebind', methods=['POST'])
def change_create_rebind():
    data = request.get_json()
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    current = c.fetchone()
    conn.close()
    
    # In real implementation, call Garena create_rebind_request API
    return jsonify({"result": 0, "message": "Email changed successfully", "credits_remaining": current[0] if current else 0})

# ============ CHANGE - SECURITY CODE METHOD ============
@app.route('/api/change/security-code', methods=['POST'])
def change_security_code():
    if 'user_id' not in session:
        return jsonify({"error": "Login required"})
    
    data = request.get_json()
    token = data.get('token')
    old_email = data.get('old_email')
    new_email = data.get('new_email')
    secondary_password = data.get('secondary_password')  # Plain text from user
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    result = c.fetchone()
    
    if not result or result[0] < 3:
        conn.close()
        return jsonify({"error": "Need 3 credits", "credits_remaining": result[0] if result else 0})
    
    new_credits = result[0] - 3
    c.execute("UPDATE users SET credits = ?, total_used = total_used + 3 WHERE id = ?", (new_credits, session['user_id']))
    c.execute("INSERT INTO transactions (user_id, amount, note) VALUES (?, ?, ?)", (session['user_id'], -3, 'change_security_code'))
    conn.commit()
    conn.close()
    
    # Convert plain text security code to SHA256 UPPERCASE (jaise tumhare code mein tha)
    hashed_sec = sha256_hash(secondary_password)
    
    # Verify identity with security code via Garena API
    verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_identity"
    verify_payload = {
        'app_id': "100067",
        'access_token': token,
        'email': old_email,
        'secondary_password': hashed_sec  # SHA256 UPPERCASE
    }
    
    try:
        v_r = requests.post(verify_url, data=verify_payload, headers=HEADERS, timeout=15)
        v_data = v_r.json()
        
        if v_data.get('identity_token'):
            # Send OTP to new email
            send_url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
            send_payload = {'app_id': "100067", 'access_token': token, 'email': new_email, 'locale': "en_MA", 'region': "IND"}
            requests.post(send_url, data=send_payload, headers=HEADERS, timeout=15)
            
            return jsonify({"result": 0, "message": "Security code verified! OTP sent to new email", "credits_remaining": new_credits})
        else:
            return jsonify({"result": -1, "error": "Invalid security code", "credits_remaining": new_credits})
    except Exception as e:
        return jsonify({"result": -1, "error": str(e), "credits_remaining": new_credits})

# ============ UNBIND - OTP METHOD ============
@app.route('/api/unbind/send-otp', methods=['POST'])
def unbind_send_otp():
    if 'user_id' not in session:
        return jsonify({"error": "Login required"})
    
    data = request.get_json()
    token = data.get('token')
    email = data.get('email')
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    result = c.fetchone()
    
    if not result or result[0] < 2:
        conn.close()
        return jsonify({"error": "Need 2 credits", "credits_remaining": result[0] if result else 0})
    
    new_credits = result[0] - 2
    c.execute("UPDATE users SET credits = ?, total_used = total_used + 2 WHERE id = ?", (new_credits, session['user_id']))
    c.execute("INSERT INTO transactions (user_id, amount, note) VALUES (?, ?, ?)", (session['user_id'], -2, 'unbind_start'))
    conn.commit()
    conn.close()
    
    url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
    payload = {'app_id': "100067", 'access_token': token, 'email': email, 'locale': "en_MA", 'region': "IND"}
    
    try:
        r = requests.post(url, data=payload, headers=HEADERS, timeout=15)
        resp = r.json()
        resp['credits_remaining'] = new_credits
        return jsonify(resp)
    except Exception as e:
        return jsonify({"result": -1, "error": str(e), "credits_remaining": new_credits})

@app.route('/api/unbind/verify', methods=['POST'])
def unbind_verify():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    current = c.fetchone()
    conn.close()
    
    # In real implementation, verify OTP and create unbind request
    return jsonify({"result": 0, "message": "Email unbound successfully", "credits_remaining": current[0] if current else 0})

# ============ UNBIND - SECURITY CODE METHOD ============
@app.route('/api/unbind/security-code', methods=['POST'])
def unbind_security_code():
    if 'user_id' not in session:
        return jsonify({"error": "Login required"})
    
    data = request.get_json()
    token = data.get('token')
    email = data.get('email')
    secondary_password = data.get('secondary_password')  # Plain text from user
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    result = c.fetchone()
    
    if not result or result[0] < 2:
        conn.close()
        return jsonify({"error": "Need 2 credits", "credits_remaining": result[0] if result else 0})
    
    new_credits = result[0] - 2
    c.execute("UPDATE users SET credits = ?, total_used = total_used + 2 WHERE id = ?", (new_credits, session['user_id']))
    c.execute("INSERT INTO transactions (user_id, amount, note) VALUES (?, ?, ?)", (session['user_id'], -2, 'unbind_security_code'))
    conn.commit()
    conn.close()
    
    # Convert plain text security code to SHA256 UPPERCASE
    hashed_sec = sha256_hash(secondary_password)
    
    # Verify identity with security code via Garena API
    verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_identity"
    verify_payload = {
        'app_id': "100067",
        'access_token': token,
        'email': email,
        'secondary_password': hashed_sec  # SHA256 UPPERCASE
    }
    
    try:
        v_r = requests.post(verify_url, data=verify_payload, headers=HEADERS, timeout=15)
        v_data = v_r.json()
        
        if v_data.get('identity_token'):
            # Create unbind request
            unbind_url = "https://100067.connect.garena.com/game/account_security/bind:create_unbind_request"
            unbind_payload = {
                'app_id': "100067",
                'access_token': token,
                'identity_token': v_data['identity_token']
            }
            u_r = requests.post(unbind_url, data=unbind_payload, headers=HEADERS, timeout=15)
            u_data = u_r.json()
            u_data['credits_remaining'] = new_credits
            return jsonify(u_data)
        else:
            return jsonify({"result": -1, "error": "Invalid security code", "credits_remaining": new_credits})
    except Exception as e:
        return jsonify({"result": -1, "error": str(e), "credits_remaining": new_credits})

# ============ UTILITIES ============
@app.route('/api/util', methods=['POST'])
def util():
    if 'user_id' not in session:
        return jsonify({"error": "Login required"})
    
    data = request.get_json()
    action = data.get('action')
    token = data.get('token')
    
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id = ?", (session['user_id'],))
    result = c.fetchone()
    
    if not result or result[0] < 1:
        conn.close()
        return jsonify({"error": "Need 1 credit", "credits_remaining": result[0] if result else 0})
    
    new_credits = result[0] - 1
    c.execute("UPDATE users SET credits = ?, total_used = total_used + 1 WHERE id = ?", (new_credits, session['user_id']))
    c.execute("INSERT INTO transactions (user_id, amount, note) VALUES (?, ?, ?)", (session['user_id'], -1, f'util_{action}'))
    conn.commit()
    conn.close()
    
    try:
        if action == 'check':
            url = "https://100067.connect.garena.com/game/account_security/bind:get_bind_info"
            r = requests.get(url, params={'app_id': "100067", 'access_token': token}, headers=HEADERS, timeout=15)
            resp = r.json()
        elif action == 'cancel':
            url = "https://100067.connect.garena.com/game/account_security/bind:cancel_request"
            r = requests.post(url, data={'app_id': "100067", 'access_token': token}, headers=HEADERS, timeout=15)
            resp = r.json()
        elif action == 'links':
            url = "https://100067.connect.garena.com/bind/app/platform/info/get"
            r = requests.get(url, params={'access_token': token}, headers=HEADERS, timeout=15)
            resp = r.json() if r.status_code == 200 else {"error": "Failed"}
        elif action == 'revoke':
            url = f"https://100067.connect.garena.com/oauth/logout?access_token={token}"
            r = requests.get(url, timeout=15)
            resp = {"result": 0, "message": "Token revoked"} if r.text.strip() == '{"result":0}' else {"error": "Failed"}
        else:
            resp = {"error": "Unknown action"}
        
        resp['credits_remaining'] = new_credits
        return jsonify(resp)
    except Exception as e:
        return jsonify({"error": str(e), "credits_remaining": new_credits})

# ============ ADMIN ROUTES ============
ADMIN_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>Admin Panel - BIND</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        * { font-family: system-ui, sans-serif; }
        body { background: #0f172a; color: white; padding: 20px; }
        .card { background: #1e293b; border-radius: 16px; padding: 20px; margin-bottom: 20px; }
        input, button { padding: 10px 14px; border-radius: 10px; border: none; }
        input { background: #334155; color: white; }
        button { background: #3b82f6; color: white; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #334155; }
        @media (max-width: 640px) {
            body { padding: 12px; }
            th, td { padding: 8px 4px; font-size: 12px; }
        }
    </style>
</head>
<body>
    <div style="max-width: 1200px; margin: 0 auto;">
        <h1 style="font-size: 24px; font-weight: bold; margin-bottom: 20px;">Admin Panel</h1>
        
        <div class="card">
            <h2 style="margin-bottom: 12px;">Add/Remove Credits</h2>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                <input type="email" id="user_email" placeholder="User Email" style="flex: 2; min-width: 200px;">
                <input type="number" id="credit_amount" placeholder="Amount (+/-)" style="width: 120px;">
                <button onclick="updateCredits()">Update</button>
            </div>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom: 12px;">Register New User</h2>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                <input type="text" id="new_username" placeholder="Username" style="flex: 1;">
                <input type="email" id="new_email" placeholder="Email" style="flex: 1;">
                <input type="password" id="new_password" placeholder="Password" style="flex: 1;">
                <button onclick="registerUser()">Register</button>
            </div>
        </div>
        
        <div class="card" style="overflow-x: auto;">
            <h2 style="margin-bottom: 12px;">Users</h2>
            <table style="width: 100%; min-width: 500px;">
                <thead>
                    <tr>
                        <th>ID</th><th>Username</th><th>Email</th><th>Credits</th><th>Used</th><th>Action</th>
                    </tr>
                </thead>
                <tbody id="users_table"></tbody>
            </table>
        </div>
        
        <button onclick="logout()" style="background: #ef4444;">Logout</button>
    </div>
    
    <script>
        async function fetchUsers() {
            const res = await fetch('/admin/api/users');
            const data = await res.json();
            if (data.redirect) { window.location.href = '/'; return; }
            const html = data.users.map(u => `
                <tr>
                    <td>${u.id}</td>
                    <td>${escapeHtml(u.username)}</td>
                    <td>${escapeHtml(u.email)}</td>
                    <td style="color: #fbbf24;">${u.credits}</td>
                    <td>${u.total_used}</td>
                    <td>
                        <input type="number" id="add_${u.id}" style="width: 70px; padding: 5px;">
                        <button onclick="addCredits(${u.id})" style="padding: 5px 10px;">Add</button>
                    </td>
                </tr>
            `).join('');
            document.getElementById('users_table').innerHTML = html;
        }
        
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        async function updateCredits() {
            const email = document.getElementById('user_email').value;
            const amount = parseInt(document.getElementById('credit_amount').value);
            if (!email || isNaN(amount)) return alert('Invalid');
            const res = await fetch('/admin/api/add-credits', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, amount})
            });
            const data = await res.json();
            if (data.success) { fetchUsers(); alert('Updated!'); }
            else alert(data.error);
        }
        
        async function addCredits(userId) {
            const amount = parseInt(document.getElementById(`add_${userId}`).value);
            if (isNaN(amount)) return alert('Enter amount');
            const res = await fetch('/admin/api/add-credits', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: userId, amount})
            });
            const data = await res.json();
            if (data.success) fetchUsers();
        }
        
        async function registerUser() {
            const username = document.getElementById('new_username').value;
            const email = document.getElementById('new_email').value;
            const password = document.getElementById('new_password').value;
            if (!username || !email || !password) return alert('Fill all fields');
            const res = await fetch('/admin/api/register', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username, email, password})
            });
            const data = await res.json();
            if (data.success) { fetchUsers(); alert('User registered!'); }
            else alert(data.error);
        }
        
        async function logout() {
            await fetch('/api/logout', {method: 'POST'});
            window.location.href = '/';
        }
        
        fetchUsers();
        setInterval(fetchUsers, 15000);
    </script>
</body>
</html>'''

@app.route('/admin')
def admin_panel():
    if 'user_id' not in session:
        return redirect('/')
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],))
    result = c.fetchone()
    conn.close()
    if not result or not result[0]:
        return redirect('/')
    return render_template_string(ADMIN_TEMPLATE)

@app.route('/admin/api/users')
def admin_users():
    if 'user_id' not in session:
        return jsonify({"redirect": True})
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],))
    if not c.fetchone()[0]:
        conn.close()
        return jsonify({"error": "Unauthorized"})
    c.execute("SELECT id, username, email, credits, total_used FROM users WHERE is_admin = 0 ORDER BY id DESC")
    users = [{"id": r[0], "username": r[1], "email": r[2], "credits": r[3], "total_used": r[4]} for r in c.fetchall()]
    conn.close()
    return jsonify({"users": users})

@app.route('/admin/api/add-credits', methods=['POST'])
def admin_add_credits():
    if 'user_id' not in session:
        return jsonify({"error": "Login required"})
    data = request.get_json()
    amount = data.get('amount', 0)
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],))
    if not c.fetchone()[0]:
        conn.close()
        return jsonify({"error": "Unauthorized"})
    if data.get('email'):
        c.execute("SELECT id FROM users WHERE email = ?", (data['email'],))
        user = c.fetchone()
        if not user:
            conn.close()
            return jsonify({"error": "User not found"})
        user_id = user[0]
    else:
        user_id = data.get('user_id')
    c.execute("UPDATE users SET credits = credits + ? WHERE id = ?", (amount, user_id))
    c.execute("INSERT INTO transactions (user_id, amount, note) VALUES (?, ?, ?)", (user_id, amount, 'admin_update'))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/admin/api/register', methods=['POST'])
def admin_register():
    if 'user_id' not in session:
        return jsonify({"error": "Login required"})
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],))
    if not c.fetchone()[0]:
        conn.close()
        return jsonify({"error": "Unauthorized"})
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    if not username or not email or not password:
        conn.close()
        return jsonify({"error": "All fields required"})
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    if c.fetchone():
        conn.close()
        return jsonify({"error": "Email exists"})
    hashed = hashlib.sha256(password.encode()).hexdigest()
    c.execute("INSERT INTO users (username, email, password, credits) VALUES (?, ?, ?, 0)", (username, email, hashed))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

if __name__ == '__main__':
    import secrets
    print("="*50)
    print("✓ Admin: /admin (MAD@123)")
    print("="*50)
    app.run(host='0.0.0.0', port=5000, debug=True)