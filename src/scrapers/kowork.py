"""KOWORK (kowork.kr) scraper

공공 고용 서비스 - 외국인 채용 정보
영어 버전: https://kowork.kr/en

Playwright 기반 스크래핑:
- 세션 쿠키 로드하여 로그인 상태 유지
- JavaScript evaluate로 데이터 추출
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.models import JobPosting
from src.utils.config import get_settings
from .base import BaseScraper

logger = logging.getLogger(__name__)


class KoworkScraper(BaseScraper):
    """KOWORK 스크래퍼

    특징:
    - E-7 Sponsors 태그로 E-7 비자 지원 여부 확인 가능
    - 영어 버전 페이지 제공
    - Firebase JWT 기반 인증 (1시간 만료)
    """

    SOURCE_NAME = "kowork"
    BASE_URL = "https://kowork.kr"
    LIST_URL = "https://kowork.kr/en"
    SESSION_FILE = "kowork_session.json"

    # 대기 시간 설정 (밀리초)
    WAIT_PAGE_LOAD_MS = 2000
    WAIT_DETAIL_MS = 1500
    WAIT_BATCH_MS = 1000

    # 한국어 수준 매핑 (영어 → 표준화된 설명)
    KOREAN_LEVEL_MAP = {
        "native": "Native level",
        "advanced": "Business level",
        "intermediate": "Intermediate (everyday conversation)",
        "basic": "Basic level",
        "not required": "Not required",
        "none": "Not required",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def _load_session(self) -> list[dict[str, Any]]:
        """세션 쿠키 로드 (만료 감지 및 경고 포함)

        Returns:
            Playwright 형식의 쿠키 목록 (만료 시 빈 리스트)
        """
        session_path = self.settings.data_path / self.SESSION_FILE
        if not session_path.exists():
            logger.warning(f"Session file not found: {session_path}")
            logger.info("Running in unauthenticated mode (public data only)")
            return []

        try:
            with open(session_path, "r") as f:
                session_data = json.load(f)

            # 만료 시간 확인
            expires_at_str = session_data.get("expires_at", "")
            if not expires_at_str:
                logger.warning("Session has no expiration time")
                return []

            expires_at = datetime.fromisoformat(expires_at_str)
            now = datetime.now()
            time_remaining = (expires_at - now).total_seconds()

            # 만료 확인
            if now > expires_at:
                logger.warning("Session expired. Please re-login.")
                logger.info("Running in unauthenticated mode (public data only)")
                return []

            # 만료 임박 경고 (10분 미만)
            if time_remaining < 600:
                logger.warning(
                    f"Session expiring soon: {time_remaining / 60:.1f} minutes remaining"
                )
            else:
                logger.info(
                    f"Session valid: {time_remaining / 60:.1f} minutes remaining"
                )

            # Playwright 쿠키 형식으로 변환
            cookies = []
            for name, value in session_data.get("cookies", {}).items():
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": ".kowork.kr",
                    "path": "/",
                })
            return cookies

        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return []

    async def _init_browser(self, with_session: bool = True) -> None:
        """브라우저 초기화 (봇 탐지 우회 설정 포함)

        Args:
            with_session: 세션 쿠키 로드 여부
        """
        playwright = await async_playwright().start()

        # 봇 탐지 우회를 위한 브라우저 옵션
        self._browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        # 사용자 에이전트 설정으로 브라우저 컨텍스트 생성
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        # 세션 쿠키 로드 (요청 시)
        if with_session:
            cookies = await self._load_session()
            if cookies:
                await self._context.add_cookies(cookies)
                logger.info("Session cookies applied")

        self._page = await self._context.new_page()

        # navigator.webdriver 속성 숨기기
        await self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

    async def _close_browser(self) -> None:
        """브라우저 종료"""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()

    # =========================================================================
    # Deep Scraping 헬퍼 메서드
    # =========================================================================

    async def _extract_detail_info(self) -> dict[str, Any]:
        """상세 페이지 정보 추출 (단일 JS 구현)

        scrape_detail()과 scrape_all_details() 모두에서 사용되는
        공통 추출 로직입니다.

        Returns:
            추출된 상세 정보 딕셔너리
        """
        assert self._page is not None

        return await self._page.evaluate("""() => {
            const data = {
                title: '',
                company: '',
                companyEng: '',
                deadline: '',
                visas: [],
                e7Support: false,
                koreanRequirement: '',
                jobDescription: '',
                qualifications: '',
                preferred: '',
                etc: '',
                benefits: [],
                jobType: '',
                jobCategory: '',
                location: '',
                contentRaw: ''
            };

            // Title (h1)
            const h1 = document.querySelector('h1');
            if (h1) data.title = h1.textContent.trim();

            // Company - near the logo
            const logoImg = document.querySelector('img[alt*="posting"][alt*="logo"]');
            if (logoImg) {
                const parent = logoImg.parentElement;
                if (parent) {
                    const p = parent.querySelector('p');
                    if (p) data.company = p.textContent.trim();
                }
            }

            // Alternative company selector (if logo method fails)
            if (!data.company) {
                const companyLink = document.querySelector('a[href*="/company/"]');
                if (companyLink) {
                    data.company = companyLink.textContent.trim();
                }
            }

            // Deadline (D-XX format)
            const allP = document.querySelectorAll('p');
            for (const p of allP) {
                const txt = p.textContent.trim();
                if (txt.match(/^D-\\d+$/) || txt === 'D-day') {
                    data.deadline = txt;
                    break;
                }
            }

            // Sections with h2 headings
            const h2s = document.querySelectorAll('h2');
            h2s.forEach(h2 => {
                const name = h2.textContent.trim();
                const next = h2.nextElementSibling;
                if (!next) return;

                switch(name) {
                    case 'Job Description':
                        data.jobDescription = next.textContent.trim().substring(0, 3000);
                        break;
                    case 'Qualifications':
                        data.qualifications = next.textContent.trim().substring(0, 3000);
                        // Extract Korean requirement
                        const koreanMatch = next.textContent.match(
                            /(?:korean|한국어|TOPIK)[^.;\\n]*/gi
                        );
                        if (koreanMatch) {
                            data.koreanRequirement = koreanMatch.join('; ').trim();
                        }
                        break;
                    case 'Preferred':
                        data.preferred = next.textContent.trim().substring(0, 3000);
                        // Also check for Korean requirement here
                        if (!data.koreanRequirement) {
                            const prefKorean = next.textContent.match(
                                /(?:korean|한국어|TOPIK)[^.;\\n]*/gi
                            );
                            if (prefKorean) {
                                data.koreanRequirement = prefKorean.join('; ').trim();
                            }
                        }
                        break;
                    case 'Etc':
                        data.etc = next.textContent.trim().substring(0, 2000);
                        break;
                    case 'Preferred Visas':
                        next.querySelectorAll('p').forEach(p =>
                            data.visas.push(p.textContent.trim())
                        );
                        break;
                    case 'Benefits':
                        next.querySelectorAll('p').forEach(p => {
                            const txt = p.textContent.trim();
                            data.benefits.push(txt);
                            if (txt.toLowerCase().includes('e-7') ||
                                txt.toLowerCase().includes('visa sponsorship')) {
                                data.e7Support = true;
                            }
                        });
                        break;
                }
            });

            // Sidebar info (Job Type, Category, Location)
            for (let i = 0; i < allP.length; i++) {
                const text = allP[i].textContent.trim();
                if (text === 'Job Type' && allP[i+1])
                    data.jobType = allP[i+1].textContent.trim();
                if (text === 'Job Category' && allP[i+1])
                    data.jobCategory = allP[i+1].textContent.trim();
                if (text === 'Location' && allP[i+1])
                    data.location = allP[i+1].textContent.trim();
            }

            // Full content for content_raw (fallback)
            const main = document.querySelector('main');
            data.contentRaw = main ? main.innerText.substring(0, 8000) : '';

            return data;
        }""")

    def _normalize_korean_level(self, raw: str) -> str:
        """한국어 수준 표준화

        Args:
            raw: 추출된 한국어 요구사항 텍스트

        Returns:
            표준화된 한국어 수준 문자열
        """
        if not raw:
            return ""

        raw_lower = raw.lower()

        # KOREAN_LEVEL_MAP에서 매칭 시도
        for key, value in self.KOREAN_LEVEL_MAP.items():
            if key in raw_lower:
                return value

        # 매칭 실패 시 원본 반환 (정보 손실 방지)
        return raw

    def _compose_content_raw(self, detail: dict[str, Any]) -> str:
        """구조화된 content_raw 생성

        Komate/Klik 패턴과 일관성을 유지하여 섹션 헤더 포함

        Args:
            detail: 추출된 상세 정보

        Returns:
            구조화된 content_raw 문자열
        """
        content_parts = []

        if detail.get("jobDescription"):
            content_parts.append(f"[Job Description]\n{detail['jobDescription']}")

        if detail.get("qualifications"):
            content_parts.append(f"[Qualifications]\n{detail['qualifications']}")

        if detail.get("preferred"):
            content_parts.append(f"[Preferred]\n{detail['preferred']}")

        if detail.get("etc"):
            content_parts.append(f"[Etc]\n{detail['etc']}")

        if detail.get("benefits"):
            benefits_text = "\n".join(f"- {b}" for b in detail["benefits"])
            content_parts.append(f"[Benefits]\n{benefits_text}")

        # 구조화된 콘텐츠가 있으면 사용, 없으면 원본 contentRaw 사용
        if content_parts:
            return "\n\n".join(content_parts)
        elif detail.get("contentRaw"):
            return detail["contentRaw"]
        return ""

    def _update_posting_from_detail(
        self, posting: JobPosting, detail: dict[str, Any]
    ) -> JobPosting:
        """상세 정보로 posting 업데이트 (비파괴적 병합)

        기존 값이 있으면 유지하고, 새로운 정보만 추가합니다.

        Args:
            posting: 기본 정보가 채워진 JobPosting
            detail: 추출된 상세 정보

        Returns:
            업데이트된 JobPosting (동일 인스턴스)
        """
        # Company (기존 값 없을 때만 업데이트)
        if detail.get("company") and not posting.company_kor:
            posting.company_kor = detail["company"]

        # Company English (새 필드)
        if detail.get("companyEng") and not posting.company_eng:
            posting.company_eng = detail["companyEng"]

        # Visas
        if detail.get("visas"):
            posting.visa = ", ".join(detail["visas"])

        # E-7 Support (additive - 한 번 True면 유지)
        if detail.get("e7Support"):
            posting.e7_support = True

        # Korean Requirement (표준화 적용)
        if detail.get("koreanRequirement"):
            posting.korean_requirement = self._normalize_korean_level(
                detail["koreanRequirement"]
            )

        # Job metadata
        if detail.get("jobType"):
            posting.job_type = detail["jobType"]
        if detail.get("jobCategory"):
            posting.job_category = detail["jobCategory"]
        if detail.get("location"):
            posting.location = detail["location"]

        # Deadline (이제 저장됨)
        if detail.get("deadline"):
            posting.deadline = detail["deadline"]

        # Content Raw (구조화된 버전)
        posting.content_raw = self._compose_content_raw(detail)

        return posting

    async def scrape_list(self) -> list[JobPosting]:
        """목록 페이지 스크래핑

        Returns:
            기본 정보가 채워진 JobPosting 목록
        """
        postings: list[JobPosting] = []
        logger.info(f"Scraping list from {self.LIST_URL}")

        try:
            await self._init_browser()
            assert self._page is not None

            # 목록 페이지 접속
            await self._page.goto(self.LIST_URL, wait_until="networkidle")
            await self._page.wait_for_timeout(2000)  # 동적 콘텐츠 로드 대기

            # JavaScript로 목록 데이터 추출
            raw_items = await self._page.evaluate("""() => {
                const jobs = [];
                const jobCards = document.querySelectorAll('a[href*="/en/post/"]');

                jobCards.forEach(card => {
                    const url = card.href || '';
                    if (!url.includes('/en/post/')) return;

                    // 텍스트 콘텐츠에서 정보 추출
                    const text = card.textContent || '';
                    const paragraphs = card.querySelectorAll('p');

                    let title = '';
                    let company = '';
                    let deadline = '';
                    let location = '';
                    let jobType = '';
                    let jobCategory = '';
                    let e7Support = text.includes('E-7 Sponsors');

                    paragraphs.forEach((p, i) => {
                        const t = p.textContent.trim();
                        if (i === 0) title = t;  // 첫 번째 p는 보통 제목
                        if (t.match(/^D-\\d+$/)) deadline = t;
                        if (t.includes('-gu,') || t.includes('-si,') || t.includes('-do')) {
                            location = t;
                        }
                        if (['Full Time', 'Part Time', 'Temporary', 'Freelance', 'Contract'].includes(t)) {
                            jobType = t;
                        }
                    });

                    // 회사명: 보통 제목 다음에 오는 텍스트
                    const spans = card.querySelectorAll('div > span, div > div > span');
                    spans.forEach(s => {
                        const t = s.textContent.trim();
                        if (t && !t.match(/^D-/) && t !== title && !['Full Time', 'Part Time'].includes(t)) {
                            if (!company) company = t;
                        }
                    });

                    // 회사명이 없으면 paragraphs에서 찾기
                    if (!company && paragraphs.length > 1) {
                        // 제목 다음에 오는 텍스트가 회사명일 가능성 높음
                        for (let i = 1; i < paragraphs.length; i++) {
                            const t = paragraphs[i].textContent.trim();
                            if (t && !t.match(/^D-/) && !t.includes('-gu,') &&
                                !['Full Time', 'Part Time', 'Temporary', 'Freelance'].includes(t)) {
                                company = t;
                                break;
                            }
                        }
                    }

                    // 직무 카테고리
                    const categories = ['IT', 'Marketing/Ads', 'Office/Administration', 'Service',
                                        'Education', 'Production/Manufacturing', 'Interpretation/Translation',
                                        'Design', 'Sales', 'Etc'];
                    paragraphs.forEach(p => {
                        const t = p.textContent.trim();
                        if (categories.includes(t)) jobCategory = t;
                    });

                    if (url && title) {
                        jobs.push({
                            url,
                            title,
                            company,
                            deadline,
                            location,
                            jobType,
                            jobCategory,
                            e7Support
                        });
                    }
                });

                return jobs;
            }""")

            logger.info(f"Found {len(raw_items)} jobs from list page")

            for item in raw_items:
                posting = self.create_posting(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    company_kor=item.get("company", ""),
                    location=item.get("location", ""),
                    e7_support=item.get("e7Support", False),
                    deadline=item.get("deadline", ""),
                    job_type=item.get("jobType", ""),
                    job_category=item.get("jobCategory", ""),
                )
                if posting:
                    postings.append(posting)

        except Exception as e:
            logger.error(f"Error scraping list: {e}")
            raise
        finally:
            await self._close_browser()

        return postings

    async def scrape_detail(self, posting: JobPosting) -> JobPosting:
        """상세 페이지 스크래핑 (단일 공고)

        Args:
            posting: 기본 정보가 채워진 JobPosting

        Returns:
            상세 정보가 추가된 JobPosting
        """
        logger.info(f"Scraping detail: {posting.url}")

        try:
            await self._init_browser()
            assert self._page is not None

            await self._page.goto(posting.url, wait_until="domcontentloaded", timeout=60000)
            await self._page.wait_for_timeout(self.WAIT_DETAIL_MS)

            # 공통 헬퍼 메서드로 추출 및 업데이트
            detail = await self._extract_detail_info()
            posting = self._update_posting_from_detail(posting, detail)

        except Exception as e:
            logger.error(f"Error scraping detail {posting.url}: {e}")
        finally:
            await self._close_browser()

        return posting

    async def run(self, deep_scrape: bool = True) -> list[JobPosting]:
        """전체 스크래핑 파이프라인 (브라우저 재사용 최적화)

        Args:
            deep_scrape: True면 신규 공고에 대해 상세 스크래핑 수행

        Returns:
            스크래핑된 JobPosting 목록
        """
        from datetime import datetime

        logger.info(f"Starting scraper: {self.SOURCE_NAME}")
        start_time = datetime.now()

        # 1. 목록 페이지 스크래핑
        logger.info("Phase 1: Scraping list page...")
        list_postings = await self.scrape_list()
        logger.info(f"Found {len(list_postings)} postings from list")

        if not list_postings:
            logger.warning("No postings found from list page")
            return []

        # 2. 신규 공고 필터링
        logger.info("Phase 2: Filtering new postings...")
        new_postings = self.storage.filter_new_postings(list_postings)
        logger.info(f"Found {len(new_postings)} new postings")

        if not new_postings:
            logger.info("No new postings to process")
            return []

        # 3. Deep Scraping (브라우저 재사용으로 최적화)
        if deep_scrape:
            logger.info("Phase 3: Deep scraping new postings...")
            new_postings = await self.scrape_all_details(new_postings)

        # 4. 저장
        logger.info("Phase 4: Saving postings...")
        valid_postings = [p for p in new_postings if self.validate_posting(p)]
        saved_count = self.storage.save_postings(valid_postings)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Completed {self.SOURCE_NAME}: "
            f"saved {saved_count} postings in {elapsed:.1f}s"
        )

        return valid_postings

    async def scrape_all_details(self, postings: list[JobPosting]) -> list[JobPosting]:
        """여러 상세 페이지를 효율적으로 스크래핑 (브라우저 재사용)

        Args:
            postings: 기본 정보가 채워진 JobPosting 목록

        Returns:
            상세 정보가 추가된 JobPosting 목록
        """
        if not postings:
            return []

        detailed_postings: list[JobPosting] = []
        logger.info(f"Scraping details for {len(postings)} postings...")

        try:
            await self._init_browser()
            assert self._page is not None

            for i, posting in enumerate(postings, 1):
                logger.info(f"  [{i}/{len(postings)}] {posting.title[:40]}...")
                try:
                    await self._page.goto(
                        posting.url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )
                    await self._page.wait_for_timeout(self.WAIT_BATCH_MS)

                    # 공통 헬퍼 메서드로 추출 및 업데이트
                    detail = await self._extract_detail_info()
                    posting = self._update_posting_from_detail(posting, detail)
                    detailed_postings.append(posting)

                except Exception as e:
                    logger.warning(f"Error on {posting.url}: {e}")
                    detailed_postings.append(posting)  # 기본 정보라도 저장

                await self.delay()

        except Exception as e:
            logger.error(f"Browser error: {e}")
            raise
        finally:
            await self._close_browser()

        return detailed_postings
