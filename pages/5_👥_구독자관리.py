"""pages/5_👥_구독자관리.py - 구독자 관리 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import csv, io
from datetime import datetime

st.set_page_config(page_title="구독자 관리 | STS뉴스레터", page_icon="👥", layout="wide")

from db.database import init_db, get_subscribers, upsert_subscriber, delete_subscriber, get_subscriber_count

init_db()

# 초기 구독자 CSV 로드 (DB가 비어 있을 때)
def load_initial_subscribers():
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "subscribers.csv")
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                upsert_subscriber({
                    "name": row.get("name",""),
                    "email": row.get("email",""),
                    "phone": row.get("phone",""),
                    "group_name": row.get("group_name",""),
                    "email_subscribed": int(row.get("email_subscribed", 1)),
                    "kakao_subscribed": int(row.get("kakao_subscribed", 1)),
                })

stats = get_subscriber_count()
if stats["total"] == 0:
    load_initial_subscribers()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
* { font-family:'Noto Sans KR',sans-serif!important; }
.page-header { background:linear-gradient(135deg,#1e1d1d,#1a237e); color:#fff; padding:24px 32px; border-radius:12px; margin-bottom:24px; }
.page-header h2 { margin:0 0 4px; font-size:24px; font-weight:900; }
.page-header p  { margin:0; font-size:13px; color:rgba(255,255,255,0.7); }
.stButton>button { background:linear-gradient(135deg,#b01413,#8b0000)!important; color:#fff!important; border:none!important; border-radius:8px!important; font-weight:700!important; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
  <h2>👥 구독자 관리</h2>
  <p>이메일 및 카카오 알림 구독자 등록·수정·삭제 관리</p>
</div>
""", unsafe_allow_html=True)

# ── KPI ─────────────────────────────────────────────────
stats = get_subscriber_count()
col1, col2, col3, col4 = st.columns(4)
col1.metric("전체 구독자", f"{stats['total']}명")
col2.metric("이메일 구독", f"{stats['active']}명")
subs_all = get_subscribers(active_only=False)
kakao_cnt = sum(1 for s in subs_all if s.get("kakao_subscribed", 1))
col3.metric("카카오 구독", f"{kakao_cnt}명")
groups = list(set(s.get("group_name","") for s in subs_all if s.get("group_name","")))
col4.metric("그룹 수", f"{len(groups)}개")

st.markdown("---")
tab_list, tab_add, tab_upload = st.tabs(["📋 구독자 목록", "➕ 구독자 추가", "📂 CSV 업로드"])

# ── 탭1: 구독자 목록 ─────────────────────────────────────
with tab_list:
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        search = st.text_input("🔎 이름/이메일 검색")
    with col_f2:
        grp_opts = ["전체"] + sorted(groups)
        sel_grp  = st.selectbox("그룹 필터", grp_opts)
    with col_f3:
        show_inactive = st.checkbox("해지 구독자 포함", value=False)

    subs = get_subscribers(active_only=not show_inactive)
    if search:
        subs = [s for s in subs if search.lower() in s["name"].lower() or search.lower() in s["email"].lower()]
    if sel_grp != "전체":
        subs = [s for s in subs if s.get("group_name","") == sel_grp]

    if subs:
        df = pd.DataFrame([{
            "ID":      s["id"],
            "이름":    s["name"],
            "이메일":  s["email"][:3]+"***@"+s["email"].split("@")[-1],
            "이메일(원본)": s["email"],
            "전화번호": s.get("phone",""),
            "그룹":    s.get("group_name",""),
            "이메일수신": "✅" if s.get("email_subscribed",1) else "❌",
            "카카오수신": "✅" if s.get("kakao_subscribed",1) else "❌",
            "등록일":  s.get("created_at","")[:10],
        } for s in subs])

        display_df = df.drop(columns=["이메일(원본)","ID"])
        st.dataframe(display_df, use_container_width=True, height=350, hide_index=True)

        # 삭제
        del_email = st.selectbox("삭제할 구독자 선택", [""] + [s["email"] for s in subs])
        col_del1, col_del2 = st.columns([3, 1])
        with col_del2:
            if st.button("🗑️ 삭제", disabled=not del_email):
                delete_subscriber(del_email)
                st.success(f"✅ {del_email} 삭제 완료")
                st.rerun()

        # CSV 내보내기
        csv_buf = io.StringIO()
        export_df = df[["이름","이메일(원본)","전화번호","그룹","이메일수신","카카오수신","등록일"]]
        export_df.columns = ["name","email","phone","group_name","email_subscribed","kakao_subscribed","created_at"]
        export_df.to_csv(csv_buf, index=False, encoding="utf-8-sig")
        st.download_button("📥 CSV 내보내기", data=csv_buf.getvalue().encode("utf-8-sig"),
                            file_name=f"subscribers_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv")
    else:
        st.info("검색 결과가 없습니다.")

# ── 탭2: 구독자 추가 ─────────────────────────────────────
with tab_add:
    with st.form("add_subscriber_form"):
        st.markdown("#### ➕ 새 구독자 등록")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            new_name  = st.text_input("이름 *", placeholder="홍길동")
            new_email = st.text_input("이메일 *", placeholder="hong@naver.com")
        with col_a2:
            new_phone = st.text_input("전화번호", placeholder="010-1234-5678")
            new_group = st.text_input("그룹", placeholder="영업팀")

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            email_sub = st.checkbox("이메일 구독", value=True)
        with col_b2:
            kakao_sub = st.checkbox("카카오 구독", value=True)

        submitted = st.form_submit_button("✅ 구독자 추가", use_container_width=True)
        if submitted:
            if not new_name or not new_email:
                st.error("이름과 이메일은 필수입니다.")
            else:
                upsert_subscriber({
                    "name": new_name, "email": new_email,
                    "phone": new_phone, "group_name": new_group,
                    "email_subscribed": int(email_sub),
                    "kakao_subscribed": int(kakao_sub),
                })
                st.success(f"✅ {new_name} ({new_email}) 등록 완료!")
                st.rerun()

# ── 탭3: CSV 업로드 ─────────────────────────────────────
with tab_upload:
    st.markdown("#### 📂 CSV 파일로 일괄 등록")
    st.markdown("""
    **CSV 컬럼 형식:**
    `name, email, phone, group_name, email_subscribed(1/0), kakao_subscribed(1/0)`
    """)

    sample_csv = "name,email,phone,group_name,email_subscribed,kakao_subscribed\n김철수,kim@naver.com,010-1234-5678,영업팀,1,1\n이영희,lee@naver.com,010-2345-6789,구매팀,1,0"
    st.download_button("📥 샘플 CSV 다운로드", data=sample_csv.encode("utf-8-sig"),
                        file_name="subscribers_sample.csv", mime="text/csv")

    uploaded = st.file_uploader("CSV 파일 업로드", type=["csv"])
    if uploaded:
        try:
            df_up = pd.read_csv(uploaded, encoding="utf-8-sig")
            st.dataframe(df_up.head(10), use_container_width=True, hide_index=True)
            st.info(f"총 {len(df_up)}명 미리보기 (상위 10명 표시)")

            if st.button("📥 일괄 등록", use_container_width=True):
                count = 0
                for _, row in df_up.iterrows():
                    upsert_subscriber({
                        "name": str(row.get("name","")),
                        "email": str(row.get("email","")),
                        "phone": str(row.get("phone","")),
                        "group_name": str(row.get("group_name","")),
                        "email_subscribed": int(row.get("email_subscribed", 1)),
                        "kakao_subscribed": int(row.get("kakao_subscribed", 1)),
                    })
                    count += 1
                st.success(f"✅ {count}명 일괄 등록 완료!")
                st.rerun()
        except Exception as e:
            st.error(f"CSV 파싱 오류: {e}")
