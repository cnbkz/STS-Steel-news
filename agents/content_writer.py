"""
content_writer.py - LLM 기반 뉴스레터 작성 에이전트
OpenAI GPT-4o / Anthropic Claude / Mock 모드 지원
"""
import os
import json
import sys
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """당신은 STS(스테인리스강) 정밀재 전문 뉴스레터 에디터입니다.
수집된 철강 뉴스를 바탕으로 STS 정밀재 업계 종사자를 위한 주간 뉴스레터를 작성합니다.

작성 지침:
- 문체: 전문적이고 간결한 비즈니스 한국어
- STS 정밀재와 직접 관련된 정보를 우선 배치
- 니켈, 크롬 등 원자재 가격 동향을 반드시 포함
- 국내외 시장 동향을 구분하여 설명
- 각 뉴스는 핵심을 2~3문장으로 요약
- 전망 섹션에서는 다음 주 주목할 포인트 제시"""

USER_PROMPT_TEMPLATE = """다음 뉴스 기사들을 바탕으로 STS 정밀재 주간 뉴스레터를 작성해주세요.

[이번 주 수집 기사]
{articles_text}

[요청 출력 형식 - JSON]
{{
  "subject": "이메일 제목 (예: STS정밀재 주간뉴스레터 Vol.N | YYYY년 MM월 W주)",
  "headline": "이번 주 핵심 요약 1~2문장",
  "market_summary": "국내외 STS 시장 동향 요약 (3~5문장)",
  "price_trends": "니켈/크롬/STS 가격 동향 (2~4문장)",
  "top_news": [
    {{"title": "뉴스 제목", "summary": "2~3문장 요약", "url": "기사 URL"}},
    ...
  ],
  "outlook": "다음 주 전망 및 주목 포인트 (2~3문장)",
  "kakao_summary": "카카오톡 발송용 3줄 요약 (각 줄 50자 이내)"
}}"""


class ContentWriter:
    def __init__(self, model: str = "claude-sonnet-4-6", provider: str = "anthropic"):
        self.model = model
        self.provider = provider
        self._openai_client = None
        self._anthropic_client = None

    # ── 공개 메서드 ──────────────────────────────────────────
    def write_newsletter(self, articles: list[dict], week_info: dict = None, progress_callback=None) -> dict:
        if progress_callback:
            progress_callback(0.1, "📝 뉴스 데이터 준비 중...")

        if week_info is None:
            now = datetime.now()
            week_num = now.isocalendar()[1]
            week_info = {
                "year": now.year,
                "month": now.month,
                "week": week_num,
                "date_range": f"{now.strftime('%Y.%m.%d')} ~ {(now + timedelta(days=6)).strftime('%m.%d')}",
            }

        articles_text = self._format_articles_for_prompt(articles)

        if progress_callback:
            progress_callback(0.3, "🤖 LLM에 뉴스레터 작성 요청 중...")

        try:
            if self.provider == "openai":
                content = self._call_openai(articles_text)
            elif self.provider == "anthropic":
                content = self._call_anthropic(articles_text)
            else:
                content = self._mock_write(articles, week_info)
        except Exception as e:
            logger.warning(f"LLM 호출 실패 ({e}), mock 데이터 사용")
            content = self._mock_write(articles, week_info)

        if progress_callback:
            progress_callback(0.7, "🎨 HTML 템플릿 렌더링 중...")

        html_body = self._render_html(content, articles, week_info)
        plain_text = self._render_plain(content, week_info)

        if progress_callback:
            progress_callback(1.0, "✅ 뉴스레터 작성 완료!")

        return {
            "subject": content.get("subject", f"STS정밀재 주간뉴스레터 {week_info['year']}년 {week_info['month']}월"),
            "html_body": html_body,
            "plain_text": plain_text,
            "kakao_summary": content.get("kakao_summary", ""),
            "headline": content.get("headline", ""),
            "sections": content,
        }

    def generate_kakao_message(self, newsletter: dict, subscriber_name: str) -> str:
        kakao_summary = newsletter.get("kakao_summary", "")
        headline = newsletter.get("headline", "")

        lines = [l.strip() for l in kakao_summary.split("\n") if l.strip()]
        while len(lines) < 3:
            lines.append("이번 주 STS 시장 동향을 이메일에서 확인하세요.")

        msg = f"""[STS정밀재 주간뉴스레터]

{subscriber_name} 님, 이번 주 뉴스레터가 발송되었습니다.

📌 이번 주 핵심
{headline}

📋 주요 뉴스 요약
1. {lines[0]}
2. {lines[1]}
3. {lines[2]}

📧 상세 내용은 이메일을 확인해주세요.

감사합니다.
철강정보원 (www.steelinfosys.com)"""
        return msg

    # ── LLM 호출 ─────────────────────────────────────────────
    def _call_openai(self, articles_text: str) -> dict:
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai 패키지가 설치되지 않았습니다.")

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-..."):
            raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")

        if self._openai_client is None:
            self._openai_client = openai.OpenAI(api_key=api_key)

        prompt = USER_PROMPT_TEMPLATE.format(articles_text=articles_text)
        response = self._openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        return json.loads(response.choices[0].message.content)

    def _call_anthropic(self, articles_text: str) -> dict:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic 패키지가 설치되지 않았습니다.")

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key or api_key.startswith("sk-ant-..."):
            raise RuntimeError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

        if self._anthropic_client is None:
            self._anthropic_client = anthropic.Anthropic(api_key=api_key)

        prompt = USER_PROMPT_TEMPLATE.format(articles_text=articles_text)
        message = self._anthropic_client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt + "\n\nJSON 형식으로만 응답하세요."}],
        )
        text = message.content[0].text
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])

    # ── Mock 데이터 ───────────────────────────────────────────
    def _mock_write(self, articles: list[dict], week_info: dict) -> dict:
        now = datetime.now()
        top_news = []
        for a in articles[:5]:
            top_news.append({
                "title": a["title"],
                "summary": a["content"][:120] + "..." if len(a.get("content", "")) > 120 else a.get("content", ""),
                "url": a["url"],
            })

        return {
            "subject": f"STS정밀재 주간뉴스레터 Vol.{week_info.get('week', now.isocalendar()[1])} | {now.strftime('%Y년 %m월')} {now.isocalendar()[1]}주차",
            "headline": "니켈 가격 약보합 속 국내 STS 정밀재 시장 관망세 지속, 하반기 수요 회복 기대",
            "market_summary": (
                "이번 주 국내 STS 정밀재 시장은 니켈 가격 하락세와 중국산 수입재 증가 우려로 "
                "전반적인 약보합 흐름을 보였습니다. 304 2B 냉연 가격은 전주 대비 소폭 하락한 반면, "
                "316L은 보합세를 유지했습니다. 해외 시장에서는 중국 내수 수요 부진이 지속되면서 "
                "수출 물량이 아시아 시장으로 유입될 가능성이 높아지고 있습니다."
            ),
            "price_trends": (
                "LME 니켈 현물가격은 이번 주 톤당 16,800달러 수준으로 전주 대비 약 120달러 하락했습니다. "
                "크롬 합금철은 보합세를 유지하며 톤당 240달러 수준에서 거래되고 있습니다. "
                "국내 STS 304 2B 0.5mm 기준 가격은 전주 대비 약 2만원 하락한 220만원 내외에 형성되어 있습니다."
            ),
            "top_news": top_news if top_news else [
                {"title": "이번 주 STS 시장 주요 뉴스", "summary": "STS 정밀재 관련 주요 동향을 정리했습니다.", "url": "https://steelinfosys.com"}
            ],
            "outlook": (
                "다음 주에는 LME 니켈 가격 방향성과 중국의 STS 수출 동향에 주목할 필요가 있습니다. "
                "국내 수요처들의 발주 패턴 변화와 원/달러 환율 움직임도 가격 변동성에 영향을 줄 것으로 전망됩니다."
            ),
            "kakao_summary": (
                "니켈 톤당 16,800달러…전주比 120달러 하락\n"
                "국내 STS 304 2B 약보합, 220만원 내외 형성\n"
                "중국 수입재 증가 우려 속 하반기 수요 회복 기대"
            ),
        }

    # ── HTML/텍스트 렌더링 (POSRI 스타일) ──────────────────────
    def _render_html(self, content: dict, articles: list[dict], week_info: dict) -> str:
        now = datetime.now()
        date_str = now.strftime("%Y. %m. %d")
        weekday_map = {0:"MON",1:"TUE",2:"WED",3:"THU",4:"FRI",5:"SAT",6:"SUN"}
        weekday_kr  = {0:"월",1:"화",2:"수",3:"목",4:"금",5:"토",6:"일"}
        weekday_str = weekday_map.get(now.weekday(), "")
        weekday_k   = weekday_kr.get(now.weekday(), "")
        vol = week_info.get("week", now.isocalendar()[1])

        # ── 카테고리 배지 색상 ───────────────────────────────
        cat_colors = {
            "가격동향": ("#c41c22", "#fff8f8"),
            "시황":     ("#0950a8", "#f0f5ff"),
            "원자재":   ("#47a75a", "#f0fff4"),
            "통상정책": ("#ee8e1e", "#fff8f0"),
        }

        def cat_badge(category: str) -> str:
            fg, bg = cat_colors.get(category, ("#16294f", "#f0f2f8"))
            return (f'<span style="display:inline-block;background:{bg};color:{fg};'
                    f'font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;'
                    f'border:1px solid {fg};letter-spacing:0.3px;">{category}</span>')

        # ── Mock 기사 제거 후, 이미지 있는 기사 우선 정렬 ──────
        def _is_mock(a: dict) -> bool:
            return "mock" in a.get("url", "") or "mock" in a.get("url_hash", "")

        real_arts   = [a for a in articles if not _is_mock(a)]
        display_arts = real_arts if real_arts else articles  # 실기사 없으면 전체 사용

        with_img    = [a for a in display_arts if a.get("image_url")]
        without_img = [a for a in display_arts if not a.get("image_url")]
        card_articles = (with_img + without_img)[:3]
        card_cells = ""
        for i, art in enumerate(card_articles):
            img_url  = art.get("image_url") or ""
            title    = art.get("title", "")[:55]
            summary  = art.get("content", "")[:110].replace("\n", " ").strip()
            url      = art.get("url", "#")
            source   = art.get("source", "")
            pub_date = art.get("published_at", "")[:10]
            category = art.get("category", "")
            badge    = cat_badge(category) if category else ""
            border_r = "" if i == 2 else "border-right:1px solid #e5e5e5;"

            # 카테고리별 placeholder 색상
            _ph_colors = {"가격동향":("#c41c22","#7b0d0d"), "시황":("#0950a8","#16294f"),
                          "원자재":("#2e7d32","#1b5e20"), "통상정책":("#e65100","#bf360c")}
            _c1, _c2 = _ph_colors.get(category, ("#1e3d72","#16294f"))
            _cat_label = category or "STS NEWS"

            img_block = (
                f'<a href="{url}" target="_blank" style="display:block;overflow:hidden;height:148px;">'
                f'<img src="{img_url}" alt="" width="100%"'
                f' style="width:100%;height:148px;object-fit:cover;display:block;border:none;"></a>'
            ) if img_url else (
                f'<a href="{url}" target="_blank" style="display:block;text-decoration:none;">'
                f'<div style="height:148px;background:linear-gradient(135deg,{_c1} 0%,{_c2} 100%);'
                f'text-align:center;padding-top:40px;">'
                f'<div style="color:rgba(255,255,255,0.25);font-size:42px;line-height:1;">◈</div>'
                f'<div style="color:rgba(255,255,255,0.8);font-size:12px;font-weight:700;'
                f'letter-spacing:2px;margin-top:10px;">{_cat_label}</div>'
                f'<div style="color:rgba(255,255,255,0.4);font-size:10px;margin-top:4px;'
                f'letter-spacing:1px;">STS PRECISION STEEL</div>'
                f'</div></a>'
            )

            card_cells += f"""
            <td style="width:33.3%;vertical-align:top;{border_r}background:#fff;">
              {img_block}
              <div style="padding:14px 14px 16px;">
                <div style="margin-bottom:8px;">{badge}</div>
                <a href="{url}" target="_blank"
                   style="display:block;font-size:13px;font-weight:700;color:#16294f;
                          text-decoration:none;line-height:1.55;margin-bottom:8px;
                          overflow:hidden;max-height:60px;">{title}</a>
                <span style="display:block;font-size:11px;color:#6e6e6e;line-height:1.65;
                             overflow:hidden;max-height:54px;">{summary}{"…" if len(art.get("content","")) > 110 else ""}</span>
                <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f0f0f0;">
                  <span style="font-size:10px;color:#2578d6;font-weight:600;">{source}</span>
                  <span style="font-size:10px;color:#a5a5a5;margin-left:6px;">{pub_date}</span>
                </div>
              </div>
            </td>"""

        # ── 우측 뉴스 리스트 (Mock 제외, 이미지 있는 기사 우선) ──
        news_list_html = ""
        list_with_img    = [a for a in display_arts if a.get("image_url")][3:]
        list_without_img = [a for a in display_arts if not a.get("image_url")][3:]
        list_articles    = (list_with_img + list_without_img)[:9]
        for art in list_articles:
            img_url  = art.get("image_url") or ""
            title    = art.get("title", "")[:48]
            url      = art.get("url", "#")
            source   = art.get("source", "")
            pub_date = art.get("published_at", "")[:10]
            category = art.get("category", "")

            _ph2 = {"가격동향":"#c41c22","시황":"#0950a8","원자재":"#2e7d32","통상정책":"#e65100"}
            _pc = _ph2.get(category, "#16294f")
            img_td = (
                f'<td width="64" style="vertical-align:top;padding-right:10px;">'
                f'<a href="{url}" target="_blank"'
                f' style="display:block;width:64px;height:48px;overflow:hidden;">'
                f'<img src="{img_url}" alt="" width="64" height="48"'
                f' style="width:64px;height:48px;object-fit:cover;display:block;border:none;"></a></td>'
            ) if img_url else (
                f'<td width="64" style="vertical-align:top;padding-right:10px;">'
                f'<div style="width:64px;height:48px;background:linear-gradient(135deg,{_pc},{_pc}99);'
                f'text-align:center;padding-top:14px;">'
                f'<div style="color:rgba(255,255,255,0.9);font-size:10px;font-weight:700;'
                f'letter-spacing:1px;">STS</div>'
                f'</div></td>'
            )

            news_list_html += f"""
            <li style="list-style:none;margin:0;padding:10px 0;border-bottom:1px solid #f0f2f5;">
              <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                  {img_td}
                  <td style="vertical-align:top;">
                    <a href="{url}" target="_blank" style="text-decoration:none;">
                      <strong style="display:block;font-size:12px;font-weight:700;color:#222;
                                     line-height:1.45;overflow:hidden;max-height:35px;
                                     margin-bottom:5px;">{title}</strong>
                    </a>
                    <span style="font-size:10px;color:#2578d6;font-weight:600;">{source}</span>
                    <span style="font-size:10px;color:#a5a5a5;margin-left:5px;">{pub_date}</span>
                  </td>
                </tr>
              </table>
            </li>"""

        # ── 섹션 헤더 공통 스타일 ───────────────────────────
        def section_header(icon: str, label: str, color: str = "#16294f") -> str:
            return (f'<tr><td style="padding:12px 16px 8px;border-bottom:2px solid {color};">'
                    f'<span style="font-size:13px;font-weight:700;color:{color};letter-spacing:-0.2px;">'
                    f'{icon} {label}</span></td></tr>')

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{content.get('subject','STS정밀재 주간뉴스레터')}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap');
  body,table,td,th,a,span,div,p {{
    font-family:'Noto Sans KR','Malgun Gothic','맑은 고딕',dotum,Helvetica,sans-serif !important;
  }}
</style>
</head>
<body style="margin:0;padding:0;background:#f0f2f5;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td align="center" style="padding:24px 0;">

<!-- ═══════════════════════════════════════════════════════ -->
<!--  메인 컨테이너  670px                                   -->
<!-- ═══════════════════════════════════════════════════════ -->
<table width="670" cellpadding="0" cellspacing="0" border="0"
       style="max-width:670px;background:#fff;
              box-shadow:5px 7px 12px 0 rgba(0,0,0,0.12);
              border-radius:4px;overflow:hidden;">
<tbody>

<!-- ① 헤더 배너 ─────────────────────────────────────────── -->
<tr>
  <td style="background:linear-gradient(135deg,#16294f 0%,#1e3d72 60%,#2578d6 100%);
             padding:0;border-bottom:3px solid #c41c22;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="padding:22px 24px;">
          <div style="font-size:11px;font-weight:500;color:#7eb3e8;
                      letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;">
            STS Precision Steel Weekly Newsletter
          </div>
          <div style="font-size:24px;font-weight:900;color:#ffffff;
                      letter-spacing:-0.5px;line-height:1.2;">
            STS 정밀재 주간뉴스레터
          </div>
          <div style="font-size:12px;color:rgba(255,255,255,0.6);margin-top:4px;font-weight:300;">
            토탈머티리얼즈 | Total Materials
          </div>
        </td>
        <td align="right" style="padding:22px 24px;white-space:nowrap;">
          <div style="font-size:18px;font-weight:700;color:#fff;line-height:1.3;">{date_str}</div>
          <div style="font-size:11px;color:#7eb3e8;margin-top:2px;">{weekday_str} · {weekday_k}요일</div>
          <div style="margin-top:8px;display:inline-block;background:rgba(196,28,34,0.85);
                      color:#fff;font-size:10px;font-weight:700;padding:3px 10px;
                      border-radius:20px;letter-spacing:0.5px;">
            Vol.{vol}
          </div>
        </td>
      </tr>
    </table>
  </td>
</tr>

<!-- ② 카드뉴스 섹션 ─────────────────────────────────────── -->
<tr>
  <td style="padding:20px 20px 0;">

    <!-- 섹션 레이블 -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="margin-bottom:12px;">
      <tr>
        <td style="border-left:3px solid #c41c22;padding-left:10px;">
          <span style="font-size:14px;font-weight:700;color:#16294f;letter-spacing:-0.3px;">
            STS 정밀재 주요 뉴스
          </span>
        </td>
        <td align="right">
          <span style="font-size:10px;color:#a5a5a5;">
            출처: 철강금속신문 · 철강데일리
          </span>
        </td>
      </tr>
    </table>

    <!-- 카드 3단 그리드 -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="border:1px solid #e5e5e5;border-radius:6px;overflow:hidden;
                  box-shadow:4px 5px 12px -1px rgba(0,0,0,0.10);">
      <tr>
        {card_cells if card_cells else
          '<td style="padding:30px;text-align:center;color:#a5a5a5;font-size:13px;">'
          '수집된 뉴스가 없습니다. 먼저 뉴스를 수집해주세요.</td>'}
      </tr>
    </table>

  </td>
</tr>

<!-- ③ 이번 주 핵심 한줄 ────────────────────────────────── -->
<tr>
  <td style="padding:16px 20px 0;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:#f5f7ff;border-left:4px solid #2578d6;border-radius:0 4px 4px 0;">
      <tr>
        <td style="padding:12px 16px;">
          <div style="font-size:10px;font-weight:700;color:#2578d6;
                      letter-spacing:1px;margin-bottom:5px;">THIS WEEK'S KEY POINT</div>
          <div style="font-size:14px;font-weight:700;color:#16294f;line-height:1.65;">
            {content.get('headline','')}
          </div>
        </td>
      </tr>
    </table>
  </td>
</tr>

<!-- ④ 본문 2단 레이아웃 ─────────────────────────────────── -->
<tr>
  <td style="padding:16px 20px 20px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>

        <!-- 좌: 시황 · 가격 · 전망 ──────────────────────── -->
        <td width="390" style="vertical-align:top;padding-right:12px;">

          <!-- 시장 동향 -->
          <table width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="border:1px solid #e5e5e5;border-radius:6px;
                        box-shadow:4px 5px 12px -1px rgba(0,0,0,0.08);
                        margin-bottom:12px;overflow:hidden;">
            {section_header("📊", "시장 동향", "#0950a8")}
            <tr>
              <td style="background:#f5f8ff;padding:14px 16px;
                         font-size:12px;color:#374151;line-height:1.85;">
                {content.get('market_summary','')}
              </td>
            </tr>
          </table>

          <!-- 가격 동향 -->
          <table width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="border:1px solid #e5e5e5;border-radius:6px;
                        box-shadow:4px 5px 12px -1px rgba(0,0,0,0.08);
                        margin-bottom:12px;overflow:hidden;">
            {section_header("💹", "가격 동향", "#47a75a")}
            <tr>
              <td style="background:#f5fff8;padding:14px 16px;
                         font-size:12px;color:#374151;line-height:1.85;">
                {content.get('price_trends','')}
              </td>
            </tr>
          </table>

          <!-- 다음 주 전망 -->
          <table width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="border:1px solid #e5e5e5;border-radius:6px;
                        box-shadow:4px 5px 12px -1px rgba(0,0,0,0.08);
                        overflow:hidden;">
            {section_header("🔮", "다음 주 전망", "#ee8e1e")}
            <tr>
              <td style="background:linear-gradient(135deg,#fffbf0,#fff8f5);
                         padding:14px 16px;font-size:12px;color:#374151;line-height:1.85;">
                {content.get('outlook','')}
              </td>
            </tr>
          </table>

        </td>

        <!-- 우: 주요뉴스 리스트 ─────────────────────────── -->
        <td width="250" style="vertical-align:top;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="border:1px solid #e5e5e5;border-radius:6px;
                        box-shadow:4px 5px 12px -1px rgba(0,0,0,0.08);
                        overflow:hidden;">
            {section_header("📋", "관련 뉴스", "#16294f")}
            <tr>
              <td style="background:#fff;padding:4px 12px 4px;">
                <ul style="margin:0;padding:0;">
                  {news_list_html if news_list_html else
                    '<li style="list-style:none;padding:16px 0;color:#a5a5a5;'
                    'font-size:12px;text-align:center;">추가 뉴스 없음</li>'}
                </ul>
              </td>
            </tr>
          </table>
        </td>

      </tr>
    </table>
  </td>
</tr>

<!-- ⑤ 푸터 ──────────────────────────────────────────────── -->
<tr>
  <td style="background:#16294f;padding:22px 24px;text-align:center;">
    <div style="margin-bottom:10px;">
      <span style="font-size:16px;font-weight:900;color:#fff;letter-spacing:-0.3px;">
        토탈머티리얼즈
      </span>
      <span style="font-size:11px;color:#7eb3e8;margin-left:8px;font-weight:300;">
        Total Materials
      </span>
    </div>
    <div style="font-size:11px;color:#a5bed8;margin-bottom:5px;line-height:1.7;">
      STS / AL / CU / 특수강 etc &nbsp;&#183;&nbsp; 원자재 컨설팅 및 개발<br>
      SHEAR / SLITTER / 표면가공 코일 및 시트
    </div>
    <div style="font-size:11px;color:#a5bed8;margin-bottom:5px;">
      <a href="mailto:total_materials@naver.com"
         style="color:#7eb3e8;text-decoration:none;">total_materials@naver.com</a>
      &nbsp;&#183;&nbsp; 010-4733-9821 &nbsp;&#183;&nbsp; 0504-434-9821
    </div>
    <div style="font-size:10px;color:#6e8faf;margin-bottom:14px;line-height:1.7;">
      안산사무소: 경기도 안산시 단원구 별망로459번길 109, 1층 105호<br>
      본&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;사: 서울특별시 금천구 가산디지털2로 40, 3층
    </div>
    <div style="border-top:1px solid rgba(255,255,255,0.1);padding-top:12px;">
      <a href="#unsubscribe"
         style="color:#c41c22;text-decoration:none;font-size:10px;font-weight:600;">
        수신거부 Unsubscribe
      </a>
      <span style="color:#3d5a7a;margin:0 10px;">|</span>
      <a href="https://www.steelinfosys.com"
         style="color:#6e8faf;text-decoration:none;font-size:10px;">
        steelinfosys.com
      </a>
    </div>
  </td>
</tr>

</tbody>
</table>
<!-- /메인 컨테이너 -->

</td></tr>
</table>
</body>
</html>"""
        return html

    def _render_plain(self, content: dict, week_info: dict) -> str:
        now = datetime.now()
        lines = [
            "=" * 60,
            f"STS정밀재 주간뉴스레터 Vol.{week_info.get('week', now.isocalendar()[1])}",
            f"{now.strftime('%Y년 %m월 %d일')}",
            "=" * 60,
            "",
            f"【이번 주 핵심】",
            content.get("headline", ""),
            "",
            "【시장 동향】",
            content.get("market_summary", ""),
            "",
            "【가격 동향】",
            content.get("price_trends", ""),
            "",
            "【주요 뉴스】",
        ]
        for i, news in enumerate(content.get("top_news", [])[:5], 1):
            lines.append(f"{i}. {news.get('title','')}")
            lines.append(f"   {news.get('summary','')}")
            lines.append("")
        lines += [
            "【다음 주 전망】",
            content.get("outlook", ""),
            "",
            "-" * 60,
            "철강정보원 (www.steelinfosys.com)",
            "수신거부: 이 이메일에 회신하세요.",
        ]
        return "\n".join(lines)

    @staticmethod
    def _format_articles_for_prompt(articles: list[dict]) -> str:
        parts = []
        for i, a in enumerate(articles[:10], 1):
            parts.append(
                f"[기사 {i}]\n"
                f"제목: {a.get('title','')}\n"
                f"출처: {a.get('source','')}\n"
                f"카테고리: {a.get('category','')}\n"
                f"URL: {a.get('url','')}\n"
                f"내용: {a.get('content','')[:500]}\n"
            )
        return "\n".join(parts)
