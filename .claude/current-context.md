# 현재 작업 컨텍스트

## 마지막 업데이트
2026-02-03 02:30

---

## 프로젝트 완료 상태

### 스크래퍼 구현 현황

| Site | 분석 | 구현 | Deep Scraping | 저장 |
|------|------|------|---------------|------|
| KOWORK | ✅ | ✅ | ✅ 리팩토링 완료 | Jobs 시트 |
| Komate | ✅ | ✅ | ✅ | 통합 저장 |
| Klik | ✅ | ✅ | ✅ | 통합 저장 |

### 통합 테스트 결과 (2026-02-03)

| 사이트 | 수집 공고 | 소요 시간 |
|--------|----------|-----------|
| Komate | 78개 | 263초 |
| Klik | 6개 | 30초 |
| **합계** | **84개** | **~5분** |

---

## 완료된 작업

### 0. KOWORK Deep Scraping 리팩토링 ✅ (2026-02-03)
- **파일**: `src/scrapers/kowork.py`
- **변경 내용**:
  - 중복 JS evaluate 블록 통합 → `_extract_detail_info()`
  - 데이터 병합 로직 분리 → `_update_posting_from_detail()`
  - 구조화된 content_raw → `_compose_content_raw()`
  - 한국어 수준 표준화 → `_normalize_korean_level()` + `KOREAN_LEVEL_MAP`
  - 세션 만료 경고 기능 추가
  - 봇 탐지 우회 설정 추가 (`--disable-blink-features`, `navigator.webdriver`)
  - 대기 시간 설정 외부화 (`WAIT_*` 상수)
  - `deadline` 필드 저장 추가
- **결과**:
  - DRY 원칙 준수 (중복 코드 제거)
  - Komate/Klik 패턴과 일관성 확보
  - 유지보수성 향상

### 1. Komate 스크래퍼 구현 ✅
- **파일**: `src/scrapers/komate.py`
- **기능**:
  - 목록 페이지 78개 공고 수집
  - Deep Scraping (담당 업무, 우대 조건, 복지 혜택 등)
  - 한국어 수준 4단계 추출
  - 비자 정보 추출 (span 태그 파싱)
- **기술적 해결**:
  - 봇 탐지 우회: `--disable-blink-features=AutomationControlled`
  - `navigator.webdriver` 속성 숨기기

### 2. Klik 스크래퍼 구현 ✅
- **파일**: `src/scrapers/klik.py`
- **기능**:
  - 목록 페이지 공고 수집 (lazy loading 대응)
  - Deep Scraping (담당 업무, 한국어 능력, 비자 등)
  - URL 패턴: `/jobs/{alphanumeric_id}`
- **기술적 해결**:
  - 봇 탐지 우회: Komate와 동일한 방식 적용

### 3. LocalStorage 시트별 저장 기능 ✅
- **파일**: `src/storage/local_storage.py`
- **기능**: `save_to_sheet()`, `load_from_sheet()`, `get_sheet_stats()`

### 4. 통합 테스트 ✅
- **명령어**: `python main.py --sites komate klik`
- **결과**: 99개 공고 저장 (kowork 15 + komate 78 + klik 6)

---

## 데이터 파일 상태

### `data/job_postings.xlsx`
| 소스 | 공고 수 |
|------|--------|
| kowork | 15 |
| komate | 78 |
| klik | 6 |
| **Total** | **99** |

---

## 유지보수 명령어

### 전체 스크래핑 실행
```bash
# Komate + Klik (KOWORK는 세션 만료)
python main.py --sites komate klik

# 목록만 수집 (Deep Scraping 없이)
python main.py --sites komate klik --no-deep
```

### 저장소 통계 확인
```bash
python main.py --stats
```

### 개별 사이트 테스트
```bash
# Komate
python -c "
import asyncio
from src.scrapers import KomateScraper
from src.storage import LocalStorage

async def main():
    storage = LocalStorage(file_format='xlsx')
    scraper = KomateScraper(storage=storage)
    postings = await scraper.scrape_list()
    print(f'Found {len(postings)} postings')

asyncio.run(main())
"

# Klik
python -c "
import asyncio
from src.scrapers import KlikScraper
from src.storage import LocalStorage

async def main():
    storage = LocalStorage(file_format='xlsx')
    scraper = KlikScraper(storage=storage)
    postings = await scraper.scrape_list()
    print(f'Found {len(postings)} postings')

asyncio.run(main())
"
```

---

## 대기 중인 작업

### GitHub Actions 일일 자동화 (우선순위: 높음)
- **상태**: ⏳ 대기 (계획 완료)
- **계획 파일**: `.claude/plans/github-actions-automation-2026-02-03.md`

#### 개요
Komate + Klik 스크래퍼를 GitHub Actions로 매일 자동 실행 (KOWORK 제외)

#### Phase 구성
| Phase | 작업 | 상태 |
|-------|------|------|
| Phase 1 | 워크플로우 파일 생성 | ⏳ 대기 |
| Phase 2 | 테스트 (수동 실행) | ⏳ 대기 |
| Phase 3 | 스케줄 활성화 | ⏳ 대기 |

#### 다음 세션 실행 명령어
```bash
# 수동 실행
/load-context && /start-dev
```

---

## 세션 시작 명령어

```bash
# 컨텍스트 로드
/load-context

# 개발 시작
/start-dev
```

---

## 참조 문서
- GitHub Actions 자동화: `.claude/plans/github-actions-automation-2026-02-03.md`
- 상세 구현 계획: `.claude/plans/scraper-implementation-plan.md`
- 코딩 가이드: `CLAUDE.md`
