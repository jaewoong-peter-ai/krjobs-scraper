# Scraper Implementation Plan

## Last Updated
2026-02-03 01:50

---

## Overview

외국인 대상 한국 채용 사이트 3개(KOWORK, Komate, Klik) 스크래핑 파이프라인 구현

---

## 1. KOWORK Scraper ✅ COMPLETED

### Target URLs
- **List**: `https://kowork.kr/en`
- **Detail**: `https://kowork.kr/en/post/{id}`

### Authentication
- **Required**: Yes (Google OAuth)
- **Session**: `data/kowork_session.json`
- **Expiry**: ~1 hour (Firebase JWT)
- **Status**: ⚠️ 세션 만료됨 - 재로그인 필요

### Implementation
- **File**: `src/scrapers/kowork.py`
- **Features**: 목록/상세 스크래핑, 브라우저 재사용 최적화

---

## 2. Komate Scraper ✅ COMPLETED

### Target URLs
- **List**: `https://komate.saramin.co.kr/recruits/list`
- **Detail**: `https://komate.saramin.co.kr/recruits/{id}`

### Authentication
- **Required**: No (공개 페이지)

### Implementation
- **File**: `src/scrapers/komate.py`
- **Features**:
  - 목록 페이지 78개 공고 수집
  - Deep Scraping (담당 업무, 우대 조건, 복지 혜택 등)
  - 한국어 수준 4단계 추출
  - 비자 정보 추출

### Technical Details
- 봇 탐지 우회: `--disable-blink-features=AutomationControlled`
- `navigator.webdriver` 속성 숨기기
- `<span>` Badge 컴포넌트에서 비자 추출

### Test Results (2026-02-03)
- 목록 스크래핑: 78개 공고
- Deep Scraping: 10개 테스트 완료
- 별도 워크시트(komate) 저장: ✅

---

## 3. Klik Scraper ✅ COMPLETED

### Target URLs
- **Base**: `https://www.klik.co.kr`
- **List**: `https://www.klik.co.kr/jobs`
- **Detail**: `https://www.klik.co.kr/jobs/{alphanumeric_id}`

### Authentication
- **Required**: No (공개 페이지)

### Implementation
- **File**: `src/scrapers/klik.py`
- **Features**:
  - 목록 페이지 공고 수집 (lazy loading 대응)
  - Deep Scraping (담당 업무, 한국어 능력, 비자 등)
  - 봇 탐지 우회 적용

### Technical Details
- 봇 탐지 우회: `--disable-blink-features=AutomationControlled`
- `navigator.webdriver` 속성 숨기기
- URL 패턴: `/jobs/{alphanumeric_id}`

### Test Results (2026-02-03)
- 목록 스크래핑: 6개 공고
- Deep Scraping: 5개 테스트 완료
- 별도 워크시트(klik) 저장: ✅

---

## Implementation Checklist

### Komate Scraper ✅
- [x] Create `src/scrapers/komate.py`
- [x] Implement `scrape_list()` - 78개 공고 수집
- [x] Implement `scrape_detail()` - 상세 정보 추출
- [x] Implement `scrape_all_details()` - 브라우저 재사용 최적화
- [x] Override `run()` for efficiency
- [x] Test with 10 postings
- [x] Save to XLSX separate worksheet

### Klik Scraper ✅
- [x] Analyze site structure (www.klik.co.kr)
- [x] Create `src/scrapers/klik.py`
- [x] Implement `scrape_list()` - 6개 공고 수집
- [x] Implement `scrape_detail()` - 상세 정보 추출
- [x] Implement `scrape_all_details()` - 브라우저 재사용 최적화
- [x] Override `run()` for efficiency
- [x] Test with 5 postings
- [x] Save to XLSX separate worksheet (klik)

### Integration ✅
- [x] Komate 전체 78개 공고 Deep Scraping
- [x] Klik 전체 공고 Deep Scraping
- [x] Test full pipeline: `python main.py --sites komate klik`
- [x] Verify deduplication works across sites (URL 기반)
- [x] 통합 테스트 완료: 99개 공고 저장 (kowork 15 + komate 78 + klik 6)

---

## Data Storage

### 파일 구조: `data/job_postings.xlsx`

| 시트 | 데이터 | 컬럼 수 | 상태 |
|------|--------|---------|------|
| Jobs | KOWORK (목록만) | 10 | 기존 데이터 |
| komate | Komate (Deep) | 14 | 완료 |
| klik | Klik (Deep) | 14 | 완료 |

### 스키마 (14 컬럼)
1. url, title, company_kor, company_eng
2. location, visa, e7_support, korean_requirement
3. job_category, job_type, deadline
4. content_raw, scraped_at, source

---

## 다음 세션 작업

### Phase 1: Komate 전체 스크래핑 (78개 공고)
```bash
python -c "
import asyncio
from src.scrapers import KomateScraper
from src.storage import LocalStorage

async def main():
    storage = LocalStorage(file_format='xlsx')
    scraper = KomateScraper(storage=storage)
    postings = await scraper.scrape_list()
    detailed = await scraper.scrape_all_details(postings)
    storage.save_to_sheet(detailed, 'komate')

asyncio.run(main())
"
```

### Phase 2: Klik 전체 스크래핑
```bash
python -c "
import asyncio
from src.scrapers import KlikScraper
from src.storage import LocalStorage

async def main():
    storage = LocalStorage(file_format='xlsx')
    scraper = KlikScraper(storage=storage)
    postings = await scraper.scrape_list()
    detailed = await scraper.scrape_all_details(postings)
    storage.save_to_sheet(detailed, 'klik')

asyncio.run(main())
"
```

### Phase 3: 통합 테스트
```bash
python main.py --sites komate,klik
python main.py --stats
```

---

## Session Resume Command

```bash
# 컨텍스트 로드
/load-context

# 개발 시작
/start-dev
```
