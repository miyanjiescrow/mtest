import logging
import uuid
from telebot import TeleBot
from telebot.types import Message, CallbackQuery

from config import config
from database import db
import utils
import pdf_generator
import keyboards

logger = logging.getLogger("Miyanji_Handlers")

# دیکشنری نگهداری استیت‌های موقت کاربران در حافظه
user_states = {}

def register_all_handlers(bot: TeleBot):
    """ثبت تمامی هندلرهای اصلی، FSM، ویرایش فیلدها، ثبت معامله، کیف پول، فیش واریزی، تحویل/رد پروژه و Callbacks ربات می‌انجی"""

    # ====================================================
    # ۱. دستور Start و احراز هویت اولیه
    # ====================================================

    @bot.message_handler(commands=['start'])
    def handle_start(message: Message):
        user_id = message.from_user.id
        username = message.from_user.username or ""
        first_name = message.from_user.first_name or ""

        try:
            db.get_or_create_user(user_id, username, first_name)
        except Exception as e:
            logger.error(f"خطا در ثبت کاربر اولیه: {e}")

        user_states.pop(user_id, None)
        db.clear_user_state(user_id)
        is_admin = user_id in getattr(config, 'ADMIN_IDS', [])

        args = message.text.split()
        if len(args) > 1 and (args[1].startswith("c_") or args[1].startswith("contract_")):
            contract_id = args[1].replace("c_", "").replace("contract_", "")
            contract = db.get_contract(contract_id)
            if contract:
                text = utils.generate_contract_text(contract)
                role = "buyer" if contract.get("buyer_id") == user_id else "seller"
                bot.send_message(
                    message.chat.id,
                    f"🤝 **شما به معامله زیر دعوت شده‌اید:**\n\n{text}",
                    parse_mode="Markdown",
                    reply_markup=keyboards.get_contract_action_keyboard(
                        contract_id, role, contract.get("status", "draft")
                    )
                )
                return

        welcome_text = (
            f"سلام {first_name} عزیز 👋\n\n"
            "به **سامانه امانت‌داری و واسطه‌گری هوشمند می‌انجی** خوش آمدید.\n"
            "با می‌انجی می‌توانید معاملات آزادکاری (فریلنسری) و خرید/فروش خود را در محیطی امن و قانونی انجام دهید.\n\n"
            "لطفاً از منوی زیر گزینه‌ای را انتخاب کنید:"
        )

        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode="Markdown",
            reply_markup=keyboards.get_main_menu(is_admin)
        )

    # ====================================================
    # ۲. دکمه‌های منوی اصلی (Reply Keyboard)
    # ====================================================

    @bot.message_handler(func=lambda msg: msg.text in ["📝 ثبت معامله جدید", "🤝 ایجاد معامله جدید"])
    def start_new_contract(message: Message):
        bot.send_message(
            message.chat.id,
            "📌 **لطفاً حوزه کاری معامله خود را انتخاب کنید:**",
            reply_markup=keyboards.get_category_keyboard()
        )

    @bot.message_handler(func=lambda msg: msg.text in ["💰 کیف پول و اعتبار", "💰 کیف پول"])
    def show_wallet(message: Message):
        user = db.get_or_create_user(message.from_user.id)
        balance = float(user.get("wallet_balance", 0.0)) if user else 0.0

        wallet_text = (
            "💰 **کیف پول و مدیریت مالی شما**\n\n"
            f"💵 **موجودی فعلی:** {utils.format_currency(balance)}\n\n"
            "جهت شارژ حساب یا درخواست تسویه حساب از گزینه‌های زیر استفاده کنید."
        )
        bot.send_message(
            message.chat.id,
            wallet_text,
            parse_mode="Markdown",
            reply_markup=keyboards.get_wallet_inline()
        )

    @bot.message_handler(func=lambda msg: msg.text in ["📂 معاملات من", "📜 معاملات من"])
    def show_my_contracts(message: Message):
        user_id = message.from_user.id
        contracts = db.get_user_contracts(user_id)

        if not contracts:
            bot.send_message(message.chat.id, "📭 شما هنوز هیچ معامله‌ای ثبت نکرده‌اید.")
            return

        for c in contracts[:5]:
            c_id = c.get("contract_id", c.get("id", "---"))
            status = c.get("status", "draft")
            role = "buyer" if c.get("buyer_id") == user_id else "seller"

            text = utils.generate_contract_text(c)
            bot.send_message(
                message.chat.id,
                text,
                parse_mode="Markdown",
                reply_markup=keyboards.get_contract_action_keyboard(c_id, role, status)
            )

    @bot.message_handler(func=lambda msg: msg.text in ["📞 پشتیبانی و ارتباط با ما", "📞 پشتیبانی و داوری"])
    def show_support(message: Message):
        bot.send_message(
            message.chat.id,
            "📞 **بخش پشتیبانی و مرکز پاسخگویی می‌انجی**\n\n"
            "برای مشاهده سوالات متداول یا ارتباط مستقیم با کارشناسان حقوقی از دکمه‌های زیر استفاده کنید:",
            reply_markup=keyboards.get_support_inline()
        )

    @bot.message_handler(func=lambda msg: msg.text in ["⚖️ قوانین و راهنما", "⚖️ قوانین و راهنمای حقوقی"])
    def show_rules(message: Message):
        rules_text = (
            "⚖️ **قوانین و مقررات سامانه می‌انجی**\n\n"
            "۱. تمام معاملات ثبت‌شده در ربات بر اساس ماده ۱۰ قانون مدنی جمهوری اسلامی ایران تنظیم گردیده و دارای وجاهت قانونی است.\n"
            "۲. وجوه امانت تا زمان تایید نهایی خریدار/کارفرما در کیف پول امانت سامانه **بلوکه** می‌ماند.\n"
            "۳. در صورت بروز اختلاف، پلتفرم می‌انجی به عنوان **داور مرضی‌الطرفین** (ماده ۴۵۵ آیین دادرسی مدنی) رای نهایی را صادر می‌نماید.\n\n"
            "💬 **پشتیبانی آنلاین:** جهت ارتباط با کارشناسان پشتیبانی، پیام خود را مستقیم ارسال نمایید."
        )
        bot.send_message(message.chat.id, rules_text, parse_mode="Markdown")

    @bot.message_handler(func=lambda msg: msg.text in ["❌ انصراف و بازگشت به منو", "❌ انصراف", "انصراف"])
    def cancel_operation(message: Message):
        user_id = message.from_user.id
        user_states.pop(user_id, None)
        db.clear_user_state(user_id)
        is_admin = user_id in getattr(config, 'ADMIN_IDS', [])
        bot.send_message(
            message.chat.id,
            "❌ عملیات جاری لغو شد. به منوی اصلی بازگشتید.",
            reply_markup=keyboards.get_main_menu(is_admin)
        )

    # ====================================================
    # ۳. انتخاب حوزه کاری و راهنمای فرم ثبت
    # ====================================================

    @bot.message_handler(func=lambda msg: msg.text in [
        "💻 برنامه‌نویسی و IT", "🎨 طراحی و گرافیک", "🎓 دانشجویی و پژوهشی", 
        "📚 آموزشی و تدریس", "📑 عمومی و خدمات"
    ])
    def handle_category_button(message: Message):
        cat_map = {
            "💻 برنامه‌نویسی و IT": "DEV",
            "🎨 طراحی و گرافیک": "DESIGN",
            "🎓 دانشجویی و پژوهشی": "ACADEMIC",
            "📚 آموزشی و تدریس": "TEACHING",
            "📑 عمومی و خدمات": "GEN"
        }
        cat_code = cat_map.get(message.text, "GEN")
        user_id = message.from_user.id

        user_states[user_id] = {
            "category": cat_code,
            "step": "WAITING_FOR_CONTRACT_FORM"
        }
        db.set_user_state(user_id, "WAITING_FOR_CONTRACT_FORM", {"category": cat_code})

        sample_text = (
            f"📌 حوزه کاری انتخابی شما: **{message.text}**\n\n"
            "📝 **فرم ثبت هوشمند معامله**\n"
            "لطفاً متن نمونه زیر را کپی کرده، اطلاعات معامله خود را جایگزین و ارسال نمایید:\n\n"
            "نقش من: کارفرما\n"
            "عنوان: پروژه جدید\n"
            "مبلغ کل: 5000000\n"
            "مهلت (روز): 7\n"
            "شرح تعهدات: توضیحات کامل وظایف و تحویلی‌ها"
        )
        bot.send_message(message.chat.id, sample_text, reply_markup=keyboards.get_cancel_keyboard())

    # ====================================================
    # ۴. دکمه‌های مربوط به ویرایش و تایید پیش‌نویس (Inline Callbacks)
    # ====================================================

    @bot.callback_query_handler(func=lambda call: call.data.startswith(("edit_draft_", "edit_field_", "back_to_preview_", "confirm_draft_", "cancel_draft")))
    def handle_draft_editing_callbacks(call: CallbackQuery):
        user_id = call.from_user.id
        data = call.data
        state = user_states.get(user_id, {})
        
        _, db_data = db.get_user_state(user_id)
        draft_data = state.get("draft_data") or db_data.get("draft_data")

        if data == "cancel_draft":
            user_states.pop(user_id, None)
            db.clear_user_state(user_id)
            bot.answer_callback_query(call.id, "❌ پیش‌نویس لغو شد.")
            bot.edit_message_text(
                "❌ **پیش‌نویس قرارداد لغو گردید.**",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
            return

        if not draft_data:
            bot.answer_callback_query(call.id, "⚠️ پیش‌نویس فعالی یافت نشد.", show_alert=True)
            return

        if data.startswith("edit_draft_"):
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                "✏️ **کدام بخش از پیش‌نویس را می‌خواهید ویرایش کنید؟**",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=keyboards.get_draft_edit_inline(),
                parse_mode="Markdown"
            )
            return

        if data.startswith("back_to_preview_"):
            bot.answer_callback_query(call.id)
            preview_text = utils.generate_draft_preview_text(draft_data)
            bot.edit_message_text(
                preview_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=keyboards.get_contract_preview_inline(),
                parse_mode="Markdown"
            )
            return

        if data.startswith("edit_field_"):
            field = data.replace("edit_field_", "").split("_")[0]
            state["editing_field"] = field
            state["step"] = "WAITING_FOR_FIELD_EDIT"
            user_states[user_id] = state
            db.set_user_state(user_id, "WAITING_FOR_FIELD_EDIT", {"editing_field": field, "draft_data": draft_data})

            field_names = {
                "title": "عنوان جدید معامله",
                "amount": "مبلغ جدید (به تومان)",
                "deadline": "مهلت جدید تحویل (به روز)",
                "desc": "شرح جدید تعهدات"
            }
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                f"📝 لطفاً **{field_names.get(field, 'مقدار جدید')}** را ارسال کنید:",
                reply_markup=keyboards.get_cancel_keyboard()
            )
            return

        if data.startswith("confirm_draft_"):
            bot.answer_callback_query(call.id)
            user = db.get_or_create_user(user_id)
            user_phone = user.get("phone_number") if user else None

            user_states[user_id] = {"draft_data": draft_data, "step": "WAITING_FOR_PHONE"}
            db.set_user_state(user_id, "WAITING_FOR_PHONE", {"draft_data": draft_data})

            if not user_phone:
                bot.send_message(
                    call.message.chat.id,
                    "📱 **جهت تایید قانونی و ثبت امضای الکترونیک، لطفاً شماره تماس خود را ارسال کنید:**",
                    reply_markup=keyboards.get_phone_sign_keyboard()
                )
            else:
                bot.send_message(
                    call.message.chat.id,
                    f"📱 شماره تماس شما (`{user_phone}`) جهت ثبت امضا استفاده خواهد شد.\nآیا تمایل به ادامه یا تغییر آن دارید؟",
                    reply_markup=keyboards.get_skip_work_phone_keyboard()
                )

    # ====================================================
    # ۵. هندلر اختصاصی دکمه «رد کردن و استفاده از شماره تلگرام»
    # ====================================================

    @bot.message_handler(func=lambda msg: any(kw in msg.text for kw in [
        "رد کردن", "استفاده از شماره", "شماره تلگرام", "ادامه با شماره", 
        "تایید و ادامه", "استفاده از شماره تلگرام"
    ]))
    def handle_skip_phone_button(message: Message):
        user_id = message.from_user.id
        state = user_states.get(user_id, {})
        _, db_data = db.get_user_state(user_id)
        
        draft_data = state.get("draft_data") or db_data.get("draft_data")

        if draft_data:
            user = db.get_or_create_user(user_id)
            user_phone = (user.get("phone_number") if user else None) or "ثبت‌شده در تلگرام"
            finalize_and_create_contract(bot, message.chat.id, user_id, draft_data, user_phone)
        else:
            is_admin = user_id in getattr(config, 'ADMIN_IDS', [])
            bot.send_message(
                message.chat.id, 
                "⚠️ پیش‌نویس فعالی یافت نشد. لطفاً مجدداً اقدام به ثبت معامله کنید.",
                reply_markup=keyboards.get_main_menu(is_admin)
            )

    # ====================================================
    # ۶. دریافت کنتاکت از تلگرام
    # ====================================================

    @bot.message_handler(content_types=['contact'])
    def handle_contact_received(message: Message):
        user_id = message.from_user.id
        contact = message.contact

        if contact.user_id != user_id:
            bot.send_message(message.chat.id, "❌ لطفاً فقط از دکمه رسمی ارسال شماره تماس استفاده کنید.")
            return

        phone_number = contact.phone_number
        db.update_user_phone(user_id, phone_number)

        state = user_states.get(user_id, {})
        _, db_data = db.get_user_state(user_id)
        draft_data = state.get("draft_data") or db_data.get("draft_data")

        if draft_data:
            finalize_and_create_contract(bot, message.chat.id, user_id, draft_data, phone_number)
            return

        is_admin = user_id in getattr(config, 'ADMIN_IDS', [])
        bot.send_message(
            message.chat.id,
            f"✅ **شماره تماس شما (`{phone_number}`) با موفقیت در سیستم ثبت گردید.**",
            parse_mode="Markdown",
            reply_markup=keyboards.get_main_menu(is_admin)
        )

    # ====================================================
    # ۷. اکشن‌های قرارداد، ارسال فیش، تحویل و رد پروژه
    # ====================================================

    @bot.callback_query_handler(func=lambda call: call.data.startswith("get_pdf_") or call.data.startswith("pdf_"))
    def handle_download_pdf(call: CallbackQuery):
        cid = call.data.rsplit("_", 1)[1]
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

    @bot.callback_query_handler(func=lambda call: call.data.startswith((
        "sign_contract_", "bargain_", "cancel_contract_", "deliver_", "final_confirm_",
        "upload_receipt_", "reject_project_", "receipt_approve_", "receipt_reject_"
    )))
    def handle_contract_actions(call: CallbackQuery):
        data = call.data
        user_id = call.from_user.id

        # ۱. امضای قرارداد
        if data.startswith("sign_contract_"):
            cid = data.replace("sign_contract_", "")
            contract = db.get_contract(cid)
            if not contract:
                bot.answer_callback_query(call.id, "❌ معامله یافت نشد.", show_alert=True)
                return

            # به‌روزرسانی نقش طرف دوم
            if not contract.get("buyer_id") and contract.get("creator_id") != user_id:
                db.update_contract(cid, {"buyer_id": user_id, "status": "awaiting_payment", "signed_by_second_party": True})
            elif not contract.get("seller_id") and contract.get("creator_id") != user_id:
                db.update_contract(cid, {"seller_id": user_id, "status": "awaiting_payment", "signed_by_second_party": True})
            else:
                db.update_contract(cid, {"status": "awaiting_payment", "signed_by_second_party": True})

            bot.answer_callback_query(call.id, "✅ قرارداد امضا شد.")
            bot.send_message(
                call.message.chat.id,
                f"🎉 **قرارداد شماره `{cid}` با موفقیت امضا شد.**\n💳 کارفرمای محترم، لطفاً جهت فعالسازی نهایی اقدام به ارسال فیش واریزی نمایید.",
                parse_mode="Markdown",
                reply_markup=keyboards.get_contract_action_keyboard(cid, "employer", "awaiting_payment")
            )
            return

        # ۲. پیشنهاد مبلغ جدید (پیشنهاد متقابل)
        if data.startswith("bargain_"):
            cid = data.replace("bargain_", "")
            user_states[user_id] = {"bargain_cid": cid, "step": "WAITING_FOR_BARGAIN_PRICE"}
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id, "💬 **لطفاً مبلغ پیشنهادی جدید خود را به تومان ارسال کنید:**", reply_markup=keyboards.get_cancel_keyboard())
            return

        # ۳. لغو معامله
        if data.startswith("cancel_contract_"):
            cid = data.replace("cancel_contract_", "")
            db.update_contract(cid, {"status": "cancelled"})
            bot.answer_callback_query(call.id, "❌ معامله لغو شد.")
            bot.send_message(call.message.chat.id, f"🚫 معامله شماره `{cid}` با موفقیت لغو شد.")
            return

        # ۴. شروع فرآیند ارسال فیش واریزی
        if data.startswith("upload_receipt_"):
            cid = data.replace("upload_receipt_", "")
            user_states[user_id] = {"step": "AWAITING_RECEIPT_PHOTO", "contract_id": cid}
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                f"📸 لطفاً تصویر فیش واریزی مربوط به قرارداد `{cid}` را ارسال فرمایید:",
                reply_markup=keyboards.get_cancel_keyboard(),
                parse_mode="Markdown"
            )
            return

        # ۵. شروع تحویل پروژه توسط مجری
        if data.startswith("deliver_"):
            cid = data.replace("deliver_", "")
            user_states[user_id] = {"step": "AWAITING_PROJECT_FILES", "contract_id": cid}
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                f"🚀 **تحویل پروژه شماره `{cid}`**\nلطفاً فایل‌ها یا توضیحات تحویلی نهایی پروژه را ارسال نمایید:",
                reply_markup=keyboards.get_cancel_keyboard(),
                parse_mode="Markdown"
            )
            return

        # ۶. تایید نهایی پروژه و آزادسازی وجه توسط کارفرما
        if data.startswith("final_confirm_"):
            cid = data.replace("final_confirm_", "")
            contract = db.get_contract(cid)
            if contract:
                db.update_contract(cid, {"status": "completed"})
                seller_id = contract.get("seller_id")
                amount = float(contract.get("amount", 0))

                # واریز اعتبار به کیف پول مجری
                if seller_id:
                    db.update_wallet_balance(seller_id, amount, mode="add")
                    bot.send_message(
                        seller_id,
                        f"🎉 **کارفرما پروژه `{cid}` را تایید نهایی کرد!**\n💰 مبلغ {utils.format_currency(amount)} به کیف پول شما واریز شد."
                    )

                bot.answer_callback_query(call.id, "✅ پروژه تایید و وجه آزاد شد.")
                bot.send_message(
                    call.message.chat.id,
                    f"✅ **پروژه `{cid}` با موفقیت تکمیل شد و مبلغ به حساب مجری منتقل گردید.**",
                    parse_mode="Markdown"
                )
            return

        # ۷. شروع ثبت دلیل رد پروژه توسط کارفرما
        if data.startswith("reject_project_"):
            cid = data.replace("reject_project_", "")
            user_states[user_id] = {"step": "AWAITING_PROJECT_REJECT_REASON", "contract_id": cid}
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                f"⚠️ لطفاً **علت عدم تایید و موارد نیازمند اصلاح** برای معامله `{cid}` را وارد کنید:",
                reply_markup=keyboards.get_cancel_keyboard(),
                parse_mode="Markdown"
            )
            return

        # ۸. تایید فیش واریزی توسط ادمین
        if data.startswith("receipt_approve_"):
            parts = data.split("_")
            cid, buyer_id = parts[2], int(parts[3])
            db.update_contract(cid, {"status": "active"})
            bot.answer_callback_query(call.id, "✅ فیش تایید شد.")
            bot.send_message(call.message.chat.id, f"✅ فیش واریزی قرارداد `{cid}` تایید و معامله **فعال** شد.")
            bot.send_message(
                buyer_id,
                f"🎉 **فیش واریزی شما برای معامله `{cid}` توسط ادمین تایید شد.**\nپروژه هم‌اکنون به وضعیت «در حال انجام» تغییر یافت."
            )
            return

        # ۹. رد فیش واریزی توسط ادمین
        if data.startswith("receipt_reject_"):
            parts = data.split("_")
            cid, buyer_id = parts[2], int(parts[3])
            user_states[user_id] = {"step": "AWAITING_RECEIPT_REJECT_REASON", "contract_id": cid, "buyer_id": buyer_id}
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                f"📝 لطفاً **علت رد فیش واریزی** برای قرارداد `{cid}` را وارد کنید:",
                reply_markup=keyboards.get_cancel_keyboard()
            )
            return

    # ====================================================
    # ۸. دریافت عکس فیش و فایل‌های تحویلی پروژه
    # ====================================================

    @bot.message_handler(content_types=['photo', 'document'])
    def handle_media_uploads(message: Message):
        user_id = message.from_user.id
        state = user_states.get(user_id, {})
        step = state.get("step")

        # پردازش عکس فیش واریزی
        if step == "AWAITING_RECEIPT_PHOTO":
            cid = state.get("contract_id")
            file_id = message.photo[-1].file_id if message.photo else message.document.file_id
            
            db.update_contract(cid, {"receipt_file_id": file_id, "status": "awaiting_receipt_approval"})
            user_states.pop(user_id, None)

            admin_ids = getattr(config, 'ADMIN_IDS', [])
            for admin_id in admin_ids:
                try:
                    bot.send_photo(
                        admin_id,
                        photo=file_id,
                        caption=f"💳 **فیش واریزی جدید**\n\n📌 **کد قرارداد:** `{cid}`\n👤 **خریدار/کارفرما:** `{user_id}`",
                        parse_mode="Markdown",
                        reply_markup=keyboards.get_receipt_admin_approval_inline(cid, user_id)
                    )
                except Exception as e:
                    logger.error(f"خطا در ارسال فیش به ادمین {admin_id}: {e}")

            bot.send_message(
                message.chat.id,
                "✅ **فیش واریزی شما دریافت شد و جهت تایید برای مدیریت ارسال گردید.**",
                reply_markup=keyboards.get_main_menu()
            )
            return

        # پردازش تحویل فایل‌های پروژه توسط مجری
        if step == "AWAITING_PROJECT_FILES":
            cid = state.get("contract_id")
            contract = db.get_contract(cid)
            buyer_id = contract.get("buyer_id") if contract else None

            db.update_contract(cid, {"status": "delivered"})
            user_states.pop(user_id, None)

            if buyer_id:
                if message.photo:
                    bot.send_photo(buyer_id, message.photo[-1].file_id, caption=f"📦 **پروژه معامله `{cid}` تحویل داده شد.**")
                elif message.document:
                    bot.send_document(buyer_id, message.document.file_id, caption=f"📦 **پروژه معامله `{cid}` تحویل داده شد.**")

                bot.send_message(
                    buyer_id,
                    f"🔔 **کارفرمای محترم، پروژه مربوط به معامله `{cid}` تحویل گردید.**\nلطفاً پس از بررسی، نسبت به تایید یا رد آن اقدام فرمایید:",
                    reply_markup=keyboards.get_contract_action_keyboard(cid, "employer", "delivered")
                )

            bot.send_message(
                message.chat.id,
                "✅ **پروژه با موفقیت تحویل کارفرما شد.** پس از بررسی و تایید کارفرما، مبلغ به حساب شما منتقل می‌گردد.",
                reply_markup=keyboards.get_main_menu()
            )

    # ====================================================
    # ۹. پردازش کلیه متون ارسالی کاربران و FSMها
    # ====================================================

    @bot.message_handler(func=lambda msg: True)
    def handle_text_messages(message: Message):
        user_id = message.from_user.id
        state = user_states.get(user_id, {})
        step = state.get("step")
        text = message.text.strip()

        # ۱. پردازش علت رد فیش توسط ادمین
        if step == "AWAITING_RECEIPT_REJECT_REASON":
            cid = state.get("contract_id")
            buyer_id = state.get("buyer_id")
            db.update_contract(cid, {"status": "awaiting_payment"})
            user_states.pop(user_id, None)

            bot.send_message(
                buyer_id,
                f"❌ **فیش واریزی شما برای معامله `{cid}` رد شد.**\n\n📝 **علت رد:** {text}\nلطفاً مجدداً تصویر فیش معتبر را ارسال نمایید."
            )
            bot.send_message(message.chat.id, "✅ دلیل رد فیش ثبت و به کارفرما ابلاغ شد.", reply_markup=keyboards.get_main_menu(True))
            return

        # ۲. پردازش علت رد پروژه توسط کارفرما
        if step == "AWAITING_PROJECT_REJECT_REASON":
            cid = state.get("contract_id")
            contract = db.get_contract(cid)
            seller_id = contract.get("seller_id") if contract else None

            free_edits = (contract.get("free_edits_left", 3) if contract else 3) - 1
            db.update_contract(cid, {"status": "active", "free_edits_left": max(0, free_edits)})
            user_states.pop(user_id, None)

            rejection_text = (
                f"⚠️ **عدم تایید و درخواست اصلاح برای معامله `{cid}`**\n\n"
                f"📝 **موارد نیازمند اصلاح:**\n{text}\n\n"
                f"🔄 **تعداد ویرایش‌های مجانی باقی‌مانده:** {max(0, free_edits)} بار"
            )

            if seller_id:
                bot.send_message(seller_id, rejection_text, parse_mode="Markdown")

            bot.send_message(message.chat.id, "✅ موارد اصلاحی به مجری ابلاغ گردید.", reply_markup=keyboards.get_main_menu())
            return

        # ۳. پردازش تحویل متنی پروژه توسط مجری
        if step == "AWAITING_PROJECT_FILES":
            cid = state.get("contract_id")
            contract = db.get_contract(cid)
            buyer_id = contract.get("buyer_id") if contract else None

            db.update_contract(cid, {"status": "delivered"})
            user_states.pop(user_id, None)

            if buyer_id:
                bot.send_message(
                    buyer_id,
                    f"📦 **توضیحات و تحویلی پروژه معامله `{cid}`:**\n\n{text}",
                    reply_markup=keyboards.get_contract_action_keyboard(cid, "employer", "delivered")
                )

            bot.send_message(
                message.chat.id,
                "✅ **توضیحات تحویل پروژه برای کارفرما ارسال شد.**",
                reply_markup=keyboards.get_main_menu()
            )
            return

        # ۴. پردازش ویرایش مجزای فیلد پیش‌نویس (FSM)
        if step == "WAITING_FOR_FIELD_EDIT":
            _, db_data = db.get_user_state(user_id)
            field = state.get("editing_field") or db_data.get("editing_field")
            draft_data = state.get("draft_data") or db_data.get("draft_data", {})
            clean_input = utils.fa_to_en_digits(text)

            if field == "title":
                draft_data["title"] = text
            elif field == "amount":
                try:
                    draft_data["amount"] = float(clean_input.replace(",", ""))
                except ValueError:
                    bot.send_message(message.chat.id, "⚠️ لطفاً مبلغ را به صورت عددی وارد کنید.")
                    return
            elif field == "deadline":
                if clean_input.isdigit():
                    draft_data["deadline"] = int(clean_input)
                else:
                    bot.send_message(message.chat.id, "⚠️ لطفاً مهلت تحویل را به عدد (روز) وارد کنید.")
                    return
            elif field == "desc":
                draft_data["description"] = text

            state["draft_data"] = draft_data
            state.pop("step", None)
            state.pop("editing_field", None)
            user_states[user_id] = state
            db.set_user_state(user_id, "IDLE", {"draft_data": draft_data})

            is_admin = user_id in getattr(config, 'ADMIN_IDS', [])
            bot.send_message(message.chat.id, "✅ تغییرات با موفقیت اعمال گردید.", reply_markup=keyboards.get_main_menu(is_admin))

            preview_text = utils.generate_draft_preview_text(draft_data)
            bot.send_message(
                message.chat.id,
                preview_text,
                parse_mode="Markdown",
                reply_markup=keyboards.get_contract_preview_inline()
            )
            return

        # ۵. پردازش چانه‌زنی و مبلغ جدید
        if step == "WAITING_FOR_BARGAIN_PRICE":
            cid = state.get("bargain_cid")
            clean_text = utils.fa_to_en_digits(text).replace(",", "").replace(" تومان", "").strip()
            if clean_text.isdigit():
                new_amount = float(clean_text)
                db.update_contract(cid, {"amount": new_amount, "status": "bargaining"})
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, f"✅ مبلغ جدید ({utils.format_currency(new_amount)}) برای معامله `{cid}` ثبت و ارسال شد.")
            else:
                bot.send_message(message.chat.id, "⚠️ لطفاً مبلغ را فقط به صورت عدد وارد کنید.")
            return

        # ۶. پردازش فرم یکجای ثبت معامله و اعمال صحیح حوزه انتخابی
        parsed = utils.parse_single_message_contract(text)
        if parsed:
            _, db_data = db.get_user_state(user_id)
            category = state.get("category") or db_data.get("category", "GEN")
            parsed["category"] = category

            user_states[user_id] = {
                "draft_data": parsed,
                "category": category
            }
            db.set_user_state(user_id, "DRAFT_CREATED", {"draft_data": parsed, "category": category})

            preview_text = utils.generate_draft_preview_text(parsed)
            bot.send_message(
                message.chat.id,
                preview_text,
                parse_mode="Markdown",
                reply_markup=keyboards.get_contract_preview_inline()
            )

# ====================================================
# تابع کمکی ثبت نهایی معامله در دیتابیس
# ====================================================

def finalize_and_create_contract(bot: TeleBot, chat_id: int, user_id: int, draft_data: dict, phone_number: str):
    """ثبت رسمی معامله در دیتابیس و تولید لینک دعوت اختصاصی با استفاده از utils"""
    try:
        category = draft_data.get("category", "GEN")
        
        raw_cid = utils.generate_archive_contract_id(category) if hasattr(utils, 'generate_archive_contract_id') else None
        contract_id = raw_cid or f"{category}-{uuid.uuid4().hex[:6].upper()}"

        role = str(draft_data.get("role", "employer")).lower()
        is_employer = role in ["employer", "buyer", "کارفرما", "خریدار"]

        contract_payload = {
            "contract_id": str(contract_id),
            "category": str(category),
            "title": str(draft_data.get("title", "معامله جدید")),
            "amount": float(draft_data.get("amount", 0)),
            "deadline": int(draft_data.get("deadline", 1)),
            "description": str(draft_data.get("description", "")),
            "milestones": draft_data.get("milestones", []),
            "buyer_id": user_id if is_employer else None,
            "seller_id": None if is_employer else user_id,
            "buyer_phone": str(phone_number) if is_employer else None,
            "seller_phone": None if is_employer else str(phone_number),
            "status": "pending_approval",
            "creator_id": user_id,
            "signed_by_second_party": False,
            "free_edits_left": 3
        }

        created = db.create_contract(contract_payload)
        user_states.pop(user_id, None)
        db.clear_user_state(user_id)

        contract_data = created if created else contract_payload
        c_text = utils.generate_contract_text(contract_data)
        
        bot_info = bot.get_me()
        bot_username = bot_info.username if bot_info else ""
        
        if hasattr(utils, 'generate_quick_contract_link'):
            invite_link = utils.generate_quick_contract_link(bot_username, contract_id)
        else:
            invite_link = f"https://t.me/{bot_username}?start=contract_{contract_id}"

        is_admin = user_id in getattr(config, 'ADMIN_IDS', [])
        bot.send_message(
            chat_id,
            f"🎉 **معامله شما با موفقیت ثبت شد!**\n\n"
            f"{c_text}\n\n"
            f"🔗 **لینک دعوت اختصاصی:**\n`{invite_link}`\n\n"
            f"این لینک را برای طرف مقابل ارسال کنید تا وارد معامله شده و آن را امضا کند.",
            parse_mode="Markdown",
            reply_markup=keyboards.get_main_menu(is_admin)
        )

    except Exception as e:
        logger.error(f"خطا در ایجاد معامله نهایی: {e}")
        bot.send_message(chat_id, f"❌ خطای سیستم هنگام ثبت معامله: {e}")
