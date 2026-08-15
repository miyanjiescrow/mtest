import os
import sys
import time
import signal
import logging
from telebot import TeleBot

# بارگذاری ماژول‌های داخلی پروژه می‌انجی
from config import config
from keep_alive import keep_alive
import database as db

# ایمپورت مستقیم هندلرهای کاربر و ادمین
from user import register_user_handlers
from admin import register_admin_handlers

# ----------------------------------------------------
# پیکربندی سیستم لاگینگ (Logging)
# ----------------------------------------------------
logging.basicConfig(
    level=logging.INFO if not getattr(config, 'DEBUG', False) else logging.DEBUG,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("Miyanji_Main")

def main():
    """نقطه ورود اصلی اجرای پلتفرم واسطه‌گری و داوری آنلاین می‌انجی"""
    logger.info("=== در حال راه‌اندازی سامانه حقوقی و واسطه‌گری می‌انجی ===")

    # ۱. بررسی صحت توکن ربات
    if not config.BOT_TOKEN:
        logger.critical("خطای بحرانی: BOT_TOKEN در فایل کانفیگ یا متغیرهای محیطی Render تعریف نشده است!")
        sys.exit(1)

    # ۲. ایجاد نمونه اصلی TeleBot
    bot = TeleBot(token=config.BOT_TOKEN, parse_mode=None)

    # ۳. روشن کردن سرور نگهدارنده (Keep Alive) جهت زنده نگه داشتن ربات روی Render
    try:
        keep_alive()
        logger.info(f"سرور وب زنده نگه‌دارنده (Keep Alive) روی پورت {getattr(config, 'PORT', 8080)} با موفقیت فعال شد.")
    except Exception as e:
        logger.error(f"هشدار در راه‌اندازی سرور وب Keep Alive: {e}")

    # ۴. ثبت تمامی هندلرهای کاربر و ادمین به صورت مستقیم
    try:
        register_user_handlers(bot)
        register_admin_handlers(bot)
        logger.info("تمامی هندلرهای کاربر، ثبت معامله یکجا، کیف پول و داوری ادمین ثبت شدند.")
    except Exception as e:
        logger.critical(f"خطای بحرانی در ثبت هندلرها: {e}")
        sys.exit(1)

    # ۵. مدیریت سیگنال‌های خروج جهت بستن تمیز ربات در سرویس‌های ابری
    def signal_handler(sig, frame):
        logger.info("سیگنال توقف (Termination) دریافت شد. در حال بستن اتصالات ربات...")
        try:
            bot.stop_polling()
        except Exception:
            pass
        logger.info("ربات می‌انجی با موفقیت متوقف شد.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # ۶. پاک‌سازی وب‌هوک و آپدیت‌های تلنبار شده در زمان خاموشی
    try:
        bot.delete_webhook(drop_pending_updates=True)
        logger.info("آپدیت‌های معوقه و وب‌هوک‌های قبلی با موفقیت پاک‌سازی شدند.")
    except Exception as e:
        logger.warning(f"هشدار در پاک‌سازی آپدیت‌های معوقه: {e}")

    # ۷. اجرای حلقه اصلی ربات با قابلیت بازیابی خودکار (Auto-Reconnect)
    logger.info("🚀 ربات می‌انجی با موفقیت لایو شد و آماده ارائه خدمات است.")

    while True:
        try:
            bot.polling(
                non_stop=True,
                interval=1,
                timeout=60,
                long_polling_timeout=60,
                skip_pending=True
            )
        except Exception as e:
            logger.error(f"خطا در شبکه یا حلقه Polling ربات: {e}")
            logger.info("در حال تلاش مجدد برای اتصال پس از ۵ ثانیه...")
            time.sleep(5)

if __name__ == "__main__":
    main()
