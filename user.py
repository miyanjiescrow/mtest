import io
import re
import logging
from telebot import TeleBot
from telebot.types import Message, CallbackQuery

from config import config
import database as db
import keyboards as kb
import utils
import pdf_generator

logger = logging.getLogger("Miyanji_User")

CONTRACT_ID_PATTERN = re.compile(r"^[A-Za-z]{2,5}-\d{3,4}-\d{3,4}$")


# ====================================================
# توابع کمکی سراسری (اطلاع‌رسانی طرف مقابل + ارسال خودکار PDF)
# ====================================================

def notify_other_party(bot: TeleBot, contract: dict, actor_id: int, text: str):
    """
    ارسال اعلان به طرف دیگر معامله (نه کسی که دکمه را زده).
    رفع باگ: قبلاً هیچ پیامی به طرف مقابل ارسال نمی‌شد و او کاملاً از
    اتفاقات معامله (امضا، پیشنهاد قیمت، تحویل، لغو و ...) بی‌خبر می‌ماند.
    """
    buyer_id = contract.get("buyer_id") or contract.get("employer_id")
    seller_id = contract.get("seller_id") or contract.get("freelancer_id")
    other_id = None
    if buyer_id and buyer_id != actor_id:
        other_id = buyer_id
    elif seller_id and seller_id != actor_id:
        other_id = seller_id

    if other_id:
        try:
            bot.send_message(other_id, text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"ارسال اعلان به طرف مقابل ({other_id}) ناموفق بود: {e}")


def send_contract_pdf_to_parties(bot: TeleBot, contract: dict):
    """
    تولید خودکار سند رسمی PDF فارسی قرارداد و ارسال آن برای هر دو طرف معامله.
    این تابع بلافاصله پس از امضای هر دو طرف صدا زده می‌شود.
    """
    buyer_id = contract.get("buyer_id") or contract.get("employer_id")
    seller_id = contract.get("seller_id") or contract.get("freelancer_id")
    cid = contract.get("contract_id") or contract.get("id", "---")

    try:
        pdf_buffer = pdf_generator.build_contract_pdf(contract)
        pdf_bytes = pdf_buffer.getvalue()
    except Exception as e:
        logger.error(f"خطا در ساخت خودکار PDF برای معامله {cid}: {e}")
        return

    for recipient_id in {rid for rid in (buyer_id, seller_id) if rid}:
        try:
            doc_copy = io.BytesIO(pdf_bytes)
            doc_copy.name = f"Miyanji_Contract_{cid}.pdf"
            bot.send_document(
                recipient_id,
                doc_copy,
                caption=(
                    f"📑 **سند رسمی و امضاشدهٔ قرارداد شماره `{cid}`**\n"
                    "این سند به‌صورت خودکار پس از امضای هر دو طرف صادر و ارسال شد."
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"ارسال خودکار PDF به {recipient_id} ناموفق بود: {e}")


def build_draft_preview_text(draft: dict) -> str:
    """
    تولید متن یکسان پیش‌نمایش پیش‌نویس معامله؛ هم در نمایش اولیه بعد از پارس فرم
    و هم بعد از ویرایش هر فیلد (بخش ویرایش پیش‌نویس) از همین تابع استفاده می‌شود
    تا دو تکه کد مجزا و ناهماهنگ نداشته باشیم.
    """
    role = draft.get("role", "employer")
    role_str = "کارفرما" if role == "employer" else "مجری"
    category = draft.get("category", "GEN")

    ms_text = ""
    if draft.get("milestones"):
        ms_text = "\n\n🔹 **مراحل پرداخت:**\n" + "\n".join(
            [f"• {m['title']}: {float(m['amount']):,.0f} تومان" for m in draft["milestones"]]
        )

    return (
        "🧐 **پیش‌نمایش و بررسی نهایی معامله**\n\n"
        f"👤 **نقش شما:** {role_str}\n"
        f"📂 **دسته‌بندی:** `{category}`\n"
        f"📌 **عنوان:** {draft.get('title')}\n"
        f"💵 **مبلغ کل:** {float(draft.get('amount', 0)):,.0f} تومان\n"
        f"⏳ **مهلت تحویل:** {draft.get('deadline', 1)} روز\n"
        f"{ms_text}\n\n"
        f"📝 **تعهدات:**\n{draft.get('description', 'ثبت نشده')}\n\n"
        "آیا اطلاعات فوق مورد تایید است؟"
    )


def register_user_handlers(bot: TeleBot):
    """ثبت تمامی هندلرهای مربوط به کاربر در سیستم می‌انجی (کامل و بدون حذفیات)"""

    # ====================================================
    # ۱. انصراف کلی و بازگشت به منوی اصلی (اولویت بالا)
    # ====================================================
    @bot.message_handler(func=lambda msg: msg.text in ["❌ انصراف و بازگشت به منو", "❌ انصراف"])
    def handle_cancel(message: Message):
        db.clear_user_state(message.from_user.id)
        is_admin = (message.from_user.id == getattr(config, 'ADMIN_ID', 0) or message.from_user.id in getattr(config, 'ADMIN_IDS', []))
        bot.send_message(
            message.chat.id,
            "❌ عملیات لغو شد. به منوی اصلی بازگشتید.",
            reply_markup=kb.get_main_menu(is_admin)
        )

    # ====================================================
    # ۲. دستور /start (به همراه پردازش لینک دعوت معامله)
    # ====================================================
    @bot.message_handler(commands=['start'])
    def handle_start(message: Message):
        user = message.from_user
        db.clear_user_state(user.id)
        
        db.register_or_update_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )

        is_admin = (user.id == getattr(config, 'ADMIN_ID', 0) or user.id in getattr(config, 'ADMIN_IDS', []))

        # -----------------------------------------------
        # رفع باگ: قبلاً پارامتر لینک دعوت (?start=c_...) اصلاً
        # خوانده نمی‌شد و طرف دوم معامله فقط پیام خوش‌آمدگویی عمومی
        # می‌دید و هیچ راهی برای مشاهده/امضای قرارداد نداشت.
        # -----------------------------------------------
        args = message.text.split()
        if len(args) > 1 and args[1].startswith("c_"):
            contract_id = args[1][2:]
            contract = db.get_contract(contract_id)
            if contract:
                if contract.get("buyer_id") == user.id:
                    role = "employer"
                elif contract.get("seller_id") == user.id:
                    role = "freelancer"
                elif not contract.get("buyer_id"):
                    role = "employer"
                elif not contract.get("seller_id"):
                    role = "freelancer"
                else:
                    role = "employer"

                text = utils.generate_contract_text(contract)
                bot.send_message(
                    message.chat.id,
                    f"🤝 **شما به معامله زیر دعوت شده‌اید:**\n\n{text}",
                    parse_mode="Markdown",
                    reply_markup=kb.get_contract_action_keyboard(
                        contract_id,
                        role,
                        contract.get("status", "draft"),
                        bool(contract.get("milestones"))
                    )
                )
                return
            else:
                bot.send_message(message.chat.id, "⚠️ معامله موردنظر یافت نشد یا حذف شده است.")

        welcome_text = (
            f"سلام {user.first_name} عزیز! 👋\n"
            "به **سامانه امن واسطه‌گری و ثبت قرارداد می‌انجی (Miyanji)** خوش آمدید.\n\n"
            "با می‌انجی می‌توانید معاملات و پروژه‌های خود را با خیال راحت، همراه با امضای قانونی الکترونیک "
            "و ضمانت داوری ثبت و اجرا کنید."
        )
        
        bot.send_message(
            message.chat.id, 
            welcome_text, 
            parse_mode="Markdown", 
            reply_markup=kb.get_main_menu(is_admin)
        )

    # ====================================================
    # ۳. شروع ثبت معامله جدید (انتخاب نقش)
    # ====================================================
    @bot.message_handler(func=lambda msg: msg.text == "🤝 ایجاد معامله جدید")
    def start_new_contract(message: Message):
        user_id = message.from_user.id
        db.set_user_state(user_id, "WAITING_ROLE_SELECTION")
        
        bot.send_message(
            message.chat.id,
            "👤 **لطفاً نقش خود را در این معامله مشخص کنید:**",
            reply_markup=kb.get_role_keyboard()
        )

    @bot.message_handler(func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_ROLE_SELECTION")
    def process_role_selection(message: Message):
        user_id = message.from_user.id
        role_text = message.text

        if "کارفرما" in role_text:
            role = "employer"
        elif "مجری" in role_text:
            role = "freelancer"
        else:
            bot.send_message(message.chat.id, "⚠️ لطفاً یکی از گزینه‌های موجود در کیبورد را انتخاب کنید.", reply_markup=kb.get_role_keyboard())
            return

        db.set_user_state(user_id, "WAITING_CATEGORY_SELECTION", {"draft": {"role": role}})
        
        bot.send_message(
            message.chat.id,
            "📂 **لطفاً نوع و دسته‌بندی موضوع معامله خود را انتخاب کنید:**",
            reply_markup=kb.get_category_keyboard()
        )

    # ====================================================
    # ۴. انتخاب دسته‌بندی معامله
    # ====================================================
    @bot.message_handler(func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_CATEGORY_SELECTION")
    def process_category_selection(message: Message):
        user_id = message.from_user.id
        state_tuple = db.get_user_state(user_id)
        data = state_tuple[1] if isinstance(state_tuple, tuple) and len(state_tuple) > 1 else {}
        draft = data.get("draft", {}) if isinstance(data, dict) else {}
        
        cat_text = message.text
        if "برنامه‌نویسی" in cat_text:
            category = "DEV"
        elif "طراحی" in cat_text or "گرافیک" in cat_text:
            category = "DESIGN"
        elif "دانشجویی" in cat_text:
            category = "ACADEMIC"
        elif "آموزشی" in cat_text:
            category = "TEACHING"
        else:
            category = "GEN"

        draft["category"] = category
        db.set_user_state(user_id, "WAITING_SINGLE_CONTRACT_TEXT", {"draft": draft})

        instruction_text = (
            f"📝 **ثبت سریع جزئیات معامله ({cat_text})**\n\n"
            "لطفاً الگوی زیر را کپی کرده، اطلاعات معامله خود را پر کنید و **در یک پیام** بفرستید:\n\n"
            "```text\n"
            "📋 فرم ثبت معامله جدید:\n\n"
            "📌 عنوان: طراحی لوگو و هویت بصری\n"
            "💵 مبلغ کل (تومان): 8000000\n"
            "⏳ مهلت تحویل (روز): 7\n\n"
            "🔹 مراحل پرداخت (اختیاری):\n"
            "۱. تحویل اتودهای اولیه: 3000000\n"
            "۲. تحویل سورس کامل: 5000000\n\n"
            "📝 شرح تعهدات:\n"
            "ارائه فایل‌های وکتور AI، PSD و تمامی فونت‌های استفاده‌شده.\n"
            "```\n\n"
            "📌 *نکته:* بخش «مراحل پرداخت» اختیاری است."
        )

        bot.send_message(
            message.chat.id,
            instruction_text,
            parse_mode="Markdown",
            reply_markup=kb.get_cancel_keyboard()
        )

    # ====================================================
    # ۵. پارس فرم متنی یکجا
    # ====================================================
    @bot.message_handler(func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_SINGLE_CONTRACT_TEXT")
    def process_single_contract_text(message: Message):
        user_id = message.from_user.id
        state_tuple = db.get_user_state(user_id)
        data = state_tuple[1] if isinstance(state_tuple, tuple) and len(state_tuple) > 1 else {}
        draft = data.get("draft", {}) if isinstance(data, dict) else {}

        parsed = utils.parse_single_message_contract(message.text)

        if not parsed:
            bot.send_message(
                message.chat.id,
                "❌ **فرمت پیام وارد شده معتبر نیست.**\n"
                "لطفاً مطمئن شوید عنوان و مبلغ کل به درستی وارد شده‌اند و مجدداً پیام را ارسال کنید.",
                parse_mode="Markdown",
                reply_markup=kb.get_cancel_keyboard()
            )
            return

        parsed["role"] = draft.get("role", "employer")
        parsed["category"] = draft.get("category", "GEN")

        db.set_user_state(user_id, "WAITING_PREVIEW_CONFIRM", {"contract_draft": parsed})

        preview_text = build_draft_preview_text(parsed)

        bot.send_message(
            message.chat.id,
            preview_text,
            parse_mode="Markdown",
            reply_markup=kb.get_contract_preview_inline()
        )

    # ====================================================
    # ۶. پنل شیشه‌ای پیش‌نمایش
    # ====================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_draft_"))
    def confirm_draft_callback(call: CallbackQuery):
        user_id = call.from_user.id
        bot.answer_callback_query(call.id)

        sign_text = (
            "✍️ **امضای قانونی و الکترونیک قرارداد**\n\n"
            "طبق مواد ۶، ۷ و ۱۲ قانون تجارت الکترونیک، جهت رسمیت یافتن سند و غیرقابل انکار بودن آن، "
            "ارسال شماره اکانت تلگرام الزامی است.\n\n"
            "لطفاً جهت ثبت امضا روی دکمه زیر کلیک کنید:"
        )

        state_tuple = db.get_user_state(user_id)
        data = state_tuple[1] if isinstance(state_tuple, tuple) and len(state_tuple) > 1 else {}
        db.set_user_state(user_id, "WAITING_SIGN_PHONE", data)

        bot.send_message(
            call.message.chat.id,
            sign_text,
            parse_mode="Markdown",
            reply_markup=kb.get_phone_sign_keyboard()
        )

    @bot.callback_query_handler(func=lambda call: call.data == "cancel_draft")
    def cancel_draft_callback(call: CallbackQuery):
        user_id = call.from_user.id
        db.clear_user_state(user_id)
        is_admin = (user_id == getattr(config, 'ADMIN_ID', 0) or user_id in getattr(config, 'ADMIN_IDS', []))
        
        bot.answer_callback_query(call.id, "پیش‌نویس لغو شد.")
        bot.send_message(
            call.message.chat.id,
            "❌ پیش‌نویس معامله لغو شد. به منوی اصلی بازگشتید.",
            reply_markup=kb.get_main_menu(is_admin)
        )

    # ====================================================
    # ۶.۵ ویرایش پیش‌نویس پیش از امضا (قبلاً فقط دکمه بود، هیچ کدی پشتش نبود
    #     و با کلیک روی «ویرایش پیش‌نویس» فقط پیام «به‌زودی فعال می‌شود» دیده می‌شد)
    # ====================================================

    @bot.callback_query_handler(func=lambda call: call.data.startswith("edit_draft_"))
    def handle_edit_draft_menu(call: CallbackQuery):
        user_id = call.from_user.id
        _, data = db.get_user_state(user_id)
        draft = data.get("contract_draft") if isinstance(data, dict) else None

        if not draft:
            bot.answer_callback_query(call.id, "⚠️ پیش‌نویس فعالی یافت نشد.", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            "✏️ **کدام بخش از پیش‌نویس را می‌خواهید ویرایش کنید؟**",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb.get_draft_edit_inline(),
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("edit_field_"))
    def handle_edit_field_start(call: CallbackQuery):
        user_id = call.from_user.id
        # فرمت callback_data: edit_field_{field}_{draft_id} → فیلد همیشه اولین تکه بعد از پیشوند است
        field = call.data.replace("edit_field_", "", 1).split("_")[0]

        _, data = db.get_user_state(user_id)
        draft = data.get("contract_draft") if isinstance(data, dict) else None
        if not draft:
            bot.answer_callback_query(call.id, "⚠️ پیش‌نویس فعالی یافت نشد.", show_alert=True)
            return

        db.set_user_state(user_id, "WAITING_FIELD_EDIT", {"editing_field": field, "contract_draft": draft})

        field_names = {
            "title": "عنوان جدید معامله",
            "amount": "مبلغ جدید (به تومان)",
            "deadline": "مهلت جدید تحویل (به روز)",
            "desc": "شرح جدید تعهدات",
        }
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"📝 لطفاً **{field_names.get(field, 'مقدار جدید')}** را ارسال کنید:",
            parse_mode="Markdown",
            reply_markup=kb.get_cancel_keyboard()
        )

    @bot.message_handler(func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_FIELD_EDIT")
    def process_field_edit(message: Message):
        user_id = message.from_user.id
        _, data = db.get_user_state(user_id)
        field = data.get("editing_field") if isinstance(data, dict) else None
        draft = data.get("contract_draft", {}) if isinstance(data, dict) else {}

        if not field or not draft:
            db.clear_user_state(user_id)
            is_admin = (user_id == getattr(config, 'ADMIN_ID', 0) or user_id in getattr(config, 'ADMIN_IDS', []))
            bot.send_message(message.chat.id, "⚠️ خطایی رخ داد، لطفاً دوباره از «ایجاد معامله جدید» شروع کنید.", reply_markup=kb.get_main_menu(is_admin))
            return

        text = message.text.strip()
        clean_input = utils.fa_to_en_digits(text)

        if field == "title":
            draft["title"] = text
        elif field == "amount":
            try:
                new_amount = float(clean_input.replace(",", ""))
                if new_amount <= 0:
                    raise ValueError
                draft["amount"] = new_amount
            except ValueError:
                bot.send_message(message.chat.id, "⚠️ لطفاً مبلغ را به‌صورت عددی و مثبت وارد کنید.")
                return
        elif field == "deadline":
            if clean_input.isdigit() and int(clean_input) > 0:
                draft["deadline"] = int(clean_input)
            else:
                bot.send_message(message.chat.id, "⚠️ لطفاً مهلت تحویل را به عدد (روز) وارد کنید.")
                return
        elif field == "desc":
            draft["description"] = text

        db.set_user_state(user_id, "WAITING_PREVIEW_CONFIRM", {"contract_draft": draft})

        bot.send_message(message.chat.id, "✅ تغییرات با موفقیت اعمال گردید.")
        bot.send_message(
            message.chat.id,
            build_draft_preview_text(draft),
            parse_mode="Markdown",
            reply_markup=kb.get_contract_preview_inline()
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("back_to_preview_"))
    def handle_back_to_preview(call: CallbackQuery):
        user_id = call.from_user.id
        _, data = db.get_user_state(user_id)
        draft = data.get("contract_draft") if isinstance(data, dict) else None

        if not draft:
            bot.answer_callback_query(call.id, "⚠️ پیش‌نویس فعالی یافت نشد.", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            build_draft_preview_text(draft),
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb.get_contract_preview_inline(),
            parse_mode="Markdown"
        )

    # ====================================================
    # ۷. دریافت کنتاکت برای امضا
    # ====================================================
    @bot.message_handler(content_types=['contact'], func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_SIGN_PHONE")
    def process_sign_contact(message: Message):
        user_id = message.from_user.id
        contact = message.contact

        if contact.user_id != user_id:
            bot.send_message(
                message.chat.id,
                "❌ لطفاً فقط شماره مربوط به **اکانت خودتان** را جهت ثبت امضا ارسال کنید.",
                reply_markup=kb.get_phone_sign_keyboard()
            )
            return

        state_tuple = db.get_user_state(user_id)
        data = state_tuple[1] if isinstance(state_tuple, tuple) and len(state_tuple) > 1 else {}
        phone = contact.phone_number
        db.register_or_update_user(user_id, message.from_user.username, message.from_user.first_name, phone_number=phone)

        contract_draft = data.get("contract_draft", {}) if isinstance(data, dict) else {}
        if contract_draft.get("role") == "employer":
            contract_draft["buyer_phone"] = phone
        else:
            contract_draft["seller_phone"] = phone

        db.set_user_state(user_id, "WAITING_WORK_PHONE", {"contract_draft": contract_draft})

        work_phone_text = (
            "📱 **شماره تماس کاری و پاسخگو**\n\n"
            "جهت هماهنگی‌های بعدی، می‌توانید یک شماره تماس کاری ثبت کنید یا از همان شماره تلگرام استفاده نمایید:"
        )

        bot.send_message(
            message.chat.id,
            work_phone_text,
            parse_mode="Markdown",
            reply_markup=kb.get_skip_work_phone_keyboard()
        )

    # ====================================================
    # ۸. نهایی‌سازی در دیتابیس
    # ====================================================
    @bot.message_handler(func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_WORK_PHONE")
    def process_work_phone_and_finalize(message: Message):
        user_id = message.from_user.id
        state_tuple = db.get_user_state(user_id)
        data = state_tuple[1] if isinstance(state_tuple, tuple) and len(state_tuple) > 1 else {}
        draft = data.get("contract_draft", {}) if isinstance(data, dict) else {}

        is_admin = (user_id == getattr(config, 'ADMIN_ID', 0) or user_id in getattr(config, 'ADMIN_IDS', []))

        if message.text and message.text != "⏭ رد کردن و استفاده از شماره تلگرام":
            work_phone = message.text.strip()
            role = draft.get("role", "employer")
            if role == "employer":
                draft["buyer_phone"] = work_phone
            else:
                draft["seller_phone"] = work_phone

        role = draft.get("role", "employer")
        employer_id = user_id if role == "employer" else None
        freelancer_id = user_id if role == "freelancer" else None
        category = draft.get("category", "GEN")

        # رفع باگ: قبلاً contract_id هیچ‌وقت تولید/ذخیره نمی‌شد و لینک دعوت
        # بر پایه‌ی id عددی داخلی ساخته می‌شد که با پیشوند لینک هم‌خوان نبود.
        contract_id = utils.generate_archive_contract_id(category)

        payload = {
            "contract_id": contract_id,
            "title": draft.get("title"),
            "amount": draft.get("amount"),
            "deadline": draft.get("deadline", 1),
            "description": draft.get("description", ""),
            "category": category,
            "milestones": draft.get("milestones", []),
            "employer_id": employer_id,
            "freelancer_id": freelancer_id,
            "buyer_phone": draft.get("buyer_phone"),
            "seller_phone": draft.get("seller_phone"),
            "status": "pending_approval"
        }

        contract = db.create_contract(payload)
        
        if not contract:
            bot.send_message(
                message.chat.id, 
                "❌ خطایی در ثبت معامله در دیتابیس رخ داد.", 
                reply_markup=kb.get_main_menu(is_admin)
            )
            db.clear_user_state(user_id)
            return

        db.clear_user_state(user_id)
        cid = contract.get("contract_id") or contract_id
        contract_text = utils.generate_contract_text(contract)
        
        # رفع باگ: پیشوند لینک با پیشوندی که در /start خوانده می‌شود («c_») هم‌خوان شد
        share_link = f"https://t.me/{getattr(config, 'BOT_USERNAME', 'MiyanjiBot')}?start=c_{cid}"

        final_msg = (
            f"✅ **معامله با موفقیت ثبت و امضا شد!**\n\n"
            f"{contract_text}\n\n"
            f"🔗 **لینک اختصاصی پیوستن طرف مقابل:**\n`{share_link}`\n\n"
            "لینک فوق را برای طرف مقابل ارسال کنید تا با کلیک روی آن، قرارداد را تایید و امضا کند."
        )

        bot.send_message(message.chat.id, final_msg, parse_mode="Markdown", reply_markup=kb.get_main_menu(is_admin))

    # ====================================================
    # ۹. معاملات من (با صفحه‌بندی — قبلاً همیشه فقط ۵ معامله اول نمایش داده می‌شد
    #     و هیچ راهی برای دیدن باقی معاملات کاربر وجود نداشت)
    # ====================================================
    PAGE_SIZE = 5

    def render_contract_card(chat_id: int, user_id: int, c: dict):
        cid = c.get("contract_id") or c.get("id", "---")
        title = c.get("title", "بدون عنوان")
        status = c.get("status", "نامشخص")
        amount = float(c.get("amount", 0))

        role = "کارفرما" if c.get("employer_id") == user_id or c.get("buyer_id") == user_id else "مجری"
        has_ms = len(c.get("milestones", []) or []) > 0

        text = (
            f"📄 **معامله `{cid}`**\n"
            f"📌 عنوان: {title}\n"
            f"👤 نقش شما: {role}\n"
            f"💵 مبلغ: {amount:,.0f} تومان\n"
            f"📊 وضعیت: `{status}`"
        )

        bot.send_message(
            chat_id,
            text,
            parse_mode="Markdown",
            reply_markup=kb.get_contract_action_keyboard(cid, "employer" if role == "کارفرما" else "freelancer", status, has_ms)
        )

    def send_contracts_page(chat_id: int, user_id: int, contracts: list, offset: int):
        page = contracts[offset:offset + PAGE_SIZE]
        for c in page:
            render_contract_card(chat_id, user_id, c)

        remaining = len(contracts) - (offset + PAGE_SIZE)
        if remaining > 0:
            bot.send_message(
                chat_id,
                f"📜 {remaining} معامله دیگر دارید.",
                reply_markup=kb.get_more_contracts_inline(offset + PAGE_SIZE)
            )

    @bot.message_handler(func=lambda msg: msg.text == "📜 معاملات من")
    def show_my_contracts(message: Message):
        user_id = message.from_user.id
        contracts = db.get_user_contracts(user_id)

        if not contracts:
            bot.send_message(message.chat.id, "📜 شما هنوز هیچ معامله‌ای ثبت نکرده‌اید.")
            return

        send_contracts_page(message.chat.id, user_id, contracts, 0)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("contracts_more_"))
    def handle_contracts_more(call: CallbackQuery):
        user_id = call.from_user.id
        try:
            offset = int(call.data.replace("contracts_more_", "", 1))
        except ValueError:
            offset = 0

        contracts = db.get_user_contracts(user_id)
        bot.answer_callback_query(call.id)
        send_contracts_page(call.message.chat.id, user_id, contracts, offset)

    # ====================================================
    # ۱۰. کیف پول
    # ====================================================
    @bot.message_handler(func=lambda msg: msg.text == "💰 کیف پول و اعتبار")
    def show_wallet(message: Message):
        user = db.get_user(message.from_user.id)
        balance = float(user.get("wallet_balance", 0.0)) if user else 0.0

        wallet_text = (
            "💰 **کیف پول حساب شما در می‌انجی**\n\n"
            f"💵 **موجودی نقد شما:** `{balance:,.0f}` تومان\n\n"
            "از بخش زیر می‌توانید نسبت به شارژ حساب یا درخواست برداشت اقدام فرمایید:"
        )

        bot.send_message(message.chat.id, wallet_text, parse_mode="Markdown", reply_markup=kb.get_wallet_inline())

    # ====================================================
    # ۱۱. قوانین و راهنما
    # ====================================================
    @bot.message_handler(func=lambda msg: msg.text in ["⚖️ قوانین و راهنمای حقوقی", "⚖️ قوانین و راهنما"])
    def show_rules(message: Message):
        rules_text = (
            "⚖️ **قوانین و مقررات سامانه می‌انجی**\n\n"
            "۱. تمام معاملات ثبت‌شده در ربات بر اساس ماده ۱۰ قانون مدنی و مواد ۶، ۷ و ۱۲ قانون تجارت الکترونیک تنظیم گردیده است.\n"
            "۲. وجوه امانت تا زمان تایید نهایی خریدار/کارفرما در کیف پول امانت سامانه محفوظ می‌ماند.\n"
            "۳. در صورت بروز اختلاف، هیئت داوری می‌انجی با بررسی مستندات طرفین، رای نهایی را صادر و اجرا می‌نماید."
        )
        bot.send_message(message.chat.id, rules_text, parse_mode="Markdown")

    # ====================================================
    # ۱۲. پشتیبانی و ارتباط با ما
    # ====================================================
    @bot.message_handler(func=lambda msg: msg.text == "📞 پشتیبانی و ارتباط با ما")
    def show_support(message: Message):
        bot.send_message(
            message.chat.id,
            "📞 **پشتیبانی و مرکز پاسخگویی می‌انجی**\n\n"
            "در صورت وجود هرگونه سوال، پیشنهاد یا گزارش مشکل در معاملات، "
            "می‌توانید از طریق دکمه‌های زیر با تیم پشتیبانی در ارتباط باشید:",
            parse_mode="Markdown",
            reply_markup=kb.get_support_inline()
        )

    # ====================================================
    # ۱۳. اقدامات روی معامله پس از ثبت (این بخش کاملاً جدید و رفع‌شده است)
    #     امضا / پیشنهاد مبلغ / لغو / تحویل کار / تایید نهایی / دانلود PDF
    #     قبلاً این هندلرها فقط در handlers.py وجود داشتند که هرگز رجیستر
    #     نمی‌شد؛ به همین دلیل کلیک روی این دکمه‌ها هیچ اتفاقی نمی‌انداخت.
    # ====================================================

    @bot.callback_query_handler(func=lambda call: call.data.startswith("sign_contract_"))
    def handle_sign_contract(call: CallbackQuery):
        cid = call.data.replace("sign_contract_", "", 1)
        user_id = call.from_user.id
        contract = db.get_contract(cid)

        if not contract:
            bot.answer_callback_query(call.id, "❌ معامله یافت نشد.", show_alert=True)
            return

        # اگر امضاکننده هنوز نقشی در معامله ندارد، جای خالی (خریدار/فروشنده) را پر می‌کنیم
        updates = {}
        if not contract.get("buyer_id") and contract.get("seller_id") != user_id:
            updates["buyer_id"] = user_id
        elif not contract.get("seller_id") and contract.get("buyer_id") != user_id:
            updates["seller_id"] = user_id

        contract.update(updates)  # به‌روزرسانی محلی جهت تصمیم‌گیری فوری در همین تابع
        both_signed = bool(contract.get("buyer_id") and contract.get("seller_id"))

        # نکتهٔ امانی مهم: امضای هر دو طرف به‌معنای فعال‌شدن فوری پروژه نیست.
        # تا زمانی‌که کارفرما فیش واریزی را ارسال نکند و ادمین آن را تایید نکند،
        # وجه امانت هنوز بلوکه نشده و مجری نباید کار را شروع کند. پس وضعیت را
        # به «awaiting_payment» می‌بریم، نه مستقیم «active».
        updates["status"] = "awaiting_payment" if both_signed else contract.get("status", "pending_approval")
        db.update_contract(cid, updates)
        contract.update(updates)

        bot.answer_callback_query(call.id, "✅ قرارداد با موفقیت امضا شد.")

        if both_signed:
            bot.send_message(
                call.message.chat.id,
                f"🎉 معامله شماره `{cid}` توسط هر دو طرف امضا شد.\n"
                "💳 کارفرمای محترم، لطفاً جهت بلوکه‌شدن امانی وجه، از «📜 معاملات من» فیش واریزی را ارسال کنید.",
                parse_mode="Markdown"
            )
            # سند رسمی امضاشده (مستقل از وضعیت پرداخت) برای هر دو طرف ارسال می‌شود
            send_contract_pdf_to_parties(bot, contract)
        else:
            bot.send_message(
                call.message.chat.id,
                f"✍️ امضای شما برای معامله شماره `{cid}` ثبت شد. منتظر امضای طرف مقابل بمانید.",
                parse_mode="Markdown"
            )
            # فقط یک طرف امضا کرده؛ طرف مقابل مطلع می‌شود که باید بیاید و تایید کند
            notify_other_party(
                bot, contract, user_id,
                f"✍️ طرف مقابل معامله شماره `{cid}` را امضا کرد.\n"
                "برای مشاهده و تایید نهایی، از «📜 معاملات من» وارد شوید."
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("upload_receipt_"))
    def handle_upload_receipt_start(call: CallbackQuery):
        """شروع مرحلهٔ ارسال فیش واریزی توسط کارفرما (بخشی که قبلاً هیچ هندلری نداشت)"""
        cid = call.data.replace("upload_receipt_", "", 1)
        contract = db.get_contract(cid)
        if not contract:
            bot.answer_callback_query(call.id, "❌ معامله یافت نشد.", show_alert=True)
            return

        user_id = call.from_user.id
        buyer_id = contract.get("buyer_id") or contract.get("employer_id")
        if buyer_id != user_id:
            bot.answer_callback_query(call.id, "❌ فقط کارفرمای معامله می‌تواند فیش واریزی ارسال کند.", show_alert=True)
            return

        db.set_user_state(user_id, "WAITING_RECEIPT_PHOTO", {"receipt_cid": cid})
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"📸 لطفاً تصویر فیش واریزی مربوط به معامله `{cid}` را ارسال فرمایید:",
            parse_mode="Markdown",
            reply_markup=kb.get_cancel_keyboard()
        )

    @bot.message_handler(
        content_types=['photo', 'document'],
        func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_RECEIPT_PHOTO"
    )
    def handle_receipt_photo(message: Message):
        """دریافت تصویر فیش واریزی و ارسال آن برای تایید ادمین"""
        user_id = message.from_user.id
        _, data = db.get_user_state(user_id)
        cid = data.get("receipt_cid") if isinstance(data, dict) else None
        is_admin = (user_id == getattr(config, 'ADMIN_ID', 0) or user_id in getattr(config, 'ADMIN_IDS', []))

        if not cid:
            db.clear_user_state(user_id)
            bot.send_message(message.chat.id, "⚠️ خطایی رخ داد، لطفاً دوباره تلاش کنید.", reply_markup=kb.get_main_menu(is_admin))
            return

        file_id = message.photo[-1].file_id if message.photo else (message.document.file_id if message.document else None)
        if not file_id:
            bot.send_message(message.chat.id, "⚠️ لطفاً فقط تصویر یا فایل فیش واریزی را ارسال کنید.")
            return

        db.update_contract(cid, {"receipt_file_id": file_id, "status": "awaiting_receipt_approval"})
        db.clear_user_state(user_id)

        for admin_id in getattr(config, 'ADMIN_IDS', []):
            try:
                bot.send_photo(
                    admin_id,
                    photo=file_id,
                    caption=f"💳 **فیش واریزی جدید**\n\n📌 **کد معامله:** `{cid}`\n👤 **کارفرما:** `{user_id}`",
                    parse_mode="Markdown",
                    reply_markup=kb.get_receipt_admin_approval_inline(cid, user_id)
                )
            except Exception as e:
                logger.error(f"خطا در ارسال فیش به ادمین {admin_id}: {e}")

        bot.send_message(
            message.chat.id,
            "✅ **فیش واریزی شما دریافت شد و جهت تایید برای مدیریت ارسال گردید.**",
            reply_markup=kb.get_main_menu(is_admin)
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("reject_project_"))
    def handle_reject_project_start(call: CallbackQuery):
        """شروع مرحلهٔ ثبت دلیل عدم تایید پروژه توسط کارفرما (بخشی که قبلاً هیچ هندلری نداشت)"""
        cid = call.data.replace("reject_project_", "", 1)
        contract = db.get_contract(cid)
        if not contract:
            bot.answer_callback_query(call.id, "❌ معامله یافت نشد.", show_alert=True)
            return

        db.set_user_state(call.from_user.id, "WAITING_PROJECT_REJECT_REASON", {"reject_cid": cid})
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"⚠️ لطفاً **علت عدم تایید و موارد نیازمند اصلاح** برای معامله `{cid}` را بنویسید:",
            parse_mode="Markdown",
            reply_markup=kb.get_cancel_keyboard()
        )

    @bot.message_handler(func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_PROJECT_REJECT_REASON")
    def handle_reject_project_reason(message: Message):
        user_id = message.from_user.id
        _, data = db.get_user_state(user_id)
        cid = data.get("reject_cid") if isinstance(data, dict) else None
        is_admin = (user_id == getattr(config, 'ADMIN_ID', 0) or user_id in getattr(config, 'ADMIN_IDS', []))

        if not cid:
            db.clear_user_state(user_id)
            bot.send_message(message.chat.id, "⚠️ خطایی رخ داد، لطفاً دوباره تلاش کنید.", reply_markup=kb.get_main_menu(is_admin))
            return

        contract = db.get_contract(cid)
        seller_id = contract.get("seller_id") or contract.get("freelancer_id") if contract else None
        free_edits_left = max(0, (contract.get("free_edits_left", 3) if contract else 3) - 1)
        reason = message.text.strip()

        # پروژه به وضعیت «در حال اجرا» برمی‌گردد تا مجری بتواند دوباره تحویل دهد
        db.update_contract(cid, {"status": "active", "free_edits_left": free_edits_left})
        db.clear_user_state(user_id)

        bot.send_message(message.chat.id, "✅ موارد اصلاحی ثبت و به مجری ابلاغ گردید.", reply_markup=kb.get_main_menu(is_admin))

        if seller_id:
            try:
                rejection_msg = utils.format_project_rejection_msg(cid, reason, free_edits_left)
                bot.send_message(seller_id, rejection_msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"خطا در ارسال پیام رد پروژه به مجری: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("bargain_"))
    def handle_bargain_start(call: CallbackQuery):
        cid = call.data.replace("bargain_", "", 1)
        user_id = call.from_user.id
        db.set_user_state(user_id, "WAITING_BARGAIN_PRICE", {"bargain_cid": cid})
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "💬 **لطفاً مبلغ پیشنهادی جدید خود را به تومان ارسال کنید:**",
            parse_mode="Markdown",
            reply_markup=kb.get_cancel_keyboard()
        )

    @bot.message_handler(func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_BARGAIN_PRICE")
    def process_bargain_price(message: Message):
        user_id = message.from_user.id
        _, data = db.get_user_state(user_id)
        cid = data.get("bargain_cid") if isinstance(data, dict) else None
        is_admin = (user_id == getattr(config, 'ADMIN_ID', 0) or user_id in getattr(config, 'ADMIN_IDS', []))

        if not cid:
            db.clear_user_state(user_id)
            bot.send_message(message.chat.id, "⚠️ معامله موردنظر یافت نشد.", reply_markup=kb.get_main_menu(is_admin))
            return

        clean_text = utils.fa_to_en_digits(message.text).replace(",", "").replace(" تومان", "").strip()
        if not clean_text.isdigit():
            bot.send_message(message.chat.id, "⚠️ لطفاً مبلغ را فقط به صورت عدد وارد کنید.")
            return

        new_amount = float(clean_text)
        db.update_contract(cid, {"amount": new_amount, "status": "bargaining"})
        db.clear_user_state(user_id)

        bot.send_message(
            message.chat.id,
            f"✅ پیشنهاد مبلغ جدید ({utils.format_currency(new_amount)}) برای معامله `{cid}` ثبت شد.",
            parse_mode="Markdown",
            reply_markup=kb.get_main_menu(is_admin)
        )

        updated_contract = db.get_contract(cid)
        if updated_contract:
            notify_other_party(
                bot, updated_contract, user_id,
                f"🔄 طرف مقابل برای معامله `{cid}` مبلغ جدیدی پیشنهاد داد: "
                f"**{utils.format_currency(new_amount)}**\n"
                "برای بررسی و پاسخ، از «📜 معاملات من» وارد شوید."
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("deliver_"))
    def handle_deliver_contract(call: CallbackQuery):
        cid = call.data.replace("deliver_", "", 1)
        contract = db.get_contract(cid)
        if not contract:
            bot.answer_callback_query(call.id, "❌ معامله یافت نشد.", show_alert=True)
            return

        db.update_contract(cid, {"status": "delivered"})
        bot.answer_callback_query(call.id, "📦 کار تحویل داده شد.")
        bot.send_message(
            call.message.chat.id,
            f"📦 **پروژه معامله `{cid}` تحویل داده شد.** کارفرما باید تایید نهایی را انجام دهد.",
            parse_mode="Markdown"
        )
        notify_other_party(
            bot, contract, call.from_user.id,
            f"📦 مجری معاملهٔ `{cid}` کار را تحویل داد.\n"
            "برای بررسی و تایید نهایی (و آزادسازی وجه)، از «📜 معاملات من» وارد شوید."
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("final_confirm_"))
    def handle_final_confirm(call: CallbackQuery):
        cid = call.data.replace("final_confirm_", "", 1)
        contract = db.get_contract(cid)
        if not contract:
            bot.answer_callback_query(call.id, "❌ معامله یافت نشد.", show_alert=True)
            return

        db.update_contract(cid, {"status": "completed"})

        amount = float(contract.get("amount", 0))
        _, net = utils.calculate_commission(amount)
        seller_id = contract.get("seller_id") or contract.get("freelancer_id")

        # آزادسازی وجه فقط برای معاملات تک‌مرحله‌ای اینجا انجام می‌شود؛
        # معاملات دارای مراحل پرداخت، هر مرحله را جداگانه در بخش «مدیریت مراحل پرداخت» تسویه می‌کنند.
        if seller_id and not contract.get("milestones"):
            db.update_wallet_balance(seller_id, net, "contract_release", f"آزادسازی وجه معامله {cid}")

        bot.answer_callback_query(call.id, "✅ تایید نهایی ثبت و وجه آزاد شد.")
        bot.send_message(
            call.message.chat.id,
            f"✅ **معامله `{cid}` با موفقیت تکمیل شد** و مبلغ به کیف پول مجری واریز گردید.",
            parse_mode="Markdown"
        )
        notify_other_party(
            bot, contract, call.from_user.id,
            f"✅ کارفرمای معاملهٔ `{cid}` تحویل کار را تایید کرد.\n"
            f"مبلغ **{utils.format_currency(net)}** به کیف پول شما واریز شد."
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_contract_"))
    def handle_cancel_contract(call: CallbackQuery):
        cid = call.data.replace("cancel_contract_", "", 1)
        contract = db.get_contract(cid)
        if not contract:
            bot.answer_callback_query(call.id, "❌ معامله یافت نشد.", show_alert=True)
            return

        db.update_contract(cid, {"status": "cancelled"})
        bot.answer_callback_query(call.id, "🚫 معامله لغو شد.")
        bot.send_message(
            call.message.chat.id,
            f"🚫 معامله شماره `{cid}` لغو گردید.",
            parse_mode="Markdown"
        )
        notify_other_party(bot, contract, call.from_user.id, f"🚫 طرف مقابل معاملهٔ `{cid}` را لغو کرد.")

    # ====================================================
    # ۱۳.۵ مدیریت مراحل پرداخت (Milestones) — قبلاً هیچ هندلری برای این دکمه‌ها نبود
    # ====================================================

    @bot.callback_query_handler(func=lambda call: call.data.startswith("manage_milestones_"))
    def handle_manage_milestones(call: CallbackQuery):
        cid = call.data.replace("manage_milestones_", "", 1)
        user_id = call.from_user.id
        contract = db.get_contract(cid)
        if not contract:
            bot.answer_callback_query(call.id, "❌ معامله یافت نشد.", show_alert=True)
            return

        milestones = contract.get("milestones") or []
        if not milestones:
            bot.answer_callback_query(call.id, "این معامله فاقد مراحل پرداخت است.", show_alert=True)
            return

        is_employer = (contract.get("buyer_id") == user_id or contract.get("employer_id") == user_id)
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"📊 **مدیریت مراحل پرداخت معامله `{cid}`**",
            parse_mode="Markdown",
            reply_markup=kb.get_milestones_inline(cid, milestones, is_employer)
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("release_ms_"))
    def handle_release_milestone(call: CallbackQuery):
        user_id = call.from_user.id
        payload = call.data.replace("release_ms_", "", 1)
        try:
            cid, idx_str = payload.rsplit("_", 1)
            idx = int(idx_str)
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "❌ درخواست نامعتبر.", show_alert=True)
            return

        contract = db.get_contract(cid)
        if not contract:
            bot.answer_callback_query(call.id, "❌ معامله یافت نشد.", show_alert=True)
            return

        if contract.get("buyer_id") != user_id and contract.get("employer_id") != user_id:
            bot.answer_callback_query(call.id, "❌ فقط کارفرما می‌تواند مرحله را آزاد کند.", show_alert=True)
            return

        milestones = contract.get("milestones") or []
        if idx < 0 or idx >= len(milestones):
            bot.answer_callback_query(call.id, "❌ مرحله یافت نشد.", show_alert=True)
            return

        if milestones[idx].get("status") == "released":
            bot.answer_callback_query(call.id, "این مرحله قبلاً آزاد شده است.", show_alert=True)
            return

        milestones[idx]["status"] = "released"
        db.update_contract(cid, {"milestones": milestones})

        ms_amount = float(milestones[idx].get("amount", 0))
        _, net = utils.calculate_commission(ms_amount)
        seller_id = contract.get("seller_id") or contract.get("freelancer_id")
        if seller_id:
            db.update_wallet_balance(
                seller_id, net, "milestone_release",
                f"آزادسازی مرحله «{milestones[idx].get('title', '')}» از معامله {cid}"
            )

        bot.answer_callback_query(call.id, "✅ این مرحله آزاد و مبلغ به کیف پول مجری واریز شد.")
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=kb.get_milestones_inline(cid, milestones, True)
            )
        except Exception:
            pass

        notify_other_party(
            bot, contract, user_id,
            f"🔓 مرحله «{milestones[idx].get('title', '')}» از معامله `{cid}` آزاد شد.\n"
            f"مبلغ **{utils.format_currency(net)}** به کیف پول شما واریز گردید."
        )

    # ====================================================
    # ۱۳.۶ درخواست داوری توسط کاربر — قبلاً تابعش در دیتابیس بود ولی هیچ دکمه‌ای وصل نبود
    # ====================================================

    @bot.callback_query_handler(func=lambda call: call.data == "request_dispute")
    def handle_dispute_request_start(call: CallbackQuery):
        user_id = call.from_user.id
        db.set_user_state(user_id, "WAITING_DISPUTE_CID")
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "⚖️ **درخواست داوری**\n\n"
            "لطفاً شناسه معامله موردنظر (مثال: `DEV-2508-1234`) را ارسال کنید.\n"
            "شناسه را می‌توانید از بخش «📜 معاملات من» پیدا کنید.",
            parse_mode="Markdown",
            reply_markup=kb.get_cancel_keyboard()
        )

    @bot.message_handler(func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_DISPUTE_CID")
    def handle_dispute_cid(message: Message):
        user_id = message.from_user.id
        cid = message.text.strip()
        contract = db.get_contract(cid)

        if not contract:
            bot.send_message(message.chat.id, "❌ معامله‌ای با این شناسه یافت نشد. لطفاً دوباره بررسی و ارسال کنید.")
            return

        if contract.get("buyer_id") != user_id and contract.get("seller_id") != user_id \
                and contract.get("employer_id") != user_id and contract.get("freelancer_id") != user_id:
            bot.send_message(message.chat.id, "❌ شما یکی از طرفین این معامله نیستید.")
            db.clear_user_state(user_id)
            return

        db.set_user_state(user_id, "WAITING_DISPUTE_REASON", {"dispute_cid": cid})
        bot.send_message(
            message.chat.id,
            "📝 لطفاً شرح کامل اختلاف و درخواست خود را بنویسید:",
            reply_markup=kb.get_cancel_keyboard()
        )

    @bot.message_handler(func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_DISPUTE_REASON")
    def handle_dispute_reason(message: Message):
        user_id = message.from_user.id
        _, data = db.get_user_state(user_id)
        cid = data.get("dispute_cid") if isinstance(data, dict) else None
        is_admin = (user_id == getattr(config, 'ADMIN_ID', 0) or user_id in getattr(config, 'ADMIN_IDS', []))

        if not cid:
            db.clear_user_state(user_id)
            bot.send_message(message.chat.id, "⚠️ خطایی رخ داد، لطفاً دوباره تلاش کنید.", reply_markup=kb.get_main_menu(is_admin))
            return

        reason = message.text.strip()
        ok = db.create_dispute_ticket(cid, user_id, reason)
        db.clear_user_state(user_id)

        if ok:
            bot.send_message(
                message.chat.id,
                f"✅ درخواست داوری شما برای معامله `{cid}` ثبت شد. تیم داوری می‌انجی به‌زودی بررسی می‌کند.",
                parse_mode="Markdown",
                reply_markup=kb.get_main_menu(is_admin)
            )
            for admin_id in getattr(config, 'ADMIN_IDS', []):
                try:
                    bot.send_message(
                        admin_id,
                        f"⚠️ **درخواست داوری جدید**\nمعامله: `{cid}`\nثبت‌کننده: `{user_id}`\nشرح:\n{reason}",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
        else:
            bot.send_message(message.chat.id, "❌ خطایی در ثبت درخواست داوری رخ داد.", reply_markup=kb.get_main_menu(is_admin))

    # ====================================================
    # ۱۳.۷ کیف پول: درخواست شارژ و برداشت با تایید ادمین — قبلاً فقط یک Alert «به‌زودی» بود
    # ====================================================

    @bot.callback_query_handler(func=lambda call: call.data == "deposit_wallet")
    def handle_deposit_start(call: CallbackQuery):
        user_id = call.from_user.id
        db.set_user_state(user_id, "WAITING_DEPOSIT_AMOUNT")
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "💳 لطفاً مبلغی که واریز کرده‌اید (به تومان) را ارسال کنید:",
            reply_markup=kb.get_wallet_amount_cancel_keyboard()
        )

    @bot.message_handler(func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_DEPOSIT_AMOUNT")
    def handle_deposit_amount(message: Message):
        user_id = message.from_user.id
        is_admin = (user_id == getattr(config, 'ADMIN_ID', 0) or user_id in getattr(config, 'ADMIN_IDS', []))
        clean_text = utils.fa_to_en_digits(message.text).replace(",", "").strip()

        if not clean_text.isdigit() or int(clean_text) <= 0:
            bot.send_message(message.chat.id, "⚠️ لطفاً مبلغ را فقط به‌صورت عدد مثبت وارد کنید.")
            return

        amount = float(clean_text)
        db.clear_user_state(user_id)
        db.create_support_ticket(user_id, "درخواست شارژ کیف پول", f"مبلغ درخواستی: {utils.format_currency(amount)}")

        bot.send_message(
            message.chat.id,
            "✅ درخواست شارژ شما ثبت شد و پس از بررسی و تایید ادمین، مبلغ به کیف پول شما اضافه خواهد شد.",
            reply_markup=kb.get_main_menu(is_admin)
        )
        for admin_id in getattr(config, 'ADMIN_IDS', []):
            try:
                bot.send_message(
                    admin_id,
                    f"💳 **درخواست شارژ کیف پول جدید**\nکاربر: `{user_id}`\nمبلغ: {utils.format_currency(amount)}",
                    parse_mode="Markdown",
                    reply_markup=kb.get_wallet_admin_approval_inline("deposit", user_id, amount)
                )
            except Exception:
                pass

    @bot.callback_query_handler(func=lambda call: call.data == "withdraw_wallet")
    def handle_withdraw_start(call: CallbackQuery):
        user_id = call.from_user.id
        user = db.get_user(user_id)
        balance = float(user.get("wallet_balance", 0.0)) if user else 0.0
        db.set_user_state(user_id, "WAITING_WITHDRAW_AMOUNT")
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"🏧 موجودی فعلی شما: {utils.format_currency(balance)}\nلطفاً مبلغ برداشت موردنظر را ارسال کنید:",
            reply_markup=kb.get_wallet_amount_cancel_keyboard()
        )

    @bot.message_handler(func=lambda msg: db.get_user_state(msg.from_user.id)[0] == "WAITING_WITHDRAW_AMOUNT")
    def handle_withdraw_amount(message: Message):
        user_id = message.from_user.id
        is_admin = (user_id == getattr(config, 'ADMIN_ID', 0) or user_id in getattr(config, 'ADMIN_IDS', []))
        clean_text = utils.fa_to_en_digits(message.text).replace(",", "").strip()

        if not clean_text.isdigit() or int(clean_text) <= 0:
            bot.send_message(message.chat.id, "⚠️ لطفاً مبلغ را فقط به‌صورت عدد مثبت وارد کنید.")
            return

        amount = float(clean_text)
        user = db.get_user(user_id)
        balance = float(user.get("wallet_balance", 0.0)) if user else 0.0

        if amount > balance:
            bot.send_message(message.chat.id, f"⚠️ موجودی شما ({utils.format_currency(balance)}) کمتر از مبلغ درخواستی است.")
            return

        db.clear_user_state(user_id)
        db.create_support_ticket(user_id, "درخواست برداشت از کیف پول", f"مبلغ درخواستی: {utils.format_currency(amount)}")

        bot.send_message(
            message.chat.id,
            "✅ درخواست برداشت شما ثبت شد و پس از تایید ادمین واریز خواهد شد.",
            reply_markup=kb.get_main_menu(is_admin)
        )
        for admin_id in getattr(config, 'ADMIN_IDS', []):
            try:
                bot.send_message(
                    admin_id,
                    f"🏧 **درخواست برداشت از کیف پول**\nکاربر: `{user_id}`\nمبلغ: {utils.format_currency(amount)}",
                    parse_mode="Markdown",
                    reply_markup=kb.get_wallet_admin_approval_inline("withdraw", user_id, amount)
                )
            except Exception:
                pass

    @bot.callback_query_handler(func=lambda call: call.data.startswith("get_pdf_") or call.data.startswith("pdf_"))
    def handle_download_pdf(call: CallbackQuery):
        if call.data.startswith("get_pdf_"):
            cid = call.data.replace("get_pdf_", "", 1)
        else:
            cid = call.data.replace("pdf_", "", 1)

        contract = db.get_contract(cid)
        if not contract:
            bot.answer_callback_query(call.id, "❌ معامله مورد نظر یافت نشد.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "⏳ در حال ساخت سند رسمی PDF...")

        try:
            pdf_buffer = pdf_generator.build_contract_pdf(contract)
            pdf_buffer.name = f"Miyanji_Contract_{cid}.pdf"

            bot.send_document(
                call.message.chat.id,
                pdf_buffer,
                caption=f"📑 **سند رسمی قرارداد امانی شماره `{cid}`**\nتنظیم‌شده طبق ماده ۱۰ قانون مدنی و قوانین تجارت الکترونیک",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"خطا در ارسال فایل PDF: {e}")
            bot.send_message(call.message.chat.id, "❌ خطایی در تولید فایل PDF رخ داد. لطفاً مجدداً تلاش کنید.")

    # ====================================================
    # ۱۴. کالبک‌های عمومی (Callback Query Handlers)
    # ====================================================
    @bot.callback_query_handler(func=lambda call: call.data == "none")
    def handle_noop_callback(call: CallbackQuery):
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: True)
    def handle_user_callbacks(call: CallbackQuery):
        data = call.data
        if data == "faq_info":
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                "❓ **سوالات متداول می‌انجی:**\n\n"
                "۱. کارمزد سامانه چقدر است؟ حدود ۱ الی ۲ درصد.\n"
                "۲. زمان واریز چقدر طول می‌کشد؟ پس از تایید تحویل کارفرما به صورت پایا/پایا لحظه‌ای عودت داده می‌شود.\n"
                "۳. چگونه اختلاف حل می‌شود؟ با بررسی مستندات چت و توضیحات فایل‌ها توسط تیم داوری."
            )
        else:
            # این حالت دیگر برای دکمه‌های شناخته‌شده رخ نمی‌دهد (همه دکمه‌های واقعی ربات
            # هندلر اختصاصی دارند)؛ فقط یک شبکه ایمنی برای callback_data ناشناخته است.
            bot.answer_callback_query(call.id, "⏳ این بخش به‌زودی فعال می‌شود.", show_alert=False)

    # ====================================================
    # ۱۵. جست‌وجوی سریع معامله با شناسه + پاسخ پیش‌فرض به پیام‌های نامفهوم
    #     (قبلاً اگر متن کاربر با هیچ دکمه یا مرحله‌ای مطابقت نداشت، ربات کاملاً
    #     ساکت می‌ماند و کاربر فکر می‌کرد چیزی خراب شده. این هندلر همیشه باید
    #     آخرین message_handler ثبت‌شده باشد تا هیچ‌کدام از مراحل بالا را قاپ نزند.)
    # ====================================================
    @bot.message_handler(func=lambda msg: True)
    def handle_fallback_text(message: Message):
        user_id = message.from_user.id
        text = (message.text or "").strip()
        is_admin = (user_id == getattr(config, 'ADMIN_ID', 0) or user_id in getattr(config, 'ADMIN_IDS', []))

        # اگر متن دقیقاً شبیه شناسه یک معامله بود (مثل DEV-2508-1234)،
        # مستقیم کارت همان معامله را نشان بده — نیازی به رفتن به «معاملات من» نیست
        candidate = utils.fa_to_en_digits(text).upper()
        if CONTRACT_ID_PATTERN.match(candidate):
            contract = db.get_contract(candidate)
            if contract:
                cid = contract.get("contract_id") or contract.get("id", candidate)
                role = "employer" if contract.get("buyer_id") == user_id or contract.get("employer_id") == user_id else "freelancer"
                bot.send_message(
                    message.chat.id,
                    utils.generate_contract_text(contract),
                    parse_mode="Markdown",
                    reply_markup=kb.get_contract_action_keyboard(
                        cid, role, contract.get("status", "draft"), bool(contract.get("milestones"))
                    )
                )
                return
            bot.send_message(message.chat.id, "❌ معامله‌ای با این شناسه یافت نشد.")
            return

        bot.send_message(
            message.chat.id,
            "🤔 متوجه پیام شما نشدم.\n"
            "لطفاً از دکمه‌های منوی زیر استفاده کنید، یا اگر شناسه یک معامله را دارید "
            "مستقیم همان را برایم بفرستید (مثال: `DEV-2508-1234`).",
            parse_mode="Markdown",
            reply_markup=kb.get_main_menu(is_admin)
        )
