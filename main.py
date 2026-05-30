import os
import httpx
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime

app = FastAPI(title="TradingView x Claude Bot")

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


@app.post("/webhook")
async def receive_webhook(request: Request):
    if WEBHOOK_SECRET:
        secret = request.headers.get("X-Webhook-Secret", "")
        if secret != WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    print(f"Webhook received: {payload}")
    analysis = await analyze_with_claude(payload)

    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        await send_telegram(payload, analysis)

    return JSONResponse({
        "status": "success",
        "symbol": payload.get("symbol"),
        "action": payload.get("action"),
        "analysis": analysis,
        "timestamp": datetime.utcnow().isoformat()
    })


async def analyze_with_claude(data: dict) -> str:
    symbol    = data.get("symbol", "غير محدد")
    action    = data.get("action", "غير محدد")
    price     = data.get("price", "غير محدد")
    indicator = data.get("indicator", "غير محدد")
    timeframe = data.get("timeframe", "غير محدد")
    volume    = data.get("volume", "")

    prompt = f"""أنت محلل تقني متخصص في الأسواق المالية. وصلتك إشارة تداول من TradingView:

الرمز: {symbol}
الإشارة: {action}
السعر الحالي: {price}
المؤشر: {indicator}
الإطار الزمني: {timeframe}
{f"الحجم: {volume}" if volume else ""}

قدّم تحليلاً موجزاً واحترافياً يشمل:
1. تقييم الإشارة (قوية/متوسطة/ضعيفة)
2. نقاط الدخول والخروج المقترحة
3. مستوى المخاطرة
4. توصية نهائية

كن موجزاً ومباشراً (4-6 أسطر)."""

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]


async def send_telegram(data: dict, analysis: str):
    action = data.get("action", "")
    symbol = data.get("symbol", "")
    price  = data.get("price", "")
    emoji  = "🟢" if action == "BUY" else "🔴"

    message = f"""{emoji} *إشارة: {action} {symbol}*
السعر: `{price}`
المؤشر: {data.get('indicator', '')}
الإطار: {data.get('timeframe', '')}

*تحليل Claude:*
{analysis}"""

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
        )


@app.get("/")
async def health():
    return {"status": "running", "message": "TradingView x Claude Bot is live!"}


@app.post("/test")
async def test_webhook():
    sample = {
        "symbol": "BTCUSDT",
        "action": "BUY",
        "price": 67420.5,
        "indicator": "RSI Oversold + MA Cross",
        "timeframe": "1H",
        "volume": 12400,
    }
    analysis = await analyze_with_claude(sample)
    return {"sample_payload": sample, "analysis": analysis}
