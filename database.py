import logging
import threading
from typing import Dict, Any, Optional, List, Union
from supabase import create_client, Client
from config import config

logger = logging.getLogger("Miyanji_Database")

# قفل Thread جهت جلوگیری از Race Condition
db_lock = threading.Lock()

# ایجاد کلاینت اتصال به Supabase
try:
    supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    logger.info("اتصال به Supabase با موفقیت برقرار شد.")
except Exception as e:
    logger.error(f"خطا در اتصال به Supabase: {e}")
    supabase = None

# حافظه موقت برای مدیریت وضعیت کاربران (FSM State Management)
_user_states: Dict[int, Dict[str, Any]] = {}

# ====================================================
# ۱. مدیریت وضعیت کاربران (FSM State Management)
# ====================================================

def set_user_state(user_id: int, state: str, data: Optional[Dict[str, Any]] = None) -> None:
    """تنظیم وضعیت و داده‌های موقت کاربر"""
    with db_lock:
        if user_id not in _user_states:
            _user_states[user_id] = {}
        _user_states[user_id]["state"] = state
        if data:
            if "data" not in _user_states[user_id]:
                _user_states[user_id]["data"] = {}
            _user_states[user_id]["data"].update(data)


def get_user_state(user_id: int) -> tuple:
    """دریافت وضعیت و داده‌های جاری کاربر"""
    with db_lock:
        user_info = _user_states.get(user_id, {"state": None, "data": {}})
        state = user_info.get("state")
        data = user_info.get("data", {})
        return state, data


def clear_user_state(user_id: int) -> None:
    """پاک‌سازی کامل وضعیت و داده‌های موقت کاربر"""
    with db_lock:
        if user_id in _user_states:
            del _user_states[user_id]


# ====================================================
# ۲. مدیریت کاربران، کیف پول و ادمین (Users, Roles & Impersonation)
# ====================================================

def register_or_update_user(
    user_id: int, 
    username: Optional[str] = "", 
    first_name: Optional[str] = "", 
    referrer_id: Optional[int] = None, 
    phone_number: Optional[str] = None,
    role: Optional[str] = "user"
) -> Dict[str, Any]:
    """ثبت‌نام یا بروزرسانی اطلاعات کاربر و شماره تماس در پایگاه داده"""
    if not supabase:
        return {}

    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()
        existing_user = res.data[0] if res.data else None

        if existing_user:
            update_data = {}
            if first_name: update_data["first_name"] = first_name
            if username: update_data["username"] = username
            if phone_number: update_data["phone_number"] = phone_number
            
            if update_data:
                supabase.table("users").update(update_data).eq("user_id", user_id).execute()
            return existing_user
        else:
            new_user = {
                "user_id": user_id,
                "username": username or "",
                "first_name": first_name or "کاربر",
                "phone_number": phone_number,
                "wallet_balance": 0.0,
                "referrer_id": referrer_id if (referrer_id and referrer_id != user_id) else None,
                "role": role,  # super_admin, financial_admin, support_admin, user
                "impersonated_by": None
            }
            res_insert = supabase.table("users").insert(new_user).execute()
            return res_insert.data[0] if res_insert.data else new_user
    except Exception as e:
        logger.error(f"خطا در ثبت یا بروزرسانی کاربر {user_id}: {e}")
        return {}

get_or_create_user = register_or_update_user


def update_user_phone(user_id: int, phone_number: str) -> bool:
    """بروزرسانی شماره تماس کاربر"""
    try:
        register_or_update_user(user_id, phone_number=phone_number)
        return True
    except Exception as e:
        logger.error(f"خطا در بروزرسانی شماره تلفن کاربر {user_id}: {e}")
        return False


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """دریافت اطلاعات کامل کاربر"""
    if not supabase:
        return None
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"خطا در دریافت اطلاعات کاربر {user_id}: {e}")
        return None


def set_user_role(user_id: int, role: str) -> bool:
    """تنظیم سطح دسترسی کاربر (RBAC: super_admin, financial, support, user)"""
    if not supabase: return False
    try:
        supabase.table("users").update({"role": role}).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        logger.error(f"خطا در تغییر سطح دسترسی کاربر {user_id}: {e}")
        return False


def set_impersonation(admin_id: int, target_user_id: Optional[int]) -> bool:
    """قابلیت اتصال به کاربر جهت بررسی و مدیریت مستقیم حساب کاربر"""
    if not supabase: return False
    try:
        supabase.table("users").update({"impersonated_by": target_user_id}).eq("user_id", admin_id).execute()
        return True
    except Exception as e:
        logger.error(f"خطا در Impersonation برای ادمین {admin_id}: {e}")
        return False


def update_wallet_balance(
    user_id: int, 
    amount_change: float, 
    transaction_type: str = "general", 
    description: str = ""
) -> bool:
    """بروزرسانی، افزایش یا کاهش موجودی کیف پول کاربر و ثبت لاگ تراکنش"""
    user = get_user(user_id)
    if not user:
        return False
    
    current_balance = float(user.get("wallet_balance", 0.0))
    new_balance = current_balance + amount_change
    
    if new_balance < 0:
        return False

    try:
        supabase.table("users").update({"wallet_balance": new_balance}).eq("user_id", user_id).execute()
        
        try:
            supabase.table("transactions").insert({
                "user_id": user_id,
                "amount": amount_change,
                "type": transaction_type,
                "description": description
            }).execute()
        except Exception as tx_err:
            logger.warning(f"تراکنش ثبت شد اما لاگ تراکنش خطاداد: {tx_err}")

        return True
    except Exception as e:
        logger.error(f"خطا در بروزرسانی کیف پول کاربر {user_id}: {e}")
        return False

change_wallet_balance = update_wallet_balance


# ====================================================
# ۳. مدیریت معاملات، فازها و سیستم ویرایش مجانی
# ====================================================

def create_contract(
    payload_or_creator_id: Union[Dict[str, Any], int], 
    role: Optional[str] = None, 
    title: Optional[str] = None, 
    amount: Optional[float] = None, 
    description: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """ایجاد یک معامله جدید در Supabase با قابلیت پشتیبانی از ویرایش مجانی و امضای طرف دوم"""
    if not supabase:
        logger.error("کلاینت Supabase مقداردهی نشده است.")
        return None

    try:
        if isinstance(payload_or_creator_id, dict):
            contract_data = payload_or_creator_id.copy()
        else:
            creator_id = payload_or_creator_id
            contract_data = {
                "title": title,
                "amount": amount,
                "description": description,
                "buyer_id": creator_id if role == "employer" else None,
                "seller_id": creator_id if role == "freelancer" else None,
                "status": "draft",
            }

        buyer_val = contract_data.get("buyer_id") or contract_data.get("employer_id")
        seller_val = contract_data.get("seller_id") or contract_data.get("freelancer_id")

        final_payload = {
            "title": str(contract_data.get("title", "بدون عنوان")),
            "amount": float(contract_data.get("amount", 0)),
            "description": str(contract_data.get("description", "")),
            "deadline": int(contract_data.get("deadline", 1)),
            "category": str(contract_data.get("category", "GEN")),
            "status": str(contract_data.get("status", "draft")),
            "signed_by_second_party": False,  # آیا نفر دوم امضا کرده است؟
            "free_edits_left": int(contract_data.get("free_edits_left", 3)), # ۳ بار ویرایش رایگان پیش‌فرض
            "project_file_id": contract_data.get("project_file_id")
        }

        if buyer_val: final_payload["buyer_id"] = int(buyer_val)
        if seller_val: final_payload["seller_id"] = int(seller_val)
        if contract_data.get("buyer_phone"): final_payload["buyer_phone"] = str(contract_data["buyer_phone"])
        if contract_data.get("seller_phone"): final_payload["seller_phone"] = str(contract_data["seller_phone"])
        if "contract_id" in contract_data: final_payload["contract_id"] = str(contract_data["contract_id"])
        if contract_data.get("milestones"):
            final_payload["milestones"] = contract_data.get("milestones")

        res = supabase.table("contracts").insert(final_payload).execute()
        return res.data[0] if res.data else None

    except Exception as e:
        logger.error(f"خطا در ثبت قرارداد در Supabase: {e}")
        try:
            fallback_payload = {
                "title": str(contract_data.get("title", "معامله جدید")),
                "amount": float(contract_data.get("amount", 0)),
                "description": str(contract_data.get("description", "")),
                "status": "draft",
                "signed_by_second_party": False,
                "free_edits_left": 3
            }
            buyer_id = contract_data.get("buyer_id") or contract_data.get("employer_id")
            seller_id = contract_data.get("seller_id") or contract_data.get("freelancer_id")
            if buyer_id: fallback_payload["buyer_id"] = int(buyer_id)
            if seller_id: fallback_payload["seller_id"] = int(seller_id)
            if "contract_id" in contract_data: fallback_payload["contract_id"] = str(contract_data["contract_id"])

            res_fb = supabase.table("contracts").insert(fallback_payload).execute()
            return res_fb.data[0] if res_fb.data else None
        except Exception as fb_err:
            logger.error(f"خطای فال‌بک در ثبت قرارداد: {fb_err}")
            raise Exception(f"خطای دیتابیس Supabase: {str(e)}")


def get_contract(contract_id: str) -> Optional[Dict[str, Any]]:
    """دریافت اطلاعات کامل یک معامله بر اساس شناسه"""
    if not supabase:
        return None
    try:
        try:
            res = supabase.table("contracts").select("*").eq("contract_id", contract_id).execute()
            if res.data:
                return res.data[0]
        except Exception:
            pass

        res_alt = supabase.table("contracts").select("*").eq("id", contract_id).execute()
        return res_alt.data[0] if res_alt.data else None

    except Exception as e:
        logger.error(f"خطا در دریافت معامله {contract_id}: {e}")
        return None


def update_contract(
    contract_id: str, 
    updates: Union[Dict[str, Any], str], 
    extra_data: Optional[Dict[str, Any]] = None
) -> bool:
    """بروزرسانی داده‌ها یا وضعیت قرارداد"""
    if not supabase:
        return False

    if isinstance(updates, dict):
        payload = updates
    else:
        payload = {"status": updates}
        if extra_data:
            payload.update(extra_data)

    try:
        try:
            res = supabase.table("contracts").update(payload).eq("contract_id", contract_id).execute()
            if res.data: return True
        except Exception:
            pass
            
        res = supabase.table("contracts").update(payload).eq("id", contract_id).execute()
        return True if res.data else False
    except Exception as e:
        logger.error(f"خطا در بروزرسانی قرارداد {contract_id}: {e}")
        return False

update_contract_status = update_contract


def use_free_edit(contract_id: str) -> bool:
    """کاهش تعداد ویرایش‌های مجانی باقی‌مانده برای یک پروژه/قرارداد"""
    contract = get_contract(contract_id)
    if not contract: return False
    
    edits_left = contract.get("free_edits_left", 0)
    if edits_left <= 0:
        return False  # ویرایش مجانی تمام شده است
        
    return update_contract(contract_id, {"free_edits_left": edits_left - 1})


def get_user_contracts(user_id: int) -> List[Dict[str, Any]]:
    """دریافت تمامی معاملات مرتبط با یک کاربر"""
    if not supabase:
        return []
    try:
        res = supabase.table("contracts").select("*").or_(
            f"buyer_id.eq.{user_id},seller_id.eq.{user_id}"
        ).order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"خطا در دریافت معاملات کاربر {user_id}: {e}")
        return []


# ====================================================
# ۴. مدیریت فازهای پروژه (Milestones)
# ====================================================

def create_milestone(contract_id: str, title: str, amount: float) -> Optional[Dict[str, Any]]:
    """ایجاد فاز/مرحله جدید برای قراردادها"""
    if not supabase:
        return None
    try:
        payload = {
            "contract_id": contract_id,
            "title": title,
            "amount": float(amount),
            "status": "pending"
        }
        res = supabase.table("milestones").insert(payload).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"خطا در ایجاد فاز برای معامله {contract_id}: {e}")
        return None


def get_contract_milestones(contract_id: str) -> List[Dict[str, Any]]:
    """دریافت لیست تمامی فازهای یک قرارداد"""
    if not supabase:
        return []
    try:
        res = supabase.table("milestones").select("*").eq("contract_id", contract_id).order("created_at", desc=False).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"خطا در دریافت فازهای قرارداد {contract_id}: {e}")
        return []


def update_milestone_status(milestone_id: str, status: str) -> bool:
    """بروزرسانی وضعیت یک فاز"""
    if not supabase:
        return False
    try:
        res = supabase.table("milestones").update({"status": status}).eq("id", milestone_id).execute()
        return True if res.data else False
    except Exception as e:
        logger.error(f"خطا در تغییر وضعیت فاز {milestone_id}: {e}")
        return False


# ====================================================
# ۵. مدیریت فیش‌های واریزی (Receipts Management)
# ====================================================

def submit_receipt(contract_id: str, user_id: int, photo_file_id: str) -> Optional[Dict[str, Any]]:
    """ثبت فیش جدید از پنل شیشه‌ای کاربر برای بررسی ادمین"""
    if not supabase: return None
    try:
        payload = {
            "contract_id": contract_id,
            "user_id": user_id,
            "photo_file_id": photo_file_id,
            "status": "pending",  # pending, approved, rejected
            "rejection_reason": None
        }
        res = supabase.table("receipts").insert(payload).execute()
        # به‌روزرسانی وضعیت قرارداد به در انتظار پرداخت
        update_contract(contract_id, "Awaiting_Payment")
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"خطا در ثبت فیش برای قرارداد {contract_id}: {e}")
        return None


def review_receipt(receipt_id: str, status: str, rejection_reason: Optional[str] = None) -> bool:
    """تایید یا رد فیش توسط ادمین همراه با دلیل رد"""
    if not supabase: return False
    try:
        payload = {"status": status}
        if rejection_reason:
            payload["rejection_reason"] = rejection_reason
            
        res = supabase.table("receipts").update(payload).eq("id", receipt_id).execute()
        
        # اگر فیش تایید شد، وضعیت قرارداد به حالت امن (Escrow_Locked) تغییر کند
        if status == "approved" and res.data:
            contract_id = res.data[0].get("contract_id")
            update_contract(contract_id, "Escrow_Locked")
            
        return True if res.data else False
    except Exception as e:
        logger.error(f"خطا در بررسی فیش {receipt_id}: {e}")
        return False


# ====================================================
# ۶. تیکت‌ها، اعلام اختلاف و قالب‌های آماده (Templates & Disputes)
# ====================================================

def create_support_ticket(user_id: int, subject: str, message: str) -> bool:
    """ثبت تیکت پشتیبانی جدید"""
    if not supabase:
        return False
    try:
        data = {
            "user_id": user_id,
            "subject": subject,
            "message": message,
            "status": "open"
        }
        supabase.table("support_tickets").insert(data).execute()
        return True
    except Exception as e:
        logger.error(f"خطا در ثبت تیکت پشتیبانی برای کاربر {user_id}: {e}")
        return False


def create_dispute_ticket(contract_id: str, user_id: int, reason: str) -> bool:
    """ثبت تیکت اعلام اختلاف / درخواست داوری برای قرارداد"""
    if not supabase:
        return False
    try:
        data = {
            "contract_id": contract_id,
            "user_id": user_id,
            "reason": reason,
            "status": "open"
        }
        supabase.table("disputes").insert(data).execute()
        update_contract(contract_id, "disputed")
        return True
    except Exception as e:
        logger.error(f"خطا در ایجاد تیکت اختلاف برای قرارداد {contract_id}: {e}")
        return False


def get_contract_templates() -> List[Dict[str, Any]]:
    """دریافت لیست قالب‌های آماده حقوقی برای ایجاد سریع قرارداد"""
    if not supabase: return []
    try:
        res = supabase.table("contract_templates").select("*").execute()
        return res.data or []
    except Exception as e:
        logger.error(f"خطا در دریافت قالب‌های آماده: {e}")
        return []
# ====================================================
# ۷. سیستم گزارش‌گیری، آمار و پنل مدیریت (Admin Analytics)
# ====================================================

def get_platform_analytics() -> Dict[str, Any]:
    """دریافت آمار کلی پلتفرم جهت نمایش در پنل مدیریت/ادمین"""
    if not supabase:
        return {}
    try:
        total_users = supabase.table("users").select("user_id", count="exact").execute().count or 0
        total_contracts = supabase.table("contracts").select("id", count="exact").execute().count or 0
        
        # محاسبه مجموع مبالغ معاملات موفق
        completed_contracts = supabase.table("contracts").select("amount").eq("status", "completed").execute()
        total_volume = sum([float(c.get("amount", 0)) for c in (completed_contracts.data or [])])
        
        # تعداد اختلافات فعال
        active_disputes = supabase.table("disputes").select("id", count="exact").eq("status", "open").execute().count or 0

        return {
            "total_users": total_users,
            "total_contracts": total_contracts,
            "total_volume": total_volume,
            "active_disputes": active_disputes
        }
    except Exception as e:
        logger.error(f"خطا در دریافت آمار کلی پلتفرم: {e}")
        return {}


def log_activity(user_id: int, action: str, details: Optional[Dict[str, Any]] = None) -> bool:
    """ثبت ردپای امنیتی و لاگ فعالیت‌های حساس (Audit Log)"""
    if not supabase:
        return False
    try:
        payload = {
            "user_id": user_id,
            "action": action,
            "details": details or {}
        }
        supabase.table("activity_logs").insert(payload).execute()
        return True
    except Exception as e:
        logger.error(f"خطا در ثبت لاگ فعالیت برای کاربر {user_id}: {e}")
        return False


# ====================================================
# ۸. سیستم نظرات، امتیازدهی و ارزیابی (Ratings & Reviews)
# ====================================================

def add_user_rating(
    contract_id: str, 
    from_user_id: int, 
    target_user_id: int, 
    rating: int, 
    comment: Optional[str] = ""
) -> bool:
    """ثبت امتیاز (۱ تا ۵) و نظر برای طرف مقابل معامله پس از اتمام پروژه"""
    if not supabase or not (1 <= rating <= 5):
        return False
    try:
        payload = {
            "contract_id": contract_id,
            "from_user_id": from_user_id,
            "target_user_id": target_user_id,
            "rating": rating,
            "comment": comment
        }
        supabase.table("ratings").insert(payload).execute()
        
        # بروزرسانی میانگین امتیاز کاربر مقصد
        _recalculate_user_rating(target_user_id)
        return True
    except Exception as e:
        logger.error(f"خطا در ثبت امتیاز توسط {from_user_id} برای {target_user_id}: {e}")
        return False


def _recalculate_user_rating(user_id: int) -> None:
    """محاسبه مجدد میانگین امتیاز کاربر و ذخیره آن در جدول کاربران"""
    try:
        res = supabase.table("ratings").select("rating").eq("target_user_id", user_id).execute()
        ratings = res.data or []
        if ratings:
            avg_rating = sum([r["rating"] for r in ratings]) / len(ratings)
            supabase.table("users").update({"avg_rating": round(avg_rating, 2)}).eq("user_id", user_id).execute()
    except Exception as e:
        logger.error(f"خطا در محاسبه مجدد امتیاز کاربر {user_id}: {e}")


def get_user_reviews(user_id: int) -> List[Dict[str, Any]]:
    """دریافت نظرات و امتیازات یک کاربر"""
    if not supabase:
        return []
    try:
        res = supabase.table("ratings").select("*").eq("target_user_id", user_id).order("created_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"خطا در دریافت نظرات کاربر {user_id}: {e}")
        return []


# ====================================================
# ۹. سیستم زیرمجموعه‌گیری و سود ارجاع (Referral & Affiliate)
# ====================================================

def process_referral_reward(new_user_id: int, transaction_amount: float, reward_percent: float = 0.05) -> bool:
    """محاسبه و پاداش‌دهی به معرفی‌کننده (Referrer) پس از اولین معامله موفق"""
    user = get_user(new_user_id)
    if not user or not user.get("referrer_id"):
        return False

    referrer_id = user["referrer_id"]
    reward_amount = transaction_amount * reward_percent

    if reward_amount > 0:
        description = f"پاداش معرف برای معامله کاربر {new_user_id}"
        return update_wallet_balance(referrer_id, reward_amount, transaction_type="referral_bonus", description=description)
    
    return False


def get_user_referrals(user_id: int) -> List[Dict[str, Any]]:
    """دریافت لیست زیرمجموعه‌های مستقیم یک کاربر"""
    if not supabase:
        return []
    try:
        res = supabase.table("users").select("user_id, first_name, username, created_at").eq("referrer_id", user_id).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"خطا در دریافت لیست زیرمجموعه‌های کاربر {user_id}: {e}")
        return []


# ====================================================
# ۱۰. گزارشات مالی و تراکنش‌ها (Transactions & Logs)
# ====================================================

def get_user_transactions(user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """دریافت تاریخچه تراکنش‌های کیف پول کاربر"""
    if not supabase:
        return []
    try:
        res = supabase.table("transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"خطا در دریافت تراکنش‌های کاربر {user_id}: {e}")
        return []
