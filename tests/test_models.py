"""Tests for job posting model"""

import pytest
from datetime import datetime

from src.models import JobPosting


class TestJobPosting:
    """JobPosting 모델 테스트"""

    def test_create_valid_posting(self) -> None:
        """유효한 공고 생성"""
        posting = JobPosting(
            url="https://example.com/job/1",
            title="Software Engineer",
            source="kowork",
            company_kor="테스트회사",
        )
        assert posting.url == "https://example.com/job/1"
        assert posting.title == "Software Engineer"
        assert posting.source == "kowork"
        assert posting.company_kor == "테스트회사"

    def test_create_posting_with_english_company(self) -> None:
        """영문 회사명만 있는 공고 생성"""
        posting = JobPosting(
            url="https://example.com/job/2",
            title="Data Analyst",
            source="klik",
            company_eng="Test Corp",
        )
        assert posting.company_eng == "Test Corp"
        assert posting.company_kor == ""

    def test_missing_url_raises_error(self) -> None:
        """URL 누락 시 에러 발생"""
        with pytest.raises(ValueError, match="url is required"):
            JobPosting(
                url="",
                title="Test Job",
                source="kowork",
                company_kor="테스트",
            )

    def test_missing_title_raises_error(self) -> None:
        """제목 누락 시 에러 발생"""
        with pytest.raises(ValueError, match="title is required"):
            JobPosting(
                url="https://example.com/job/3",
                title="",
                source="kowork",
                company_kor="테스트",
            )

    def test_missing_company_raises_error(self) -> None:
        """회사명 누락 시 에러 발생"""
        with pytest.raises(ValueError, match="company_kor or company_eng is required"):
            JobPosting(
                url="https://example.com/job/4",
                title="Test Job",
                source="kowork",
            )

    def test_to_dict(self) -> None:
        """딕셔너리 변환"""
        posting = JobPosting(
            url="https://example.com/job/5",
            title="Test Job",
            source="kowork",
            company_kor="테스트회사",
            e7_support=True,
        )
        data = posting.to_dict()

        assert data["url"] == "https://example.com/job/5"
        assert data["e7_support"] == "Y"
        assert isinstance(data["scraped_at"], str)

    def test_from_dict(self) -> None:
        """딕셔너리에서 생성"""
        data = {
            "url": "https://example.com/job/6",
            "title": "Test Job",
            "source": "komate",
            "company_kor": "테스트회사",
            "company_eng": "",
            "location": "서울",
            "visa": "E-7",
            "e7_support": "Y",
            "korean_requirement": "Basic",
            "job_category": "IT",
            "job_type": "정규직",
            "deadline": "D-30",
            "content_raw": "Job description here",
            "scraped_at": "2026-02-02T10:00:00",
        }
        posting = JobPosting.from_dict(data)

        assert posting.url == "https://example.com/job/6"
        assert posting.e7_support is True
        assert isinstance(posting.scraped_at, datetime)

    def test_is_complete(self) -> None:
        """완료 여부 확인"""
        posting = JobPosting(
            url="https://example.com/job/7",
            title="Test Job",
            source="kowork",
            company_kor="테스트",
        )
        assert posting.is_complete() is False

        posting.content_raw = "Full job description"
        assert posting.is_complete() is True

    def test_get_column_order(self) -> None:
        """컬럼 순서 반환"""
        columns = JobPosting.get_column_order()
        assert columns[0] == "url"  # URL이 첫 번째
        assert "title" in columns
        assert "source" in columns
