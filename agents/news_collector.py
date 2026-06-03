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

            # OG 이미지
            image_url = None
            og_img = soup.select_one("meta[property='og:image']")
            if og_img:
                image_url = og_img.get("content")

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


# ── 목 데이터 (API 키 없을 때 폴백) ─────────────────────────
MOCK_ARTICLES = [
    {
        "url_hash": "mock001",
        "title": "[주간-스테인리스] 니켈 가격 하락에 STS 냉연 가격 약보합…304 2B 공급 부담 지속",
        "url": "https://steelinfosys.com/news/mock001",
        "source": "철강정보원-스테인리스",
        "content": "이번 주 국내 STS 정밀재 시장은 니켈 가격 하락세가 이어지면서 304 2B 냉연 가격이 전주 대비 소폭 하락했다. 중국발 저가 수입재 유입 우려가 지속되는 가운데, 국내 제강사들은 가격 방어에 나서고 있다. 니켈 LME 현물가격은 톤당 16,800달러 수준으로 전주 대비 120달러 하락했다.",
        "image_url": None,
        "category": "시황",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["STS", "스테인리스", "냉연", "니켈"],
        "score": 12,
    },
    {
        "url_hash": "mock002",
        "title": "[K-스테인리스] 국내 STS 정밀재 수요 회복 신호…가전·자동차 부품 발주 증가",
        "url": "https://steelinfosys.com/news/mock002",
        "source": "철강정보원-K스테인리스",
        "content": "국내 STS 정밀재 수요가 회복 조짐을 보이고 있다. 가전 및 자동차 부품 업체들의 발주가 전주 대비 15% 증가했으며, 특히 304 및 316L 규격에 대한 문의가 늘어나는 추세다. 업계 관계자는 하반기 수요 개선에 대한 기대감이 높아지고 있다고 전했다.",
        "image_url": None,
        "category": "시황",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["STS", "스테인리스", "정밀재", "304", "316"],
        "score": 15,
    },
    {
        "url_hash": "mock003",
        "title": "[원자재] 니켈 선물시장 반등 시도…LME 재고 감소가 지지력 제공",
        "url": "https://steelinfosys.com/news/mock003",
        "source": "철강정보원-비철상품",
        "content": "LME 니켈 선물 가격이 반등을 시도하고 있다. LME 니켈 재고는 전주 대비 1,200톤 감소한 78,000톤을 기록했으며, 이는 가격에 일정한 지지력을 제공하고 있다. 시장에서는 중국의 니켈 생산 증가와 글로벌 수요 둔화가 맞물려 방향성 탐색이 이어질 것으로 전망하고 있다.",
        "image_url": None,
        "category": "원자재",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["니켈", "가격"],
        "score": 9,
    },
    {
        "url_hash": "mock004",
        "title": "[수출입] 중국산 STS 냉연 수입 증가…국내 시장 가격 압박 우려",
        "url": "https://steelinfosys.com/news/mock004",
        "source": "철강정보원-시장",
        "content": "올 들어 중국산 STS 냉연 수입이 전년 동기 대비 23% 증가한 것으로 나타났다. 이는 국내 STS 정밀재 가격에 하방 압력을 가하고 있으며, 국내 유통업체들은 재고 조정에 나서고 있다. 업계에서는 수입재 증가 추세가 하반기에도 지속될 경우 시장 여건이 더욱 악화될 수 있다고 우려하고 있다.",
        "image_url": None,
        "category": "통상정책",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["STS", "스테인리스", "냉연", "수입재"],
        "score": 12,
    },
    {
        "url_hash": "mock005",
        "title": "[가격동향] 이번 주 STS 304 2B 국내 가격 현황",
        "url": "https://steelinfosys.com/news/mock005",
        "source": "철강정보원-스테인리스",
        "content": "이번 주 국내 STS 304 2B 0.5mm 기준 가격은 전주 대비 톤당 2만원 하락한 220만원 수준에서 거래되고 있다. 316L은 전주와 유사한 수준인 280만원대를 유지하고 있으며, 430 2B는 150만원대 초반에서 유통되고 있다.",
        "image_url": None,
        "category": "가격동향",
        "published_at": datetime.now().strftime("%Y-%m-%d"),
        "keywords_matched": ["STS", "스테인리스", "304", "316", "430", "가격"],
        "score": 18,
    },
]


def get_mock_articles():
    return MOCK_ARTICLES
