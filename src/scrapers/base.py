"""Base scraper class for job sites"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from src.models import JobPosting
from src.storage import LocalStorage
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """스크래퍼 베이스 클래스

    모든 사이트별 스크래퍼는 이 클래스를 상속받아 구현합니다.

    주요 메서드:
    - scrape_list(): 목록 페이지에서 기본 정보 수집 (Light Scraping)
    - scrape_detail(url): 상세 페이지에서 추가 정보 수집 (Deep Scraping)
    - run(): 전체 스크래핑 파이프라인 실행
    """

    # 서브클래스에서 오버라이드할 속성
    SOURCE_NAME: str = ""  # 출처 이름 (kowork, komate, klik)
    BASE_URL: str = ""     # 사이트 기본 URL
    LIST_URL: str = ""     # 목록 페이지 URL

    def __init__(self, storage: LocalStorage | None = None) -> None:
        """
        Args:
            storage: 저장소 인스턴스 (없으면 기본 LocalStorage 사용)
        """
        self.settings = get_settings()
        self.storage = storage or LocalStorage()
        self._delay = self.settings.scrape_delay_seconds

    @abstractmethod
    async def scrape_list(self) -> list[JobPosting]:
        """목록 페이지 스크래핑 (Light Scraping)

        Returns:
            기본 정보가 채워진 JobPosting 목록
            (content_raw 등 상세 정보는 비어있음)
        """
        pass

    @abstractmethod
    async def scrape_detail(self, posting: JobPosting) -> JobPosting:
        """상세 페이지 스크래핑 (Deep Scraping)

        Args:
            posting: 기본 정보가 채워진 JobPosting

        Returns:
            상세 정보가 추가된 JobPosting
        """
        pass

    async def delay(self) -> None:
        """Rate limiting을 위한 딜레이"""
        await asyncio.sleep(self._delay)

    def validate_posting(self, posting: JobPosting) -> bool:
        """필수 필드 검증

        Returns:
            True if valid, False otherwise
        """
        try:
            # JobPosting의 __post_init__에서 기본 검증 수행
            if not posting.url:
                logger.warning("Missing url")
                return False
            if not posting.title:
                logger.warning(f"Missing title for {posting.url}")
                return False
            if not posting.company_kor and not posting.company_eng:
                logger.warning(f"Missing company for {posting.url}")
                return False
            return True
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False

    async def run(self, deep_scrape: bool = True) -> list[JobPosting]:
        """전체 스크래핑 파이프라인 실행

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

        # 3. Deep Scraping (옵션)
        if deep_scrape:
            logger.info("Phase 3: Deep scraping new postings...")
            detailed_postings = []
            for i, posting in enumerate(new_postings, 1):
                logger.info(f"  [{i}/{len(new_postings)}] {posting.title[:50]}...")
                try:
                    detailed = await self.scrape_detail(posting)
                    if self.validate_posting(detailed):
                        detailed_postings.append(detailed)
                    await self.delay()
                except TimeoutError:
                    logger.warning(f"Timeout: {posting.url}")
                    detailed_postings.append(posting)  # 기본 정보라도 저장
                except Exception as e:
                    logger.error(f"Error scraping {posting.url}: {e}")
                    detailed_postings.append(posting)
            new_postings = detailed_postings

        # 4. 저장
        logger.info("Phase 4: Saving postings...")
        saved_count = self.storage.save_postings(new_postings)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Completed {self.SOURCE_NAME}: "
            f"saved {saved_count} postings in {elapsed:.1f}s"
        )

        return new_postings

    def create_posting(
        self,
        url: str,
        title: str,
        company_kor: str = "",
        company_eng: str = "",
        **kwargs: Any,
    ) -> JobPosting | None:
        """JobPosting 생성 헬퍼

        에러 발생 시 None 반환 (로깅 후 다음 항목 진행)
        """
        try:
            return JobPosting(
                url=url,
                title=title,
                source=self.SOURCE_NAME,
                company_kor=company_kor,
                company_eng=company_eng,
                **kwargs,
            )
        except ValueError as e:
            logger.warning(f"Invalid posting data: {e}")
            return None
