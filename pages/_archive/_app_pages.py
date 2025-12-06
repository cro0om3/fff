import streamlit as st
from datetime import datetime
from pathlib import Path
import urllib.parse
import os
import pandas as pd
from ..utils.bookings import load_bookings, save_bookings, get_next_booking_id, ensure_bookings_file_exists
from ..utils.ui import build_ticket_text, inject_base_css, encode_image_base64
from ..utils.ziina import has_ziina_configured, get_payment_intent, create_payment_intent
from ..utils.io import load_settings


def render_customer_info_panel():
    st.markdown('<div class="section-card" style="margin-top:1.5rem;">', unsafe_allow_html=True)
    tabs = st.tabs(["من نحن؟", "موقعنا", "سياسة الحجز", "الأسئلة الشائعة"])
    with tabs[0]:
        st.markdown(
            '<div style="direction:rtl; text-align:right; font-size:1.05rem; line-height:1.8;">'
            'مشروع شبابي إماراتي من قلب منطقة الظفرة.<br>'
            'يقدم تجربة شتوية فريدة تجمع بين أجواء ليوا الساحرة ولمسات من البساطة والجمال.'
            '<br><br># TODO: insert FHD\'s final about-us text here'
            '</div>',
            unsafe_allow_html=True,
        )
    with tabs[1]:
        st.markdown(
            '<div style="direction:rtl; text-align:right; font-size:1.05rem; line-height:1.8;">'
            'سيتم مشاركة موقع Snow Liwa بالتفصيل بعد تأكيد الحجز عبر واتساب. 🗺️📍'
            '</div>',
            unsafe_allow_html=True,
        )
    with tabs[2]:
        st.markdown(
            (
                '<div style="direction:rtl; text-align:right; font-size:1.05rem; line-height:1.8;">'
                '<ul style="padding-right:1.2em;">'
                '<li>التذكرة صالحة للاستخدام في اليوم المحدد فقط.</li>'
                '<li>بعد تأكيد الحجز لا يمكن استرجاع المبلغ.</li>'
                '<li>يمكنكم تعديل وقت الزيارة بالتواصل معنا قبل 24 ساعة.</li>'
                '</ul>'
                '</div>'
            ),
            unsafe_allow_html=True,
        )
    with tabs[3]:
        st.markdown(
            '<div style="direction:rtl; text-align:right; font-size:1.05rem; line-height:1.8;">'
            '<b>هل يمكنني استرجاع المبلغ بعد الحجز؟</b><br>لا، بعد تأكيد الحجز لا يمكن استرجاع المبلغ.<br><br>'
            '<b>كيف أحصل على موقع Snow Liwa؟</b><br>سيتم إرسال الموقع عبر واتساب بعد تأكيد الحجز.<br><br>'
            '<b>هل يمكن تعديل وقت الزيارة؟</b><br>نعم، بالتواصل معنا قبل 24 ساعة من الموعد المحدد.<br><br>'
            '<b>هل التذكرة تشمل جميع الأنشطة؟</b><br>نعم، التذكرة تشمل جميع الأنشطة المتوفرة في اليوم المحدد.'
            '</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


def render_welcome():
    settings = load_settings()
    TICKET_PRICE = settings.get('ticket_price', 3)
    inject_base_css(st)

    # --- Section anchors for scroll/jump ---
    booking_anchor = st.empty()
    about_anchor = st.empty()

    # --- HERO LAYOUT ---
    col1, col2 = st.columns([1.15, 1], gap="large")
    with col1:
        st.markdown(f"""
        <div class='hero-content' style='align-items: flex-start; text-align: right;'>
            <div style='margin-bottom: 0.5rem;'></div>
            <div class='hero-title' style='font-size:3.2rem; letter-spacing:0.18em; color:var(--accent-blue); font-weight:800;'>SNOW LIWA</div>
            <div style='font-size:1.6rem; color:#18324a; font-weight:600; margin-bottom:0.2rem;'>تجربة شتوية في قلب الظفرة</div>
            <div class='arabic' style='margin-bottom:1.2rem; font-size:1.1rem; max-width:420px;'>
                مشروع شبابي إماراتي يقدم أجواء ليوا الشتوية للعائلات والشباب، من لعب الثلج إلى الشوكولاتة الساخنة.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # --- CTAs ---
        cta1, cta2 = st.columns([1.2, 1.1], gap="small")
        with cta1:
            if st.button("احجز تذكرتك الآن", key="cta_book", use_container_width=True):
                st.session_state["scroll_to_booking"] = True
                try:
                    st.rerun()
                except Exception:
                    return
        with cta2:
            if st.button("تعرف علينا أكثر", key="cta_about", use_container_width=True):
                st.session_state["scroll_to_about"] = True
                try:
                    st.rerun()
                except Exception:
                    return

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        # --- ICE SKATING / SLADDING pills ---
        pill1, pill2 = st.columns([1, 1], gap="small")
        with pill1:
            if st.button("ICE SKATING", key="ice_skating_pill", use_container_width=True):
                st.session_state["selected_activity"] = "ice_skating"
        with pill2:
            if st.button("SLADDING", key="sladding_pill", use_container_width=True):
                st.session_state["selected_activity"] = "sladding"

    with col2:
        # Custom snow experience cards: Arabic and English
        st.markdown("""
                <style>
                .snow-experience-card {
                        width: 100%;
                        background: radial-gradient(circle at top, #FFFFFF 0%, #F6FBFF 55%, #EDF6FF 100%);
                        border-radius: 32px;
                        padding: 2.4rem 2.2rem 2.6rem;
                        box-shadow: 0 20px 45px rgba(0, 72, 140, 0.10);
                        box-sizing: border-box;
                        text-align: center;
                        position: relative;
                        overflow: hidden;
                        margin-bottom: 1.2rem;
                }
                .snow-experience-card.arabic { direction: rtl; }
                .snow-experience-card.english { direction: ltr; }
                .snow-experience-small-title {
                        position: absolute;
                        top: 1.6rem;
                        left: 2.2rem;
                        font-size: 14px;
                        font-weight: 700;
                        letter-spacing: 0.25em;
                        text-transform: uppercase;
                        color: #76B4FF;
                        direction: ltr;
                }
                .snow-experience-pill {
                        display: inline-flex;
                        align-items: center;
                        gap: 0.5rem;
                        padding: 0.55rem 1.3rem;
                        border-radius: 999px;
                        border: 1px solid #BEE4FF;
                        background: rgba(255, 255, 255, 0.95);
                        box-shadow: 0 10px 25px rgba(0, 80, 156, 0.09);
                        font-size: 18px;
                        font-weight: 700;
                        color: #27A4FF;
                        margin-bottom: 1.4rem;
                        margin-top: 0.4rem;
                }
                .snow-experience-pill-icon {
                        font-size: 20px;
                }
                .snow-experience-text {
                        max-width: 520px;
                        margin: 0 auto;
                        font-size: 16px;
                        line-height: 1.9;
                        color: #234266;
                        font-weight: 500;
                }
                </style>
                <div class="snow-experience-card arabic">
                    <div class="snow-experience-small-title">
                        SNOW LIWA
                    </div>
                    <div style="margin-top: 1.2rem;"></div>
                    <div class="snow-experience-pill">
                        <span class="snow-experience-pill-icon">❄️</span>
                        <span>تجربة الثلج</span>
                    </div>
                    <p class="snow-experience-text">
                        في مبادرةٍ فريدةٍ تمنح الزوّار أجواءً ثلجية ممتعة وتجربةً استثنائية لا تُنسى،
                        يمكنكم الاستمتاع بمشاهدة تساقُط الثلج، وتجربة مشروب الشوكولاتة الساخنة،
                        مع ضيافةٍ راقية تشمل الفراولة ونافورة الشوكولاتة.
                        تذكرة الدخول فقط بـ ١٧٥ درهمًا.
                    </p>
                </div>
                <div class="snow-experience-card english">
                    <div class="snow-experience-small-title">
                        SNOW LIWA
                    </div>
                    <div style="margin-top: 1.2rem;"></div>
                    <div class="snow-experience-pill">
                        <span class="snow-experience-pill-icon">❄️</span>
                        <span>Snow Experience</span>
                    </div>
                    <p class="snow-experience-text">
                        In a unique initiative that gives visitors a pleasant snowy atmosphere and an exceptional and unforgettable experience, you can enjoy watching the snowfall, and try a hot chocolate drink, with high-end hospitality including strawberries and a chocolate fountain. The entrance ticket is only AED 175.
                    </p>
                </div>
                """, unsafe_allow_html=True)

    # --- SCROLL/JUMP LOGIC ---
    if st.session_state.get("scroll_to_booking"):
        st.session_state.pop("scroll_to_booking")
        booking_anchor.empty()
        st.markdown("<div id='booking_section'></div>", unsafe_allow_html=True)
        st.write("")  # force scroll
    if st.session_state.get("scroll_to_about"):
        st.session_state.pop("scroll_to_about")
        about_anchor.empty()
        st.markdown("<div id='about_section'></div>", unsafe_allow_html=True)
        st.write("")

    # --- BOOKING SECTION (anchor for scroll) ---
    booking_anchor.markdown('<div id="booking_section"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('### 🎟️ Book your ticket')
    st.write(f'Entrance ticket: **{TICKET_PRICE} AED** per person.')

    # Pre-select activity if chosen in hero
    selected_activity = st.session_state.get("selected_activity")
    activity_options = ["ice_skating", "sladding"]
    activity_labels = {"ice_skating": "Ice Skating", "sladding": "Sladding"}
    if selected_activity in activity_options:
        st.info(f"تم اختيار النشاط: {activity_labels[selected_activity]}")

    # Load poster path from settings
    poster_path = settings.get("ticket_poster_path", "assets/ticket_poster.png")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown('<div class="ticket-card">', unsafe_allow_html=True)
        with st.form("booking_form"):
            name = st.text_input("Name / الاسم الكامل")
            phone = st.text_input("Phone / رقم الهاتف (واتساب)")
            tickets = st.number_input("Number of tickets / عدد التذاكر", 1, 20, 1)
            notes = st.text_area("Notes (optional) / ملاحظات اختيارية", height=70)
            submitted = st.form_submit_button("Confirm booking / إصدار التذكرة")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="ticket-card ticket-card-poster">', unsafe_allow_html=True)
        if poster_path and os.path.exists(poster_path):
            try:
                img_b64 = encode_image_base64(Path(poster_path))
                if img_b64:
                    st.markdown(
                        f'''
                        <div class="ticket-poster-wrapper">
                            <img src="data:image/png;base64,{img_b64}" class="ticket-poster-img" />
                        </div>
                        ''',
                        unsafe_allow_html=True,
                    )
                else:
                    st.write("No poster image configured yet. Please upload one from the Settings page.")
            except Exception:
                st.write("No poster image configured yet. Please upload one from the Settings page.")
        else:
            st.write("No poster image configured yet. Please upload one from the Settings page.")
        st.markdown("</div>", unsafe_allow_html=True)

    # Add CSS for card and image fit
    st.markdown(
        '''<style>
        .ticket-card {
            background: #FFFFFF;
            border-radius: 24px;
            padding: 1.8rem 1.6rem 2rem;
            box-shadow: 0 20px 40px rgba(15, 72, 122, 0.08);
            height: 100%;
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
        }
        .ticket-card-poster {
            justify-content: center;
        }
        .ticket-poster-wrapper {
            width: 100%;
            height: 307px; /* fixed height requested */
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0.5rem;
            overflow: hidden;
        }
        .ticket-poster-img {
            max-width: 100%;
            max-height: 307px; /* ensure image never exceeds container */
            width: auto;
            height: auto;
            object-fit: contain;
            border-radius: 18px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
            display: block;
            margin: 0 auto;
        }
        </style>''',
        unsafe_allow_html=True,
    )

    if "submitted" in locals() and submitted:
        if not name.strip() or not phone.strip():
            st.error("الرجاء إدخال الاسم ورقم الهاتف.")
        else:
            df = load_bookings()
            booking_id = get_next_booking_id(df)
            total_amount = float(tickets) * TICKET_PRICE

            payment_intent_id = None
            payment_status = None
            redirect_url = None
            if has_ziina_configured():
                with st.spinner("جاري إنشاء رابط الدفع عبر Ziina..."):
                    pi = create_payment_intent(total_amount, booking_id, name, api_debug=False)
                if pi:
                    payment_intent_id = str(
                        pi.get("id")
                        or pi.get("payment_intent_id")
                        or pi.get("paymentIntent", {}).get("id")
                        or ""
                    )
                    payment_status = pi.get("status")
                    redirect_url = (
                        pi.get("redirect_url")
                        or pi.get("hosted_page_url")
                        or (pi.get("next_action") or {}).get("redirect_url")
                    )

            new_row = {
                "booking_id": booking_id,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": name,
                "phone": phone,
                "tickets": int(tickets),
                "ticket_price": TICKET_PRICE,
                "total_amount": total_amount,
                "status": "paid" if payment_status == "completed" else "pending",
                "payment_intent_id": payment_intent_id,
                "payment_status": payment_status or "pending",
                "redirect_url": redirect_url,
                "notes": notes,
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_bookings(df)

            ticket_text = build_ticket_text(booking_id, name, phone, int(tickets), total_amount)
            ticket_bytes = ticket_text.encode("utf-8")

            st.success(
                f"تم إنشاء الحجز! رقم الحجز: **{booking_id}** والمبلغ **{total_amount:.2f} AED**. "
                "يمكنك تنزيل التذكرة أو إرسالها مباشرة."
            )
            cta_ticket, cta_wa = st.columns(2, gap="small")
            with cta_ticket:
                st.download_button(
                    "⬇️ تنزيل التذكرة باسم العميل",
                    data=ticket_bytes,
                    file_name=f"{booking_id}_ticket.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with cta_wa:
                share_url = f"https://wa.me/?text={urllib.parse.quote(ticket_text)}"
                try:
                    st.markdown(f"[📲 إرسال التذكرة على واتساب]({share_url})")
                except Exception:
                    st.write("Share on WhatsApp: ", share_url)

            if redirect_url:
                try:
                    st.markdown(f"[💳 إكمال الدفع (Ziina)]({redirect_url})")
                except Exception:
                    st.write("Complete payment:", redirect_url)
            else:
                st.info("الدفع عند الوصول أو سيتم مشاركة رابط الدفع لاحقاً.")

    st.markdown("</div>", unsafe_allow_html=True)

    # --- INFO/ABOUT SECTION (anchor for scroll) ---
    about_anchor.markdown('<div id="about_section"></div>', unsafe_allow_html=True)
    render_customer_info_panel()

    # --- Debug/Admin Tools (below info panel, admin only) ---
    is_admin = st.session_state.get("is_admin", False)
    if is_admin:
        with st.expander("Debug / Admin Tools", expanded=False):
            if st.button("🔍 Test Ziina API"):
                with st.spinner("Testing Ziina..."):
                    pi = create_payment_intent(1.0, "TEST-000", "Admin Test", api_debug=True)
                st.write(pi)


def render_who_we_are():
    st.markdown('<div class="snow-title">SNOW LIWA</div>', unsafe_allow_html=True)
    st.markdown('<div class="subheading">من نحن ؟ · Who are we</div>', unsafe_allow_html=True)
    # content omitted for brevity, kept in original app.py


def render_experience():
    st.markdown('<div class="snow-title">SNOW LIWA</div>', unsafe_allow_html=True)
    st.markdown('<div class="subheading">Snow Experience · تجربة الثلج</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ticket-price">🎟️ Entrance Ticket: <strong>{load_settings().get("ticket_price",3)} AED</strong> per person</div>', unsafe_allow_html=True)


def render_contact():
    st.markdown('<div class="snow-title">SNOW LIWA</div>', unsafe_allow_html=True)
    st.markdown('<div class="subheading">Contact · تواصل معنا</div>', unsafe_allow_html=True)
    st.markdown('### 📞 Contact Us / تواصل معنا')
    st.markdown('<div class="dual-column">', unsafe_allow_html=True)
    st.markdown('<div class="arabic">**رقم الهاتف**<br><br>050 113 8781<br><br>للتواصل عبر الواتساب فقط أو من خلال حسابنا في الإنستغرام:<br>**snowliwa**</div>', unsafe_allow_html=True)
    st.markdown('<div class="english">**Phone**<br><br>050 113 8781<br><br>To contact WhatsApp only or on our Instagram account:<br>**snowliwa**</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_dashboard():
    st.markdown('<div class="snow-title">SNOW LIWA</div>', unsafe_allow_html=True)
    st.markdown('<div class="subheading">Dashboard · لوحة التحكم</div>', unsafe_allow_html=True)
    df = load_bookings()
    if df.empty:
        st.info('No bookings yet.')
        return
    total_bookings = len(df)
    total_tickets = df['tickets'].sum()
    total_amount = df['total_amount'].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric('Total bookings', int(total_bookings))
    c2.metric('Total tickets', int(total_tickets))
    c3.metric('Total amount (AED)', f"{total_amount:,.0f}")
    st.markdown('### Last 25 bookings')
    st.dataframe(df.sort_values('created_at', ascending=False).head(25), use_container_width=True)


def render_payment_result(result: str, pi_id: str):
    st.markdown('<div class="snow-title">SNOW LIWA</div>', unsafe_allow_html=True)
    st.markdown('<div class="subheading">Payment result · نتيجة الدفع</div>', unsafe_allow_html=True)
    st.write(f"**Payment Intent ID:** `{pi_id}`")
    df = load_bookings()
    row = df[df['payment_intent_id'].astype(str) == str(pi_id)]
    booking_id = row['booking_id'].iloc[0] if not row.empty else None
    if booking_id:
        st.write(f"**Booking ID:** `{booking_id}`")
    pi_status = None
    if pi_id:
        pi = get_payment_intent(pi_id)
        if pi:
            pi_status = pi.get('status')
            if not row.empty:
                idx = row.index[0]
                df.at[idx, 'payment_status'] = pi_status
                if pi_status == 'completed':
                    df.at[idx, 'status'] = 'paid'
                elif pi_status in ('failed', 'canceled'):
                    df.at[idx, 'status'] = 'cancelled'
                save_bookings(df)
    final_status = pi_status or result
    if final_status == 'completed':
        st.success('✅ تم الدفع بنجاح!')
    elif final_status in ('pending','requires_payment_instrument','requires_user_action'):
        st.info('ℹ️ عملية الدفع قيد المعالجة أو لم تكتمل بعد.')
    elif final_status in ('failed','canceled'):
        st.error('❌ لم تتم عملية الدفع أو تم إلغاؤها.')
    else:
        st.warning('تعذر التأكد من حالة الدفع.')
