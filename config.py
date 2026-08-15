import os
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی از فایل .env در محیط توسعه محلی
load_dotenv()

class Config:
    # ----------------------------------------------------
    # تنظیمات اصلی ربات تلگرام
    # ----------------------------------------------------
    BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
    BOT_USERNAME = os.getenv("BOT_USERNAME", "miyanji_ir_bot").strip()
    
    # شناسه ادمین ارشد (پشتیبانی از چند ادمین یا تک ادمین)
    _admin_env = os.getenv("ADMIN_ID")
    ADMIN_ID = int(_admin_env) if _admin_env else 1802649782
    ADMIN_IDS = [ADMIN_ID]

    # ----------------------------------------------------
    # کانال‌ها و شناسه بایگانی سیستم
    # ----------------------------------------------------
    _archive_env = os.getenv("ARCHIVE_CHANNEL_ID")
    ARCHIVE_CHANNEL_ID = int(_archive_env) if _archive_env else -1003862335372

    _channel_env = os.getenv("MIYANJI_CHANNEL_ID")
    MIYANJI_CHANNEL_ID = int(_channel_env) if _channel_env else -1002738838047

    # ----------------------------------------------------
    # تنظیمات پایگاه داده Supabase
    # ----------------------------------------------------
    _supabase_url_raw = os.getenv("SUPABASE_URL", "")
    _supabase_key_raw = os.getenv("SUPABASE_KEY", "")

    SUPABASE_URL = _supabase_url_raw.strip(' "\'')
    SUPABASE_KEY = _supabase_key_raw.strip(' "\'')
    
    SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "miyanji-docs").strip()

    # ----------------------------------------------------
    # تنظیمات سرور Render
    # ----------------------------------------------------
    PORT = int(os.getenv("PORT", 10000))
    WEB_SERVER_ALIVE_MSG = "Miyanji is running!"

    # ----------------------------------------------------
    # ثوابت مالی و کارمزدها
    # ----------------------------------------------------
    COMMISSION_PERCENT = float(os.getenv("COMMISSION_PERCENT", 10.0))
    AFFILIATE_SHARE_PERCENT = float(os.getenv("AFFILIATE_SHARE_PERCENT", 20.0))

    # ----------------------------------------------------
    # کد دسته‌بندی موضوعات قرارداد و پیشوندها
    # ----------------------------------------------------
    STYLE_CODES = {
        "💻 برنامه‌نویسی و توسعه (DEV)": "DEV",
        "🎨 طراحی و گرافیک (DS)": "DS",
        "📝 تولید محتوا و سئو (CNT)": "CNT",
        "🎓 خدمات مشاوره و آموزش (CNS)": "CNS",
        "🌐 خدمات تجاری و عمومی (TRD)": "TRD",
        "📦 سایر موارد (GEN)": "GEN",
    }

    # نگاشت کلیدهای معامله جهت یکپارچه‌سازی با Supabase
    DEAL_KEYS = {
        "ID": "contract_id",
        "TITLE": "title",
        "AMOUNT": "amount",
        "BUYER": "employer_id",
        "SELLER": "freelancer_id",
        "STATUS": "status",
        "CATEGORY": "category"
    }

    DEBUG = False

# نمونه‌سازی از کانفیگ
config = Config()
