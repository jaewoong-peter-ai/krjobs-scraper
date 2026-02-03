"""krjobs-scraper main entry point

Cloud Functions 호환 진입점 및 CLI 인터페이스
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Any

from src.scrapers import KoworkScraper, KomateScraper, KlikScraper
from src.storage import LocalStorage, SupabaseStorage
from src.utils.config import get_settings

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# Cloud Functions 진입점
def main(request: Any = None) -> dict:
    """Cloud Functions 진입점

    Args:
        request: Cloud Functions HTTP 요청 객체 (옵션)

    Returns:
        실행 결과 딕셔너리
    """
    # 요청 파라미터 파싱
    sites = ["kowork", "komate", "klik"]  # 기본값: 모든 사이트
    deep_scrape = True

    if request:
        try:
            request_json = request.get_json(silent=True)
            if request_json:
                sites = request_json.get("sites", sites)
                deep_scrape = request_json.get("deep_scrape", deep_scrape)
        except Exception:
            pass

    # 스크래핑 실행
    result = asyncio.run(run_scrapers(sites, deep_scrape))
    return result


def get_storage(storage_type: str | None = None, file_format: str = "xlsx"):
    """설정에 따른 스토리지 인스턴스 반환

    Args:
        storage_type: 스토리지 타입 (local, supabase). None이면 환경변수 사용
        file_format: 로컬 저장 형식 (csv, xlsx)

    Returns:
        LocalStorage 또는 SupabaseStorage 인스턴스
    """
    settings = get_settings()
    storage_type = storage_type or settings.storage_type

    if storage_type == "supabase":
        logger.info("Using Supabase storage")
        return SupabaseStorage(
            url=settings.supabase_url,
            key=settings.get_supabase_key(),
        )
    else:
        logger.info(f"Using local storage ({file_format})")
        return LocalStorage(file_format=file_format)


async def run_scrapers(
    sites: list[str] | None = None,
    deep_scrape: bool = True,
    storage_type: str | None = None,
    file_format: str = "xlsx",
) -> dict:
    """스크래퍼 실행

    Args:
        sites: 스크래핑할 사이트 목록 (None이면 모든 사이트)
        deep_scrape: 상세 페이지 스크래핑 여부
        storage_type: 스토리지 타입 (local, supabase). None이면 환경변수 사용
        file_format: 로컬 저장 형식 (csv, xlsx)

    Returns:
        실행 결과 딕셔너리
    """
    settings = get_settings()
    storage = get_storage(storage_type, file_format)

    # 사이트별 스크래퍼 매핑
    scraper_map = {
        "kowork": KoworkScraper,
        "komate": KomateScraper,
        "klik": KlikScraper,
    }

    # 실행할 사이트 결정
    if sites is None:
        sites = list(scraper_map.keys())

    results = {
        "started_at": datetime.now().isoformat(),
        "sites": {},
        "total_new": 0,
        "errors": [],
    }

    logger.info(f"Starting scrape for sites: {sites}")
    logger.info(f"Deep scrape: {deep_scrape}")
    logger.info(f"Data directory: {settings.data_path}")

    for site in sites:
        if site not in scraper_map:
            logger.warning(f"Unknown site: {site}")
            results["errors"].append(f"Unknown site: {site}")
            continue

        try:
            scraper = scraper_map[site](storage=storage)
            postings = await scraper.run(deep_scrape=deep_scrape)

            results["sites"][site] = {
                "status": "success",
                "new_postings": len(postings),
            }
            results["total_new"] += len(postings)

        except Exception as e:
            logger.error(f"Error scraping {site}: {e}")
            results["sites"][site] = {
                "status": "error",
                "error": str(e),
            }
            results["errors"].append(f"{site}: {str(e)}")

    results["completed_at"] = datetime.now().isoformat()

    # 저장소 통계
    stats = storage.get_stats()
    results["storage_stats"] = stats

    logger.info(f"Scraping completed. Total new postings: {results['total_new']}")
    return results


async def run_single_scraper(site: str, deep_scrape: bool = True) -> dict:
    """단일 사이트 스크래핑

    Args:
        site: 사이트 이름 (kowork, komate, klik)
        deep_scrape: 상세 페이지 스크래핑 여부

    Returns:
        실행 결과 딕셔너리
    """
    return await run_scrapers([site], deep_scrape)


# CLI 인터페이스
def cli() -> None:
    """CLI 인터페이스"""
    import argparse

    parser = argparse.ArgumentParser(
        description="krjobs-scraper - 외국인 대상 한국 채용 사이트 스크래핑"
    )
    parser.add_argument(
        "--sites",
        nargs="+",
        choices=["kowork", "komate", "klik", "all"],
        default=["all"],
        help="스크래핑할 사이트 (기본값: all)",
    )
    parser.add_argument(
        "--no-deep",
        action="store_true",
        help="상세 페이지 스크래핑 건너뛰기 (목록만 수집)",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "xlsx"],
        default="xlsx",
        help="저장 형식 (기본값: xlsx)",
    )
    parser.add_argument(
        "--storage",
        choices=["local", "supabase"],
        default=None,
        help="스토리지 타입 (기본값: 환경변수 STORAGE_TYPE)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="저장소 통계만 출력",
    )

    args = parser.parse_args()

    # 통계 출력 모드
    if args.stats:
        storage = get_storage(args.storage, args.format)
        stats = storage.get_stats()
        print("\n=== Storage Statistics ===")
        print(f"Total postings: {stats.get('total', 0)}")
        if stats.get("by_source"):
            print("By source:")
            for source, count in stats["by_source"].items():
                print(f"  - {source}: {count}")
        print(f"File: {stats.get('file_path', 'N/A')}")
        return

    # 사이트 결정
    sites = None if "all" in args.sites else args.sites

    # 스크래핑 실행
    result = asyncio.run(run_scrapers(
        sites,
        deep_scrape=not args.no_deep,
        storage_type=args.storage,
        file_format=args.format,
    ))

    # 결과 출력
    print("\n=== Scraping Result ===")
    print(f"Started: {result['started_at']}")
    print(f"Completed: {result['completed_at']}")
    print(f"Total new postings: {result['total_new']}")
    print("\nBy site:")
    for site, info in result["sites"].items():
        status = info.get("status", "unknown")
        if status == "success":
            print(f"  - {site}: {info['new_postings']} new postings")
        else:
            print(f"  - {site}: ERROR - {info.get('error', 'Unknown error')}")

    if result["errors"]:
        print("\nErrors:")
        for error in result["errors"]:
            print(f"  - {error}")


if __name__ == "__main__":
    cli()
