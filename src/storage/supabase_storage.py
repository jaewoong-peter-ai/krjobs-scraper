"""Supabase storage for job postings"""

import logging
import os
from typing import Any

from supabase import create_client, Client

from src.models import JobPosting

logger = logging.getLogger(__name__)


class SupabaseStorage:
    """Supabase 기반 스토리지

    Supabase PostgreSQL 데이터베이스를 사용하여 채용 공고를 저장합니다.
    URL 기반 중복 체크 및 upsert를 지원합니다.
    """

    TABLE_NAME = "job_postings"

    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
    ) -> None:
        """
        Args:
            url: Supabase 프로젝트 URL (기본값: SUPABASE_URL 환경변수)
            key: Supabase anon/service key (기본값: SUPABASE_ANON_KEY 환경변수)
        """
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")

        if not self.url or not self.key:
            raise ValueError(
                "Supabase URL and key are required. "
                "Set SUPABASE_URL and SUPABASE_ANON_KEY environment variables."
            )

        self._client: Client | None = None
        self._existing_urls: set[str] | None = None

    @property
    def client(self) -> Client:
        """Supabase 클라이언트 (lazy initialization)"""
        if self._client is None:
            self._client = create_client(self.url, self.key)
            logger.info(f"Connected to Supabase: {self.url}")
        return self._client

    def load_existing_urls(self) -> set[str]:
        """기존 URL 목록 로드 (중복 체크용)

        Returns:
            기존에 저장된 모든 URL의 Set
        """
        if self._existing_urls is not None:
            return self._existing_urls

        try:
            # URL 컬럼만 선택하여 메모리 효율화
            response = (
                self.client.table(self.TABLE_NAME)
                .select("url")
                .execute()
            )

            self._existing_urls = {row["url"] for row in response.data}
            logger.info(f"Loaded {len(self._existing_urls)} existing URLs from Supabase")
            return self._existing_urls

        except Exception as e:
            logger.error(f"Failed to load existing URLs: {e}")
            self._existing_urls = set()
            return self._existing_urls

    def is_new_url(self, url: str) -> bool:
        """URL이 신규인지 확인"""
        existing = self.load_existing_urls()
        return url not in existing

    def filter_new_postings(self, postings: list[JobPosting]) -> list[JobPosting]:
        """신규 공고만 필터링"""
        existing = self.load_existing_urls()
        new_postings = [p for p in postings if p.url not in existing]
        logger.info(f"Filtered: {len(new_postings)} new out of {len(postings)} total")
        return new_postings

    def _posting_to_db_dict(self, posting: JobPosting) -> dict[str, Any]:
        """JobPosting을 DB 저장용 딕셔너리로 변환"""
        data = posting.to_dict()
        # scraped_at을 ISO 형식 문자열로 변환
        if data.get("scraped_at") and hasattr(data["scraped_at"], "isoformat"):
            data["scraped_at"] = data["scraped_at"].isoformat()
        return data

    def save_postings(self, postings: list[JobPosting], append: bool = True) -> int:
        """공고 목록 저장 (upsert)

        Args:
            postings: 저장할 JobPosting 목록
            append: Supabase에서는 항상 upsert 방식 (무시됨)

        Returns:
            저장된 레코드 수
        """
        if not postings:
            logger.info("No postings to save")
            return 0

        try:
            # JobPosting을 DB용 딕셔너리로 변환
            data = [self._posting_to_db_dict(p) for p in postings]

            # Upsert: URL이 중복되면 업데이트, 아니면 삽입
            response = (
                self.client.table(self.TABLE_NAME)
                .upsert(data, on_conflict="url")
                .execute()
            )

            # 캐시 무효화
            self._existing_urls = None

            saved_count = len(response.data)
            logger.info(f"Saved {saved_count} postings to Supabase")
            return saved_count

        except Exception as e:
            logger.error(f"Failed to save postings to Supabase: {e}")
            raise

    def load_all_postings(self, source: str | None = None) -> list[JobPosting]:
        """모든 공고 로드

        Args:
            source: 특정 소스만 로드 (예: 'komate', 'klik')

        Returns:
            JobPosting 목록
        """
        try:
            query = self.client.table(self.TABLE_NAME).select("*")

            if source:
                query = query.eq("source", source)

            response = query.order("scraped_at", desc=True).execute()

            postings = []
            for row in response.data:
                try:
                    posting = JobPosting.from_dict(row)
                    postings.append(posting)
                except Exception as e:
                    logger.warning(f"Failed to parse row: {e}")
                    continue

            logger.info(f"Loaded {len(postings)} postings from Supabase")
            return postings

        except Exception as e:
            logger.error(f"Failed to load postings: {e}")
            return []

    def get_stats(self) -> dict[str, Any]:
        """저장소 통계 반환"""
        try:
            # 전체 카운트
            total_response = (
                self.client.table(self.TABLE_NAME)
                .select("id", count="exact")
                .execute()
            )
            total = total_response.count or 0

            # 소스별 카운트
            sources_response = (
                self.client.table(self.TABLE_NAME)
                .select("source")
                .execute()
            )

            sources: dict[str, int] = {}
            for row in sources_response.data:
                source = row.get("source", "unknown")
                sources[source] = sources.get(source, 0) + 1

            return {
                "total": total,
                "by_source": sources,
                "storage_type": "supabase",
                "url": self.url,
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"total": 0, "error": str(e)}

    def delete_by_source(self, source: str) -> int:
        """특정 소스의 모든 공고 삭제

        Args:
            source: 삭제할 소스 (예: 'komate', 'klik')

        Returns:
            삭제된 레코드 수
        """
        try:
            response = (
                self.client.table(self.TABLE_NAME)
                .delete()
                .eq("source", source)
                .execute()
            )

            deleted_count = len(response.data)
            logger.info(f"Deleted {deleted_count} postings from source '{source}'")

            # 캐시 무효화
            self._existing_urls = None

            return deleted_count

        except Exception as e:
            logger.error(f"Failed to delete postings: {e}")
            raise
