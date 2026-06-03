"""pages/6_📊_발송통계.py - 발송 통계 분석 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="발송 통계 | STS뉴스레터", page_icon="📊", layout="wide")

from db.database import init_db, get_send_logs, get_newsletters, get_send_stats, get_subscriber_count

init_db()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
* { font-family:'Noto Sans KR',sans-serif!important; }
.page-header { background:linear-gradient(135deg,#1e1d1d,#b01413); color:#fff; padding:24px 32px; border-radius:12px; margin-bottom:24px; }
.page-header h2 { margin:0 0 4px; font-size:24px; font-weight:900; }
.page-header p  { margin:0; font-size:13px; color:rgba(255,255,255,0.7); }
.stat-card { background:#fff; border:1px solid #e0e0e0; border-top:3px solid #b01413; border-radius:8px; padding:16px; text-align:center; }
.stat-card .val { font-size:28px; font-weight:900; color:#1e1d1d; }
.stat-card .lbl { font-size:12px; color:#888; margin-top:4px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
  <h2>📊 발송 통계</h2>
  <p>채널별 발송 현황 및 이력 분석</p>
</div>
""", unsafe_allow_html=True)

# ── 전체 요약 지표 ────────────────────────────────────────
logs = get_send_logs(limit=5000)
stats = get_send_stats()
sub_stats = get_subscriber_count()
newsletters = get_newsletters(limit=50)

email_logs   = [l for l in logs if l["channel"] == "email"]
kakao_logs   = [l for l in logs if l["channel"] == "kakao"]
email_ok     = len([l for l in email_logs if l["status"] == "success"])
email_fail   = len([l for l in email_logs if l["status"] == "failed"])
kakao_ok     = len([l for l in kakao_logs if l["status"] == "success"])
kakao_fail   = len([l for l in kakao_logs if l["status"] == "failed"])
total_send   = len(logs)
success_rate = round(len([l for l in logs if l["status"] == "success"]) / total_send * 100, 1) if total_send else 0

col1, col2, col3, col4, col5 = st.columns(5)
metrics = [
    ("📧 이메일 발송", email_ok, f"실패 {email_fail}건"),
    ("💬 카카오 발송", kakao_ok, f"실패 {kakao_fail}건"),
    ("📋 발송 뉴스레터", len(newsletters), "누적"),
    ("👥 구독자 수", sub_stats["active"], f"전체 {sub_stats['total']}명"),
    ("✅ 전체 성공률", f"{success_rate}%", f"총 {total_send}건"),
]
for col, (label, val, delta) in zip([col1, col2, col3, col4, col5], metrics):
    with col:
        st.metric(label, val, delta)

st.markdown("---")

# ── 채널별 성공/실패 차트 ─────────────────────────────────
import plotly.graph_objects as go
import plotly.express as px

tab1, tab2, tab3 = st.tabs(["📊 채널별 현황", "📋 발송 이력", "📰 뉴스레터별 통계"])

with tab1:
    col_c1, col_c2 = st.columns(2)

    with col_c1:
        st.markdown("#### 채널별 발송 성공/실패")
        fig_bar = go.Figure(data=[
            go.Bar(name="✅ 성공", x=["이메일", "카카오"],
                   y=[email_ok, kakao_ok],
                   marker_color=["#b01413", "#FEE500"],
                   text=[email_ok, kakao_ok], textposition="auto"),
            go.Bar(name="❌ 실패", x=["이메일", "카카오"],
                   y=[email_fail, kakao_fail],
                   marker_color=["#ffcdd2", "#ffe082"],
                   text=[email_fail, kakao_fail], textposition="auto"),
        ])
        fig_bar.update_layout(
            barmode="group", height=300,
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", y=1.1),
            font=dict(family="Noto Sans KR"),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_c2:
        st.markdown("#### 전체 발송 성공률")
        total_ok   = email_ok + kakao_ok
        total_fail = email_fail + kakao_fail
        if total_ok + total_fail > 0:
            fig_pie = go.Figure(data=[go.Pie(
                labels=["✅ 성공", "❌ 실패"],
                values=[total_ok, total_fail],
                marker_colors=["#b01413", "#ffcdd2"],
                hole=0.5,
                textinfo="label+percent",
            )])
            fig_pie.update_layout(
                height=300, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="white",
                font=dict(family="Noto Sans KR"),
                showlegend=False,
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("발송 데이터가 없습니다.")

with tab2:
    st.markdown("#### 발송 이력 상세")
    if logs:
        df = pd.DataFrame(logs)
        # 컬럼 정리
        show_cols = [c for c in ["channel", "recipient_masked", "status", "error_message", "sent_at"] if c in df.columns]
        df_show = df[show_cols].copy()
        df_show.columns = ["채널", "수신자", "상태", "오류내용", "발송시각"][:len(show_cols)]

        # 필터
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            ch_filter = st.selectbox("채널 필터", ["전체", "email", "kakao"])
        with col_f2:
            st_filter = st.selectbox("상태 필터", ["전체", "success", "failed"])

        if ch_filter != "전체":
            df_show = df_show[df_show["채널"] == ch_filter]
        if st_filter != "전체":
            df_show = df_show[df_show["상태"] == st_filter]

        st.dataframe(df_show, use_container_width=True, height=400, hide_index=True)

        csv = df_show.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("📥 CSV 다운로드", csv, "send_logs.csv", "text/csv")
    else:
        st.info("발송 이력이 없습니다.")

with tab3:
    st.markdown("#### 뉴스레터별 발송 결과")
    if newsletters:
        nl_rows = []
        for nl in newsletters:
            nl_id = nl["id"]
            nl_logs = [l for l in logs if str(l.get("newsletter_id", "")) == str(nl_id)]
            ok   = len([l for l in nl_logs if l["status"] == "success"])
            fail = len([l for l in nl_logs if l["status"] == "failed"])
            nl_rows.append({
                "Vol.": nl.get("volume", ""),
                "제목": nl.get("subject", "")[:50],
                "상태": nl.get("status", "draft").upper(),
                "발송성공": ok,
                "발송실패": fail,
                "발송일시": (nl.get("sent_at") or nl.get("created_at") or "")[:16],
            })
        df_nl = pd.DataFrame(nl_rows)
        st.dataframe(df_nl, use_container_width=True, height=400, hide_index=True)
    else:
        st.info("뉴스레터가 없습니다.")
