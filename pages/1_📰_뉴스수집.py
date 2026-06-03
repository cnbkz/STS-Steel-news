"""pages/1_📰_뉴스수집.py - 뉴스 수집 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="뉴스 수집 | STS뉴스레터", page_icon="📰", layout="wide")

from db.database import init_db, insert_article, get_recent_articles, get_article_count, clear_articles
from agents.news_collector import NewsCollector, get_mock_articles

init_db()

# CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
* { font-family: 'Noto Sans KR', sans-serif !important; }
.page-header { background: linear-gradient(135deg,#1e1d1d,#b01413); color:#fff; padding:24px 32px; border-radius:12px; margin-bottom:24px; }
.page-header h2 { margin:0 0 4px; font-size:24px; font-weight:900; }
.page-header p  { margin:0; font-size:13px; color:rgba(255,255,255,0.7); }
.kw-tag { display:inline-block; background:#fff0f0; color:#b01413; border:1px solid #ffcdd2; border-radius:20px; padding:2px 10px; font-size:11px; font-weight:700; margin:2px; }
.article-card { background:#fff; border:1px solid #e8e8e8; border-left:3px solid #b01413; border-radius:8px; padding:14px 18px; margin-bottom:10px; }
.article-card h4 { margin:0 0 6px; font-size:14px; color:#1e1d1d; font-weight:700; }
.article-card p  { margin:0; font-size:12px; color:#555; line-height:1.7; }
.article-meta    { font-size:11px; color:#aaa; margin-top:6px; }
.score-badge { background:#b01413; color:#fff; border-radius:12px; padding:1px 8px; font-size:11px; font-weight:700; }
.stButton>button { background:linear-gradient(135deg,#b01413,#8b0000)!important; color:#fff!important; border:none!important; border-radius:8px!important; font-weight:700!important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
  <h2>📰 뉴스 수집</h2>
  <p>steelinfosys.com 스테인리스·K-스테인리스 섹션 자동 크롤링</p>
</div>
""", unsafe_allow_html=True)

# ── 사이드바: 수집 설정 ─────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ 수집 설정")
    use_mock = st.toggle("🧪 Mock 데이터 사용 (테스트)", value=True,
                         help="실제 크롤링 대신 샘플 데이터를 사용합니다.")
    st.markdown("**수집 소스**")
    src_sts    = st.checkbox("철강정보원 - 스테인리스", value=True)
    src_ksts   = st.checkbox("철강정보원 - K-스테인리스", value=True)
    src_market = st.checkbox("철강정보원 - 시장", value=True)
    src_metal  = st.checkbox("철강정보원 - 비철상품", value=True)

    st.markdown("---")
    max_articles = st.slider("최대 기사 수", 5, 30, 10)

# ── 컨트롤 버튼 ─────────────────────────────────────────
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    run_btn = st.button("🔍 뉴스 수집 시작", use_container_width=True)
with col2:
    clear_btn = st.button("🗑️ 수집 데이터 초기화", use_container_width=True)
with col3:
    st.metric("현재 수집량", f"{get_article_count()}건")

if clear_btn:
    clear_articles()
    st.success("수집 데이터를 초기화했습니다.")
    st.rerun()

# ── 수집 실행 ───────────────────────────────────────────
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
            if src_sts:    sources.append({"url":"https://steelinfosys.com/news/list.php?mcode=m163mrwf","name":"철강정보원-스테인리스","enabled":True})
            if src_ksts:   sources.append({"url":"https://steelinfosys.com/news/list.php?mcode=m193nba6","name":"철강정보원-K스테인리스","enabled":True})
            if src_market: sources.append({"url":"https://steelinfosys.com/news/list.php?mcode=m226vwvo","name":"철강정보원-시장","enabled":True})
            if src_metal:  sources.append({"url":"https://steelinfosys.com/news/list.php?mcode=m150bs2e","name":"철강정보원-비철상품","enabled":True})
            try:
                collector = NewsCollector(sources=sources)
                articles  = collector.collect(progress_callback=cb)
            except Exception as e:
                status.warning(f"크롤링 오류 발생, Mock 데이터로 대체합니다: {e}")
                articles = get_mock_articles()

        saved = 0
        for a in articles[:max_articles]:
            if insert_article({**a, "score": a.get("score", 0)}):
                saved += 1

    st.success(f"✅ 수집 완료: {len(articles)}건 수집 / {saved}건 신규 저장")
    st.session_state["collected_articles"] = articles[:max_articles]

# ── 수집 기사 목록 ──────────────────────────────────────
st.markdown("---")
articles_in_db = get_recent_articles(limit=30)

if articles_in_db:
    # 필터
    col_f1, col_f2 = st.columns([3, 1])
    with col_f1:
        search = st.text_input("🔎 제목 검색", placeholder="예: 니켈, STS, 304")
    with col_f2:
        categories = ["전체"] + sorted(list(set(a["category"] for a in articles_in_db if a.get("category"))))
        sel_cat = st.selectbox("카테고리", categories)

    filtered = articles_in_db
    if search:
        filtered = [a for a in filtered if search.lower() in a.get("title","").lower() or search in a.get("content","")]
    if sel_cat != "전체":
        filtered = [a for a in filtered if a.get("category") == sel_cat]

    st.markdown(f"**총 {len(filtered)}건** 표시 중")
    st.markdown("---")

    for a in filtered:
        kw_html = " ".join(f'<span class="kw-tag">{k}</span>' for k in (a.get("keywords_matched") or [])[:5])
        score   = a.get("score", 0)
        pub     = a.get("published_at", "")[:10]
        src     = a.get("source", "")
        content_preview = (a.get("content","") or "")[:150]
        if len(a.get("content","") or "") > 150:
            content_preview += "..."

        st.markdown(f"""
        <div class="article-card">
          <h4>
            <a href="{a.get('url','#')}" target="_blank" style="color:#1e1d1d; text-decoration:none;">
              {a.get('title','')}
            </a>
            &nbsp;<span class="score-badge">점수 {score}</span>
          </h4>
          <p>{content_preview}</p>
          <div class="article-meta">
            📅 {pub} &nbsp;|&nbsp; 📌 {src} &nbsp;|&nbsp; 🏷️ {a.get('category','')}
            <br>{kw_html}
          </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="background:#e3f2fd;border-left:4px solid #1976d2;border-radius:8px;padding:16px 20px;color:#1565c0;">
      📭 수집된 기사가 없습니다. 위의 <strong>뉴스 수집 시작</strong> 버튼을 눌러 수집을 시작하세요.
    </div>
    """, unsafe_allow_html=True)
