import logging
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import config
import database as db
import keyboards as kb
import utils

logger = logging.getLogger("Miyanji_Admin")

# استیت‌های موقت ادمین برای ثبت علت رد فیش یا رد پروژه
admin_states = {}

def is_admin(user_id: int) -> bool:
    """بررسی دسترسی ادمین بودن کاربر"""
    admin_ids = getattr(config, 'ADMIN_IDS', [])
    single_admin = getattr(config, 'ADMIN_ID', None)
    if single_admin and single_admin not in admin_ids:
        admin_ids.append(single_admin)
    return user_id in admin_ids

def register_admin_handlers(bot: TeleBot):
    """ثبت تمامی هندلرهای مربوط به پنل مدیریت، تایید فیش‌ها، تحویل پروژه و داوری می‌انجی"""

    # ====================================================
    # ۱. ورود به پنل مدیریت
    # ====================================================
    @bot.message_handler(func=lambda msg: msg.text in ["👨‍💼 پنل مدیریت", "⚙️ پنل مدیریت ارشد"])
    def admin_panel_home(message: Message):
        user_id = message.from_user.id
        
        if not is_admin(user_id):
            bot.send_message(message.chat.id, "❌ شما دسترسی به پنل مدیریت را ندارید.")
            return

        admin_text = (
            "⚙️ **به اتاق فرمان مدیریت و داوری سامانه می‌انجی خوش آمدید.**\n\n"
            "از بخش زیر می‌توانید آمار زنده، پرونده‌های داوری، تایید فیش‌ها و تراکنش‌ها را نظارت کنید:"
        )

        bot.send_message(
            message.chat.id, 
            admin_text, 
            parse_mode="Markdown", 
            reply_markup=kb.get_admin_panel_keyboard() if hasattr(kb, 'get_admin_panel_keyboard') else get_default_admin_inline()
        )

    # ====================================================
    # ۲. مشاهده آمار کلی سامانه
    # ====================================================
    @bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
    def show_system_stats(call: CallbackQuery):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        users_count = 0
        contracts_count = 0
        disputes_count = 0

        if db.supabase:
            try:
                res_users = db.supabase.table("users").select("user_id", count="exact").execute()
                users_count = res_users.count or len(res_users.data or [])

                res_contracts = db.supabase.table("contracts").select("id", count="exact").execute()
                contracts_count = res_contracts.count or len(res_contracts.data or [])

                res_disputes = db.supabase.table("contracts").select("id").eq("status", "disputed").execute()
                disputes_count = len(res_disputes.data or [])
            except Exception as e:
                logger.error(f"خطا در دریافت آمار مدیریت: {e}")

        stats_text = (
            "📊 **آمار کلی سامانه می‌انجی**\n\n"
            f"👥 **تعداد کاربران ثبت‌شده:** `{users_count}` نفر\n"
            f"📜 **تعداد کل معاملات:** `{contracts_count}` عدد\n"
            f"⚠️ **پرونده‌های در حال داوری:** `{disputes_count}` مورد\n"
        )
        bot.send_message(call.message.chat.id, stats_text, parse_mode="Markdown")

    # ====================================================
    # ۳. تایید یا رد فیش‌های واریزی کارفرمایان توسط ادمین
    # ====================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith(("receipt_approve_", "receipt_reject_")))
    def handle_receipt_approval(call: CallbackQuery):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
            return

        is_approve = call.data.startswith("receipt_approve_")
        prefix = "receipt_approve_" if is_approve else "receipt_reject_"
        # قالب دکمه: receipt_approve_{contract_id}_{buyer_id} → buyer_id همیشه بعد از آخرین "_" است
        payload = call.data.replace(prefix, "", 1)
        cid, _, _buyer_id_str = payload.rpartition("_")
        if not cid:
            cid = payload  # اطمینان در صورت نبود buyer_id در payload

        contract = db.get_contract(cid)
        if not contract:
            bot.answer_callback_query(call.id, "❌ معامله یافت نشد.", show_alert=True)
            return

        buyer_id = contract.get("buyer_id") or contract.get("employer_id")

        if is_approve:
            # وضعیت «active» تا مجری بتواند دکمهٔ «تحویل پروژه» را ببیند (سازگار با keyboards.py)
            db.update_contract(cid, {"status": "active", "payment_verified": True})
            bot.answer_callback_query(call.id, "✅ فیش تایید گردید.")
            
            bot.edit_message_caption(
                caption=f"{call.message.caption}\n\n✅ **این فیش واریزی توسط ادمین تایید شد.**\nپروژه وارد مرحله اجرا گردید.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )

            # اطلاع‌رسانی به خریدار و فروشنده
            if buyer_id:
                try:
                    bot.send_message(buyer_id, f"✅ **فیش واریزی معامله `{cid}` تایید شد.**\nوجه در حساب امن می‌انجی بلوکه گردید و پروژه رسماً آغاز شد.")
                except Exception:
                    pass

            seller_id = contract.get("seller_id") or contract.get("freelancer_id")
            if seller_id:
                try:
                    bot.send_message(seller_id, f"🎉 **پرداخت معامله `{cid}` توسط کارفرما انجام و تایید شد.**\nمی‌توانید کار را آغاز نموده و پس از اتمام، خروجی را ارسال کنید.")
                except Exception:
                    pass
        else:
            # حالت رد فیش: دریافت علت رد از ادمین
            admin_states[call.from_user.id] = {
                "step": "WAITING_FOR_RECEIPT_REJECT_REASON",
                "cid": cid,
                "buyer_id": buyer_id,
                "msg_id": call.message.message_id
            }
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                f"❌ **لطفاً علت رد فیش واریزی معامله `{cid}` را ارسال کنید:**",
                reply_markup=kb.get_cancel_keyboard() if hasattr(kb, 'get_cancel_keyboard') else None
            )

    # ====================================================
    # ۴. تایید یا رد پروژه تحویل داده‌شده توسط ادمین / کارفرما
    # ====================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith(("admin_approve_project_", "admin_reject_project_")))
    def handle_project_approval(call: CallbackQuery):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
            return

        is_approve = call.data.startswith("admin_approve_project_")
        prefix = "admin_approve_project_" if is_approve else "admin_reject_project_"
        cid = call.data.replace(prefix, "")

        contract = db.get_contract(cid)
        if not contract:
            bot.answer_callback_query(call.id, "❌ معامله یافت نشد.", show_alert=True)
            return

        seller_id = contract.get("seller_id") or contract.get("freelancer_id")
        buyer_id = contract.get("buyer_id") or contract.get("employer_id")

        if is_approve:
            db.update_contract(cid, {"status": "completed"})
            bot.answer_callback_query(call.id, "✅ پروژه تایید و تسویه گردید.")

            amount = float(contract.get("amount", 0))
            comm, net_amount = utils.calculate_commission(amount)

            # واریز خودکار مبلغ خالص به کیف پول مجری
            if seller_id:
                db.update_wallet_balance(seller_id, net_amount, "deposit", f"تسویه معامله {cid}")
                try:
                    bot.send_message(
                        seller_id, 
                        f"🎉 **پروژه معامله `{cid}` تایید گردید!**\n\n"
                        f"💰 مبلغ **{net_amount:,.0f} تومان** (پس از کسر {comm:,.0f} تومان کارمزد) به کیف پول شما واریز شد."
                    )
                except Exception:
                    pass

            if buyer_id:
                try:
                    bot.send_message(buyer_id, f"✅ **پروژه معامله `{cid}` نهایی شد و با موفقیت به پایان رسید.**\nبا تشکر از اعتماد شما به می‌انجی.")
                except Exception:
                    pass

            bot.edit_message_text(
                f"✅ **پروژه معامله `{cid}` تایید و تسویه حساب مالی انجام شد.**",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
        else:
            # رد پروژه: محاسبه ویرایش رایگان باقی‌مانده و دریافت دلیل
            free_edits_left = contract.get("free_edits_left", 3) - 1
            if free_edits_left < 0:
                free_edits_left = 0

            db.update_contract(cid, {"free_edits_left": free_edits_left, "status": "in_progress"})

            admin_states[call.from_user.id] = {
                "step": "WAITING_FOR_PROJECT_REJECT_REASON",
                "cid": cid,
                "seller_id": seller_id,
                "free_edits_left": free_edits_left
            }
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                f"⚠️ **لطفاً علت رد/نیاز به اصلاح پروژه معامله `{cid}` را بنویسید:**\n"
                f"(فرصت ویرایش مجانی باقی‌مانده مجری: {free_edits_left} بار)",
                reply_markup=kb.get_cancel_keyboard() if hasattr(kb, 'get_cancel_keyboard') else None
            )

    # ====================================================
    # ۵. لیست پرونده‌های اختلاف و داوری
    # ====================================================
    @bot.callback_query_handler(func=lambda call: call.data == "admin_disputes")
    def show_disputed_contracts(call: CallbackQuery):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        
        disputes = []
        if db.supabase:
            try:
                res = db.supabase.table("contracts").select("*").eq("status", "disputed").execute()
                disputes = res.data or []
            except Exception as e:
                logger.error(f"خطا در دریافت لیست داوری‌ها: {e}")

        if not disputes:
            bot.send_message(call.message.chat.id, "✅ در حال حاضر هیچ پرونده دارای اختلافی وجود ندارد.")
            return

        for contract in disputes:
            cid = contract.get("contract_id") or contract.get("id", "---")
            title = contract.get("title", "بدون عنوان")
            amount = float(contract.get("amount", 0))
            
            msg_text = (
                f"⚖️ **پرونده داوری معامله `{cid}`**\n"
                f"📌 عنوان: {title}\n"
                f"💵 مبلغ درگیر: {amount:,.0f} تومان\n"
                f"👤 کارفرما: `{contract.get('buyer_id') or contract.get('employer_id')}`\n"
                f"🛠 مجری: `{contract.get('seller_id') or contract.get('freelancer_id')}`\n"
            )

            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("🟢 رای به نفع کارفرما", callback_data=f"resolve_{cid}_employer"),
                InlineKeyboardButton("🔵 رای به نفع مجری", callback_data=f"resolve_{cid}_freelancer")
            )
            
            bot.send_message(call.message.chat.id, msg_text, parse_mode="Markdown", reply_markup=markup)

    # ====================================================
    # ۶. صدور رای داوری
    # ====================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("resolve_"))
    def handle_dispute_resolution(call: CallbackQuery):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
            return

        payload = call.data.replace("resolve_", "", 1)
        try:
            cid, winner = payload.rsplit("_", 1)
        except ValueError:
            bot.answer_callback_query(call.id, "❌ داده نامعتبر.", show_alert=True)
            return

        new_status = f"resolved_{winner}"

        contract = db.get_contract(cid)
        if db.supabase:
            try:
                db.supabase.table("contracts").update({"status": new_status}).eq("contract_id", cid).execute()
            except Exception as e:
                logger.error(f"خطا در به‌روزرسانی رای داوری: {e}")

        bot.answer_callback_query(call.id, "✅ رای داوری با موفقیت ثبت شد.", show_alert=True)
        bot.edit_message_text(
            f"⚖️ **پرونده معامله `{cid}` مختومه شد.**\n\nنتیجه: رای به نفع **{winner}** صادر گردید.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown"
        )

        # اطلاع‌رسانی به طرفین معامله همراه با آزادکننده/عودت مالی
        if contract:
            winner_fa = "کارفرما" if winner == "employer" else "مجری"
            buyer_id = contract.get("buyer_id") or contract.get("employer_id")
            seller_id = contract.get("seller_id") or contract.get("freelancer_id")
            amount = float(contract.get("amount", 0))

            if winner == "freelancer" and seller_id:
                _, net_amt = utils.calculate_commission(amount)
                db.update_wallet_balance(seller_id, net_amt, "deposit", f"رای داوری معامله {cid}")
            elif winner == "employer" and buyer_id:
                db.update_wallet_balance(buyer_id, amount, "deposit", f"عودت وجه رای داوری معامله {cid}")

            for uid in {u for u in (buyer_id, seller_id) if u}:
                try:
                    bot.send_message(
                        uid,
                        f"⚖️ **نتیجه داوری معامله `{cid}` مشخص شد.**\nرای نهایی به نفع **{winner_fa}** صادر گردید و تسویه مالی انجام شد.",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

    # ====================================================
    # ۷. تایید یا رد درخواست‌های شارژ/برداشت کیف پول
    # ====================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("wallet_ok_") or call.data.startswith("wallet_no_"))
    def handle_wallet_request_decision(call: CallbackQuery):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
            return

        approve = call.data.startswith("wallet_ok_")
        prefix = "wallet_ok_" if approve else "wallet_no_"
        payload = call.data.replace(prefix, "", 1)

        try:
            req_type, target_user_id_str, amount_str = payload.split("_")
            target_user_id = int(target_user_id_str)
            amount = float(amount_str)
        except Exception:
            bot.answer_callback_query(call.id, "❌ درخواست نامعتبر است.", show_alert=True)
            return

        req_type_fa = "شارژ" if req_type == "deposit" else "برداشت"

        if approve:
            delta = amount if req_type == "deposit" else -amount
            ok = db.update_wallet_balance(target_user_id, delta, req_type, f"تایید ادمین - درخواست {req_type_fa}")
            if not ok:
                bot.answer_callback_query(call.id, "❌ خطا در اعمال تراکنش (احتمالاً موجودی کاربر برای برداشت کافی نیست).", show_alert=True)
                return
            bot.answer_callback_query(call.id, "✅ عملیات با موفقیت انجام شد.")
            try:
                bot.send_message(
                    target_user_id,
                    f"✅ درخواست {req_type_fa} شما به مبلغ {utils.format_currency(amount)} تایید و اعمال شد.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        else:
            bot.answer_callback_query(call.id, "درخواست رد شد.")
            try:
                bot.send_message(
                    target_user_id,
                    f"❌ درخواست {req_type_fa} شما به مبلغ {utils.format_currency(amount)} توسط پشتیبانی رد شد.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass

        try:
            bot.edit_message_text(
                f"{'✅ تاییدشده' if approve else '❌ ردشده'}: درخواست {req_type_fa} کاربر `{target_user_id}` "
                f"به مبلغ {utils.format_currency(amount)}",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # ====================================================
    # ۸. دریافت متون ورودی ادمین (علت رد فیش یا رد پروژه)
    # ====================================================
    @bot.message_handler(func=lambda msg: is_admin(msg.from_user.id) and msg.from_user.id in admin_states)
    def handle_admin_text_input(message: Message):
        user_id = message.from_user.id
        state = admin_states.pop(user_id, {})
        step = state.get("step")
        cid = state.get("cid")
        reason_text = message.text.strip()

        if step == "WAITING_FOR_RECEIPT_REJECT_REASON":
            buyer_id = state.get("buyer_id")
            # به awaiting_payment برمی‌گردد تا دکمهٔ «ارسال فیش واریزی» دوباره برای کارفرما نمایش داده شود
            db.update_contract(cid, {"status": "awaiting_payment"})

            bot.send_message(message.chat.id, f"✅ علت رد فیش ثبت شد و برای خریدار ارسال گردید.")

            if buyer_id:
                try:
                    rejection_msg = utils.format_receipt_rejection_msg(cid, reason_text)
                    bot.send_message(buyer_id, rejection_msg, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"خطا در ارسال پیام رد فیش به خریدار: {e}")

        elif step == "WAITING_FOR_PROJECT_REJECT_REASON":
            seller_id = state.get("seller_id")
            free_edits_left = state.get("free_edits_left", 3)

            bot.send_message(message.chat.id, f"✅ علت رد/اصلاح پروژه ثبت و به مجری ابلاغ شد.")

            if seller_id:
                try:
                    proj_msg = utils.format_project_rejection_msg(cid, reason_text, free_edits_left)
                    bot.send_message(seller_id, proj_msg, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"خطا در ارسال پیام رد پروژه به مجری: {e}")

# ====================================================
# کیبورد رزرو ادمین در صورت عدم وجود در keyboards.py
# ====================================================
def get_default_admin_inline() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats"),
        InlineKeyboardButton("⚖️ پرونده‌های داوری", callback_data="admin_disputes")
    )
    return markup
