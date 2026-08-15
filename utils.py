import re
import random
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from config import config

logger = logging.getLogger("Miyanji_Utils")

# ====================================================
# ۱. جدول کدگذاری حوزه‌ها جهت بایگانی رسمی
# ====================================================
CATEGORY_CODES = {
    "DEV": "DEV",       # برنامه‌نویسی و IT
    "DESIGN": "DSG",    # طراحی و گرافیک
    "ACADEMIC": "RSH",  # دانشجویی و پژوهشی
    "TEACHING": "EDU",  # آموزشی و تدریس
    "GEN": "GEN"        # عمومی و خدمات
}

# ====================================================
# ۲. شروط و مفاد حقوقی تخصصی هر حوزه (بر اساس قوانین ایران)
# ====================================================
CATEGORY_LEGAL_CLAUSES = {
    "DESIGN": (
        "📜 **مفاد تخصصی حوزه طراحی و گرافیک:**\n"
        "۱. کلیه حقوق مادی و معنوی طرح نهایی پس از تسویه کامل حساب به کارفرما منتقل می‌گردد.\n"
        "۲. مجری متعهد به تحویل سورس‌کدها و فایل‌های لایه باز (AI, PSD, CDR) با کیفیت اصلی و تمامی فونت‌ها می‌باشد.\n"
        "۳. مجری اصالت طرح را تضمین کرده و متعهد است طرح کپی‌برداری مستقیم از آثار دیگران نباشد.\n"
        "۴. اصلاحات و ویرایش طرح تا ۲ مرحله در چارچوب فرم اولیه رایگان بوده و تغییرات کلی مستلزم پرداخت هزینه مجزا است."
    ),
    "DEV": (
        "📜 **مفاد تخصصی حوزه برنامه‌نویسی و نرم‌افزار:**\n"
        "۱. مجری متعهد به تحویل کامل سورس‌کد، داکیومنت راهنمای نصب و ساختار دیتابیس می‌باشد.\n"
        "۲. مجری دوره پشتیبانی و رفع باگ‌های احتمالی مرتبط با سرفصل‌ها را تا ۱۴ روز پس از تحویل نهایی تضمین می‌نماید.\n"
        "۳. مجری متعهد است کدها فاقد هرگونه درِ پشتی (Backdoor)، کدهای مخرب یا لایسنس‌های محدودکننده غیرمجاز باشند.\n"
        "۴. تغییر در سرفصل‌های فنی پس از تایید قرارداد، مستلزم ثبت متمم قرارداد و توافق مجدد خواهد بود."
    ),
    "ACADEMIC": (
        "📜 **مفاد تخصصی حوزه پژوهش و پروژه‌های آموزشی/دانشجویی:**\n"
        "۱. مجری متعهد به رعایت اصل عدم سرقت ادبی (Plagiarism) و ارائه گزارش سلامت متن می‌باشد.\n"
        "۲. تحویل خروجی‌ها طبق جدول زمانی مصوب الزامی بوده و تاخیر غیرمجاز شامل جریمه خواهد بود.\n"
        "۳. مجری متعهد به ارائه فایل‌های محاسباتی و داده‌های خام (نظیر SPSS، MATLAB یا Python) در صورت درخواست می‌باشد."
    ),
    "TEACHING": (
        "📜 **مفاد تخصصی حوزه تدریس و آموزش آنلاین:**\n"
        "۱. مدرس متعهد به پوشش کامل سرفصل‌های توافق‌شده در زمان‌بندی مشخص می‌باشد.\n"
        "۲. ضبط و انتشار ویدیوهای آموزشی اختصاصی تنها با مجوز کتبی طرفین امکان‌پذیر است."
    ),
    "GEN": (
        "📜 **مفاد عمومی خدمات:**\n"
        "۱. مجری متعهد به انجام مفاد موضوع قرارداد با بالاترین کیفیت کاری و رعایت حسن نیت می‌باشد.\n"
        "۲. کارفرما متعهد به بررسی و اعلام نظر در خصوص خروجی‌ها ظرف حداکثر ۴۸ ساعت پس از تحویل می‌باشد."
    )
}

# ====================================================
# ۳. توابع کمکی تبدیل اعداد، زمان و فرمت‌دهی
# ====================================================

def fa_to_en_digits(text: str) -> str:
    """تبدیل اعداد فارسی و عربی به اعداد انگلیسی"""
    if not text:
        return ""
    fa_digits = "۰۱۲۳۴۵۶۷۸۹"
    ar_digits = "٠١٢٣٤٥٦٧٨٩"
    en_digits = "0123456789"
    
    translation_table = str.maketrans(fa_digits + ar_digits, en_digits * 2)
    return str(text).translate(translation_table)

def get_jalali_year_month() -> str:
    """محاسبه هوشمند و دقیق سال و ماه شمسی دو رقمی بدون نیازمندی به پکیج خارجی"""
    now = datetime.now()
    g_y, g_m, g_d = now.year, now.month, now.day
    
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if (g_y % 4 == 0 and g_y % 100 != 0) or (g_y % 400 == 0):
        g_days_in_month[1] = 29

    gy = g_y - 1600
    gm = g_m - 1
    gd = g_d - 1

    g_day_no = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
    for i in range(gm):
        g_day_no += g_days_in_month[i]
    g_day_no += gd

    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    jm = 0
    for i in range(12):
        if j_day_no < j_days_in_month[i]:
            jm = i + 1
            break
        j_day_no -= j_days_in_month[i]

    year_2digit = f"{jy % 100:02d}"
    month_2digit = f"{jm:02d}"
    
    return f"{year_2digit}{month_2digit}"

def generate_archive_contract_id(category: str) -> str:
    """تولید کد یکتا و حقوقی بایگانی (نمونه: DSG-0508-8492)"""
    prefix = CATEGORY_CODES.get(category, "GEN")
    date_code = get_jalali_year_month()
    rand_code = random.randint(1000, 9999)
    return f"{prefix}-{date_code}-{rand_code}"

def parse_single_message_contract(text: str) -> Optional[Dict[str, Any]]:
    """پارس کردن فرم متنی یکجا با پشتیبانی از اعداد فارسی و فرمت‌های مختلف"""
    try:
        if not text:
            return None

        clean_text = fa_to_en_digits(text)

        parsed_data = {
            "category": "GEN",
            "role": "employer",
            "title": "",
            "amount": 0.0,
            "deadline": 1,
            "milestones": [],
            "description": ""
        }

        # ۱. استخراج نقش
        if "مجری" in clean_text or "فروشنده" in clean_text or "پیمانکار" in clean_text:
            parsed_data["role"] = "freelancer"
        else:
            parsed_data["role"] = "employer"

        # ۲. استخراج عنوان
        title_match = re.search(r"عنوان:\s*(.+)", clean_text)
        if title_match:
            parsed_data["title"] = title_match.group(1).strip()

        # ۳. استخراج مبلغ کل
        amount_match = re.search(r"مبلغ کل.*:\s*([\d,]+)", clean_text)
        if amount_match:
            clean_amount = amount_match.group(1).replace(",", "").strip()
            parsed_data["amount"] = float(clean_amount)

        # ۴. استخراج مهلت تحویل (روز)
        deadline_match = re.search(r"مهلت.*:\s*(\d+)", clean_text)
        if deadline_match:
            parsed_data["deadline"] = int(deadline_match.group(1))

        # ۵. استخراج مراحل پرداخت (Milestones)
        milestones_block = re.search(r"مراحل پرداخت:\s*\n((?:[\d]+\..+\n?)+)", clean_text)
        if milestones_block:
            m_lines = milestones_block.group(1).strip().split("\n")
            for line in m_lines:
                m_match = re.search(r"\d+\.\s*(.+):\s*([\d,]+)", line)
                if m_match:
                    m_title = m_match.group(1).strip()
                    m_amt = float(m_match.group(2).replace(",", "").strip())
                    parsed_data["milestones"].append({
                        "title": m_title,
                        "amount": m_amt,
                        "status": "pending"
                    })

        # ۶. استخراج توضیحات
        desc_match = re.search(r"شرح تعهدات:\s*(.+)", clean_text, re.DOTALL)
        if desc_match:
            parsed_data["description"] = desc_match.group(1).strip()

        if not parsed_data["title"] or parsed_data["amount"] <= 0:
            return None

        return parsed_data

    except Exception as e:
        logger.error(f"خطا در پارس کردن متن معامله: {e}")
        return None

def calculate_commission(amount: float) -> Tuple[float, float]:
    """محاسبه میزان کارمزد می‌انجی و مبلغ خالص دریافتی مجری"""
    comm_pct = getattr(config, 'COMMISSION_PERCENT', 2.5)
    commission = (amount * comm_pct) / 100.0
    net_amount = amount - commission
    return commission, net_amount

# ====================================================
# ۴. توابع ساخت لینک سریع، نمایش سند و پنل شیشه‌ای
# ====================================================

def generate_quick_contract_link(bot_username: str, contract_id: str) -> str:
    """تولید لینک اختصاصی امضای سریع قرارداد (Deep Link)"""
    return f"https://t.me/{bot_username}?start=contract_{contract_id}"

def generate_draft_preview_text(draft_data: Dict[str, Any]) -> str:
    """تولید متن پیش‌نمایش پیش‌نویس معامله جهت نمایش و ویرایش"""
    title = draft_data.get("title", "ثبت نشده")
    amount = float(draft_data.get("amount", 0))
    deadline = draft_data.get("deadline", 1)
    desc = draft_data.get("description", "ثبت نشده")
    role = draft_data.get("role", "employer")
    role_str = "کارفرما (خریدار)" if role == "employer" else "مجری (فروشنده)"

    comm, net = calculate_commission(amount)

    text = (
        "📋 **پیش‌نویس قرارداد شما:**\n"
        "───────────────────────\n"
        f"👤 **نقش شما:** {role_str}\n"
        f"📌 **عنوان معامله:** {title}\n"
        f"💰 **مبلغ کل:** {amount:,.0f} تومان\n"
        f"⏱ **مهلت تحویل:** {deadline} روز\n"
        f"💳 **کارمزد سامانه (۲.۵٪):** {comm:,.0f} تومان\n"
        f"🎯 **مبلغ خالص مجری:** {net:,.0f} تومان\n"
        f"📝 **شرح تعهدات:**\n{desc}\n"
        "───────────────────────\n"
        "جهت تایید، ویرایش هر بخش یا لغو معامله، از دکمه‌های زیر استفاده کنید:"
    )
    return text

def generate_contract_text(contract: Dict[str, Any], buyer_user: Dict[str, Any] = None, seller_user: Dict[str, Any] = None) -> str:
    """تولید متن رسمی قرارداد همراه با وضعیت امضاها، شماره تماس پاسخگو، سقف ویرایش رایگان و پنل شیشه‌ای"""
    cid = contract.get("contract_id") or contract.get("id", "---")
    category = contract.get("category", "GEN")
    title = contract.get("title", "بدون عنوان")
    amount = float(contract.get("amount", 0))
    deadline = contract.get("deadline", 1)
    desc = contract.get("description", "بدون توضیحات تکمیلی")
    milestones = contract.get("milestones", [])
    
    is_signed = contract.get("signed_by_second_party", False)
    sign_status = "✅ امضا شده توسط هر دو طرف" if is_signed else "⏳ در انتظار امضای طرف دوم"
    free_edits = contract.get("free_edits_left", 3)

    comm, net = calculate_commission(amount)

    # استخراج هوشمند شماره تماس پاسخگوی طرفین
    buyer_phone = contract.get("buyer_phone") or (buyer_user.get("phone_number") if buyer_user else None) or "ثبت نشده"
    seller_phone = contract.get("seller_phone") or (seller_user.get("phone_number") if seller_user else None) or "ثبت نشده"

    text = (
        f"🏛 **سند رسمی معامله و واسطه‌گری می‌انجی**\n"
        f"🔖 **شناسه اختصاصی بایگانی:** `{cid}`\n"
        f"✒️ **وضعیت امضا:** {sign_status}\n"
        f"🔄 **ویرایش رایگان باقی‌مانده:** {free_edits} بار\n"
        "───────────────────────\n"
        f"📌 **عنوان معامله:** {title}\n"
        f"💵 **مبلغ کل معامله:** {amount:,.0f} تومان\n"
        f"💳 **کارمزد سامانه ({getattr(config, 'COMMISSION_PERCENT', 2.5)}%):** {comm:,.0f} تومان\n"
        f"🎯 **مبلغ خالص دریافتی مجری:** {net:,.0f} تومان\n"
        f"⏳ **مهلت تحویل پروژه:** {deadline} روز\n\n"
        f"👤 **کارفرما (خریدار):**\n"
        f"📞 شماره پاسخگو: `{buyer_phone}`\n\n"
        f"🛠 **مجری (فروشنده):**\n"
        f"📞 شماره پاسخگو: `{seller_phone}`\n\n"
    )

    if milestones:
        text += "📊 **جدول مراحل پرداخت و آزادسازی امانی:**\n"
        for idx, m in enumerate(milestones, 1):
            st = "✅ آزاد شده" if m.get("status") == "released" else "🔒 در حساب امانت (بلوکه)"
            text += f"   {idx}. {m.get('title')}: {float(m.get('amount', 0)):,.0f} تومان [{st}]\n"
        text += "\n"

    specific_clauses = CATEGORY_LEGAL_CLAUSES.get(category, CATEGORY_LEGAL_CLAUSES["GEN"])
    
    text += (
        f"📝 **شرح تعهدات اختصاصی طرفین:**\n{desc}\n\n"
        f"{specific_clauses}\n\n"
        "⚖️ **شرایط واسطه‌گری، امانت‌داری و داوری آنلاین می‌انجی:**\n"
        "۱. **تضمین امن وجوه (Escrow):** کلیه مبالغ تا زمان تایید تحویل توسط کارفرما یا صدور رای داوری، در حساب امانت واسط می‌انجی **بلوکه** می‌ماند.\n"
        "۲. **استناد قانونی:** این سند طبق ماده ۱۰ قانون مدنی و مواد ۶، ۷ و ۱۲ قانون تجارت الکترونیک، یک سند الکترونیکی رسمی، معتبر و غیرقابل انکار است.\n"
        "۳. **شرط داوری:** پلتفرم می‌انجی بر اساس ماده ۴۵۵ آیین دادرسی مدنی به عنوان **داور مرضی‌الطرفین** تعیین شده و رای آن در صورت بروز اختلاف، قطعی و لازم‌الاجرا خواهد بود."
    )

    return text

def format_receipt_rejection_msg(contract_id: str, reason: str) -> str:
    """قالب‌بندی پیام اعلام رد فیش واریزی برای کارفرما"""
    return (
        f"❌ **فیش واریزی شما برای قرارداد `{contract_id}` تایید نشد.**\n\n"
        f"📌 **علت رد فیش:**\n{reason}\n\n"
        "💡 لطفاً فیش صحیح را از طریق پنل شیشه‌ای قرارداد مجدداً ارسال کنید."
    )

def format_project_rejection_msg(contract_id: str, reason: str, free_edits_left: int) -> str:
    """قالب‌بندی پیام رد پروژه/پایان کار توسط ادمین به همراه تعداد ویرایش مجانی باقی‌مانده"""
    return (
        f"⚠️ **پروژه تحویلی برای قرارداد `{contract_id}` رد شد.**\n\n"
        f"📌 **دلیل رد/نیاز به اصلاح:**\n{reason}\n\n"
        f"🔄 **تعداد ویرایش رایگان باقی‌مانده:** {free_edits_left} بار\n"
        "لطفاً اصلاحات لازم را انجام داده و مجدداً فایل/پروژه را ارسال کنید."
    )

def convert_to_jalali(date_str: str) -> str:
    """تبدیل تاریخ به فرمت مناسب"""
    return date_str if date_str else "ثبت نشده"

def format_currency(amount: float) -> str:
    """فرمت‌دهی مبلغ به تومان"""
    return f"{amount:,.0f} تومان"
