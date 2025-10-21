from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from bs4 import BeautifulSoup
import os

# --- Configuration ---
BOT_TOKEN = os.getenv("BOT_TOKEN")       # from @BotFather
CHAT_ID = os.getenv("CHAT_ID")           # your Telegram user ID (from @userinfobot)

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

# --- Function to fetch IPO GMP data ---
def get_ipo_gmp_data():
    url = "https://www.investorgain.com/ipo-grey-market-premium/latest-ipos/"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"class": "table"})
    data = []

    if not table:
        return data

    for row in table.find_all("tr")[1:]:
        cols = [c.text.strip() for c in row.find_all("td")]
        if len(cols) >= 5:
            ipo_name = cols[0]
            try:
                price_str = cols[2].split("–")[-1].replace("₹", "").strip()
                price = float(price_str)
                gmp_str = cols[3].replace("₹", "").replace("+", "").replace("-", "").strip()
                gmp = float(gmp_str)
                gmp_percent = (gmp / price) * 100
                data.append((ipo_name, price, gmp, gmp_percent))
            except:
                continue
    return data

# --- Function to check and notify ---
def check_and_notify():
    try:
        data = get_ipo_gmp_data()
        high = [d for d in data if d[3] > 50]

        if high:
            msg = "🔥 IPOs with GMP > 50%:\n\n"
            for d in high:
                msg += f"• {d[0]} — GMP ₹{d[2]} (~{d[3]:.1f}%)\n"
        else:
            msg = "📉 No IPOs with GMP > 50% right now."

        bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Error: {e}")

# --- /check Command Handler ---
def check_command(update: Update, context):
    user_id = update.message.chat_id
    if str(user_id) != CHAT_ID:
        update.message.reply_text("❌ You are not authorized to use this bot.")
        return
    update.message.reply_text("⏳ Checking latest IPO GMPs...")
    data = get_ipo_gmp_data()
    high = [d for d in data if d[3] > 50]
    if high:
        msg = "🔥 IPOs with GMP > 50%:\n\n"
        for d in high:
            msg += f"• {d[0]} — GMP ₹{d[2]} (~{d[3]:.1f}%)\n"
    else:
        msg = "📉 No IPOs with GMP > 50% right now."
    update.message.reply_text(msg)

# --- Telegram Dispatcher ---
dispatcher = Dispatcher(bot, None, use_context=True)
dispatcher.add_handler(CommandHandler("check", check_command))

# --- Flask Route for Webhook ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

# --- Health Check Route ---
@app.route("/")
def home():
    return "✅ IPO GMP Bot is running!"

# --- Background Scheduler (every Monday 9 AM IST) ---
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
scheduler.add_job(check_and_notify, "cron", day_of_week="mon", hour=9, minute=0)
scheduler.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
