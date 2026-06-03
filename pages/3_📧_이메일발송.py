"""pages/3_📧_이메일발송.py - 이메일 발송 페이지 (네이버 SMTP)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="이메일 발송 | STS뉴스레터", page_icon="📧", layout="wide")

from db.database import init_db, get_subscribers, get_newsletters, get_newsletter_by_id, log_send, update_newsletter_status
from agents.email_sender import EmailSender

init_db()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
* { font-family:'Noto Sans KR',sans-serif!important; }
.page-header { background:linear-gradient(135deg,#1e1d1d,#b01413); color:#fff; padding:24px 32px; border-radius:12px; margin-bottom:24px; }
.page-header h2 { margin:0 0 4px; font-size:24px; font-weight:900; }
.page-header p  { margin:0; font-size:13px; color:rgba(255,255,255,0.7); }
.smtp-box { background:#f8f9fa; border:1px solid #dee2e6; border-radius:10px; padding:20px; margin-bottom:16px; }
.smtp-box h4 { margin:0 0 12px; font-size:14px; font-weight:700; color:#333; }
.result-row-ok  { background:#e8f5e9!important; }
.result-row-err { background:#ffebee!important; }
.stButton>button { background:linear-gradient(135deg,#b01413,#8b0000)!important; color:#fff!important; border:none!important; border-radius:8px!important; font-weight:700!important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
  <h2>📧 이메일 발송</h2>
  <p>Google SMTP 기반 구독자 대상 뉴스레터 발송 (smtp.gmail.com:587)</p>
</div>
""", unsafe_allow_html=True)

# ── 사이드바: SMTP 설정 ─────────────────────────────────
with st.sidebar:
    st.markdown("### 📮 Google SMTP 설정")
    smtp_user  = st.text_input("Google 이메일", value=os.getenv("SMTP_USER","cnbkaz@gmail.com"), placeholder="your@gmail.com")
    smtp_pass  = st.text_input("앱 비밀번호", value=os.getenv("SMTP_PASSWORD",""), type="password",
                                help="Google 계정 → 보안 → 앱 비밀번호 (2단계 인증 필요)")
    simulation = st.toggle("🧪 시뮬레이션 모드", value=not bool(smtp_pass),
                            help="ON: 실제 발송 없이 결과만 시뮬레이션")
    rate_limit = st.slider("초당 발송 수", 1, 10, 3)

    st.markdown("""
    <div style="background:#fff3cd;border-left:3px solid #ffc107;border-radius:6px;padding:10px;font-size:11px;color:#856404;margin-top:8px;">
    ⚠️ <strong>Google 앱 비밀번호 발급 방법</strong><br>
    1. Google 계정 → 보안<br>
    2. 2단계 인증 활성화<br>
    3. 앱 비밀번호 → 메일 선택<br>
    4. 생성된 16자리 비밀번호 사용
    </div>
    """, unsafe_allow_html=True)

# ── 뉴스레터 선택 ────────────────────────────────────────
newsletters = get_newsletters(limit=10)
if not newsletters:
    st.warning("⚠️ 저장된 뉴스레터가 없습니다. 먼저 '뉴스레터 작성' 페이지에서 뉴스레터를 생성·저장하세요.")
    st.stop()

nl_options = {f"Vol.{nl['volume']} - {nl.get('subject','')[:50]} ({nl.get('status','')})": nl["id"] for nl in newsletters}
selected_label = st.selectbox("📋 발송할 뉴스레터 선택", list(nl_options.keys()))
selected_id = nl_options[selected_label]
nl = get_newsletter_by_id(selected_id)

col_info1, col_info2, col_info3 = st.columns(3)
with col_info1:
    st.metric("선택된 뉴스레터", f"Vol.{nl.get('volume','?')}")
with col_info2:
    st.metric("현재 상태", nl.get("status","draft").upper())
with col_info3:
    subscribers = get_subscribers(active_only=True)
    st.metric("발송 대상 구독자", f"{len(subscribers)}명")

# ── 이메일 미리보기 ─────────────────────────────────────
with st.expander("📧 이메일 미리보기"):
    st.text(f"제목: {nl.get('subject','')}")
    st.components.v1.html(nl.get("html_body",""), height=400, scrolling=True)

st.markdown("---")

# ── 발송 탭 ─────────────────────────────────────────────
tab_test, tab_all = st.tabs(["🧪 테스트 발송", "📤 전체 발송"])

with tab_test:
    st.markdown("#### 단일 이메일 테스트 발송")
    test_email = st.text_input("테스트 수신 이메일", placeholder="your_email@naver.com")
    test_btn   = st.button("🧪 테스트 발송", disabled=not test_email)

    if test_btn and test_email:
        sender = EmailSender(
            smtp_host="smtp.naver.com",
            smtp_port=587,
            smtp_user=smtp_user,
            smtp_password=smtp_pass,
            sender_name="STS정밀재 뉴스레터",
            sender_email=smtp_user,
            simulation_mode=simulation,
        )
        with st.spinner("테스트 발송 중..."):
            ok, msg = sender.send_test(test_email, nl)
        if ok:
            st.success(f"✅ 테스트 발송 성공! → {test_email}")
            if simulation:
                st.info("ℹ️ 시뮬레이션 모드: 실제로 발송되지 않았습니다.")
        else:
            st.error(f"❌ 발송 실패: {msg}")

with tab_all:
    st.markdown("#### 전체 구독자 발송")
    if not subscribers:
        st.warning("구독자가 없습니다.")
    else:
        # 구독자 목록 미리보기
        df_subs = pd.DataFrame([{
            "이름": s["name"],
            "이메일": s["email"][:3] + "***@" + s["email"].split("@")[-1],
            "그룹": s.get("group_name",""),
        } for s in subscribers])
        st.dataframe(df_subs, use_container_width=True, height=180, hide_index=True)

        col_a1, col_a2 = st.columns([2, 1])
        with col_a2:
            confirm = st.checkbox(f"✅ {len(subscribers)}명에게 발송을 확인합니다.")
        with col_a1:
            send_all_btn = st.button("📤 전체 발송 시작", disabled=not confirm, use_container_width=True)

        if send_all_btn:
            sender = EmailSender(
                smtp_host="smtp.naver.com",
                smtp_port=587,
                smtp_user=smtp_user,
                smtp_password=smtp_pass,
                sender_name="STS정밀재 뉴스레터",
                sender_email=smtp_user,
                rate_limit_per_sec=rate_limit,
                simulation_mode=simulation,
            )
            progress = st.progress(0, "발송 준비 중...")
            result   = sender.send_newsletter(
                subscribers, nl,
                progress_callback=lambda p, t: progress.progress(int(p*100), t)
            )

            # DB 기록
            for log in result["logs"]:
                raw_email = next((s["email"] for s in subscribers if s["name"] == log["name"]), log.get("email",""))
                log_send(selected_id, "email", raw_email, log["status"], log.get("message",""))

            if result["failed"] == 0:
                update_newsletter_status(selected_id, "sent", datetime.now().isoformat())

            # 결과 표시
            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric("전체", f"{result['total']}건")
            col_r2.metric("✅ 성공", f"{result['success']}건")
            col_r3.metric("❌ 실패", f"{result['failed']}건")

            if simulation:
                st.info("ℹ️ 시뮬레이션 모드로 실행되었습니다. 실제 이메일은 발송되지 않았습니다.")

            # 발송 로그
            with st.expander("📋 발송 상세 로그"):
                log_df = pd.DataFrame(result["logs"])
                st.dataframe(log_df, use_container_width=True, hide_index=True)
