"""Klik (www.klik.co.kr) scraper

다국어 채용 플랫폼 - 28개 언어 번역 지원
로그인 불필요, 영어 UI 지원
"""

import logging
from datetime import datetime
from typing import Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.models import JobPosting
from .base import BaseScraper

logger = logging.getLogger(__name__)


class KlikScraper(BaseScraper):
    """Klik 스크래퍼

    특징:
    - 로그인 불필요 (공개 페이지)
    - 28개 언어 번역 지원
    - 한국어 능력 명시 (4단계)
    - 비자 정보 제공
    - URL 패턴: /jobs/{alphanumeric_id}
    """

    SOURCE_NAME = "klik"
    BASE_URL = "https://www.klik.co.kr"
    LIST_URL = "https://www.klik.co.kr/jobs"

    # 한국어 수준 매핑 (한국어 → 영어)
    KOREAN_LEVEL_MAP = {
        "고급": "Advanced (business level)",
        "중급": "Intermediate (everyday conversation)",
        "초급": "Basic level",
        "무관": "Not required",
        "비지니스 회의 가능": "Advanced (business level)",
        "일상대화 가능": "Intermediate (everyday conversation)",
        "기초적인 의사소통 가능": "Basic level",
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

        logger.info("Browser initialized for Klik scraping")

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

            # 목록 페이지 접속
            await self._page.goto(self.LIST_URL, wait_until="domcontentloaded", timeout=60000)
            await self._page.wait_for_timeout(3000)  # 동적 콘텐츠 로드 대기

            # 스크롤하여 더 많은 공고 로드 (lazy loading 대응)
            for _ in range(5):
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self._page.wait_for_timeout(1500)

            # JavaScript로 목록 데이터 추출
            raw_items = await self._page.evaluate("""() => {
                const jobs = [];

                // 공고 링크 찾기 (/jobs/{id} 패턴)
                const allLinks = Array.from(document.querySelectorAll('a[href*="/jobs/"]'));
                const jobLinks = allLinks.filter(a => {
                    const href = a.getAttribute('href') || '';
                    // /jobs/{id} 패턴 매칭 (알파뉴메릭 ID)
                    return /\\/jobs\\/[A-Za-z0-9]+$/.test(href);
                });

                // 중복 URL 추적
                const seenUrls = new Set();

                jobLinks.forEach(link => {
                    const href = link.getAttribute('href');
                    if (!href) return;

                    const url = href.startsWith('http')
                        ? href
                        : 'https://www.klik.co.kr' + href;

                    // 중복 체크
                    if (seenUrls.has(url)) return;
                    seenUrls.add(url);

                    const text = link.textContent || '';
                    const innerText = link.innerText || '';
                    const lines = innerText.split('\\n').map(l => l.trim()).filter(l => l);

                    let company = '';
                    let deadline = '';
                    let title = '';
                    let location = '';
                    let salary = '';
                    let jobType = '';
                    let jobCategory = '';

                    // 마감일 패턴 (D-XX)
                    const deadlineMatch = text.match(/D-\\d+|D-day/i);
                    if (deadlineMatch) deadline = deadlineMatch[0];

                    // 급여 패턴
                    const salaryMatch = text.match(/(시급|월급|연봉)\\s*[\\d,]+원/);
                    if (salaryMatch) salary = salaryMatch[0];

                    // 고용 형태
                    const jobTypes = ['정규직', '계약직', '프리랜서', '인턴', '파견직', '아르바이트'];
                    const foundTypes = [];
                    for (const jt of jobTypes) {
                        if (text.includes(jt)) {
                            foundTypes.push(jt);
                        }
                    }
                    jobType = foundTypes.join(', ');

                    // 줄 단위로 파싱
                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i];

                        // 첫 번째 줄 또는 회사명 패턴
                        if (i === 0 && !company && line.length < 50 && !line.match(/^D-/)) {
                            company = line;
                        }

                        // D-XX 다음 줄이 제목일 가능성
                        if (line.match(/^D-\\d+$|^D-day$/i)) {
                            deadline = line;
                            // 다음 줄이 제목
                            if (i + 1 < lines.length && !title) {
                                const nextLine = lines[i + 1];
                                if (nextLine.length > 5 &&
                                    !nextLine.match(/^(정규직|계약직|아르바이트|시급|월급)/) &&
                                    !nextLine.match(/^(서울|경기|인천|부산)/)) {
                                    title = nextLine;
                                }
                            }
                        }

                        // 지역 패턴
                        if (line.match(/^(서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주|재택)/)) {
                            location = line.replace('cash', '').trim();
                        }

                        // 직무 카테고리 (·로 구분)
                        if (line.includes('·') && line.length < 50 && !line.match(/^(서울|경기)/)) {
                            jobCategory = line;
                        }
                    }

                    // 제목을 찾지 못한 경우 대안
                    if (!title) {
                        for (const line of lines) {
                            if (line.length > 10 && line.length < 150 &&
                                line !== company &&
                                !line.match(/^D-|^(정규직|계약직|아르바이트)$/) &&
                                !line.match(/^(서울|경기|인천|부산)/) &&
                                !line.match(/^(시급|월급)/) &&
                                !line.includes('저장하기')) {
                                title = line;
                                break;
                            }
                        }
                    }

                    // 유효한 데이터만 추가
                    if (url && (title || company)) {
                        jobs.push({
                            url,
                            title: title || '',
                            company,
                            deadline,
                            location,
                            salary,
                            jobType,
                            jobCategory
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
                title: '',
                company: '',
                deadline: '',
                location: '',
                salary: '',
                workTime: '',
                workDays: '',
                jobType: '',
                jobCategory: '',
                koreanLevel: '',
                koreanLevelDesc: '',
                visa: '',
                visaNote: '',
                preferred: '',
                duties: '',
                contentRaw: '',
                e7Support: false
            };

            const text = document.body.textContent || '';

            // 제목 (h1)
            const h1 = document.querySelector('h1');
            if (h1) {
                data.title = h1.textContent.trim();
            }

            // 회사명 (제목 아래)
            const articleHeader = document.querySelector('article');
            if (articleHeader) {
                const companyElem = articleHeader.querySelector('div > div:first-child');
                if (companyElem) {
                    // 회사명은 보통 heading 아래 첫번째 div
                    const spans = articleHeader.querySelectorAll('div');
                    for (const span of spans) {
                        const t = span.textContent.trim();
                        if (t.length > 2 && t.length < 50 && !t.match(/^D-/) && !t.match(/^(식·음료|사무|제조)/)) {
                            data.company = t;
                            break;
                        }
                    }
                }
            }

            // 마감일
            const timeElem = document.querySelector('time');
            if (timeElem) {
                data.deadline = timeElem.textContent.trim();
            }

            // 직무 카테고리
            const categoryMatch = text.match(/(식·음료|서비스|사무|제조|교육|IT|판매|기타)[^\\n]*/);
            if (categoryMatch) {
                data.jobCategory = categoryMatch[0].substring(0, 50);
            }

            // 고용 형태 추출
            const jobTypes = ['정규직', '계약직', '프리랜서', '인턴', '파견직', '아르바이트'];
            const foundTypes = [];
            for (const jt of jobTypes) {
                if (text.includes(jt)) {
                    foundTypes.push(jt);
                }
            }
            data.jobType = foundTypes.join(', ');

            // 리스트 아이템에서 정보 추출
            const listItems = document.querySelectorAll('li');
            listItems.forEach(li => {
                const liText = li.textContent.trim();

                // location / salary 패턴
                if (liText.includes('location') || liText.match(/^(서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)/)) {
                    const locMatch = liText.match(/(서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)[^\\n]*/);
                    if (locMatch) data.location = locMatch[0].trim();
                }
                if (liText.includes('salary') || liText.match(/(시급|월급|연봉)/)) {
                    const salaryMatch = liText.match(/(시급|월급|연봉)[^\\n]*/);
                    if (salaryMatch) data.salary = salaryMatch[0].trim();
                }
                if (liText.includes('요일')) {
                    data.workDays = liText.replace('요일', '').trim();
                }
                if (liText.includes('jobWorkTime') || liText.match(/\\d{1,2}:\\d{2}~\\d{1,2}:\\d{2}/)) {
                    const timeMatch = liText.match(/\\d{1,2}:\\d{2}~\\d{1,2}:\\d{2}/);
                    if (timeMatch) data.workTime = timeMatch[0];
                }

                // 한국어 능력
                if (liText.includes('한국어 능력') || liText.includes('한국어능력')) {
                    const levels = ['고급', '중급', '초급', '무관'];
                    for (const level of levels) {
                        if (liText.includes(level)) {
                            data.koreanLevel = level;
                            break;
                        }
                    }
                    // 상세 설명
                    if (liText.includes('비지니스')) data.koreanLevelDesc = '비지니스 회의 가능';
                    else if (liText.includes('일상')) data.koreanLevelDesc = '일상대화 가능';
                    else if (liText.includes('기초')) data.koreanLevelDesc = '기초적인 의사소통 가능';
                }

                // 비자 정보
                if (liText.includes('VISA') || liText.includes('비자')) {
                    // 비자 종류 추출
                    const visaPatterns = ['E-7', 'F-2', 'F-4', 'F-5', 'F-6', 'D-10', 'D-2', 'C-4', 'H-2'];
                    const foundVisas = [];
                    for (const visa of visaPatterns) {
                        if (liText.includes(visa)) {
                            foundVisas.push(visa);
                        }
                    }
                    if (foundVisas.length > 0) {
                        data.visa = foundVisas.join(', ');
                    }
                    // 확인 필요 여부
                    if (liText.includes('확인필요') || liText.includes('확인이 필요')) {
                        data.visaNote = '확인필요';
                    }
                }

                // 우대조건
                if (liText.includes('우대조건') || liText.includes('우대 조건')) {
                    data.preferred = liText.replace('우대조건', '').replace('우대 조건', '').trim();
                }
            });

            // 담당업무 섹션
            const allDivs = document.querySelectorAll('div');
            allDivs.forEach(div => {
                const divText = div.textContent.trim();
                if (divText === '담당업무' || divText === '담당 업무') {
                    const nextSibling = div.nextElementSibling || div.parentElement?.nextElementSibling;
                    if (nextSibling) {
                        const dutiesText = nextSibling.textContent.trim();
                        if (dutiesText.length > 10 && dutiesText.length < 3000) {
                            data.duties = dutiesText;
                        }
                    }
                }
            });

            // E-7 비자 지원 확인
            if (text.includes('E-7') && (text.includes('지원') || text.includes('sponsor'))) {
                data.e7Support = true;
            }

            // 전체 콘텐츠 (article 또는 main)
            const article = document.querySelector('article') || document.querySelector('main');
            if (article) {
                data.contentRaw = article.innerText.substring(0, 8000);
            }

            return data;
        }""")

    def _update_posting_from_detail(
        self, posting: JobPosting, detail: dict[str, Any]
    ) -> JobPosting:
        """상세 정보로 posting 업데이트"""

        if detail.get("title") and not posting.title:
            posting.title = detail["title"]

        if detail.get("company") and not posting.company_kor:
            posting.company_kor = detail["company"]

        if detail.get("location"):
            posting.location = detail["location"]

        if detail.get("jobType"):
            posting.job_type = detail["jobType"]

        if detail.get("jobCategory"):
            posting.job_category = detail["jobCategory"]

        # 한국어 능력
        if detail.get("koreanLevel"):
            korean_text = detail["koreanLevel"]
            if detail.get("koreanLevelDesc"):
                korean_text += f" ({detail['koreanLevelDesc']})"
            posting.korean_requirement = korean_text

        # 비자 정보
        if detail.get("visa"):
            posting.visa = detail["visa"]
        elif detail.get("visaNote"):
            posting.visa = detail["visaNote"]

        # E-7 지원
        if detail.get("e7Support"):
            posting.e7_support = True

        # 전체 콘텐츠 구성
        content_parts = []
        if detail.get("duties"):
            content_parts.append(f"[담당업무]\n{detail['duties']}")
        if detail.get("salary"):
            content_parts.append(f"[급여] {detail['salary']}")
        if detail.get("workTime"):
            content_parts.append(f"[근무시간] {detail['workTime']}")
        if detail.get("workDays"):
            content_parts.append(f"[근무요일] {detail['workDays']}")
        if detail.get("preferred"):
            content_parts.append(f"[우대조건] {detail['preferred']}")

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
                logger.info(f"  [{i}/{len(postings)}] {posting.title[:40] if posting.title else posting.url}...")
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
