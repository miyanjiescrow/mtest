import io
import os
import re
import logging
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import config
import utils

logger = logging.getLogger("Miyanji_PDF")

# ====================================================
# ۰. بارگذاری فونت فارسی (Vazirmatn) و ابزار شکل‌دهی راست‌به‌چپ
# ====================================================
# نکته نصب: چون در محیط ساخت این پاسخ دسترسی شبکه نداشتم، باید خودتان
# فایل فونت را یک‌بار در ریشه پروژه، داخل پوشه fonts/ قرار دهید:
#
#   mkdir -p fonts
#   wget https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Regular.ttf -O fonts/Vazirmatn-Regular.ttf
#   wget https://github.com/rastikerdar/vazirmatn/raw/master/fonts/ttf/Vazirmatn-Bold.ttf -O fonts/Vazirmatn-Bold.ttf
#
# اگر این فایل‌ها نباشند، PDF همچنان تولید می‌شود ولی حروف فارسی به‌درستی
# نمایش داده نخواهند شد (فونت پیش‌فرض Helvetica از یونیکد فارسی پشتیبانی نمی‌کند).

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONT_REGULAR_PATH = os.path.join(FONT_DIR, "Vazirmatn-Regular.ttf")
FONT_BOLD_PATH = os.path.join(FONT_DIR, "Vazirmatn-Bold.ttf")

PERSIAN_FONT_REGULAR = "Helvetica"
PERSIAN_FONT_BOLD = "Helvetica-Bold"
PERSIAN_FONT_LOADED = False

try:
    if os.path.exists(FONT_REGULAR_PATH):
        pdfmetrics.registerFont(TTFont("Vazirmatn", FONT_REGULAR_PATH))
        PERSIAN_FONT_REGULAR = "Vazirmatn"
        if os.path.exists(FONT_BOLD_PATH):
            pdfmetrics.registerFont(TTFont("Vazirmatn-Bold", FONT_BOLD_PATH))
            PERSIAN_FONT_BOLD = "Vazirmatn-Bold"
        else:
            PERSIAN_FONT_BOLD = "Vazirmatn"
        PERSIAN_FONT_LOADED = True
        logger.info("فونت فارسی Vazirmatn با موفقیت بارگذاری شد.")
    else:
        logger.warning(
            "فونت فارسی در fonts/Vazirmatn-Regular.ttf یافت نشد. "
            "متن فارسی سند PDF به‌درستی نمایش داده نخواهد شد."
        )
except Exception as e:
    logger.error(f"خطا در بارگذاری فونت فارسی: {e}")

# ابزار شکل‌دهی حروف فارسی/عربی (اتصال حروف) و چیدمان راست‌به‌چپ
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    RESHAPE_AVAILABLE = True
except Exception:
    RESHAPE_AVAILABLE = False
    logger.warning(
        "کتابخانه‌های arabic_reshaper / python-bidi نصب نیستند. "
        "به requirements.txt اضافه و نصب کنید تا متن فارسی درست نمایش داده شود."
    )


def rtl(text) -> str:
    """آماده‌سازی متن فارسی جهت نمایش صحیح (اتصال حروف + راست‌به‌چپ) در ReportLab"""
    if text is None:
        return ""
    text = str(text)
    if not RESHAPE_AVAILABLE:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text


def strip_markdown_bold(text: str) -> str:
    """حذف نشانه‌های ** از متون کپی‌شده از utils.py (چون این‌ها برای تلگرام نوشته شده‌اند نه PDF)"""
    if not text:
        return ""
    return re.sub(r"\*\*(.*?)\*\*", r"\1", text)


class NumberedCanvas(canvas.Canvas):
    """کلاس سفارشی جهت درج شماره صفحه، کادر تزئینی و پاورقی رسمی می‌انجی"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()

        # رسم کادر تزئینی دور صفحه
        self.setStrokeColor(colors.HexColor("#1e293b"))
        self.setLineWidth(1)
        self.rect(20, 20, 555, 802)

        # درج پاورقی رسمی (فارسی)
        self.setFont(PERSIAN_FONT_REGULAR, 9)
        self.setFillColor(colors.HexColor("#64748b"))
        footer_text = rtl(f"سامانه امانی می‌انجی  |  صفحه {self._pageNumber} از {page_count}")
        self.drawCentredString(297, 30, footer_text)

        self.restoreState()


def build_contract_pdf(contract_data: dict, buyer_user: dict = None, seller_user: dict = None) -> io.BytesIO:
    """تولید سند رسمی PDF فارسی معامله همراه با اطلاعات طرفین، مراحل پرداخت و بندهای حقوقی اختصاصی حوزه"""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=35,
        rightMargin=35,
        topMargin=40,
        bottomMargin=40
    )

    # -------- استایل‌های پایه (راست‌چین، فونت فارسی) --------
    title_style = ParagraphStyle(
        'DocTitle',
        fontName=PERSIAN_FONT_BOLD,
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a")
    )
    sub_title_style = ParagraphStyle(
        'DocSub',
        fontName=PERSIAN_FONT_REGULAR,
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748b")
    )
    body_style = ParagraphStyle(
        'DocBody',
        fontName=PERSIAN_FONT_REGULAR,
        fontSize=10,
        leading=16,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#334155")
    )
    body_bold_style = ParagraphStyle(
        'DocBodyBold',
        fontName=PERSIAN_FONT_BOLD,
        fontSize=10,
        leading=16,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#0f172a")
    )
    head_style = ParagraphStyle(
        'DocHead',
        fontName=PERSIAN_FONT_BOLD,
        fontSize=11.5,
        leading=16,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#0f172a")
    )
    legal_style = ParagraphStyle(
        'DocLegal',
        fontName=PERSIAN_FONT_REGULAR,
        fontSize=9,
        leading=15,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#1e293b")
    )
    footer_note_style = ParagraphStyle(
        'DocFooterNote',
        fontName=PERSIAN_FONT_REGULAR,
        fontSize=8,
        leading=13,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#94a3b8")
    )

    def P(text, style=body_style):
        return Paragraph(rtl(text), style)

    elements = []

    # -------- استخراج ایمن داده‌های قرارداد --------
    deal_keys = getattr(config, 'DEAL_KEYS', {})

    c_id = contract_data.get("contract_id") or contract_data.get(deal_keys.get("ID", "id"), "---")
    c_title = contract_data.get("title") or contract_data.get(deal_keys.get("TITLE", "title"), "بدون عنوان")
    c_amount = float(contract_data.get("amount") or contract_data.get(deal_keys.get("AMOUNT", "amount"), 0))
    c_status = contract_data.get("status") or contract_data.get(deal_keys.get("STATUS", "status"), "نامشخص")
    c_deadline = contract_data.get("deadline", 1)
    raw_date = contract_data.get("created_at", "")
    c_date = utils.convert_to_jalali(str(raw_date)) if raw_date else "ثبت نشده"
    c_category = contract_data.get("category", "GEN")
    c_desc = contract_data.get("description") or "توضیحات و شرح تعهدات ثبت نشده است."
    milestones = contract_data.get("milestones") or []

    comm, net = utils.calculate_commission(c_amount)

    # اگر اطلاعات کاربران پاس داده نشده باشد، خودمان از دیتابیس واکشی می‌کنیم
    if buyer_user is None or seller_user is None:
        try:
            import database as db
            buyer_id = contract_data.get("buyer_id") or contract_data.get("employer_id")
            seller_id = contract_data.get("seller_id") or contract_data.get("freelancer_id")
            if buyer_user is None and buyer_id:
                buyer_user = db.get_user(buyer_id)
            if seller_user is None and seller_id:
                seller_user = db.get_user(seller_id)
        except Exception as e:
            logger.warning(f"واکشی اطلاعات طرفین معامله ناموفق بود: {e}")

    buyer_name = (buyer_user.get("first_name") if buyer_user else None) or "ثبت نشده"
    buyer_phone = contract_data.get("buyer_phone") or (buyer_user.get("phone_number") if buyer_user else None) or "ثبت نشده"
    seller_name = (seller_user.get("first_name") if seller_user else None) or "ثبت نشده"
    seller_phone = contract_data.get("seller_phone") or (seller_user.get("phone_number") if seller_user else None) or "ثبت نشده"

    status_fa_map = {
        "pending_approval": "در انتظار امضا",
        "bargaining": "در حال چانه‌زنی",
        "active": "در حال اجرا",
        "delivered": "تحویل داده‌شده - در انتظار تایید نهایی",
        "completed": "تکمیل‌شده و تسویه‌شده",
        "cancelled": "لغوشده",
        "disputed": "در حال داوری",
        "in_dispute": "در حال داوری",
        "resolved_employer": "مختومه - رای به نفع کارفرما",
        "resolved_freelancer": "مختومه - رای به نفع مجری",
        "draft": "پیش‌نویس",
    }
    c_status_fa = status_fa_map.get(str(c_status), str(c_status))

    # ۱. عنوان اصلی سند
    elements.append(P("قرارداد امانی و واسطه‌گری هوشمند می‌انجی", title_style))
    elements.append(P("سند رسمی و لازم‌الاجرای معامله دیجیتال", sub_title_style))
    elements.append(Spacer(1, 15))

    # ۲. جدول مشخصات اصلی معامله
    main_rows = [
        [P(str(c_id), body_style), P("شناسه بایگانی قرارداد:", body_bold_style)],
        [P(str(c_title), body_style), P("عنوان معامله:", body_bold_style)],
        [P(str(c_category), body_style), P("دسته‌بندی:", body_bold_style)],
        [P(utils.format_currency(c_amount), body_style), P("مبلغ کل معامله:", body_bold_style)],
        [P(utils.format_currency(comm), body_style), P(f"کارمزد سامانه ({getattr(config, 'COMMISSION_PERCENT', 2.5)}%):", body_bold_style)],
        [P(utils.format_currency(net), body_style), P("مبلغ خالص دریافتی مجری:", body_bold_style)],
        [P(f"{c_deadline} روز", body_style), P("مهلت تحویل پروژه:", body_bold_style)],
        [P(c_status_fa, body_style), P("وضعیت فعلی:", body_bold_style)],
        [P(str(c_date), body_style), P("تاریخ ثبت:", body_bold_style)],
    ]
    t = Table(main_rows, colWidths=[330, 190])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0, 0), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 12))

    # ۳. جدول اطلاعات طرفین معامله
    elements.append(P("مشخصات طرفین معامله:", head_style))
    elements.append(Spacer(1, 4))
    parties_rows = [
        [P("کارفرما (خریدار)", body_bold_style), P("مجری (فروشنده)", body_bold_style)],
        [P(buyer_name, body_style), P(seller_name, body_style)],
        [P(buyer_phone, body_style), P(seller_phone, body_style)],
    ]
    pt = Table(parties_rows, colWidths=[260, 260])
    pt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(pt)
    elements.append(Spacer(1, 12))

    # ۴. مراحل پرداخت و آزادسازی امانی (در صورت وجود)
    if milestones:
        elements.append(P("جدول مراحل پرداخت و آزادسازی امانی:", head_style))
        elements.append(Spacer(1, 4))

        m_table_data = [[
            P("وضعیت", body_bold_style),
            P("مبلغ", body_bold_style),
            P("عنوان مرحله", body_bold_style),
            P("#", body_bold_style),
        ]]
        for idx, m in enumerate(milestones, 1):
            m_amt = float(m.get("amount", 0))
            m_st = "آزاد شده ✅" if m.get("status") == "released" else "بلوکه‌شده 🔒"
            m_table_data.append([
                P(m_st, body_style),
                P(utils.format_currency(m_amt), body_style),
                P(str(m.get("title", "")), body_style),
                P(str(idx), body_style),
            ])

        mt = Table(m_table_data, colWidths=[130, 130, 190, 40])
        mt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(mt)
        elements.append(Spacer(1, 12))

    # ۵. شرح تعهدات و توضیحات پروژه
    elements.append(P("شرح تعهدات و توضیحات پروژه:", head_style))
    elements.append(Spacer(1, 4))
    elements.append(P(c_desc, body_style))
    elements.append(Spacer(1, 12))

    # ۶. بندهای حقوقی اختصاصی حوزه کاری (همان متن استفاده‌شده در پیش‌نمایش تلگرام)
    cat_terms_raw = utils.CATEGORY_LEGAL_CLAUSES.get(c_category, utils.CATEGORY_LEGAL_CLAUSES["GEN"])
    cat_terms_clean = strip_markdown_bold(cat_terms_raw)
    for line in cat_terms_clean.split("\n"):
        if line.strip():
            elements.append(P(line.strip(), legal_style))
    elements.append(Spacer(1, 12))

    # ۷. بند قانونی، امانت‌داری و داوری آنلاین
    elements.append(P("شرایط واسطه‌گری، امانت‌داری و داوری آنلاین می‌انجی:", head_style))
    elements.append(Spacer(1, 4))
    legal_lines = [
        "۱. تضمین امن وجوه (Escrow): کلیه مبالغ تا زمان تایید تحویل توسط کارفرما یا صدور رای داوری، در حساب امانت واسط می‌انجی بلوکه می‌ماند.",
        "۲. استناد قانونی: این سند طبق ماده ۱۰ قانون مدنی و مواد ۶، ۷ و ۱۲ قانون تجارت الکترونیک، یک سند الکترونیکی رسمی، معتبر و غیرقابل انکار است.",
        "۳. شرط داوری: پلتفرم می‌انجی بر اساس ماده ۴۵۵ آیین دادرسی مدنی به عنوان داور مرضی‌الطرفین تعیین شده و رای آن در صورت بروز اختلاف، قطعی و لازم‌الاجرا خواهد بود.",
    ]
    for line in legal_lines:
        elements.append(P(line, legal_style))
    elements.append(Spacer(1, 10))

    notice_text = (
        "توضیح: این سند نمایانگر یک توافق دیجیتال لازم‌الاجرا تحت شرایط پلتفرم امانی می‌انجی و ماده ۱۰ "
        "قانون مدنی است. شناسه بایگانی فوق، هویت و رضایت طرفین را در سامانه تایید می‌کند."
    )
    elements.append(P(notice_text, footer_note_style))

    # ساخت سند نهایی
    try:
        doc.build(elements, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer
    except Exception as e:
        logger.error(f"خطا در تولید فایل PDF برای قرارداد {c_id}: {e}")
        buffer.seek(0)
        return buffer
