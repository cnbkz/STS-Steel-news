"""pages/1_📰_뉴스수집.py - 뉴스 수집 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="뉴스 수집 | STS뉴스레터", page_icon="📰", layout="wide")

from db.database import init_db, insert_article, get_recent_articles, get_article_count, clear_articles
from agents.news_collector import NewsCollector, get_mock_articles
from agents.content_writer import ContentWriter

init_db()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
* { font-family:'Noto Sans KR',sans-serif !important; }
.page-header {
  background:linear-gradient(135deg,#16294f 0%,#1e3d72 60%,#2578d6 100%);
  border-bottom:3px solid #c41c22;
  color:#fff; padding:24px 32px; border-radius:12px; margin-bottom:24px;
}
.page-header h2 { margin:0 0 4px; font-size:24px; font-weight:900; }
.page-header p  { margin:0; font-size:13px; color:rgba(255,255,255,0.7); }
.kw-tag {
  display:inline-block; background:#f0f5ff; color:#2578d6;
  border:1px solid #b3d0ff; border-radius:20px;
  padding:2px 10px; font-size:11px; font-weight:600; margin:2px;
}
.article-card {
  background:#fff; border:1px solid #e5e5e5;
  border-left:3px solid #2578d6; border-radius:8px;
  padding:14px 18px; margin-bottom:10px;
  box-shadow:4px 5px 12px -1px rgba(0,0,0,0.06);
}
.article-card h4 { margin:0 0 6px; font-size:14px; color:#16294f; font-weight:700; }
.article-card p  { margin:0; font-size:12px; color:#555; line-height:1.7; }
.article-meta    { font-size:11px; color:#a5a5a5; margin-top:6px; }
.score-badge {
  background:#16294f; color:#fff;
  border-radius:12px; padding:1px 8px; font-size:11px; font-weight:700;
}
.preview-section {
  background:#f5f7ff; border:1px solid #c3d5f5;
  border-radius:10px; padding:20px; margin-top:16px;
}
.stButton>button {
  background:linear-gradient(135deg,#16294f,#2578d6)!important;
  color:#fff!important; border:none!important;
  border-radius:8px!important; font-weight:700!important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
  <h2>📰 뉴스 수집</h2>
  <p>철강금속신문 · 철강데일리 STS 정밀재 섹션 자동 크롤링</p>
</div>
""", unsafe_allow_html=True)

# ── 사이드바 ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 수집 설정")
    use_mock = st.toggle("🧪 Mock 데이터 사용", value=False,
                         help="실제 크롤링 대신 샘플 데이터를 사용합니다.")
    st.markdown("**수집 소스**")
    src_snm   = st.checkbox("철강금속신문 - STS",    value=True)
    src_daily = st.checkbox("철강데일리 - 스테인리스", value=True)
    st.markdown("---")
    max_articles = st.slider("최대 기사 수", 5, 30, 15)

# ── 컨트롤 버튼 ─────────────────────────────────────────────
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    run_btn = st.button("🔍 뉴스 수집 시작", use_container_width=True)
with col2:
    clear_btn = st.button("🗑️ 수집 데이터 초기화", use_container_width=True)
with col3:
    st.metric("현재 수집량", f"{get_article_count()}건")

if clear_btn:
    clear_articles()
    st.session_state.pop("collected_articles", None)
    st.session_state.pop("preview_html", None)
    st.success("수집 데이터를 초기화했습니다.")
    st.rerun()

# ── 수집 실행 ────────────────────────────────────────────────
if run_btn:
    progress = st.progress(0, "수집 준비 중...")
    status   = st.empty()

    def cb(p, t):
        progress.progress(int(p * 100), t)

    with st.spinner("뉴스 수집 중..."):
        if use_mock:
            articles = get_mock_articles()
            progress.progress(100, "✅ Mock 데이터 로드 완료")
        else:
            sources = []
            if src_snm:
                sources.append({
                    "url": "https://www.snmnews.com/news/articleList.html?sc_serial_code=SRN469&view_type=sm",
                    "name": "철강금속신문-STS", "type": "korean_news",
                    "base_url": "https://www.snmnews.com", "enabled": True,
                })
            if src_daily:
                sources.append({
                    "url": "https://www.steeldaily.co.kr/news/articleList.html?sc_sub_section_code=S2N11&view_type=sm",
                    "name": "철강데일리-스테인리스", "type": "korean_news",
                    "base_url": "https://www.steeldaily.co.kr", "enabled": True,
                })
            try:
                collector = NewsCollector(sources=sources)
                articles  = collector.collect(progress_callback=cb)
            except Exception as e:
                status.warning(f"크롤링 오류, Mock 데이터로 대체: {e}")
                articles = get_mock_articles()

        saved = 0
        for a in articles[:max_articles]:
            if insert_article({**a, "score": a.get("score", 0)}):
                saved += 1

    st.success(f"✅ 수집 완료: {len(articles)}건 수집 / {saved}건 신규 저장")
    st.session_state["collected_articles"] = articles[:max_articles]
    st.session_state.pop("preview_html", None)

# ── 미리보기 생성 버튼 ───────────────────────────────────────
articles_for_preview = st.session_state.get("collected_articles") or get_recent_articles(limit=max_articles if "max_articles" in dir() else 15)

if articles_for_preview:
    st.markdown("---")
    col_prev1, col_prev2 = st.columns([2, 1])
    with col_prev1:
        preview_btn = st.button("👁️ 뉴스레터 미리보기 생성", use_container_width=True,
                                help="수집된 기사로 뉴스레터 HTML을 즉시 생성합니다 (Mock 모드)")
    with col_prev2:
        if "preview_html" in st.session_state:
            html_bytes = st.session_state["preview_html"].encode("utf-8")
            st.download_button(
                "📥 HTML 다운로드", html_bytes,
                file_name=f"newsletter_preview_{datetime.now().strftime('%Y%m%d')}.html",
                mime="text/html", use_container_width=True,
            )

    if preview_btn:
        with st.spinner("뉴스레터 초안 생성 중..."):
            writer = ContentWriter(provider="mock")
            nl = writer.write_newsletter(articles_for_preview)
            st.session_state["preview_html"] = nl["html_body"]
            st.session_state["preview_subject"] = nl["subject"]
        st.success(f"✅ 미리보기 생성 완료 — {nl['subject']}")
        st.rerun()

    if "preview_html" in st.session_state:
        st.markdown(f"""
        <div class="preview-section">
          <div style="font-size:13px;font-weight:700;color:#16294f;margin-bottom:10px;">
            📧 뉴스레터 미리보기 — {st.session_state.get('preview_subject','')}
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.components.v1.html(st.session_state["preview_html"], height=750, scrolling=True)

# ── 수집 기사 목록 ───────────────────────────────────────────
st.markdown("---")
articles_in_db = get_recent_articles(limit=50)

if articles_in_db:
    col_f1, col_f2, col_f3 = st.columns([3, 1, 1])
    with col_f1:
        search = st.text_input("🔎 제목 검색", placeholder="예: 니켈, STS, 304, 할증료")
    with col_f2:
        categories = ["전체"] + sorted(set(a["category"] for a in articles_in_db if a.get("category")))
        sel_cat = st.selectbox("카테고리", categories)
    with col_f3:
        sources_list = ["전체"] + sorted(set(a["source"] for a in articles_in_db if a.get("source")))
        sel_src = st.selectbox("출처", sources_list)

    filtered = articles_in_db
    if search:
        filtered = [a for a in filtered if search.lower() in a.get("title","").lower()
                    or search in a.get("content","")]
    if sel_cat != "전체":
        filtered = [a for a in filtered if a.get("category") == sel_cat]
    if sel_src != "전체":
        filtered = [a for a in filtered if a.get("source") == sel_src]

    st.markdown(f"**총 {len(filtered)}건** 표시 중")
    st.markdown("---")

    for a in filtered:
        kw_html = " ".join(
            f'<span class="kw-tag">{k}</span>'
            for k in (a.get("keywords_matched") or [])[:5]
        )
        score   = a.get("score", 0)
        pub     = a.get("published_at", "")[:10]
        src     = a.get("source", "")
        preview = (a.get("content") or "")[:160]
        if len(a.get("content") or "") > 160:
            preview += "..."

        st.markdown(f"""
        <div class="article-card">
          <h4>
            <a href="{a.get('url','#')}" target="_blank"
               style="color:#16294f;text-decoration:none;">
              {a.get('title','')}
            </a>
            &nbsp;<span class="score-badge">점수 {score}</span>
          </h4>
          <p>{preview}</p>
          <div class="article-meta">
            📅 {pub} &nbsp;|&nbsp; 📌 {src} &nbsp;|&nbsp; 🏷️ {a.get('category','')}
            <br>{kw_html}
          </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="background:#f0f5ff;border-left:4px solid #2578d6;
                border-radius:8px;padding:16px 20px;color:#16294f;">
      📭 수집된 기사가 없습니다.
      위의 <strong>뉴스 수집 시작</strong> 버튼을 눌러 수집을 시작하세요.
    </div>
    """, unsafe_allow_html=True)
