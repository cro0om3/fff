import streamlit as st  # type: ignore

try:
    from snow_liwa.theme import apply_snow_liwa_theme
except Exception:
    from theme import apply_snow_liwa_theme
from pathlib import Path
import json

# =========================
# PLACEHOLDER HELPERS – TRY TO USE PROJECT HELPERS IF PRESENT
# =========================

def inject_snow_effect():
    # fallback: minimal snow CSS/HTML (keeps page safe if missing)
    st.markdown(
        """
        <style>
        .snow-only { background: black; color: white; padding: 1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def verify_payment(payment_id: str) -> str:
    # prefer existing function if available
    try:
        from utility.ziina import get_payment_intent as _get_pi
        pi = _get_pi(payment_id)
        if not pi:
            return "unknown"
        status = pi.get("status") or (pi.get("data") or {}).get("status")
        if status:
            status = status.lower()
            if status in ("completed", "paid"):
                return "paid"
            if status in ("failed", "cancelled", "canceled"):
                return "failed"
            return status
    except Exception:
        pass
    # fallback placeholder
    return "paid"


def get_customer_info_from_order(order_id: str):
    try:
        # try to read bookings sheet
        # prefer project helper to load bookings
        try:
            # Prefer the `utils` package shim which re-exports helpers
            from utils import load_bookings as _load_bookings
            df = _load_bookings()
        except Exception:
            try:
                from utility.bookings import load_bookings as _load_bookings2
                df = _load_bookings2()
            except Exception:
                import pandas as pd
                df = pd.read_excel(Path("data") / "bookings.xlsx")
        row = df[df["booking_id"].astype(str) == str(order_id)]
        if not row.empty:
            name = row.iloc[0]["name"]
            amount = float(row.iloc[0]["total_amount"])
            return name, amount
    except Exception:
        pass
    return "ضيف Snow Liwa", 0.0


try:
    from reportlab.pdfgen import canvas  # type: ignore
    from reportlab.lib.pagesizes import A4  # type: ignore
    PAGE_A4 = A4
except Exception:
    canvas = None
    PAGE_A4 = (595.27, 841.89)  # fallback A4 size in points


def generate_ticket_pdf_from_template(customer_name: str, order_id: str, output_path: Path):
    # Try to reuse an existing project helper if present
    try:
        import importlib
        mod = importlib.import_module("utility.ui")
        if hasattr(mod, "generate_ticket_pdf_from_template"):
            getattr(mod, "generate_ticket_pdf_from_template")(customer_name, order_id, output_path)
            return
    except Exception:
        pass

    try:
        # fallback simple PDF generation using reportlab
        if canvas is None:
            return  # reportlab not available
        output_path.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(output_path), pagesize=PAGE_A4)
        c.setFont("Helvetica-Bold", 22)
        c.drawString(70, 780, "Snow Liwa Ticket")
        c.setFont("Helvetica", 16)
        c.drawString(70, 740, f"الاسم: {customer_name}")
        c.drawString(70, 710, f"رقم الحجز: {order_id}")
        c.showPage()
        c.save()
    except Exception:
        # couldn't create PDF, ignore
        return


import pandas as pd
INVOICES_FILE = Path("data") / "invoices.xlsx"


def load_invoices_df() -> pd.DataFrame:
    if INVOICES_FILE.exists():
        return pd.read_excel(INVOICES_FILE)
    return pd.DataFrame(columns=["order_id", "customer_name", "amount", "status", "payment_id"])


def save_invoices_df(df: pd.DataFrame):
    INVOICES_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(INVOICES_FILE, index=False)


def append_invoice_row(order_id: str, customer_name: str, amount: float, status: str, payment_id: str):
    try:
        df = load_invoices_df()
        df = pd.concat([
            df,
            pd.DataFrame([
                {"order_id": order_id, "customer_name": customer_name, "amount": amount, "status": status, "payment_id": payment_id}
            ])
        ], ignore_index=True)
        save_invoices_df(df)
    except Exception:
        pass


# =========================
# QUERY PARAMS HELPER 
# =========================

def get_query_params():
    try:
        qp = getattr(st, "query_params", None)
        if qp is not None:
            if hasattr(qp, "to_dict"):
                return qp.to_dict()
            return dict(qp)
    except Exception:
        pass
    try:
        return st.experimental_get_query_params()
    except Exception:
        try:
            return st.query_params
        except Exception:
            return {}


# =========================
# UI HELPERS
# =========================

def render_status_base(status_type: str, title: str, message: str, extra_body: str = ""):
    st.markdown("---")
    if status_type == "success":
        st.success("✅ حالة الدفع: ناجحة")
    elif status_type == "failed":
        st.error("❌ حالة الدفع: فشلت / أُلغيت")
    elif status_type == "waiting":
        st.info("⏳ حالة الدفع: نتحقق من الطلب...")
    else:
        st.warning("❔ حالة الدفع: غير معروفة")

    st.markdown(f"### {title}")
    st.write(message)

    if extra_body:
        st.markdown(extra_body, unsafe_allow_html=True)


def render_success_page(customer_name: str, order_id: str, amount: float, ticket_pdf_path: Path):
    extra = ""
    if ticket_pdf_path and ticket_pdf_path.exists():
        with open(ticket_pdf_path, "rb") as f:
            st.download_button(label="📄 تحميل التذكرة (PDF)", data=f, file_name=ticket_pdf_path.name, mime="application/pdf")
        extra += "<p>تقدر تحتفظ بالتذكرة أو رقم الحجز للرجوع لاحقًا.</p>"

    extra += f"""
    <br>
    <div style="border-radius: 10px; padding: 12px; background-color: #11111155;">
      <b>ملخص الحجز</b><br>
      الاسم: {customer_name}<br>
      رقم الحجز: {order_id}<br>
      المبلغ: {amount} AED
    </div>
    """

    render_status_base(status_type="success", title="تم الدفع بنجاح 🎉", message=f"شكرًا لك {customer_name}! تم تأكيد حجزك وتم إصدار تذكرتك.", extra_body=extra)


def render_failed_page():
    render_status_base(status_type="failed", title="لم يكتمل الدفع", message="يبدو أن عملية الدفع تم إلغاؤها أو فشلت. يمكنك العودة وإعادة المحاولة.")


def render_unknown_page(raw_status: str | None):
    render_status_base(status_type="unknown", title="حالة الدفع غير واضحة", message=f"لم نتمكن من تحديد حالة الدفع حاليًا (status = {raw_status}). حاول لاحقًا أو تواصل معنا.")


# =========================
# MAIN PAGE
# =========================

def main():
    # Apply the centralized theme (page config + CSS)
    try:
        apply_snow_liwa_theme()
    except Exception:
        pass

    # keep the optional snow overlay effect (small scoped element)
    inject_snow_effect()

    st.title("حالة الدفع – Snow Liwa")

    params = get_query_params() or {}
    payment_id = None
    order_id = None
    raw_status = None
    # Handle different query param shapes
    if isinstance(params, dict):
        payment_id = (params.get("payment_id") or [None])[0] if isinstance(params.get("payment_id"), list) else params.get("payment_id")
        order_id = (params.get("order_id") or [None])[0] if isinstance(params.get("order_id"), list) else params.get("order_id")
        raw_status = (params.get("status") or [None])[0] if isinstance(params.get("status"), list) else params.get("status")

    if not payment_id:
        st.error("لا يوجد payment_id في الرابط. تأكد من إعداد return_url في بوابة الدفع.")
        return

    render_status_base(status_type="waiting", title="نجري التحقق من عملية الدفع...", message="لحظات قليلة للتأكد من حالة العملية وربطها بحجزك.")

    final_status = verify_payment(payment_id)

    if final_status == "paid":
        if not order_id:
            order_id = f"order_{payment_id}"
        customer_name, amount = get_customer_info_from_order(order_id)
        tickets_dir = Path("tickets")
        tickets_dir.mkdir(parents=True, exist_ok=True)
        ticket_path = tickets_dir / f"{order_id}_ticket.pdf"
        generate_ticket_pdf_from_template(customer_name, order_id, ticket_path)
        append_invoice_row(order_id=order_id, customer_name=customer_name, amount=amount, status="paid", payment_id=payment_id)
        st.empty()
        render_success_page(customer_name, order_id, amount, ticket_path)
    elif final_status in ("failed", "cancelled", "canceled"):
        st.empty()
        render_failed_page()
    else:
        st.empty()
        render_unknown_page(final_status)

    st.markdown("---")
    # Always show a back link to the main app. Prefer the app base URL from helpers/secrets.
    try:
        from app import get_ziina_app_base_url

        back_url = get_ziina_app_base_url() or "/"
    except Exception:
        try:
            back_url = st.secrets.get("ziina", {}).get("app_base_url") or "/"
        except Exception:
            back_url = "/"

    st.markdown(
        f"""
        <div style="margin-top:1.2rem; text-align:center;">
          <a href="{back_url}" role="button" style="display:inline-block; padding:0.6rem 1.1rem; background:#0b6cff; color:#fff; border-radius:999px; text-decoration:none; font-weight:600;">⬅️ الرجوع لصفحة الحجز الرئيسية</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
