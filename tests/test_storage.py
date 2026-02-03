"""Tests for local storage"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.models import JobPosting
from src.storage import LocalStorage


class TestLocalStorage:
    """LocalStorage 테스트"""

    @pytest.fixture
    def temp_storage(self, tmp_path: Path) -> LocalStorage:
        """임시 저장소 생성"""
        with patch("src.storage.local_storage.get_settings") as mock_settings:
            mock_settings.return_value.data_path = tmp_path
            storage = LocalStorage(file_format="csv")
            return storage

    @pytest.fixture
    def sample_postings(self) -> list[JobPosting]:
        """샘플 공고 목록"""
        return [
            JobPosting(
                url="https://example.com/job/1",
                title="Software Engineer",
                source="kowork",
                company_kor="테스트회사1",
            ),
            JobPosting(
                url="https://example.com/job/2",
                title="Data Analyst",
                source="komate",
                company_kor="테스트회사2",
            ),
        ]

    def test_save_and_load_postings(
        self, temp_storage: LocalStorage, sample_postings: list[JobPosting]
    ) -> None:
        """공고 저장 및 로드"""
        # 저장
        saved_count = temp_storage.save_postings(sample_postings)
        assert saved_count == 2

        # 로드
        loaded = temp_storage.load_all_postings()
        assert len(loaded) == 2
        assert loaded[0].url == "https://example.com/job/1"

    def test_load_existing_urls(
        self, temp_storage: LocalStorage, sample_postings: list[JobPosting]
    ) -> None:
        """기존 URL 로드"""
        temp_storage.save_postings(sample_postings)

        urls = temp_storage.load_existing_urls()
        assert len(urls) == 2
        assert "https://example.com/job/1" in urls
        assert "https://example.com/job/2" in urls

    def test_is_new_url(
        self, temp_storage: LocalStorage, sample_postings: list[JobPosting]
    ) -> None:
        """신규 URL 확인"""
        temp_storage.save_postings(sample_postings)

        assert temp_storage.is_new_url("https://example.com/job/1") is False
        assert temp_storage.is_new_url("https://example.com/job/3") is True

    def test_filter_new_postings(
        self, temp_storage: LocalStorage, sample_postings: list[JobPosting]
    ) -> None:
        """신규 공고 필터링"""
        temp_storage.save_postings(sample_postings)

        new_postings = [
            JobPosting(
                url="https://example.com/job/1",  # 기존
                title="Duplicate",
                source="kowork",
                company_kor="중복회사",
            ),
            JobPosting(
                url="https://example.com/job/3",  # 신규
                title="New Job",
                source="klik",
                company_kor="새회사",
            ),
        ]

        filtered = temp_storage.filter_new_postings(new_postings)
        assert len(filtered) == 1
        assert filtered[0].url == "https://example.com/job/3"

    def test_append_mode(
        self, temp_storage: LocalStorage, sample_postings: list[JobPosting]
    ) -> None:
        """추가 모드 테스트"""
        # 첫 번째 저장
        temp_storage.save_postings([sample_postings[0]])

        # 두 번째 저장 (추가)
        temp_storage.save_postings([sample_postings[1]], append=True)

        loaded = temp_storage.load_all_postings()
        assert len(loaded) == 2

    def test_duplicate_prevention(
        self, temp_storage: LocalStorage, sample_postings: list[JobPosting]
    ) -> None:
        """중복 방지 테스트"""
        temp_storage.save_postings(sample_postings)
        temp_storage.save_postings(sample_postings, append=True)  # 같은 데이터 다시 저장

        loaded = temp_storage.load_all_postings()
        assert len(loaded) == 2  # 중복 제거되어 2개만

    def test_get_stats(
        self, temp_storage: LocalStorage, sample_postings: list[JobPosting]
    ) -> None:
        """통계 조회"""
        temp_storage.save_postings(sample_postings)

        stats = temp_storage.get_stats()
        assert stats["total"] == 2
        assert stats["by_source"]["kowork"] == 1
        assert stats["by_source"]["komate"] == 1

    def test_empty_storage_stats(self, temp_storage: LocalStorage) -> None:
        """빈 저장소 통계"""
        stats = temp_storage.get_stats()
        assert stats["total"] == 0
