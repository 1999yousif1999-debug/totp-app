import os
import re
import time
import socket
import pyotp
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>TOTP 2FA Authenticator</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            background-color: #0b0f19;
            color: #f1f5f9;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 16px;
        }

        .container {
            background-color: #151d30;
            border: 1px solid #1e293b;
            border-radius: 16px;
            width: 100%;
            max-width: 460px;
            padding: 28px 24px;
            box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.6);
        }

        .header {
            text-align: center;
            margin-bottom: 24px;
        }

        .header h1 {
            font-size: 1.55rem;
            font-weight: 700;
            color: #38bdf8;
            letter-spacing: -0.5px;
        }

        .header p {
            font-size: 0.85rem;
            color: #64748b;
            margin-top: 4px;
        }

        .field-card {
            background-color: #0d1322;
            border: 1px solid #222f46;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 20px;
        }

        .field-label {
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #94a3b8;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .input-group {
            display: flex;
            gap: 8px;
        }

        .input-group input {
            flex: 1;
            background-color: #151d30;
            border: 1px solid #293854;
            color: #f8fafc;
            border-radius: 8px;
            padding: 12px 14px;
            font-size: 0.95rem;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }

        .input-group input:focus {
            border-color: #38bdf8;
            box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.25);
        }

        .btn-action {
            background-color: #38bdf8;
            color: #0b0f19;
            border: none;
            border-radius: 8px;
            padding: 0 16px;
            font-size: 0.9rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            white-space: nowrap;
        }

        .btn-action:hover { background-color: #7dd3fc; }
        .btn-action:active { transform: scale(0.96); }

        .output-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            background-color: #151d30;
            border: 1px solid #293854;
            border-radius: 10px;
            padding: 10px 14px;
            margin: 6px 0 16px;
        }

        .code-display {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 2.3rem;
            font-weight: 700;
            letter-spacing: 4px;
            color: #f8fafc;
            user-select: all;
            flex: 1;
            text-align: center;
        }

        .code-display.empty { color: #334155; letter-spacing: 3px; }
        .code-display.error { color: #f87171; font-size: 1rem; letter-spacing: normal; }

        .btn-copy {
            background-color: #1e293b;
            color: #38bdf8;
            border: 1px solid #38bdf8;
            border-radius: 8px;
            padding: 10px 16px;
            font-size: 0.85rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
        }

        .btn-copy:hover { background-color: #38bdf8; color: #0b0f19; }
        .btn-copy:active { transform: scale(0.96); }
        .btn-copy.copied {
            background-color: #10b981 !important;
            border-color: #10b981 !important;
            color: #ffffff !important;
        }

        .timer-bar-wrapper {
            background-color: #1b263b;
            border-radius: 6px;
            height: 6px;
            overflow: hidden;
            margin-bottom: 10px;
        }

        .timer-bar-fill {
            height: 100%;
            width: 100%;
            background-color: #38bdf8;
            transition: width 1s linear, background-color 0.3s;
        }

        .timer-bar-fill.urgent { background-color: #ef4444; }

        .timer-meta {
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            color: #64748b;
        }

        .timer-seconds { color: #38bdf8; font-weight: 700; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TOTP Authenticator</h1>
            <p>Cloud 2FA Generator &bull; 24/7</p>
        </div>

        <!-- Field 1: Secret Key Input + Paste -->
        <div class="field-card">
            <div class="field-label">
                <span>Field 1 &bull; Secret Key</span>
                <span id="keyStatus" style="font-weight:normal;text-transform:none;color:#64748b;">Waiting for key</span>
            </div>
            <div class="input-group">
                <input
                    type="text"
                    id="secretInput"
                    placeholder="Enter or paste Base32 key..."
                    autocomplete="off"
                    autocapitalize="none"
                    spellcheck="false"
                >
                <button type="button" class="btn-action" id="pasteBtn" title="Paste from clipboard">Paste</button>
            </div>
        </div>

        <!-- Field 2: TOTP Code Output + Copy + Countdown -->
        <div class="field-card">
            <div class="field-label">
                <span>Field 2 &bull; Active TOTP Code</span>
                <span id="liveBadge" style="color:#10b981;">&bull; Live</span>
            </div>

            <div class="output-row">
                <div class="code-display empty" id="codeDisplay">------</div>
                <button type="button" class="btn-copy" id="copyBtn" title="Copy 6-digit code">Copy</button>
            </div>

            <div class="timer-bar-wrapper">
                <div class="timer-bar-fill" id="timerFill"></div>
            </div>
            <div class="timer-meta">
                <span>Time Remaining</span>
                <span><span class="timer-seconds" id="secondsText">30</span>s</span>
            </div>
        </div>
    </div>

    <script>
        const secretInput  = document.getElementById('secretInput');
        const pasteBtn     = document.getElementById('pasteBtn');
        const codeDisplay  = document.getElementById('codeDisplay');
        const copyBtn      = document.getElementById('copyBtn');
        const keyStatus    = document.getElementById('keyStatus');
        const timerFill    = document.getElementById('timerFill');
        const secondsText  = document.getElementById('secondsText');

        let currentRawCode = '';

        function formatCode(c) {
            return /^\\d{6}$/.test(c) ? `${c.slice(0,3)} ${c.slice(3)}` : c;
        }

        async function fetchTotpCode() {
            const secret = secretInput.value.trim();
            if (!secret) {
                currentRawCode = '';
                codeDisplay.textContent = '------';
                codeDisplay.className = 'code-display empty';
                keyStatus.textContent = 'Waiting for key';
                keyStatus.style.color = '#64748b';
                return;
            }
            try {
                const res  = await fetch('/api/totp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ secret })
                });
                const data = await res.json();
                if (data.success) {
                    currentRawCode = data.code;
                    codeDisplay.textContent = formatCode(data.code);
                    codeDisplay.className = 'code-display';
                    keyStatus.textContent = 'Active';
                    keyStatus.style.color = '#10b981';
                } else {
                    currentRawCode = '';
                    codeDisplay.textContent = data.error || 'Invalid Key';
                    codeDisplay.className = 'code-display error';
                    keyStatus.textContent = 'Error';
                    keyStatus.style.color = '#ef4444';
                }
            } catch {
                currentRawCode = '';
                codeDisplay.textContent = 'Network Error';
                codeDisplay.className = 'code-display error';
                keyStatus.textContent = 'Offline';
                keyStatus.style.color = '#ef4444';
            }
        }

        // Paste button — Clipboard API with fallback
        pasteBtn.addEventListener('click', async () => {
            try {
                if (navigator.clipboard?.readText) {
                    secretInput.value = (await navigator.clipboard.readText()).trim();
                } else {
                    const t = prompt('Paste your secret key:');
                    if (t !== null) secretInput.value = t.trim();
                }
            } catch {
                const t = prompt('Clipboard restricted. Paste key here:');
                if (t !== null) secretInput.value = t.trim();
            }
            fetchTotpCode();
        });

        // Copy button — dual-method for PC + iPhone Safari
        copyBtn.addEventListener('click', async () => {
            if (!currentRawCode || currentRawCode.length !== 6) return;
            let ok = false;

            // Method 1: Modern Clipboard API (HTTPS)
            if (navigator.clipboard && window.isSecureContext) {
                try { await navigator.clipboard.writeText(currentRawCode); ok = true; } catch {}
            }

            // Method 2: execCommand fallback (HTTP / iOS Safari)
            if (!ok) {
                try {
                    const ta = document.createElement('textarea');
                    ta.value = currentRawCode;
                    ta.style.cssText = 'position:fixed;left:-9999px;top:0;';
                    ta.setAttribute('readonly', '');
                    document.body.appendChild(ta);
                    ta.focus();
                    ta.select();
                    ta.setSelectionRange(0, 99999);
                    ok = document.execCommand('copy');
                    document.body.removeChild(ta);
                } catch {}
            }

            if (ok) {
                const orig = copyBtn.textContent;
                copyBtn.textContent = '✓ Copied';
                copyBtn.classList.add('copied');
                setTimeout(() => { copyBtn.textContent = orig; copyBtn.classList.remove('copied'); }, 1500);
            }
        });

        secretInput.addEventListener('input', fetchTotpCode);

        // Live countdown + auto-refresh at epoch boundary
        function updateTimer() {
            const now       = Math.floor(Date.now() / 1000);
            const remaining = 30 - (now % 30);
            secondsText.textContent  = remaining;
            timerFill.style.width    = `${(remaining / 30) * 100}%`;
            remaining <= 5 ? timerFill.classList.add('urgent') : timerFill.classList.remove('urgent');
            if ((remaining === 30 || remaining === 29) && secretInput.value.trim()) fetchTotpCode();
        }

        setInterval(updateTimer, 1000);
        updateTimer();
    </script>
</body>
</html>
"""

def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@app.route("/api/totp", methods=["POST"])
def generate_totp():
    payload        = request.get_json(silent=True) or {}
    raw_secret     = payload.get("secret", "")
    cleaned_secret = re.sub(r"[\s\-]", "", raw_secret).upper()

    if not cleaned_secret:
        return jsonify({"success": False, "error": "Empty Key"}), 400

    try:
        totp      = pyotp.TOTP(cleaned_secret)
        code      = totp.now()
        remaining = 30 - (int(time.time()) % 30)
        return jsonify({"success": True, "code": code, "remaining": remaining})
    except Exception:
        return jsonify({"success": False, "error": "Invalid Secret Key"}), 400

if __name__ == "__main__":
    # Reads PORT from environment (required by Render/cloud) or falls back to 5000 locally
    port   = int(os.environ.get("PORT", 5000))
    lan_ip = get_lan_ip()

    print("=" * 60)
    print(" TOTP 2FA Authenticator — Starting")
    print("=" * 60)
    print(f" -> Local  : http://localhost:{port}")
    print(f" -> LAN    : http://{lan_ip}:{port}")
    print("=" * 60)

    app.run(host="0.0.0.0", port=port, debug=False)
