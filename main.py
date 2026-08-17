import logging

import telebot

from config import config
import user as user_module
import admin as admin_module
from keep_alive import keep_alive

# ----------------------------------------------------
# تنظیمات لاگینگ سیستم
# ----------------------------------------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("Miyanji_Bot")

# ----------------------------------------------------
# تابع اصلی اجرای ربات (Main Entry Point)
# ----------------------------------------------------
def main() -> None:
    """راه‌اندازی کلاینت ربات و ثبت تمامی هندلرهای واقعی ربات میانجی"""
    if not config.BOT_TOKEN:
        logger.error("خطا: BOT_TOKEN در فایل کانفیگ یا متغیرهای محیطی یافت نشد.")
        return

    # ایجاد شیء اصلی ربات (pyTelegramBotAPI)
    #
    # نکتهٔ مهم (رفع باگ اصلی): نسخهٔ قبلی این فایل از کتابخانهٔ کاملاً متفاوتی
    # (python-telegram-bot) استفاده می‌کرد، در حالی که تمام منطق واقعی ربات
    # (منوها، ثبت معامله، امضا، کیف پول، فیش واریزی، داوری و ...) در
    # user.py/admin.py با کتابخانهٔ telebot (pyTelegramBotAPI) نوشته شده است.
    # چون این دو کتابخانه با هم سازگار نیستند و register_user_handlers /
    # register_admin_handlers هرگز از main.py صدا زده نمی‌شدند، عملاً هیچ‌یک
    # از دکمه‌های واقعی ربات به کدشان وصل نبودند و کاربر با کلیک روی آن‌ها
    # پاسخی دریافت نمی‌کرد یا به پیام پیش‌فرض «این بخش هنوز فعال نمی‌شود» برخورد
    # می‌کرد. با این بازنویسی، هر دو ماژول به‌درستی روی همین شیء bot ثبت می‌شوند.
    bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode=None, threaded=True)

    # ثبت هندلرهای کاربر (منوی اصلی، ثبت/ویرایش/امضای معامله، فیش واریزی،
    # تحویل/رد پروژه، کیف پول، درخواست داوری، دریافت PDF و ...)
    user_module.register_user_handlers(bot)

    # ثبت هندلرهای پنل مدیریت (آمار، تایید/رد فیش، پرونده‌های داوری و صدور رای،
    # تایید/رد درخواست‌های کیف پول)
    admin_module.register_admin_handlers(bot)

    # سرور HTTP سبک جهت زنده نگه‌داشتن سرویس روی Render (health check)
    keep_alive()

    logger.info("ربات میانجی با موفقیت مقداردهی شد و آماده دریافت دستورات است...")

    # شروع دریافت پیام‌ها از سرورهای تلگرام (Polling)
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)

if __name__ == '__main__':
    main()
