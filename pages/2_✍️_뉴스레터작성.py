"""pages/2_✍️_뉴스레터작성.py - 뉴스레터 작성 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import datetime

st.set_page_config(page_title="뉴스레터 작성 | STS뉴스레터", page_icon="✍️", layout="wide")

from db.database import init_db, get_recent_articles, save_newsletter, get_next_volume, get_newsletters
from agents.news_collector import get_mock_articles
from agents.content_writer import ContentWriter

init_db()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
* { font-family:'Noto Sans KR',sans-serif!important; }
.page-header { background:linear-gradient(135deg,#1e1d1d,#b01413); color:#fff; padding:24px 32px; border-radius:12px; margin-bottom:24px; }
.page-header h2 { margin:0 0 4px; font-size:24px; font-weight:900; }
.page-header p  { margin:0; font-size:13px; color:rgba(255,255,255,0.7); }
.section-box { background:#fff; border:1px solid #e0e0e0; border-radius:10px; padding:20px; margin-bottom:16px; }
.section-box h3 { margin:0 0 12px; font-size:15px; color:#b01413; font-weight:700; border-bottom:2px solid #f5f5f5; padding-bottom:8px; }
.preview-frame { border:1px solid #ddd; border-radius:8px; overflow:hidden; }
.kakao-preview { background:#fee500; border-radius:16px; padding:16px 20px; max-width:320px; font-size:13px; line-height:1.7; color:#333; box-shadow:0 4px 16px rgba(0,0,0,0.12); }
.kakao-header { font-weight:900; font-size:14px; margin-bottom:8px; color:#3c1e1e; }
.stButton>button { background:linear-gradient(135deg,#b01413,#8b0000)!important; color:#fff!important; border:none!important; border-radius:8px!important; font-weight:700!important; }
.stTextArea textarea { font-size:13px!important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
  <h2>✍️ 뉴스레터 작성</h2>
  <p>Claude AI 기반 STS 정밀재 주간 뉴스레터 자동 작성</p>
</div>
""", unsafe_allow_html=True)

# ── 사이드바: LLM 설정 ──────────────────────────────────
with st.sidebar:
    st.markdown("### 🤖 LLM 설정")
    provider = st.selectbox("LLM 제공자", ["anthropic (Claude)", "openai (GPT)", "mock (테스트)"],
                            index=0, help="Claude를 기본으로 사용합니다.")
    provider_key = provider.split(" ")[0]

    model_options = {
        "anthropic": ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001"],
        "openai":    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "mock":      ["mock"],
    }
    model = st.selectbox("모델", model_options.get(provider_key, ["mock"]))

    st.markdown("---")
    st.markdown("### 📋 뉴스 소스")
    use_db_articles = st.radio("기사 소스", ["DB 수집 기사 사용", "Mock 샘플 기사 사용"], index=0)

# ── 기사 로드 ────────────────────────────────────────────
articles = get_recent_articles(limit=10)
if not articles or use_db_articles == "Mock 샘플 기사 사용":
    articles = get_mock_articles()
    st.info("💡 Mock 샘플 기사를 사용합니다. 먼저 '뉴스 수집' 페이지에서 기사를 수집하면 실제 데이터를 활용할 수 있습니다.")

col1, col2 = st.columns([1, 1])
with col1:
    st.markdown(f"**📰 사용할 기사**: {len(articles)}건")
    with st.expander("기사 목록 보기"):
        for i, a in enumerate(articles, 1):
            st.markdown(f"**{i}.** {a.get('title','')[:60]}... `{a.get('category','')}`")

with col2:
    gen_btn = st.button("🤖 뉴스레터 자동 생성", use_container_width=True)

# ── 뉴스레터 생성 ────────────────────────────────────────
if gen_btn or "current_newsletter" in st.session_state:
    if gen_btn:
        progress = st.progress(0, "뉴스레터 작성 준비 중...")
        writer   = ContentWriter(model=model, provider=provider_key)
        with st.spinner("Claude AI가 뉴스레터를 작성하고 있습니다..."):
            try:
                newsletter = writer.write_newsletter(
                    articles,
                    progress_callback=lambda p, t: progress.progress(int(p*100), t)
                )
                st.session_state["current_newsletter"] = newsletter
                st.session_state["current_articles"]   = articles
                st.success("✅ 뉴스레터 초안 생성 완료!")
            except Exception as e:
                st.error(f"❌ 생성 오류: {e}")
                st.stop()

    nl = st.session_state.get("current_newsletter", {})
    if not nl:
        st.stop()

    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs(["📝 내용 편집", "🌐 이메일 미리보기", "💬 카카오 미리보기", "💾 저장"])

    # ── 탭1: 내용 편집 ───────────────────────────────────
    with tab1:
        col_e1, col_e2 = st.columns(2)

        with col_e1:
            st.markdown('<div class="section-box">', unsafe_allow_html=True)
            st.markdown("### 📌 이번 주 핵심")
            headline = st.text_area("헤드라인", value=nl.get("headline",""), height=80, key="edit_headline")
            st.markdown("### 📊 시장 동향")
            market = st.text_area("시장 요약", value=nl.get("sections",{}).get("market_summary",""), height=130, key="edit_market")
            st.markdown('</div>', unsafe_allow_html=True)

        with col_e2:
            st.markdown('<div class="section-box">', unsafe_allow_html=True)
            st.markdown("### 💰 가격 동향")
            price = st.text_area("가격 동향", value=nl.get("sections",{}).get("price_trends",""), height=130, key="edit_price")
            st.markdown("### 🔮 다음 주 전망")
            outlook = st.text_area("전망", value=nl.get("sections",{}).get("outlook",""), height=80, key="edit_outlook")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### 💬 카카오톡 요약 (3줄)")
        kakao_msg = st.text_area("카카오 요약", value=nl.get("kakao_summary",""), height=100, key="edit_kakao",
                                  help="각 줄 50자 이내 권장")

        if st.button("✏️ 편집 내용 적용"):
            nl["headline"]       = headline
            nl["kakao_summary"]  = kakao_msg
            if "sections" not in nl:
                nl["sections"] = {}
            nl["sections"]["market_summary"] = market
            nl["sections"]["price_trends"]   = price
            nl["sections"]["outlook"]         = outlook
            # HTML 재생성
            writer2 = ContentWriter(model=model, provider=provider_key)
            now = datetime.now()
            nl["html_body"] = writer2._render_html(nl["sections"], articles, {"week": now.isocalendar()[1]})
            nl["plain_text"]= writer2._render_plain(nl["sections"], {"week": now.isocalendar()[1]})
            st.session_state["current_newsletter"] = nl
            st.success("✅ 편집 내용이 적용되었습니다.")
            st.rerun()

    # ── 탭2: 이메일 미리보기 ─────────────────────────────
    with tab2:
        st.markdown(f"**📧 이메일 제목**: `{nl.get('subject','')}`")
        st.markdown('<div class="preview-frame">', unsafe_allow_html=True)
        st.components.v1.html(nl.get("html_body","<p>미리보기가 없습니다.</p>"), height=700, scrolling=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── 탭3: 카카오 미리보기 ─────────────────────────────
    with tab3:
        writer3 = ContentWriter(provider="mock")
        sample_msg = writer3.generate_kakao_message(nl, "홍길동")
        col_kk1, col_kk2 = st.columns([1, 1])
        with col_kk1:
            st.markdown("**💬 카카오톡 알림톡 미리보기**")
            st.markdown(f"""
            <div style="background:#f0f0f0; padding:20px; border-radius:12px;">
              <div style="font-size:11px; color:#888; text-align:right; margin-bottom:8px;">오전 9:05</div>
              <div class="kakao-preview">
                <div class="kakao-header">kakao</div>
                <pre style="margin:0; font-family:inherit; font-size:13px; white-space:pre-wrap; word-break:break-all;">{sample_msg}</pre>
              </div>
            </div>
            """, unsafe_allow_html=True)
        with col_kk2:
            st.markdown("**📝 메시지 원문**")
            st.code(sample_msg, language=None)

    # ── 탭4: 저장 ────────────────────────────────────────
    with tab4:
        st.markdown("### 💾 뉴스레터 DB 저장")
        vol = get_next_volume()
        st.info(f"저장 시 Vol.{vol}로 등록됩니다.")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            custom_subject = st.text_input("이메일 제목 (수정 가능)", value=nl.get("subject",""))
        with col_s2:
            save_status = st.selectbox("저장 상태", ["draft", "ready"], index=0)

        if st.button("💾 뉴스레터 저장", use_container_width=True):
            nl_id = save_newsletter({
                "volume":       vol,
                "week_label":   custom_subject,
                "subject":      custom_subject,
                "html_body":    nl.get("html_body",""),
                "plain_text":   nl.get("plain_text",""),
                "kakao_summary":nl.get("kakao_summary",""),
                "headline":     nl.get("headline",""),
                "status":       save_status,
            })
            st.success(f"✅ 뉴스레터 Vol.{vol} 저장 완료! (ID: {nl_id})")
            st.session_state["saved_newsletter_id"] = nl_id
else:
    st.markdown("""
    <div style="background:#e3f2fd;border-left:4px solid #1976d2;border-radius:8px;padding:20px 24px;color:#1565c0;">
      <strong>🤖 Claude AI 뉴스레터 자동 작성</strong><br><br>
      위의 <strong>뉴스레터 자동 생성</strong> 버튼을 클릭하면 수집된 STS 정밀재 뉴스를 바탕으로
      Claude AI가 자동으로 주간 뉴스레터 초안을 작성합니다.<br><br>
      <small>💡 Anthropic API 키가 없으면 Mock 모드로 샘플 뉴스레터를 생성합니다.</small>
    </div>
    """, unsafe_allow_html=True)
