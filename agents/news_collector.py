"""
news_collector.py - STS 정밀재 관련 뉴스 수집 에이전트
steelinfosys.com 스테인리스/K-스테인리스 섹션 크롤링
"""
import hashlib
import time
import logging
import sys
import os
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

DEFAULT_SOURCES = [
    {"url": "https://www.snmnews.com/news/articleList.html?sc_serial_code=SRN469&view_type=sm", "name": "철강금속신문-STS", "type": "korean_news", "base_url": "https://www.snmnews.com", "enabled": True},
    {"url": "https://www.steeldaily.co.kr/news/articleList.html?sc_sub_section_code=S2N11&view_type=sm", "name": "철강데일리-스테인리스", "type": "korean_news", "base_url": "https://www.steeldaily.co.kr", "enabled": True},
]

PRIMARY_KEYWORDS = ["STS", "스테인리스", "정밀재", "냉연", "니켈", "304", "316", "430", "2B", "헤어라인"]
SECONDARY_KEYWORDS = [
    # 철강 원자재
    "크롬", "몰리브덴", "합금철", "LME", "수입재",
    # 철강 시장 일반
    "철강", "열연", "후판", "선재", "철근", "강판", "코일",
    # 시황·가격
    "시황", "가격", "가격동향", "철강가격", "원자재가격",
    # 거시경제·통상
    "관세", "수출", "수입", "무역", "통상", "공급망", "수급",
    "환율", "달러", "금리", "인플레이션", "경기",
    # 중국·글로벌
    "중국철강", "중국산", "글로벌", "아시아", "수출입",
    # 에너지·탄소
    "탄소", "에너지", "전기로", "고로",
]
EXCLUDE_KEYWORDS = ["광고", "채용", "이벤트", "구인", "부고", "인사", "승진"]


class NewsCollector:
    def __init__(self, sources=None, primary_kw=None, secondary_kw=None, exclude_kw=None):
        self.sources = sources or DEFAULT_SOURCES
        self.primary_kw = primary_kw or PRIMARY_KEYWORDS
        self.secondary_kw = secondary_kw or SECONDARY_KEYWORDS
        self.exclude_kw = exclude_kw or EXCLUDE_KEYWORDS
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ── 공개 메서드 ──────────────────────────────────────────
    def collect(self, progress_callback=None) -> list[dict]:
        """모든 소스에서 뉴스 수집 후 중복 제거된 리스트 반환."""
        all_articles = []
        active = [s for s in self.sources if s.get("enabled", True)]

        for i, source in enumerate(active):
            if progress_callback:
                progress_callback(i / len(active), f"🔍 수집 중: {source['name']}")
            try:
                source_type = source.get("type", "steelinfosys")
                if source_type == "korean_news":
                    articles = self._crawl_korean_news(
                        source["url"], source["name"], source.get("base_url", "")
                    )
                else:
                    articles = self._crawl_steelinfosys(source["url"], source["name"])
                all_articles.extend(articles)
                time.sleep(1.5)
            except Exception as e:
                logger.warning(f"[{source['name']}] 수집 실패: {e}")

        if progress_callback:
            progress_callback(0.9, "🔄 중복 제거 및 STS 필터링 중...")

        deduped = self.deduplicate(all_articles)
        scored = self._score_articles(deduped)

        # 필터링:
        #  - STS 정밀재 직접 관련 (1차 키워드 1개 이상, score >= 3) → 반드시 포함
        #  - 거시 철강·경제 뉴스 (2차 키워드 3개 이상, score >= 3) → 포함
        #  → 결론: score >= 3 이면 포함 (1차 1개 OR 2차 3개 이상)
        sts_filtered = [a for a in scored if a["score"] >= 3]
        result = sorted(sts_filtered, key=lambda x: x["score"], reverse=True)

        if progress_callback:
            progress_callback(1.0, f"✅ 완료: 전체 {len(scored)}건 중 관련 {len(result)}건 수집")

        return result

    def deduplicate(self, articles: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for a in articles:
            h = a.get("url_hash") or self._make_hash(a["url"])
            if h not in seen:
                seen.add(h)
                result.append(a)
        return result

    # ── 내부 메서드 ───────────────────────────────────────────
    def _crawl_steelinfosys(self, list_url: str, source_name: str) -> list[dict]:
        articles = []
        try:
            resp = self.session.get(list_url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # 기사 링크 추출 (steelinfosys 구조)
            links = []
            for a_tag in soup.select("a[href*='/news/']"):
                href = a_tag.get("href", "")
                if re.search(r"/news/\d+", href):
                    full_url = href if href.startswith("http") else "https://steelinfosys.com" + href
                    title_text = a_tag.get_text(strip=True)
                    if title_text and len(title_text) > 5:
                        links.append((full_url, title_text))

            # 중복 URL 제거
            seen_urls = set()
            unique_links = []
            for url, title in links:
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_links.append((url, title))

            for url, title in unique_links[:20]:
                if self._is_excluded(title):
                    continue
                article = self._fetch_article(url, title, source_name)
                if article:
                    articles.append(article)
                time.sleep(0.8)

        except Exception as e:
            logger.error(f"크롤링 실패 [{list_url}]: {e}")

        return articles

    def _fetch_article(self, url: str, title: str, source_name: str) -> Optional[dict]:
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # 본문 추출
            content = ""
            for selector in ["#bo_v_con", ".view-content", ".article-body", "#article-view-content-div", ".content"]:
                el = soup.select_one(selector)
                if el:
                    content = el.get_text(separator="\n", strip=True)[:2000]
                    break
            if not content:
                content = soup.get_text(separator="\n", strip=True)[:2000]

            # 이미지 추출
            image_url = None
            img = soup.select_one("meta[property='og:image']")
            if img:
                image_url = img.get("content")

            # 날짜 추출
            published_at = datetime.now().strftime("%Y-%m-%d")
            for date_sel in ["meta[property='article:published_time']", ".date", ".time", ".datetime"]:
                date_el = soup.select_one(date_sel)
                if date_el:
                    dt_str = date_el.get("content") or date_el.get_text(strip=True)
                    if dt_str:
                        published_at = dt_str[:10]
                    break

            # 카테고리 추정
            category = self._guess_category(title + " " + content)
            keywords_matched = self._find_matching_keywords(title + " " + content)

            return {
                "url_hash": self._make_hash(url),
                "title": title,
                "url": url,
                "source": source_name,
                "content": content,
                "image_url": image_url,
                "category": category,
                "published_at": published_at,
                "keywords_matched": keywords_matched,
                "score": 0,
            }
        except Exception as e:
            logger.debug(f"기사 가져오기 실패 [{url}]: {e}")
            return None

    def _crawl_korean_news(self, list_url: str, source_name: str, base_url: str) -> list[dict]:
        """철강데일리·철강금속신문 등 한국 뉴스 CMS(articleList.html 방식) 크롤링."""
        articles = []
        try:
            resp = self.session.get(list_url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # articleView.html 링크 추출 (한국 뉴스 CMS 공통 패턴)
            seen_urls: set = set()
            links: list[tuple[str, str]] = []

            for a_tag in soup.select("a[href*='articleView.html']"):
                href = a_tag.get("href", "")
                full_url = href if href.startswith("http") else base_url + href
                title_text = a_tag.get_text(strip=True)
                if title_text and len(title_text) > 5 and full_url not in seen_urls:
                    seen_urls.add(full_url)
                    links.append((full_url, title_text))

            # 목록 페이지에서 제목만 있는 경우 폴백: li/h4/h3 내 링크
            if not links:
                for a_tag in soup.select("ul.type2 li a, .list-body a, h4 a, h3 a"):
                    href = a_tag.get("href", "")
                    if not href:
                        continue
                    full_url = href if href.startswith("http") else base_url + href
                    title_text = a_tag.get_text(strip=True)
                    if title_text and len(title_text) > 5 and full_url not in seen_urls:
                        seen_urls.add(full_url)
                        links.append((full_url, title_text))

            for url, title in links[:20]:
                if self._is_excluded(title):
                    continue
                article = self._fetch_korean_article(url, title, source_name)
                if article:
                    articles.append(article)
                time.sleep(1.0)

        except Exception as e:
            logger.error(f"한국뉴스 크롤링 실패 [{list_url}]: {e}")

        return articles

    def _fetch_korean_article(self, url: str, title: str, source_name: str) -> Optional[dict]:
        """한국 뉴스 사이트 기사 본문 수집."""
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # 본문 추출 (한국 뉴스 CMS 공통 선택자)
            content = ""
            for selector in [
                "#article-view-content-div",
                ".article-view-content",
                "#articleBody",
                ".article_content",
                "#newsViewArea",
                ".view_con",
                ".news_view",
                ".article-body",
            ]:
                el = soup.select_one(selector)
                if el:
                    content = el.get_text(separator="\n", strip=True)[:2000]
                    break
            if not content:
                content = soup.get_text(separator="\n", strip=True)[:2000]

            # 발행일 추출
            published_at = datetime.now().strftime("%Y-%m-%d")
            for sel in [
                "meta[property='article:published_time']",
                "meta[name='article:published_time']",
                ".info_text em",
                ".article-date",
                ".date",
                "em.info_text",
                ".byline em",
            ]:
                el = soup.select_one(sel)
                if el:
                    dt_str = el.get("content") or el.get_text(strip=True)
                    if dt_str:
                        published_at = dt_str[:10]
                    break

            # 이미지 추출 (다중 소스 시도, http → https 변환)
            image_url = None
            img_candidates = [
                soup.select_one("meta[property='og:image']"),
                soup.select_one("meta[name='og:image']"),
                soup.select_one("meta[name='twitter:image']"),
                soup.select_one("meta[property='twitter:image']"),
                soup.select_one("meta[name='thumbnail']"),
            ]
            for cand in img_candidates:
                if cand:
                    raw = cand.get("content") or cand.get("value") or ""
                    if raw and raw.startswith("http"):
                        image_url = raw.replace("http://", "https://")
                        break

            # og:image가 없으면 본문 첫 번째 <img> 시도
            if not image_url:
                for sel in ["#article-view-content-div img",
                            ".article-view-content img",
                            "#articleBody img",
                            ".article_content img"]:
                    img_tag = soup.select_one(sel)
                    if img_tag:
                        src = img_tag.get("src") or ""
                        if src and ("thumb" in src or "photo" in src or ".jpg" in src or ".png" in src):
                            image_url = src.replace("http://", "https://")
                            break

            category = self._guess_category(title + " " + content)
            keywords_matched = self._find_matching_keywords(title + " " + content)

            return {
                "url_hash": self._make_hash(url),
                "title": title,
                "url": url,
                "source": source_name,
                "content": content,
                "image_url": image_url,
                "category": category,
                "published_at": published_at,
                "keywords_matched": keywords_matched,
                "score": 0,
            }
        except Exception as e:
            logger.debug(f"기사 가져오기 실패 [{url}]: {e}")
            return None

    def _score_articles(self, articles: list[dict]) -> list[dict]:
        for a in articles:
            text = (a.get("title", "") + " " + a.get("content", "")).upper()
            score = 0
            for kw in self.primary_kw:
                if kw.upper() in text:
                    score += 3
            for kw in self.secondary_kw:
                if kw.upper() in text:
                    score += 1
            a["score"] = score
        return articles

    def _find_matching_keywords(self, text: str) -> list[str]:
        matched = []
        for kw in self.primary_kw + self.secondary_kw:
            if kw.upper() in text.upper():
                matched.append(kw)
        return matched

    def _guess_category(self, text: str) -> str:
        text_up = text.upper()
        if any(k in text_up for k in ["가격", "PRICE", "달러", "원"]):
            return "가격동향"
        if any(k in text_up for k in ["수출", "수입", "무역", "통상"]):
            return "통상정책"
        if any(k in text_up for k in ["니켈", "크롬", "몰리브덴", "합금"]):
            return "원자재"
        if any(k in text_up for k in ["시황", "동향", "전망"]):
            return "시황"
        return "일반"

    def _is_excluded(self, text: str) -> bool:
        return any(kw in text for kw in self.exclude_kw)

    @staticmethod
    def _make_hash(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:16]


# ── 목 데이터 (크롤링 실패 시 폴백) ─────────────────────────
MOCK_ARTICLES = [
    {
        "url_hash": "mock001",
        "title": "대만 유스코, 6월 300계 할증료 또 인상… 亞STS시장도 '공급자 주도' 강세장",
        "url": "https://www.snmnews.com/news/articleView.html?idxno=570067",
        "source": "철강금속신문-STS",
        "content": "300계 할증료 7개월 연속 인상…몰리브데넘계 폭등, 316강종 6월에만 31만 원 인상. 글로벌 STS 밀 6월 동조화 뚜렷…국내 STS밀 압박 유지. 니켈 LME 현물가격은 톤당 16,800달러 수준으로 전주 대비 120달러 하락했다.",
        "image_url": None,
        "category": "가격동향",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["STS", "스테인리스", "냉연", "니켈", "304", "316"],
        "score": 16,
    },
    {
        "url_hash": "mock002",
        "title": "북미 NAS, 6월 300계 할증료 최고 8.7% 인상…인상 랠리 최고조",
        "url": "https://www.snmnews.com/news/articleView.html?idxno=569979",
        "source": "철강금속신문-STS",
        "content": "몰리브데넘 고첨가 강종 STS316(L)·316Ti 할증료 전월比 8.7% 폭등…304강종도 7.8% 인상. 페라이트계 STS430 할증료는 소폭 인상에 그쳐 대조. 국내 STS 정밀재 수요가 회복 조짐을 보이고 있으며 가전·자동차 부품 발주가 전주 대비 15% 증가했다.",
        "image_url": None,
        "category": "가격동향",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["STS", "스테인리스", "정밀재", "304", "316"],
        "score": 16,
    },
    {
        "url_hash": "mock003",
        "title": "유럽 STS 3社, 6월 할증료 일제히 인상…316강종 톤당 '200유로' 급등",
        "url": "https://www.snmnews.com/news/articleView.html?idxno=570038",
        "source": "철강금속신문-STS",
        "content": "유럽 주요 STS 제강사 3곳이 6월 할증료를 일제히 인상했다. 316강종은 전월 대비 200유로 급등하며 시장에 충격을 줬다. LME 니켈 선물 가격이 반등을 시도하며 LME 니켈 재고는 전주 대비 1,200톤 감소한 78,000톤을 기록했다.",
        "image_url": None,
        "category": "가격동향",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["STS", "스테인리스", "304", "316", "가격"],
        "score": 15,
    },
    {
        "url_hash": "mock004",
        "title": "중국 STS 내수 부진에도 생산 증가…4월 생산량 371만 톤 신기록",
        "url": "https://www.snmnews.com/news/articleView.html?idxno=569924",
        "source": "철강금속신문-STS",
        "content": "중국 STS 생산이 내수 부진에도 사상 최대치를 기록했다. 4월 생산량은 371만 톤으로 전월 대비 2.8% 증가. 올 들어 중국산 STS 냉연 수입이 전년 동기 대비 23% 증가해 국내 STS 정밀재 가격에 하방 압력을 가하고 있다.",
        "image_url": None,
        "category": "통상정책",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["STS", "스테인리스", "냉연", "수입재", "중국산"],
        "score": 13,
    },
    {
        "url_hash": "mock005",
        "title": "STS 304 2B 국내 가격 약보합…0.5mm 기준 220만원 내외 형성",
        "url": "https://www.snmnews.com/news/articleView.html?idxno=569983",
        "source": "철강금속신문-STS",
        "content": "이번 주 국내 STS 304 2B 0.5mm 기준 가격은 전주 대비 톤당 2만원 하락한 220만원 수준에서 거래되고 있다. 316L은 전주와 유사한 수준인 280만원대를 유지하고 있으며, 430 2B는 150만원대 초반에서 유통되고 있다.",
        "image_url": None,
        "category": "가격동향",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["STS", "스테인리스", "304", "316", "430", "가격"],
        "score": 18,
    },
    {
        "url_hash": "mock006",
        "title": "STS 열·냉연 수입 동반 감소…고원가에 계약도 주춤",
        "url": "https://www.steeldaily.co.kr/news/articleView.html?idxno=200480",
        "source": "철강데일리-스테인리스",
        "content": "STS 열연과 냉연 수입이 동반 감소세를 보이고 있다. 고원가 부담으로 바이어들의 계약 체결이 주춤하고 있으며, 중국산 수입재 가격 경쟁력도 다소 약화된 것으로 분석된다.",
        "image_url": None,
        "category": "시황",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["STS", "스테인리스", "냉연", "수입재", "가격"],
        "score": 13,
    },
    {
        "url_hash": "mock007",
        "title": "포스코, 세계STS협회 어워드서 '3관왕'…냉매배관 STS 대체 성과 인정",
        "url": "https://www.snmnews.com/news/articleView.html?idxno=569983",
        "source": "철강금속신문-STS",
        "content": "포스코가 세계스테인리스협회 어워드에서 3개 부문을 석권했다. 냉매배관 STS 대체 프로젝트가 혁신상을 수상하며 기술력을 인정받았다.",
        "image_url": None,
        "category": "시황",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["STS", "스테인리스", "정밀재"],
        "score": 9,
    },
]


def get_mock_articles():
    return MOCK_ARTICLES
