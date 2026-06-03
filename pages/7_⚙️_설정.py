"""pages/7_⚙️_설정.py - 서비스 설정 관리 페이지"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import yaml
from pathlib import Path
from dotenv import load_dotenv, set_key

load_dotenv()

st.set_page_config(page_title="설정 | STS뉴스레터", page_icon="⚙️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
* { font-family:'Noto Sans KR',sans-serif!important; }
.page-header { background:linear-gradient(135deg,#1e1d1d,#b01413); color:#fff; padding:24px 32px; border-radius:12px; margin-bottom:24px; }
.page-header h2 { margin:0 0 4px; font-size:24px; font-weight:900; }
.page-header p  { margin:0; font-size:13px; color:rgba(255,255,255,0.7); }
.setting-box { background:#fff; border:1px solid #e0e0e0; border-radius:10px; padding:20px; margin-bottom:16px; }
.setting-box h3 { margin:0 0 14px; font-size:15px; color:#b01413; font-weight:700;
                  border-bottom:2px solid #f5f5f5; padding-bottom:8px; }
.stButton>button { background:linear-gradient(135deg,#b01413,#8b0000)!important;
                   color:#fff!important; border:none!important; border-radius:8px!important; font-weight:700!important; }
.info-tip { background:#e3f2fd; border-left:3px solid #1976d2; border-radius:6px;
            padding:10px 14px; font-size:12px; color:#1565c0; margin-top:8px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="page-header">
  <h2>⚙️ 서비스 설정</h2>
  <p>LLM API, 이메일 SMTP, 회사정보, 발송 스케줄 설정</p>
</div>
""", unsafe_allow_html=True)

# ── 경로 ──────────────────────────────────────────────────
APP_DIR  = Path(__file__).parent.parent
CFG_PATH = APP_DIR / "config.yaml"
ENV_PATH = APP_DIR / ".env"

def load_cfg():
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_cfg(cfg: dict):
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

cfg = load_cfg()

tab_llm, tab_email, tab_company, tab_schedule, tab_env = st.tabs([
    "🤖 LLM 설정", "📮 이메일 SMTP", "🏢 회사 정보", "⏰ 발송 스케줄", "🔑 API 키"
])

# ── 탭1: LLM 설정 ────────────────────────────────────────
with tab_llm:
    st.markdown('<div class="setting-box">', unsafe_allow_html=True)
    st.markdown("### 🤖 LLM 설정")

    nl_cfg = cfg.get("newsletter", {})
    provider = st.selectbox(
        "LLM 제공자",
        ["anthropic", "openai", "mock"],
        index=["anthropic", "openai", "mock"].index(nl_cfg.get("llm_provider", "anthropic")),
        help="anthropic(Claude)를 기본으로 권장합니다."
    )
    model_map = {
        "anthropic": ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001"],
        "openai":    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
        "mock":      ["mock"],
    }
    current_model = nl_cfg.get("llm_model", "claude-sonnet-4-6")
    model_list = model_map.get(provider, ["mock"])
    model_idx = model_list.index(current_model) if current_model in model_list else 0
    model = st.selectbox("LLM 모델", model_list, index=model_idx)
    max_articles = st.slider("뉴스레터에 포함할 최대 기사 수", 5, 20, nl_cfg.get("max_articles", 10))

    st.markdown("""
    <div class="info-tip">
    💡 <strong>claude-sonnet-4-6</strong>: 비용·품질 최적 균형 (권장)<br>
    💡 <strong>claude-opus-4-8</strong>: 최고 품질, 높은 비용<br>
    💡 <strong>mock</strong>: API 키 없이 샘플 데이터 테스트
    </div>
    """, unsafe_allow_html=True)

    if st.button("💾 LLM 설정 저장", key="save_llm"):
        cfg["newsletter"]["llm_provider"] = provider
        cfg["newsletter"]["llm_model"]    = model
        cfg["newsletter"]["max_articles"] = max_articles
        save_cfg(cfg)
        st.success("✅ LLM 설정이 저장되었습니다.")

    st.markdown('</div>', unsafe_allow_html=True)

# ── 탭2: 이메일 SMTP ─────────────────────────────────────
with tab_email:
    st.markdown('<div class="setting-box">', unsafe_allow_html=True)
    st.markdown("### 📮 네이버 SMTP 설정")

    em_cfg = cfg.get("email", {})
    smtp_host    = st.text_input("SMTP 호스트", value=em_cfg.get("smtp_host", "smtp.naver.com"))
    smtp_port    = st.number_input("SMTP 포트", value=int(em_cfg.get("smtp_port", 587)), step=1)
    sender_name  = st.text_input("발신자 이름", value=em_cfg.get("sender_name", "토탈머티리얼즈 뉴스레터"))
    sender_email = st.text_input("발신 이메일", value=em_cfg.get("sender_email", "total_materials@naver.com"))
    rate_limit   = st.slider("초당 발송 수 제한", 1, 10, int(em_cfg.get("rate_limit_per_second", 3)))
    max_retry    = st.slider("최대 재시도 횟수", 1, 5, int(em_cfg.get("max_retry", 3)))

    st.markdown("""
    <div class="info-tip">
    ⚠️ <strong>네이버 SMTP 활성화 방법</strong><br>
    1. 네이버 메일 → 환경설정 → POP3/IMAP 설정<br>
    2. SMTP 사용 <strong>체크</strong> 후 저장<br>
    3. 보안설정 → 외부 앱 비밀번호 설정 (2단계 인증 사용 시)
    </div>
    """, unsafe_allow_html=True)

    if st.button("💾 이메일 설정 저장", key="save_email"):
        cfg["email"]["smtp_host"]            = smtp_host
        cfg["email"]["smtp_port"]            = int(smtp_port)
        cfg["email"]["sender_name"]          = sender_name
        cfg["email"]["sender_email"]         = sender_email
        cfg["email"]["rate_limit_per_second"]= rate_limit
        cfg["email"]["max_retry"]            = max_retry
        save_cfg(cfg)
        st.success("✅ 이메일 설정이 저장되었습니다.")

    st.markdown('</div>', unsafe_allow_html=True)

# ── 탭3: 회사 정보 ───────────────────────────────────────
with tab_company:
    st.markdown('<div class="setting-box">', unsafe_allow_html=True)
    st.markdown("### 🏢 회사 정보 (뉴스레터 푸터에 표시)")

    co_cfg = cfg.get("company", {})
    col_a, col_b = st.columns(2)
    with col_a:
        co_name    = st.text_input("회사명", value=co_cfg.get("name", "토탈머티리얼즈"))
        co_ceo     = st.text_input("대표자명", value=co_cfg.get("ceo", "백우혁"))
        co_email   = st.text_input("회사 이메일", value=co_cfg.get("email", "total_materials@naver.com"))
        co_phone   = st.text_input("전화번호", value=co_cfg.get("phone", "010-4733-9821"))
    with col_b:
        co_biz     = st.text_input("사업 분야", value=co_cfg.get("business", "STS/AL/CU/특수강 etc · 원자재 컨설팅 및 개발"))
        co_web     = st.text_input("웹사이트", value=co_cfg.get("website", "https://www.steelinfosys.com"))
        co_addr_an = st.text_input("안산사무소 주소", value=co_cfg.get("address_ansan", "경기도 안산시 단원구 별망로459번길 109 (목내동) 1층 105호"))
        co_addr_hq = st.text_input("본사 주소", value=co_cfg.get("address_hq", "서울특별시 금천구 가산디지털2로 40, 3층(가산동)"))

    if st.button("💾 회사 정보 저장", key="save_company"):
        cfg["company"] = {
            "name": co_name, "ceo": co_ceo, "email": co_email,
            "phone": co_phone, "business": co_biz, "website": co_web,
            "address_ansan": co_addr_an, "address_hq": co_addr_hq,
        }
        save_cfg(cfg)
        st.success("✅ 회사 정보가 저장되었습니다.")

    st.markdown('</div>', unsafe_allow_html=True)

# ── 탭4: 발송 스케줄 ─────────────────────────────────────
with tab_schedule:
    st.markdown('<div class="setting-box">', unsafe_allow_html=True)
    st.markdown("### ⏰ 발송 스케줄 설정")

    sc_cfg = cfg.get("schedule", {})
    day_map = {"monday":"월요일","tuesday":"화요일","wednesday":"수요일",
               "thursday":"목요일","friday":"금요일","saturday":"토요일","sunday":"일요일"}
    day_keys = list(day_map.keys())
    day_labels = list(day_map.values())
    cur_day = sc_cfg.get("day_of_week", "monday")
    day_idx = day_keys.index(cur_day) if cur_day in day_keys else 0

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        day_label = st.selectbox("발송 요일", day_labels, index=day_idx)
        day_of_week = day_keys[day_labels.index(day_label)]
    with col_s2:
        hour = st.number_input("발송 시간 (시)", min_value=0, max_value=23,
                               value=int(sc_cfg.get("hour", 8)))
    with col_s3:
        minute = st.number_input("발송 시간 (분)", min_value=0, max_value=59,
                                 value=int(sc_cfg.get("minute", 0)))

    st.info(f"⏰ 현재 설정: 매주 **{day_label}** 오전/오후 **{hour:02d}:{minute:02d}** 발송")

    if st.button("💾 스케줄 설정 저장", key="save_schedule"):
        cfg["schedule"]["day_of_week"] = day_of_week
        cfg["schedule"]["hour"]        = int(hour)
        cfg["schedule"]["minute"]      = int(minute)
        save_cfg(cfg)
        st.success("✅ 발송 스케줄이 저장되었습니다.")

    st.markdown('</div>', unsafe_allow_html=True)

# ── 탭5: API 키 관리 ─────────────────────────────────────
with tab_env:
    st.markdown('<div class="setting-box">', unsafe_allow_html=True)
    st.markdown("### 🔑 API 키 설정")
    st.warning("⚠️ API 키는 .env 파일에 저장됩니다. 외부에 공유하지 마세요.")

    anthropic_key = st.text_input(
        "Anthropic API Key (Claude)",
        value=os.getenv("ANTHROPIC_API_KEY", ""),
        type="password",
        placeholder="sk-ant-...",
        help="https://console.anthropic.com 에서 발급"
    )
    openai_key = st.text_input(
        "OpenAI API Key (선택)",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        placeholder="sk-...",
    )
    smtp_user = st.text_input(
        "네이버 SMTP 아이디",
        value=os.getenv("SMTP_USER", "total_materials@naver.com"),
        placeholder="your_id@naver.com",
    )
    smtp_pass = st.text_input(
        "네이버 SMTP 비밀번호",
        value=os.getenv("SMTP_PASSWORD", ""),
        type="password",
        help="네이버 메일 → 환경설정 → 외부앱 비밀번호"
    )

    col_k1, col_k2 = st.columns(2)
    with col_k1:
        kakao_api = st.text_input("카카오 API Key", value=os.getenv("KAKAO_API_KEY", ""), type="password")
    with col_k2:
        kakao_sender = st.text_input("카카오 발신번호", value=os.getenv("KAKAO_SENDER_PHONE", "010-4733-9821"))

    if st.button("💾 API 키 저장", key="save_env"):
        if not ENV_PATH.exists():
            ENV_PATH.touch()
        pairs = [
            ("ANTHROPIC_API_KEY", anthropic_key),
            ("OPENAI_API_KEY",    openai_key),
            ("SMTP_USER",         smtp_user),
            ("SMTP_PASSWORD",     smtp_pass),
            ("SMTP_HOST",         "smtp.naver.com"),
            ("SMTP_PORT",         "587"),
            ("KAKAO_API_KEY",     kakao_api),
            ("KAKAO_SENDER_PHONE",kakao_sender),
        ]
        for key, val in pairs:
            if val:
                set_key(str(ENV_PATH), key, val)
        st.success("✅ API 키가 .env 파일에 저장되었습니다. 앱을 재시작하면 적용됩니다.")

    st.markdown('</div>', unsafe_allow_html=True)

    # .env 현재 상태 확인
    with st.expander("📄 .env 파일 현재 상태 (키 이름만 표시)"):
        if ENV_PATH.exists():
            lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
            for line in lines:
                if "=" in line and not line.startswith("#"):
                    key_name = line.split("=")[0]
                    has_val  = len(line.split("=", 1)[1]) > 0
                    icon     = "✅" if has_val else "❌"
                    st.text(f"{icon}  {key_name}")
        else:
            st.warning(".env 파일이 없습니다. 위에서 저장하면 생성됩니다.")
