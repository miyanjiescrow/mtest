import logging
from telebot import TeleBot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import config
import database as db
import keyboards as kb
import utils

logger = logging.getLogger("Miyanji_Admin")

def is_admin(user_id: int) -> bool:
    """بررسی دسترسی ادمین بودن کاربر"""
    admin_ids = getattr(config, 'ADMIN_IDS', [])
    single_admin = getattr(config, 'ADMIN_ID', None)
    if single_admin and single_admin not in admin_ids:
        admin_ids.append(single_admin)
    return user_id in admin_ids

def register_admin_handlers(bot: TeleBot):
    """ثبت تمامی هندلرهای مربوط به پنل مدیریت و داوری سامانه می‌انجی"""

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
            "از بخش زیر می‌توانید آمار زنده، پرونده‌های داوری و وضعیت تراکنش‌ها را نظارت کنید:"
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
    # ۳. لیست پرونده‌های اختلاف و داوری
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
    # ۴. صدور رای داوری
    # ====================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("resolve_"))
    def handle_dispute_resolution(call: CallbackQuery):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ عدم دسترسی", show_alert=True)
            return

        # فرمت callback_data: resolve_{cid}_{winner} — چون خود cid می‌تواند خط‌تیره داشته باشد
        # ولی هرگز آندرلاین ندارد (مثال DEV-2508-1234)، split از راست امن است.
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

        # اطلاع‌رسانی به هر دو طرف معامله از نتیجه داوری
        if contract:
            winner_fa = "کارفرما" if winner == "employer" else "مجری"
            buyer_id = contract.get("buyer_id") or contract.get("employer_id")
            seller_id = contract.get("seller_id") or contract.get("freelancer_id")
            for uid in {u for u in (buyer_id, seller_id) if u}:
                try:
                    bot.send_message(
                        uid,
                        f"⚖️ **نتیجه داوری معامله `{cid}` مشخص شد.**\nرای نهایی به نفع **{winner_fa}** صادر گردید.",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

    # ====================================================
    # ۵. تایید یا رد درخواست‌های شارژ/برداشت کیف پول
    # (رفع باگ: قبلاً هیچ راهی برای تسویه واقعی درخواست‌های کیف پول کاربران وجود نداشت)
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
# کیبورد رزرو ادمین در صورت عدم وجود در keyboards.py
# ====================================================
def get_default_admin_inline() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats"),
        InlineKeyboardButton("⚖️ پرونده‌های داوری", callback_data="admin_disputes")
    )
    return markup
