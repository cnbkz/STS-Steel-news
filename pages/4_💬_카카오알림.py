"""pages/4_💬_카카오알림.py - 카카오 알림톡 발송 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="카카오 알림 | STS뉴스레터", page_icon="💬", layout="wide")

from db.database import init_db, get_subscribers, get_newsletters, get_newsletter_by_id, log_send
from agents.kakao_notifier import KakaoNotifier
from agents.content_writer import ContentWriter

init_db()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
* { font-family:'Noto Sans KR',sans-serif!important; }
.page-header { background:linear-gradient(135deg,#1e1d1d,#3c1e1e); color:#fff; padding:24px 32px; border-radius:12px; margin-bottom:24px; }
.page-header h2 { margin:0 0 4px; font-size:24px; font-weight:900; }
.page-header p  { margin:0; font-size:13px; color:rgba(255,255,255,0.7); }
.kakao-phone-mock { background:#f0f0f0; border-radius:16px; padding:20px; max-width:340px; margin:0 auto; }
.kakao-bubble { background:#fee500; border-radius:0 16px 16px 16px; padding:14px 18px; font-size:13px; line-height:1.8; color:#333; box-shadow:0 2px 8px rgba(0,0,0,0.1); }
.kakao-time { font-size:11px; color:#999; text-align:right; margin-top:8px; }
.stButton>button { background:linear-gradient(135deg,#FEE500,#f0d800)!important; color:#333!important; border:none!important; border-radius:8px!important; font-weight:700!important; }
.stButton>button:hover { background:linear-gradient(135deg,#f0d800,#d4bc00)!important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
  <h2>💬 카카오 알림</h2>
  <p>카카오 알림톡 API 기반 뉴스레터 요약 및 발송 알림 전송</p>
</div>
""", unsafe_allow_html=True)

# ── 사이드바 ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 카카오 설정")
    simulation = st.toggle("🧪 시뮬레이션 모드", value=True, help="ON: 실제 발송 없이 결과만 시뮬레이션")
    api_key     = st.text_input("카카오 API Key", value=os.getenv("KAKAO_API_KEY",""), type="password")
    sender_key  = st.text_input("발신 프로필 Key", value=os.getenv("KAKAO_SENDER_KEY",""), type="password")
    tpl_code    = st.text_input("템플릿 코드", value=os.getenv("KAKAO_TEMPLATE_CODE","STS_NEWSLETTER_01"))

    st.markdown("""
    <div style="background:#fff9c4;border-left:3px solid #f9a825;border-radius:6px;padding:10px;font-size:11px;color:#5d4037;margin-top:10px;">
    ⚠️ <strong>카카오 알림톡 사용 안내</strong><br>
    • 카카오비즈메시지 채널 등록 필요<br>
    • 템플릿 사전 심사 후 사용 가능<br>
    • 테스트는 시뮬레이션 모드로 확인
    </div>
    """, unsafe_allow_html=True)

# ── 뉴스레터 선택 ────────────────────────────────────────
newsletters = get_newsletters(limit=10)
nl = None
if newsletters:
    nl_options = {f"Vol.{n['volume']} - {n.get('subject','')[:40]}": n["id"] for n in newsletters}
    sel = st.selectbox("📋 알림 발송할 뉴스레터", list(nl_options.keys()))
    nl  = get_newsletter_by_id(nl_options[sel])
else:
    st.warning("⚠️ 저장된 뉴스레터가 없습니다. 먼저 뉴스레터를 작성·저장하세요.")
    # Mock 뉴스레터 생성
    writer_mock = ContentWriter(provider="mock")
    from agents.news_collector import get_mock_articles
    nl = writer_mock.write_newsletter(get_mock_articles())
    nl["volume"] = 1
    st.info("💡 샘플 Mock 뉴스레터로 미리보기를 제공합니다.")

# ── 메시지 미리보기 ─────────────────────────────────────
writer = ContentWriter(provider="mock")
sample_msg = writer.generate_kakao_message(nl, "홍길동")

col_preview, col_info = st.columns([1, 1])

with col_preview:
    st.markdown("#### 💬 알림톡 미리보기")
    st.markdown(f"""
    <div class="kakao-phone-mock">
        <div style="font-size:12px;color:#888;font-weight:600;margin-bottom:12px;">
            💛 카카오 알림톡
        </div>
        <div style="font-size:11px;color:#999;margin-bottom:4px;">STS정밀재 뉴스레터</div>
        <div class="kakao-bubble">
            <pre style="margin:0;font-family:inherit;font-size:13px;white-space:pre-wrap;word-break:break-all;">{sample_msg}</pre>
        </div>
        <div class="kakao-time">오전 9:05 ✓✓</div>
    </div>
    """, unsafe_allow_html=True)

with col_info:
    st.markdown("#### 📊 발송 대상")
    subscribers = get_subscribers(active_only=True)
    kakao_subs  = [s for s in subscribers if s.get("kakao_subscribed", 1)]

    col_i1, col_i2 = st.columns(2)
    col_i1.metric("전체 구독자", f"{len(subscribers)}명")
    col_i2.metric("카카오 수신자", f"{len(kakao_subs)}명")

    if kakao_subs:
        df = pd.DataFrame([{
            "이름": s["name"],
            "전화번호": s.get("phone","")[:3] + "****" + s.get("phone","")[-4:] if s.get("phone","") else "-",
            "그룹": s.get("group_name",""),
        } for s in kakao_subs])
        st.dataframe(df, use_container_width=True, height=200, hide_index=True)

    st.markdown("#### 📝 메시지 원문")
    st.code(sample_msg, language=None)

st.markdown("---")

# ── 발송 탭 ─────────────────────────────────────────────
tab_test, tab_all = st.tabs(["🧪 테스트 발송", "📤 전체 발송"])

with tab_test:
    st.markdown("#### 단일 번호 테스트 발송")
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        test_phone = st.text_input("테스트 전화번호", placeholder="010-1234-5678")
        test_name  = st.text_input("수신자 이름", value="테스트 수신자")
    with col_t2:
        test_btn = st.button("💬 테스트 발송", disabled=not test_phone, use_container_width=True)

    if test_btn and test_phone:
        notifier = KakaoNotifier(api_key=api_key, sender_key=sender_key,
                                  template_code=tpl_code, simulation_mode=simulation)
        writer_t = ContentWriter(provider="mock")
        ok, msg, full_msg = notifier.send_test(test_phone, nl, test_name)
        if ok:
            st.success(f"✅ 테스트 발송 성공! → {test_phone[:3]}****{test_phone[-4:]}")
            if simulation:
                st.info("ℹ️ 시뮬레이션 모드: 실제 발송되지 않았습니다.")
            st.code(full_msg, language=None)
        else:
            st.error(f"❌ 발송 실패: {msg}")

with tab_all:
    st.markdown("#### 전체 구독자 카카오 알림 발송")
    if not kakao_subs:
        st.warning("카카오 수신 동의 구독자가 없습니다.")
    else:
        confirm = st.checkbox(f"✅ {len(kakao_subs)}명에게 카카오 알림 발송을 확인합니다.")
        send_btn = st.button("💬 전체 카카오 발송", disabled=not confirm, use_container_width=True)

        if send_btn:
            notifier = KakaoNotifier(api_key=api_key, sender_key=sender_key,
                                      template_code=tpl_code, simulation_mode=simulation)
            writer_a = ContentWriter(provider="mock")
            progress = st.progress(0, "카카오 발송 준비 중...")

            result = notifier.send_notification(
                kakao_subs, nl, writer_a,
                progress_callback=lambda p, t: progress.progress(int(p*100), t)
            )

            # DB 기록
            nl_id = nl.get("id", 0)
            for log in result["logs"]:
                phone = next((s.get("phone","") for s in kakao_subs if s["name"] == log["name"]), "unknown")
                log_send(nl_id, "kakao", phone, log["status"])

            col_r1, col_r2, col_r3 = st.columns(3)
            col_r1.metric("전체", f"{result['total']}건")
            col_r2.metric("✅ 성공", f"{result['success']}건")
            col_r3.metric("❌ 실패", f"{result['failed']}건")

            if simulation:
                st.info("ℹ️ 시뮬레이션 모드로 실행되었습니다.")

            with st.expander("📋 발송 상세 로그"):
                log_data = [{
                    "이름": l["name"],
                    "전화번호": l["phone"],
                    "상태": "✅ 성공" if l["status"]=="success" else "❌ 실패",
                } for l in result["logs"]]
                st.dataframe(pd.DataFrame(log_data), use_container_width=True, hide_index=True)
