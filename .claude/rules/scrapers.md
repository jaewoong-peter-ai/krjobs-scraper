# 스크래퍼 작성 규칙

**적용 대상**: `src/scrapers/**/*.py`

이 파일에서 작업할 때:

## 필수 사항
1. `BaseScraper` 클래스를 상속
2. `async def scrape_list()` - 리스트 페이지 스크래핑
3. `async def scrape_detail(url)` - 상세 페이지 Deep Scraping
4. Type hints 모든 함수에 적용

## 에러 처리
```python
try:
    # 스크래핑 로직
except TimeoutError:
    logger.warning(f"Timeout: {url}")
    return None
except Exception as e:
    logger.error(f"Error scraping {url}: {e}")
    raise
```

## Rate Limiting
- 요청 간 최소 1초 delay
- 연속 실패 시 exponential backoff
- 사이트별 동시 요청 제한

## 필수 필드 검증
스크래핑 후 반드시 검증:
- `url` (not empty)
- `title` (not empty)
- `company_kor` or `company_eng` (at least one)

## 테스트
- 각 스크래퍼는 단위 테스트 필수
- Mock 데이터로 파싱 로직 테스트
