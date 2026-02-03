"""Job Posting data model"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class JobPosting:
    """채용 공고 데이터 모델

    URL을 Primary Key로 사용하여 중복 체크에 활용
    """

    # 필수 필드 (목록 페이지에서 수집)
    url: str                              # 공고 고유 주소 (PK)
    title: str                            # 공고 제목
    source: str                           # 출처 사이트 (kowork/komate/klik)

    # 목록 페이지에서 수집 가능한 필드
    company_kor: str = ""                 # 한국 회사명
    company_eng: str = ""                 # 영문 회사명
    location: str = ""                    # 근무지 (도시)
    job_type: str = ""                    # 고용 형태 (정규직, 계약직 등)
    job_category: str = ""                # 직무 카테고리
    deadline: str = ""                    # 마감일 (D-XX 또는 날짜)
    e7_support: bool = False              # E-7 비자 지원 여부

    # 상세 페이지에서 수집 (Deep Scraping)
    visa: str = ""                        # 지원 가능 비자 상세
    korean_requirement: str = ""          # 한국어 요구사항 **중요**
    content_raw: str = ""                 # 상세 본문 전체

    # 메타데이터 (자동 생성)
    scraped_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """필수 필드 검증"""
        if not self.url:
            raise ValueError("url is required")
        if not self.title:
            raise ValueError("title is required")
        if not self.source:
            raise ValueError("source is required")
        # 회사명은 한글 또는 영문 중 하나 이상 필요
        if not self.company_kor and not self.company_eng:
            raise ValueError("company_kor or company_eng is required")

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (CSV/Excel 저장용)"""
        data = asdict(self)
        # datetime을 문자열로 변환
        data["scraped_at"] = self.scraped_at.isoformat()
        # bool을 문자열로 변환 (Excel 호환)
        data["e7_support"] = "Y" if self.e7_support else "N"
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "JobPosting":
        """딕셔너리에서 JobPosting 생성"""
        # scraped_at 문자열을 datetime으로 변환
        if isinstance(data.get("scraped_at"), str):
            data["scraped_at"] = datetime.fromisoformat(data["scraped_at"])
        # e7_support 문자열을 bool로 변환
        if isinstance(data.get("e7_support"), str):
            data["e7_support"] = data["e7_support"].upper() == "Y"
        return cls(**data)

    @classmethod
    def get_column_order(cls) -> list[str]:
        """CSV/Excel 컬럼 순서 반환"""
        return [
            "url",
            "title",
            "company_kor",
            "company_eng",
            "location",
            "visa",
            "e7_support",
            "korean_requirement",
            "job_category",
            "job_type",
            "deadline",
            "content_raw",
            "scraped_at",
            "source",
        ]

    def is_complete(self) -> bool:
        """Deep Scraping 완료 여부 확인"""
        return bool(self.content_raw)
