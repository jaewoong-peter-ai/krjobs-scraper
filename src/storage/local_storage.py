"""Local file storage for job postings (CSV/XLSX)"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.models import JobPosting
from src.utils.config import get_settings

logger = logging.getLogger(__name__)


class LocalStorage:
    """로컬 파일 기반 스토리지

    CSV와 XLSX 형식을 지원하며, URL 기반 중복 체크 기능을 제공합니다.
    Cloud Functions에서는 /tmp 디렉토리를 사용해야 합니다.
    """

    def __init__(self, file_format: str = "xlsx") -> None:
        """
        Args:
            file_format: 저장 형식 ("csv" 또는 "xlsx")
        """
        self.settings = get_settings()
        self.file_format = file_format.lower()
        if self.file_format not in ("csv", "xlsx"):
            raise ValueError(f"Unsupported format: {file_format}")

        self._existing_urls: set[str] | None = None

    @property
    def file_path(self) -> Path:
        """메인 데이터 파일 경로"""
        return self.settings.data_path / f"job_postings.{self.file_format}"

    def load_existing_urls(self) -> set[str]:
        """기존 URL 목록 로드 (중복 체크용)

        Returns:
            기존에 저장된 모든 URL의 Set
        """
        if self._existing_urls is not None:
            return self._existing_urls

        if not self.file_path.exists():
            logger.info(f"No existing data file: {self.file_path}")
            self._existing_urls = set()
            return self._existing_urls

        try:
            if self.file_format == "csv":
                df = pd.read_csv(self.file_path, usecols=["url"])
            else:
                df = pd.read_excel(self.file_path, usecols=["url"])

            self._existing_urls = set(df["url"].dropna().tolist())
            logger.info(f"Loaded {len(self._existing_urls)} existing URLs")
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

    def save_postings(self, postings: list[JobPosting], append: bool = True) -> int:
        """공고 목록 저장

        Args:
            postings: 저장할 JobPosting 목록
            append: True면 기존 데이터에 추가, False면 덮어쓰기

        Returns:
            저장된 레코드 수
        """
        if not postings:
            logger.info("No postings to save")
            return 0

        # DataFrame 생성
        new_df = pd.DataFrame([p.to_dict() for p in postings])
        new_df = new_df[JobPosting.get_column_order()]  # 컬럼 순서 정렬

        if append and self.file_path.exists():
            # 기존 데이터 로드 후 병합
            try:
                if self.file_format == "csv":
                    existing_df = pd.read_csv(self.file_path)
                else:
                    existing_df = pd.read_excel(self.file_path)

                # 중복 제거 (URL 기준)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=["url"], keep="last")
                df_to_save = combined_df
            except Exception as e:
                logger.warning(f"Failed to load existing data, overwriting: {e}")
                df_to_save = new_df
        else:
            df_to_save = new_df

        # 저장
        if self.file_format == "csv":
            df_to_save.to_csv(self.file_path, index=False, encoding="utf-8-sig")
        else:
            df_to_save.to_excel(self.file_path, index=False, engine="openpyxl")

        # 캐시 무효화
        self._existing_urls = None

        logger.info(f"Saved {len(postings)} new postings to {self.file_path}")
        return len(postings)

    def load_all_postings(self) -> list[JobPosting]:
        """모든 공고 로드"""
        if not self.file_path.exists():
            return []

        try:
            if self.file_format == "csv":
                df = pd.read_csv(self.file_path)
            else:
                df = pd.read_excel(self.file_path)

            postings = []
            for _, row in df.iterrows():
                try:
                    posting = JobPosting.from_dict(row.to_dict())
                    postings.append(posting)
                except Exception as e:
                    logger.warning(f"Failed to parse row: {e}")
                    continue

            return postings

        except Exception as e:
            logger.error(f"Failed to load postings: {e}")
            return []

    def get_stats(self) -> dict:
        """저장소 통계 반환"""
        postings = self.load_all_postings()
        if not postings:
            return {"total": 0}

        sources = {}
        for p in postings:
            sources[p.source] = sources.get(p.source, 0) + 1

        return {
            "total": len(postings),
            "by_source": sources,
            "file_path": str(self.file_path),
        }

    def backup(self) -> Path | None:
        """현재 데이터 백업"""
        if not self.file_path.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.settings.data_path / f"jobs_backup_{timestamp}.{self.file_format}"

        import shutil
        shutil.copy(self.file_path, backup_path)
        logger.info(f"Backup created: {backup_path}")
        return backup_path

    def save_to_sheet(
        self,
        postings: list[JobPosting],
        sheet_name: str,
        append: bool = True
    ) -> int:
        """특정 시트에 공고 저장 (XLSX 전용)

        Args:
            postings: 저장할 JobPosting 목록
            sheet_name: 시트 이름 (예: 'komate', 'kowork')
            append: True면 기존 데이터에 추가

        Returns:
            저장된 레코드 수
        """
        if self.file_format != "xlsx":
            logger.warning("Sheet-based storage only supports XLSX format")
            return self.save_postings(postings, append)

        if not postings:
            logger.info("No postings to save")
            return 0

        # 새 데이터 DataFrame
        new_df = pd.DataFrame([p.to_dict() for p in postings])
        new_df = new_df[JobPosting.get_column_order()]

        try:
            if self.file_path.exists():
                # 기존 파일의 모든 시트 로드
                with pd.ExcelFile(self.file_path) as xls:
                    existing_sheets = {
                        name: pd.read_excel(xls, sheet_name=name)
                        for name in xls.sheet_names
                    }
            else:
                existing_sheets = {}

            # 해당 시트에 데이터 병합
            if append and sheet_name in existing_sheets:
                existing_df = existing_sheets[sheet_name]
                # 컬럼 맞추기 (기존 파일에 없는 컬럼 추가)
                for col in new_df.columns:
                    if col not in existing_df.columns:
                        existing_df[col] = ""
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=["url"], keep="last")
                existing_sheets[sheet_name] = combined_df
            else:
                existing_sheets[sheet_name] = new_df

            # 모든 시트 저장
            with pd.ExcelWriter(self.file_path, engine="openpyxl") as writer:
                for name, df in existing_sheets.items():
                    df.to_excel(writer, sheet_name=name, index=False)

            logger.info(f"Saved {len(postings)} postings to sheet '{sheet_name}'")
            return len(postings)

        except Exception as e:
            logger.error(f"Failed to save to sheet: {e}")
            raise

    def load_from_sheet(self, sheet_name: str) -> list[JobPosting]:
        """특정 시트에서 공고 로드 (XLSX 전용)"""
        if self.file_format != "xlsx" or not self.file_path.exists():
            return []

        try:
            df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            postings = []
            for _, row in df.iterrows():
                try:
                    posting = JobPosting.from_dict(row.to_dict())
                    postings.append(posting)
                except Exception as e:
                    logger.warning(f"Failed to parse row: {e}")
            return postings
        except Exception as e:
            logger.error(f"Failed to load from sheet '{sheet_name}': {e}")
            return []

    def get_sheet_stats(self) -> dict:
        """시트별 통계 반환"""
        if self.file_format != "xlsx" or not self.file_path.exists():
            return {}

        try:
            with pd.ExcelFile(self.file_path) as xls:
                stats = {}
                for name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=name)
                    stats[name] = len(df)
                return stats
        except Exception as e:
            logger.error(f"Failed to get sheet stats: {e}")
            return {}
