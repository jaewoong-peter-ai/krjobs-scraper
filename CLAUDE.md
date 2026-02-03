# Claude 코딩 가이드라인

## 프로젝트 개요
**krjobs-scraper** - 외국인 대상 한국 채용 사이트 스크래핑 파이프라인

### 기술 스택
| Layer | Technology |
|-------|------------|
| **Language** | Python 3.11+ |
| **Scraping** | Playwright / BeautifulSoup |
| **Output** | Google Sheets API |
| **Scheduler** | GitHub Actions (추후) |

### 타겟 사이트
| 사이트 | URL | 특징 |
|--------|-----|------|
| KOWORK | kowork.go.kr | 공공 고용 서비스 |
| Komate | komate.co.kr | 외국인 전문 채용 |
| Klik | klik.kr | 다국어 채용 플랫폼 |

## 코딩 스타일

### Python
- Type hints 사용 필수
- Async/await 패턴 권장 (Playwright)
- 함수명: `snake_case`
- 클래스명: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

### 프로젝트 구조 (예정)
```
krjobs-scraper/
├── src/
│   ├── scrapers/        # 사이트별 스크래퍼
│   │   ├── base.py      # 공통 베이스 클래스
│   │   ├── kowork.py
│   │   ├── komate.py
│   │   └── klik.py
│   ├── models/          # 데이터 모델
│   ├── sheets/          # Google Sheets 연동
│   └── utils/           # 유틸리티
├── tests/
├── docs/
└── requirements.txt
```

## 해야 할 것 (Do's)
- URL을 고유 ID로 사용하여 중복 체크
- 영어 버전 페이지 우선 스크래핑
- 에러 발생 시 로깅 후 다음 항목 진행
- 각 사이트별 rate limiting 준수
- 스크래핑 결과 검증 (필수 필드 체크)

## 하지 말아야 할 것 (Don'ts)
- 하드코딩된 credentials (환경변수 사용)
- 과도한 요청 (적절한 delay 유지)
- 본문 없이 메타데이터만 수집 (Deep Scraping 필수)
- Google Sheets 직접 쓰기 (batch 처리 권장)

## 데이터 스키마
```python
@dataclass
class JobPosting:
    url: str                    # 공고 고유 주소 (PK)
    title: str                  # 공고 제목
    company_kor: str            # 한국 회사명
    company_eng: str            # 영문 회사명
    location: str               # 근무지 (도시)
    visa: str                   # 지원 가능 비자
    e7_support: bool            # E-7 비자 지원 여부
    korean_requirement: str     # 한국어 요구사항 **중요**
    job_category: str           # 직무
    job_type: str               # 고용 형태
    content_raw: str            # 상세 본문 전체
    scraped_at: datetime        # 스크래핑 시각
    source: str                 # 출처 사이트
```

## 컨텍스트 파일 관리

### `.claude/current-context.md` (Primary)
- **세션 시작 시 참조**: `/load-context`로 로드
- **실시간 트래킹**: 현재 진행 중인 작업, 다음 할 일
- **간결하게 유지**: context window 절약을 위해 핵심 정보만

### `.claude/rules/` (Advanced)
- 파일 패턴별 자동 규칙 로드
- 스크래퍼 작성 시 `scrapers.md` 규칙 적용
