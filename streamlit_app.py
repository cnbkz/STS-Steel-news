"""
streamlit_app.py - STS정밀재 주간뉴스레터 서비스 메인 대시보드
철강정보원(steelinfosys.com) 디자인 레퍼런스 기반
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time

# ── 페이지 설정 ────────────────────────────────────────────
st.set_page_config(
    page_title="STS정밀재 뉴스레터 서비스",
    page_icon="🔩",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DB / 에이전트 초기화 ───────────────────────────────────
from db.database import init_db, get_subscribers, get_newsletters, get_send_logs, get_article_count, get_subscriber_count, get_send_stats

init_db()

# ── 전역 CSS ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');

* { font-family: 'Noto Sans KR', sans-serif !important; }

/* 사이드바 */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e1d1d 0%, #2d2c2c 100%);
    border-right: 3px solid #b01413;
}
section[data-testid="stSidebar"] * { color: #fff !important; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stRadio label { color: #ccc !important; }

/* 메트릭 카드 */
div[data-testid="metric-container"] {
    background: #fff;
    border: 1px solid #e0e0e0;
    border-top: 3px solid #b01413;
    border-radius: 8px;
    padding: 16px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
div[data-testid="metric-container"] label { color: #666 !important; font-size: 12px !important; }
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-size: 28px !important; font-weight: 900 !important; color: #1e1d1d !important;
}
div[data-testid="metric-container"] div[data-testid="stMetricDelta"] { font-size: 12px !important; }

/* 헤더 배너 */
.sts-header {
    background: linear-gradient(135deg, #1e1d1d 0%, #3d0000 50%, #b01413 100%);
    color: white;
    padding: 32px 40px;
    border-radius: 12px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.sts-header::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -10%;
    width: 300px;
    height: 300px;
    background: rgba(176,20,19,0.3);
    border-radius: 50%;
}
.sts-header h1 { font-size: 32px; font-weight: 900; margin: 0 0 8px; letter-spacing: -1px; }
.sts-header p { font-size: 14px; color: rgba(255,255,255,0.7); margin: 0; }

/* 섹션 제목 */
.section-title {
    font-size: 16px; font-weight: 700; color: #1e1d1d;
    border-left: 4px solid #b01413;
    padding-left: 12px;
    margin: 24px 0 16px;
}

/* 상태 배지 */
.badge-success { background: #e8f5e9; color: #2e7d32; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
.badge-failed  { background: #ffebee; color: #c62828; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
.badge-draft   { background: #e3f2fd; color: #1565c0; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
.badge-sent    { background: #f3e5f5; color: #6a1b9a; padding: 2px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }

/* 파이프라인 스텝 */
.pipeline-step {
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    padding: 16px;
    text-align: center;
    transition: all 0.2s;
    cursor: pointer;
}
.pipeline-step:hover { border-color: #b01413; box-shadow: 0 4px 12px rgba(176,20,19,0.15); }
.pipeline-step.active { border-color: #b01413; background: #fff8f8; }
.pipeline-icon { font-size: 32px; margin-bottom: 8px; }
.pipeline-label { font-size: 12px; font-weight: 700; color: #333; }
.pipeline-sublabel { font-size: 11px; color: #888; margin-top: 2px; }

/* 버튼 스타일 */
.stButton > button {
    background: linear-gradient(135deg, #b01413, #8b0000) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    padding: 10px 24px !important;
    transition: all 0.2s !important;
    width: 100% !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #8b0000, #600000) !important;
    box-shadow: 0 4px 12px rgba(176,20,19,0.35) !important;
    transform: translateY(-1px) !important;
}

/* 테이블 */
.dataframe { border: none !important; }
.dataframe thead tr th {
    background: #1e1d1d !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 12px !important;
}
.dataframe tbody tr:hover { background: #fff8f8 !important; }

/* 뉴스카드 */
.news-card {
    background: #fff;
    border: 1px solid #e8e8e8;
    border-left: 3px solid #b01413;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
    transition: all 0.15s;
}
.news-card:hover { box-shadow: 0 3px 12px rgba(0,0,0,0.1); transform: translateX(2px); }
.news-card h4 { margin: 0 0 6px; font-size: 14px; color: #1e1d1d; font-weight: 700; }
.news-card p  { margin: 0; font-size: 12px; color: #666; line-height: 1.6; }
.news-card .meta { font-size: 11px; color: #aaa; margin-top: 6px; }

/* 알림 스타일 */
.info-box {
    background: linear-gradient(135deg, #e3f2fd, #bbdefb);
    border-left: 4px solid #1976d2;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 12px 0;
    font-size: 13px;
    color: #1565c0;
}
.warn-box {
    background: linear-gradient(135deg, #fff3e0, #ffe0b2);
    border-left: 4px solid #e65100;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 12px 0;
    font-size: 13px;
    color: #bf360c;
}
</style>
""", unsafe_allow_html=True)

# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 20px 0 10px;">
        <div style="font-size:40px;">🔩</div>
        <div style="font-size:18px; font-weight:900; color:#fff; letter-spacing:-0.5px;">STS정밀재</div>
        <div style="font-size:12px; color:#b01413; font-weight:700;">뉴스레터 서비스</div>
        <div style="height:1px; background: rgba(255,255,255,0.1); margin: 16px 0;"></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**📋 메뉴**")
    st.page_link("streamlit_app.py", label="🏠 대시보드", icon="🏠")
    st.page_link("pages/1_📰_뉴스수집.py", label="뉴스 수집", icon="📰")
    st.page_link("pages/2_✍️_뉴스레터작성.py", label="뉴스레터 작성", icon="✍️")
    st.page_link("pages/3_📧_이메일발송.py", label="이메일 발송", icon="📧")
    st.page_link("pages/4_💬_카카오알림.py", label="카카오 알림", icon="💬")
    st.page_link("pages/5_👥_구독자관리.py", label="구독자 관리", icon="👥")
    st.page_link("pages/6_📊_발송통계.py", label="발송 통계", icon="📊")
    st.page_link("pages/7_⚙️_설정.py", label="설정", icon="⚙️")

    st.markdown("<div style='height:1px; background:rgba(255,255,255,0.1); margin:16px 0;'></div>", unsafe_allow_html=True)

    # 다음 발송 예정
    now = datetime.now()
    days_until_monday = (7 - now.weekday()) % 7
    if days_until_monday == 0 and now.hour >= 8:
        days_until_monday = 7
    next_send = (now + timedelta(days=days_until_monday)).replace(hour=8, minute=0, second=0)
    delta = next_send - now
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes = remainder // 60

    st.markdown(f"""
    <div style="background:rgba(176,20,19,0.2); border:1px solid rgba(176,20,19,0.4); border-radius:8px; padding:12px; text-align:center;">
        <div style="font-size:11px; color:#aaa;">⏰ 다음 발송 예정</div>
        <div style="font-size:20px; font-weight:900; color:#fff; margin:4px 0;">{hours}h {minutes}m</div>
        <div style="font-size:10px; color:#888;">{next_send.strftime('%m/%d (월) 08:00')}</div>
    </div>
    """, unsafe_allow_html=True)

# ── 메인 콘텐츠 ───────────────────────────────────────────

# 헤더 배너
st.markdown("""
<div class="sts-header">
    <h1>🔩 STS정밀재 주간뉴스레터 서비스</h1>
    <p>Steel Information System | 스테인리스 정밀재 전문 뉴스레터 자동화 플랫폼</p>
    <p style="margin-top:8px; font-size:12px;">steelinfosys.com 기반 뉴스 자동 수집 → LLM 작성 → 이메일·카카오톡 발송</p>
</div>
""", unsafe_allow_html=True)

# ── KPI 메트릭 ──────────────────────────────────────────
sub_stats = get_subscriber_count()
newsletters = get_newsletters(limit=5)
send_logs = get_send_logs(limit=200)
article_count = get_article_count()

total_sent = len([l for l in send_logs if l["channel"] == "email" and l["status"] == "success"])
total_kakao = len([l for l in send_logs if l["channel"] == "kakao" and l["status"] == "success"])
success_rate = 0
if send_logs:
    success = len([l for l in send_logs if l["status"] == "success"])
    success_rate = round(success / len(send_logs) * 100, 1)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("📧 이메일 발송", f"{total_sent:,}건", delta="이번 달")
with col2:
    st.metric("💬 카카오 알림", f"{total_kakao:,}건", delta="이번 달")
with col3:
    st.metric("👥 구독자 수", f"{sub_stats['active']:,}명", delta=f"전체 {sub_stats['total']}명")
with col4:
    st.metric("📰 수집 기사", f"{article_count:,}건", delta="누계")
with col5:
    st.metric("✅ 발송 성공률", f"{success_rate}%", delta=None)

st.markdown("---")

# ── 전체 파이프라인 실행 섹션 ─────────────────────────────
st.markdown('<div class="section-title">⚡ 전체 파이프라인 실행</div>', unsafe_allow_html=True)

col_p1, col_p2, col_p3, col_p4, col_arrow = st.columns([2, 2, 2, 2, 1])

with col_p1:
    st.markdown("""
    <div class="pipeline-step">
        <div class="pipeline-icon">📰</div>
        <div class="pipeline-label">STEP 1</div>
        <div class="pipeline-sublabel">뉴스 수집</div>
    </div>
    """, unsafe_allow_html=True)
with col_p2:
    st.markdown("""
    <div class="pipeline-step">
        <div class="pipeline-icon">✍️</div>
        <div class="pipeline-label">STEP 2</div>
        <div class="pipeline-sublabel">뉴스레터 작성</div>
    </div>
    """, unsafe_allow_html=True)
with col_p3:
    st.markdown("""
    <div class="pipeline-step">
        <div class="pipeline-icon">📧</div>
        <div class="pipeline-label">STEP 3</div>
        <div class="pipeline-sublabel">이메일 발송</div>
    </div>
    """, unsafe_allow_html=True)
with col_p4:
    st.markdown("""
    <div class="pipeline-step">
        <div class="pipeline-icon">💬</div>
        <div class="pipeline-label">STEP 4</div>
        <div class="pipeline-sublabel">카카오 알림</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
with col_btn2:
    run_all = st.button("🚀 전체 파이프라인 자동 실행", use_container_width=True)

if run_all:
    from agents.news_collector import NewsCollector, get_mock_articles
    from agents.content_writer import ContentWriter
    from agents.email_sender import EmailSender
    from agents.kakao_notifier import KakaoNotifier
    from db.database import (
        insert_article, save_newsletter, update_newsletter_status,
        get_subscribers as db_get_subscribers, get_next_volume, log_send
    )

    progress_bar = st.progress(0, text="파이프라인 시작...")
    status_area = st.empty()

    try:
        # STEP 1 – 뉴스 수집
        status_area.info("📰 STEP 1: 뉴스 수집 중...")
        progress_bar.progress(5, "뉴스 수집 시작...")

        try:
            collector = NewsCollector()
            articles = collector.collect(progress_callback=lambda p, t: progress_bar.progress(int(5 + p * 20), t))
        except Exception:
            articles = get_mock_articles()

        for a in articles:
            insert_article({**a, "score": a.get("score", 0)})
        progress_bar.progress(25, f"✅ 뉴스 수집 완료: {len(articles)}건")

        # STEP 2 – 뉴스레터 작성
        status_area.info("✍️ STEP 2: 뉴스레터 작성 중...")
        import yaml
        cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        provider = cfg.get("newsletter", {}).get("llm_provider", "mock")
        model = cfg.get("newsletter", {}).get("llm_model", "gpt-4o")
        writer = ContentWriter(model=model, provider=provider)
        newsletter = writer.write_newsletter(
            articles,
            progress_callback=lambda p, t: progress_bar.progress(int(25 + p * 25), t)
        )
        progress_bar.progress(50, "✅ 뉴스레터 작성 완료")

        vol = get_next_volume()
        nl_id = save_newsletter({
            "volume": vol,
            "week_label": newsletter["subject"],
            "subject": newsletter["subject"],
            "html_body": newsletter["html_body"],
            "plain_text": newsletter["plain_text"],
            "kakao_summary": newsletter["kakao_summary"],
            "headline": newsletter["headline"],
            "status": "draft",
        })

        # STEP 3 – 이메일 발송
        status_area.info("📧 STEP 3: 이메일 발송 중...")
        subscribers = db_get_subscribers(active_only=True)
        if not subscribers:
            import csv
            csv_path = os.path.join(os.path.dirname(__file__), "data", "subscribers.csv")
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                subscribers = [{"name": r["name"], "email": r["email"], "phone": r.get("phone", ""),
                                "kakao_subscribed": int(r.get("kakao_subscribed", 1))} for r in reader]

        email_cfg = cfg.get("email", {})
        simulation = not bool(os.getenv("SMTP_USER", ""))
        sender = EmailSender(
            smtp_host=email_cfg.get("smtp_host"),
            smtp_port=email_cfg.get("smtp_port", 587),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            sender_name=email_cfg.get("sender_name", "STS정밀재 뉴스레터"),
            sender_email=email_cfg.get("sender_email") or os.getenv("SMTP_USER", ""),
            simulation_mode=simulation,
        )
        email_result = sender.send_newsletter(
            subscribers, newsletter,
            progress_callback=lambda p, t: progress_bar.progress(int(50 + p * 25), t)
        )
        for log in email_result["logs"]:
            log_send(nl_id, "email", log["email"].replace("***@", "@"), log["status"])
        progress_bar.progress(75, f"✅ 이메일 발송 완료: {email_result['success']}/{email_result['total']}건 성공")

        # STEP 4 – 카카오 알림
        status_area.info("💬 STEP 4: 카카오 알림 발송 중...")
        notifier = KakaoNotifier(simulation_mode=True)
        kakao_result = notifier.send_notification(
            subscribers, newsletter, writer,
            progress_callback=lambda p, t: progress_bar.progress(int(75 + p * 20), t)
        )
        for log in kakao_result["logs"]:
            log_send(nl_id, "kakao", log.get("phone", "unknown"), log["status"])

        update_newsletter_status(nl_id, "sent", datetime.now().isoformat())
        progress_bar.progress(100, "🎉 전체 파이프라인 완료!")
        status_area.success(f"""
        ✅ **전체 파이프라인 실행 완료!**
        - 뉴스 수집: {len(articles)}건
        - 이메일 발송: {email_result['success']}/{email_result['total']}건 성공
        - 카카오 알림: {kakao_result['success']}/{kakao_result['total']}건 성공
        """)
        st.balloons()

    except Exception as e:
        status_area.error(f"❌ 파이프라인 오류: {str(e)}")

# ── 최근 뉴스레터 이력 ────────────────────────────────────
st.markdown("---")
col_left, col_right = st.columns([3, 2])

with col_left:
    st.markdown('<div class="section-title">📋 최근 발송 이력</div>', unsafe_allow_html=True)
    newsletters = get_newsletters(limit=8)
    if newsletters:
        for nl in newsletters:
            status_badge = {
                "sent": '<span class="badge-sent">✅ 발송완료</span>',
                "draft": '<span class="badge-draft">📝 초안</span>',
                "failed": '<span class="badge-failed">❌ 실패</span>',
            }.get(nl.get("status", "draft"), '<span class="badge-draft">초안</span>')

            sent_at = nl.get("sent_at", nl.get("created_at", ""))[:16] if nl.get("sent_at") or nl.get("created_at") else "-"
            st.markdown(f"""
            <div class="news-card">
                <h4>Vol.{nl.get('volume','?')} &nbsp; {status_badge}</h4>
                <p>{nl.get('subject', '(제목 없음)')}</p>
                <div class="meta">📅 {sent_at} &nbsp;|&nbsp; {nl.get('headline','')[:60]+'...' if nl.get('headline','') else ''}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-box">📭 발송된 뉴스레터가 없습니다. 파이프라인을 실행해주세요.</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="section-title">📊 발송 현황</div>', unsafe_allow_html=True)
    stats = get_send_stats()
    if stats:
        df_stats = pd.DataFrame(stats)
        import plotly.graph_objects as go
        email_s = sum(r["cnt"] for r in stats if r["channel"] == "email" and r["status"] == "success")
        email_f = sum(r["cnt"] for r in stats if r["channel"] == "email" and r["status"] == "failed")
        kakao_s = sum(r["cnt"] for r in stats if r["channel"] == "kakao" and r["status"] == "success")
        kakao_f = sum(r["cnt"] for r in stats if r["channel"] == "kakao" and r["status"] == "failed")

        fig = go.Figure(data=[
            go.Bar(name='✅ 성공', x=['이메일', '카카오'], y=[email_s, kakao_s],
                   marker_color=['#b01413', '#FEE500'], text=[email_s, kakao_s], textposition='auto'),
            go.Bar(name='❌ 실패', x=['이메일', '카카오'], y=[email_f, kakao_f],
                   marker_color=['#ffcdd2', '#ffe0b2'], text=[email_f, kakao_f], textposition='auto'),
        ])
        fig.update_layout(
            barmode='group',
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=280,
            margin=dict(l=0, r=0, t=20, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(family="Noto Sans KR"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown('<div class="info-box">발송 데이터가 아직 없습니다.</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">👥 구독자 현황</div>', unsafe_allow_html=True)
    subs = get_subscribers(active_only=False)
    if subs:
        df_subs = pd.DataFrame(subs)[["name", "group_name", "email_subscribed", "kakao_subscribed"]]
        df_subs.columns = ["이름", "그룹", "이메일", "카카오"]
        df_subs["이메일"] = df_subs["이메일"].map({1: "✅", 0: "❌"})
        df_subs["카카오"] = df_subs["카카오"].map({1: "✅", 0: "❌"})
        st.dataframe(df_subs, use_container_width=True, height=200, hide_index=True)
    else:
        st.markdown('<div class="info-box">구독자가 없습니다.</div>', unsafe_allow_html=True)

# 푸터
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#aaa; font-size:12px; padding: 16px 0;">
    🔩 STS정밀재 뉴스레터 서비스 v1.0 &nbsp;|&nbsp;
    <a href="https://steelinfosys.com" target="_blank" style="color:#b01413; text-decoration:none;">steelinfosys.com</a> 기반
    &nbsp;|&nbsp; 철강인의 지성, 혁신, 가치
</div>
""", unsafe_allow_html=True)
