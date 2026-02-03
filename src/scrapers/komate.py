"""Komate (komate.saramin.co.kr) scraper

외국인 전문 채용 플랫폼 - 사람인 운영
로그인 불필요, 영어 버전 없음 (한국어 페이지만 존재)
"""

import logging
import re
from datetime import datetime
from typing import Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.models import JobPosting
from .base import BaseScraper

logger = logging.getLogger(__name__)


class KomateScraper(BaseScraper):
    """Komate 스크래퍼

    특징:
    - 로그인 불필요 (공개 페이지)
    - 한국어 수준이 명시적으로 표시됨 (4단계)
    - E-7 비자 지원 여부가 목록에서 바로 확인 가능
    - 사람인 플랫폼 기반
    """

    SOURCE_NAME = "komate"
    BASE_URL = "https://komate.saramin.co.kr"
    LIST_URL = "https://komate.saramin.co.kr/recruits/list"

    # 한국어 수준 매핑 (한국어 → 영어)
    KOREAN_LEVEL_MAP = {
        "원어민 수준 대화 가능": "Native level",
        "비즈니스 회화 가능": "Business level",
        "일상 대화 가능": "Intermediate (everyday conversation)",
        "기초 회화 가능": "Basic level",
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def _init_browser(self) -> None:
        """브라우저 초기화 (봇 탐지 우회 설정 포함)"""
        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
        )
        self._page = await self._context.new_page()

        # navigator.webdriver 속성 숨기기 (봇 탐지 우회)
        await self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        logger.info("Browser initialized for Komate scraping")

    async def _close_browser(self) -> None:
        """브라우저 종료"""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        self._page = None
        self._context = None
        self._browser = None

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

            # 목록 페이지 접속 (networkidle은 타임아웃 발생 가능)
            await self._page.goto(self.LIST_URL, wait_until="domcontentloaded", timeout=60000)
            await self._page.wait_for_timeout(3000)  # 동적 콘텐츠 로드 대기

            # 스크롤하여 더 많은 공고 로드 (lazy loading 대응)
            for _ in range(3):
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self._page.wait_for_timeout(1000)

            # JavaScript로 목록 데이터 추출
            raw_items = await self._page.evaluate("""() => {
                const jobs = [];
                // 모든 a 태그에서 recruits 링크 필터링 (resume 제외)
                const allLinks = Array.from(document.querySelectorAll('a'));
                const listItems = allLinks.filter(a => {
                    const href = a.getAttribute('href') || '';
                    return href.includes('/recruits/') && !href.includes('resume');
                });

                listItems.forEach(link => {
                    const href = link.getAttribute('href');
                    if (!href || !href.includes('/recruits/')) return;

                    // URL 정리 (쿼리 파라미터 제거)
                    const urlMatch = href.match(/\\/recruits\\/(\\d+)/);
                    if (!urlMatch) return;
                    const recruitId = urlMatch[1];
                    const url = 'https://komate.saramin.co.kr/recruits/' + recruitId;

                    const text = link.textContent || '';
                    const innerText = link.innerText || '';

                    // innerText를 줄바꿈으로 분리하여 파싱
                    const lines = innerText.split('\\n').map(l => l.trim()).filter(l => l);

                    let company = '';
                    let deadline = '';
                    let title = '';
                    let e7Support = false;
                    let jobType = '';
                    let jobCategory = '';
                    let location = '';
                    let koreanLevel = '';
                    let visas = [];

                    // 텍스트에서 E-7 비자 지원 확인
                    if (text.includes('E-7 비자지원') || text.includes('E-7 비자 지원')) {
                        e7Support = true;
                    }

                    // 마감일 패턴
                    const deadlineMatch = text.match(/D-\\d+|D-day|상시\\s*채용/i);
                    if (deadlineMatch) deadline = deadlineMatch[0];

                    // 한국어 수준 패턴
                    const koreanPatterns = [
                        '원어민 수준 대화 가능',
                        '비즈니스 회화 가능',
                        '일상 대화 가능',
                        '기초 회화 가능'
                    ];
                    for (const pattern of koreanPatterns) {
                        if (text.includes(pattern)) {
                            koreanLevel = pattern;
                            break;
                        }
                    }

                    // 고용 형태
                    const jobTypes = ['정규직', '계약직', '프리랜서', '인턴', '파견직', '위촉직'];
                    for (const jt of jobTypes) {
                        if (text.includes(jt)) {
                            jobType = jt;
                            break;
                        }
                    }

                    // 비자 추출
                    const visaPatterns = ['E-7', 'F-2', 'F-4', 'F-5', 'F-6', 'D-10', 'C-4', 'H-2'];
                    for (const visa of visaPatterns) {
                        if (text.includes(visa)) {
                            visas.push(visa);
                        }
                    }

                    // 줄 단위로 파싱
                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i];

                        // 첫 번째 줄은 보통 회사명
                        if (i === 0 && !company) {
                            company = line;
                        }

                        // D-XX 패턴 다음 줄은 제목
                        if (line.match(/^D-\\d+$|^D-day$|^상시 채용$/i)) {
                            deadline = line;
                            // 다음 줄이 제목
                            if (i + 1 < lines.length && !title) {
                                const nextLine = lines[i + 1];
                                if (nextLine.length > 10 && !nextLine.match(/^(정규직|계약직|프리랜서|E-7)/)) {
                                    title = nextLine;
                                }
                            }
                        }

                        // 지역 패턴
                        if (line.match(/^(서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\\s/)) {
                            location = line;
                        }

                        // 직무 카테고리 (·로 구분된 텍스트)
                        if (line.includes('·') && line.length < 80 && !line.match(/^(서울|경기)/)) {
                            if (!jobCategory) jobCategory = line;
                        }
                    }

                    // 제목을 찾지 못한 경우 대안
                    if (!title) {
                        for (const line of lines) {
                            if (line.length > 15 &&
                                line !== company &&
                                !line.match(/^D-|^(정규직|계약직|프리랜서)$/) &&
                                !koreanPatterns.some(p => line.includes(p)) &&
                                !line.match(/^(서울|경기|인천|부산)/) &&
                                !line.includes('·')) {
                                title = line;
                                break;
                            }
                        }
                    }

                    if (url && title && company) {
                        jobs.push({
                            url,
                            title,
                            company,
                            deadline,
                            location,
                            jobType,
                            jobCategory,
                            koreanLevel,
                            visas: visas.join(', '),
                            e7Support
                        });
                    }
                });

                // 중복 URL 제거
                const seen = new Set();
                return jobs.filter(job => {
                    if (seen.has(job.url)) return false;
                    seen.add(job.url);
                    return true;
                });
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
                    korean_requirement=item.get("koreanLevel", ""),
                    visa=item.get("visas", ""),
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
        """상세 페이지 스크래핑

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
            await self._page.wait_for_timeout(2000)

            # 상세 정보 추출
            detail = await self._extract_detail_info()

            # posting 업데이트
            posting = self._update_posting_from_detail(posting, detail)

        except Exception as e:
            logger.error(f"Error scraping detail {posting.url}: {e}")
        finally:
            await self._close_browser()

        return posting

    async def _extract_detail_info(self) -> dict[str, Any]:
        """상세 페이지에서 정보 추출"""
        assert self._page is not None

        return await self._page.evaluate("""() => {
            const data = {
                company: '',
                title: '',
                deadline: '',
                location: '',
                locationFull: '',
                jobType: '',
                jobCategory: '',
                koreanLevel: '',
                visas: [],
                e7Support: false,
                career: '',
                education: '',
                duties: '',
                preferred: '',
                benefits: '',
                contentRaw: ''
            };

            const text = document.body.textContent || '';

            // 회사명
            const companyElem = document.querySelector('a[href*="company-info"] div');
            if (companyElem) data.company = companyElem.textContent.trim();

            // 제목
            const titleElem = document.querySelector('main div > div > div:nth-child(2)');
            if (titleElem) {
                const titleText = titleElem.textContent.trim();
                if (titleText.length > 10 && titleText.length < 200) {
                    data.title = titleText;
                }
            }

            // 마감일
            const deadlineMatch = text.match(/D-\\d+|상시\\s*채용/);
            if (deadlineMatch) data.deadline = deadlineMatch[0];

            // E-7 비자 지원
            if (text.includes('E-7 비자지원') || text.includes('E-7 비자 지원')) {
                data.e7Support = true;
            }

            // 섹션별 정보 추출
            const allDivs = document.querySelectorAll('div');
            allDivs.forEach(div => {
                const divText = div.textContent.trim();
                const nextSibling = div.nextElementSibling;

                // 섹션 헤더 확인
                if (divText === '담당 업무' && nextSibling) {
                    data.duties = nextSibling.textContent.trim().substring(0, 3000);
                }
                if (divText === '우대 조건' && nextSibling) {
                    data.preferred = nextSibling.textContent.trim().substring(0, 1000);
                }
                if (divText === '복지 및 혜택' && nextSibling) {
                    data.benefits = nextSibling.textContent.trim().substring(0, 1000);
                }
                if (divText === '근무지' && nextSibling) {
                    data.locationFull = nextSibling.textContent.trim()
                        .replace('지도', '')
                        .replace('복사', '')
                        .trim();
                }
                if (divText === '경력' && nextSibling) {
                    const careerText = nextSibling.textContent.trim();
                    if (careerText.length < 50) data.career = careerText;
                }
                if (divText === '학력' && nextSibling) {
                    const eduText = nextSibling.textContent.trim();
                    if (eduText.length < 50) data.education = eduText;
                }
                if (divText === '한국어 수준' && nextSibling) {
                    const levelText = nextSibling.textContent.trim();
                    if (levelText.length < 50) data.koreanLevel = levelText;
                }
                if (divText === '지원 가능한 비자' && nextSibling) {
                    // span 태그에서 비자 추출 (Badge 컴포넌트)
                    const visaElements = nextSibling.querySelectorAll('span');
                    visaElements.forEach(ve => {
                        const visaText = ve.textContent.trim();
                        // 비자 코드만 추출 (E-7 특정활동 -> E-7)
                        const visaMatch = visaText.match(/^([A-Z]-\\d+)/);
                        if (visaMatch && !data.visas.includes(visaMatch[1])) {
                            data.visas.push(visaMatch[1]);
                        }
                    });
                }
            });

            // 전체 콘텐츠 (main 영역)
            const main = document.querySelector('main');
            if (main) {
                data.contentRaw = main.innerText.substring(0, 8000);
            }

            return data;
        }""")

    def _update_posting_from_detail(
        self, posting: JobPosting, detail: dict[str, Any]
    ) -> JobPosting:
        """상세 정보로 posting 업데이트"""

        if detail.get("company") and not posting.company_kor:
            posting.company_kor = detail["company"]

        if detail.get("koreanLevel"):
            posting.korean_requirement = detail["koreanLevel"]

        if detail.get("visas"):
            posting.visa = ", ".join(detail["visas"])

        if detail.get("e7Support"):
            posting.e7_support = True

        if detail.get("locationFull"):
            posting.location = detail["locationFull"]

        # 전체 콘텐츠 구성
        content_parts = []
        if detail.get("duties"):
            content_parts.append(f"[담당 업무]\n{detail['duties']}")
        if detail.get("preferred"):
            content_parts.append(f"[우대 조건]\n{detail['preferred']}")
        if detail.get("benefits"):
            content_parts.append(f"[복지 및 혜택]\n{detail['benefits']}")
        if detail.get("career"):
            content_parts.append(f"[경력] {detail['career']}")
        if detail.get("education"):
            content_parts.append(f"[학력] {detail['education']}")

        if content_parts:
            posting.content_raw = "\n\n".join(content_parts)
        elif detail.get("contentRaw"):
            posting.content_raw = detail["contentRaw"]

        return posting

    async def scrape_all_details(
        self, postings: list[JobPosting]
    ) -> list[JobPosting]:
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
                    await self._page.goto(posting.url, wait_until="domcontentloaded", timeout=60000)
                    await self._page.wait_for_timeout(1500)

                    detail = await self._extract_detail_info()
                    posting = self._update_posting_from_detail(posting, detail)
                    detailed_postings.append(posting)

                except Exception as e:
                    logger.warning(f"Error on {posting.url}: {e}")
                    detailed_postings.append(posting)

                await self.delay()

        except Exception as e:
            logger.error(f"Browser error: {e}")
            raise
        finally:
            await self._close_browser()

        return detailed_postings

    async def run(self, deep_scrape: bool = True) -> list[JobPosting]:
        """전체 스크래핑 파이프라인 (브라우저 재사용 최적화)

        Args:
            deep_scrape: True면 신규 공고에 대해 상세 스크래핑 수행

        Returns:
            스크래핑된 JobPosting 목록
        """
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
