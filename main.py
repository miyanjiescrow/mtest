import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from config import config
from database import db

# ----------------------------------------------------
# تنظیمات لاگینگ سیستم
# ----------------------------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("Miyanji_Bot")

# ----------------------------------------------------
# هندلرهای اصلی دستورات
# ----------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور /start: ثبت‌نام یا بروزرسانی کاربر و ارسال پیام خوش‌آمدگویی"""
    user = update.effective_user
    if not user:
        return

    # ثبت یا بروزرسانی کاربر در دیتابیس Supabase
    db.register_or_update_user(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "کاربر"
    )

    welcome_text = (
        f"سلام {user.first_name} عزیز! 👋\n\n"
        f"به ربات مدیریت معاملات و قراردادهای **میانجی** خوش آمدید.\n"
        f"سیستم آماده ارائه خدمات امنیتی و حقوقی به شماست."
    )
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور /help: راهنمای استفاده از ربات"""
    help_text = (
        "📌 **راهنمای ربات میانجی**\n\n"
        "🔹 /start - شروع مجدد ربات و مشاهده پنل اصلی\n"
        "🔹 /help - دریافت راهنمای کامل استفاده از سیستم\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# ----------------------------------------------------
# تابع اصلی اجرای ربات (Main Entry Point)
# ----------------------------------------------------
def main() -> None:
    """راه‌اندازی کلاینت ربات و اضافه کردن هندلرها"""
    if not config.BOT_TOKEN:
        logger.error("خطا: BOT_TOKEN در فایل کانفیگ یا متغیرهای محیطی یافت نشد.")
        return

    # ایجاد شیء اصلی برنامه
    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    # ۱. تعریف ConversationHandler جهت مدیریت جریان‌های چندمرحله‌ای
    sample_conversation = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={},
        fallbacks=[CommandHandler("help", help_command)],
        per_message=False  # جلوگیری از هشدار PTBUserWarning
    )

    # ۲. ثبت هندلرهای دستورات و مکالمات در برنامه
    app.add_handler(sample_conversation)
    app.add_handler(CommandHandler("help", help_command))

    logger.info("ربات میانجی با موفقیت مقداردهی شد و آماده دریافت دستورات است...")

    # ۳. شروع دریافت پیام‌ها از سرورهای تلگرام (Polling)
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
