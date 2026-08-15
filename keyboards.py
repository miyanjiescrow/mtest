from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """منوی اصلی ربات با پوشش کامل تمام قابلیت‌ها"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🤝 ایجاد معامله جدید"),
        KeyboardButton("📜 معاملات من")
    )
    markup.add(
        KeyboardButton("💰 کیف پول و اعتبار"),
        KeyboardButton("📞 پشتیبانی و ارتباط با ما")
    )
    markup.add(
        KeyboardButton("⚖️ قوانین و راهنمای حقوقی")
    )
    if is_admin:
        markup.add(KeyboardButton("👨‍💼 پنل مدیریت"))
    return markup

def get_role_keyboard() -> ReplyKeyboardMarkup:
    """کیبورد انتخاب نقش کاربر در معامله"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("👤 کارفرما (خریدار)"), KeyboardButton("🛠 مجری (فروشنده/پیمانکار)"))
    markup.add(KeyboardButton("❌ انصراف و بازگشت به منو"))
    return markup

def get_category_keyboard() -> ReplyKeyboardMarkup:
    """کیبورد انتخاب نوع و دسته‌بندی قرارداد"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("💻 برنامه‌نویسی و IT"),
        KeyboardButton("🎨 طراحی و گرافیک"),
        KeyboardButton("🎓 دانشجویی و پژوهشی"),
        KeyboardButton("📚 آموزشی و تدریس"),
        KeyboardButton("📑 عمومی و خدمات")
    )
    markup.add(KeyboardButton("❌ انصراف و بازگشت به منو"))
    return markup

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """کیبورد انصراف کلی"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("❌ انصراف و بازگشت به منو"))
    return markup

def get_contract_preview_inline(draft_id: str = "draft") -> InlineKeyboardMarkup:
    """پنل شیشه‌ای پیش‌نمایش، ویرایش و تایید نهایی پیش از امضا"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ تایید و مرحله امضا", callback_data=f"confirm_draft_{draft_id}"),
        InlineKeyboardButton("✏️ ویرایش پیش‌نویس", callback_data=f"edit_draft_{draft_id}")
    )
    markup.add(
        InlineKeyboardButton("❌ لغو پیش‌نویس", callback_data="cancel_draft")
    )
    return markup

def get_draft_edit_inline(draft_id: str = "draft") -> InlineKeyboardMarkup:
    """منوی شیشه‌ای انتخاب بخش برای ویرایش مجزا"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✏️ ویرایش عنوان", callback_data=f"edit_field_title_{draft_id}"),
        InlineKeyboardButton("💰 ویرایش مبلغ", callback_data=f"edit_field_amount_{draft_id}")
    )
    markup.add(
        InlineKeyboardButton("⏱ ویرایش مهلت تحویل", callback_data=f"edit_field_deadline_{draft_id}"),
        InlineKeyboardButton("📝 ویرایش شرح تعهدات", callback_data=f"edit_field_desc_{draft_id}")
    )
    markup.add(
        InlineKeyboardButton("🔙 بازگشت به پیش‌نمایش قرارداد", callback_data=f"back_to_preview_{draft_id}")
    )
    return markup

def get_phone_sign_keyboard() -> ReplyKeyboardMarkup:
    """کیبورد ارسال شماره جهت امضای الکترونیک"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📱 ارسال شماره جهت ثبت امضا", request_contact=True))
    markup.add(KeyboardButton("❌ انصراف و بازگشت به منو"))
    return markup

def get_skip_work_phone_keyboard() -> ReplyKeyboardMarkup:
    """کیبورد ثبت شماره کاری اختیاری"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("⏭ رد کردن و استفاده از شماره تلگرام"))
    markup.add(KeyboardButton("❌ انصراف و بازگشت به منو"))
    return markup

def get_wallet_inline() -> InlineKeyboardMarkup:
    """دکمه‌های شیشه‌ای مدیریت کیف پول"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💳 شارژ حساب", callback_data="deposit_wallet"),
        InlineKeyboardButton("🏧 درخواست برداشت", callback_data="withdraw_wallet")
    )
    return markup

def get_support_inline() -> InlineKeyboardMarkup:
    """دکمه‌های شیشه‌ای بخش پشتیبانی و سوالات متداول"""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("❓ سوالات متداول (FAQ)", callback_data="faq_info"),
        InlineKeyboardButton("⚖️ درخواست داوری برای یک معامله", callback_data="request_dispute"),
        InlineKeyboardButton("💬 ارتباط مستقیم با پشتیبانی", url="https://t.me/Miyanji_Support")
    )
    return markup

def get_wallet_amount_cancel_keyboard() -> ReplyKeyboardMarkup:
    """کیبورد لغو حین وارد کردن مبلغ شارژ/برداشت"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("❌ انصراف و بازگشت به منو"))
    return markup

def get_wallet_admin_approval_inline(request_type: str, user_id: int, amount: float) -> InlineKeyboardMarkup:
    """دکمه شیشه‌ای تایید/رد درخواست شارژ یا برداشت کیف پول برای ادمین"""
    markup = InlineKeyboardMarkup(row_width=2)
    amt_int = int(amount)
    markup.add(
        InlineKeyboardButton("✅ تایید", callback_data=f"wallet_ok_{request_type}_{user_id}_{amt_int}"),
        InlineKeyboardButton("❌ رد درخواست", callback_data=f"wallet_no_{request_type}_{user_id}_{amt_int}")
    )
    return markup

def get_contract_action_keyboard(contract_id: str, user_role: str, status: str, has_milestones: bool = False) -> InlineKeyboardMarkup:
    """دکمه‌های مدیریتی قرارداد بسته به وضعیت فعلی معامله و نقش کاربر"""
    markup = InlineKeyboardMarkup(row_width=2)

    if status == "pending_approval":
        markup.add(InlineKeyboardButton("✍️ امضا و تایید قرارداد", callback_data=f"sign_contract_{contract_id}"))
        markup.add(InlineKeyboardButton("🔄 پیشنهاد مبلغ جدید", callback_data=f"bargain_{contract_id}"))

    if status == "bargaining":
        markup.add(InlineKeyboardButton("✍️ تایید مبلغ و امضا", callback_data=f"sign_contract_{contract_id}"))
        markup.add(InlineKeyboardButton("🔄 پیشنهاد مبلغ دیگر", callback_data=f"bargain_{contract_id}"))

    # واریز فیش وجه امانی توسط کارفرما
    if status == "awaiting_payment" and user_role == "employer":
        markup.add(InlineKeyboardButton("💳 ارسال فیش واریزی", callback_data=f"upload_receipt_{contract_id}"))

    # تحویل پروژه توسط مجری
    if status == "active" and user_role == "freelancer":
        markup.add(InlineKeyboardButton("🚀 تحویل پروژه / ارسال فایل", callback_data=f"deliver_{contract_id}"))

    # تایید یا رد پروژه تحویلی توسط کارفرما
    if status == "delivered" and user_role == "employer":
        markup.add(InlineKeyboardButton("✅ تایید نهایی پروژه و آزادسازی وجه", callback_data=f"final_confirm_{contract_id}"))
        markup.add(InlineKeyboardButton("⚠️ عدم تایید و درخواست اصلاح پروژه", callback_data=f"reject_project_{contract_id}"))

    if has_milestones:
        markup.add(InlineKeyboardButton("📊 مدیریت مراحل پرداخت", callback_data=f"manage_milestones_{contract_id}"))

    if status not in ["completed", "cancelled", "resolved_employer", "resolved_freelancer"]:
        markup.add(InlineKeyboardButton("❌ لغو معامله", callback_data=f"cancel_contract_{contract_id}"))

    markup.add(InlineKeyboardButton("📥 دریافت فایل PDF", callback_data=f"get_pdf_{contract_id}"))
    return markup

# ====================================================
# دکمه‌های جدید: مدیریت فیش واریزی و بررسی پروژه (ادمین/کارفرما)
# ====================================================

def get_receipt_admin_approval_inline(contract_id: str, buyer_id: int) -> InlineKeyboardMarkup:
    """پنل مدیریت جهت تایید یا رد فیش واریزی توسط ادمین"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ تایید فیش و فعالسازی معامله", callback_data=f"receipt_approve_{contract_id}_{buyer_id}"),
        InlineKeyboardButton("❌ رد فیش واریزی", callback_data=f"receipt_reject_{contract_id}_{buyer_id}")
    )
    return markup

def get_project_admin_review_inline(contract_id: str, seller_id: int) -> InlineKeyboardMarkup:
    """پنل مدیریت جهت بررسی فایل‌های پروژه تحویلی توسط ادمین (در صورت نیاز)"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✅ تایید کیفی پروژه", callback_data=f"project_approve_{contract_id}_{seller_id}"),
        InlineKeyboardButton("⚠️ رد پروژه و اعلام علت", callback_data=f"project_reject_reason_{contract_id}_{seller_id}")
    )
    return markup

def get_more_contracts_inline(next_offset: int) -> InlineKeyboardMarkup:
    """دکمه نمایش صفحه بعدی معاملات کاربر"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("نمایش معاملات بعدی ▶️", callback_data=f"contracts_more_{next_offset}"))
    return markup

def get_milestones_inline(contract_id: str, milestones: list, is_employer: bool) -> InlineKeyboardMarkup:
    """دکمه‌های آزادسازی مراحل پرداخت"""
    markup = InlineKeyboardMarkup(row_width=1)
    for idx, ms in enumerate(milestones):
        title = ms.get("title", f"مرحله {idx+1}")
        amt = float(ms.get("amount", 0))
        st = ms.get("status", "pending")
        
        if st == "released":
            btn_text = f"✅ {title} ({amt:,.0f} تومان) - آزاد شده"
            markup.add(InlineKeyboardButton(btn_text, callback_data="none"))
        else:
            if is_employer:
                btn_text = f"🔓 آزادسازی {title} ({amt:,.0f} تومان)"
                markup.add(InlineKeyboardButton(btn_text, callback_data=f"release_ms_{contract_id}_{idx}"))
            else:
                btn_text = f"⏳ {title} ({amt:,.0f} تومان) - در انتظار کارفرما"
                markup.add(InlineKeyboardButton(btn_text, callback_data="none"))
                
    return markup
