# krjobs-scraper: Playwright MCP 스크래핑 계획

## 개요
- **목표**: Playwright MCP를 활용하여 3개 외국인 채용 사이트의 채용공고를 스크래핑하고, Google Sheets Master DB와 대조하여 신규 공고만 추가
- **예상 소요**: 3 Phase (사전 준비 + 사이트별 스크래핑 + 검증)
- **생성일**: 2026-02-02

---

## 타겟 사이트 분석 결과

| 사이트 | URL | 공고 URL 패턴 | 특징 |
|--------|-----|--------------|------|
| **KOWORK** | kowork.kr/en | /en/post/{id} | E-7 Sponsors 태그, 상세 JD |
| **Komate** | komate.saramin.co.kr | /recruits/{id} | iframe 내 JD, 한국어 수준 표시 |
| **Klik** | www.klik.co.kr | /jobs/{id} | 28개 언어 번역 지원 |

---

## 효율화된 워크플로우

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  1. 사이트 접속  │───▶│ 2. 목록 스크래핑 │───▶│ 3. Google Sheet │
│  (Playwright)   │    │  (URL+메타정보)  │    │   기존 URL 로드 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                               ┌──────▼──────┐
                                               │ 4. 중복 체크 │
                                               │  (URL 비교)  │
                                               └──────┬──────┘
                                                      │
                       ┌─────────────────┐     ┌──────▼──────┐
                       │ 6. 신규 공고만   │◀────│ 5. 신규 공고 │
                       │   Sheet에 추가   │     │  Deep Scrape │
                       └─────────────────┘     └─────────────┘
```

### 핵심 효율화 포인트
- **목록 스크래핑 먼저**: 메타정보(URL, Title, Company 등)만 빠르게 수집
- **중복 체크 후 Deep Scraping**: Google Sheet의 기존 URL과 대조
- **신규 공고만 상세 접속**: 불필요한 상세 페이지 방문 최소화

---

## Phase 구성

### Phase 1: Google Sheets API 설정 (사전 준비)
- **목표**: Google Sheets API 연동 환경 구성
- **작업 내용**:
  1. Google Cloud Console에서 Service Account 생성
  2. Google Sheets API 활성화
  3. Service Account JSON 키 다운로드
  4. Master DB Sheet에 Service Account 권한 부여
  5. .env 파일 생성 및 설정
- **완료 조건**: API 연동 테스트 성공

### Phase 2: 사이트별 스크래핑 실행 (효율화된 흐름)
- **목표**: 3개 사이트 채용공고 스크래핑 (신규 공고만 Deep Scraping)
- **각 사이트별 실행 흐름**:
  ```
  2-1. 목록 페이지 스크래핑 (메타정보만)
       - URL, Title, Company, Location, Job_Type, Deadline 등

  2-2. Google Sheet에서 기존 URL 목록 로드

  2-3. 신규 공고 필터링 (URL 비교)
       - 기존에 없는 URL만 추출

  2-4. 신규 공고만 상세 페이지 Deep Scraping
       - Content_Raw, Visa, Korean_Req 등 상세 정보

  2-5. 신규 공고 데이터 Sheet에 배치 추가
  ```
- **완료 조건**: 각 사이트별 신규 공고 데이터 Sheet 저장 완료

### Phase 3: 검증 및 정리
- **목표**: 데이터 정합성 확인
- **작업 내용**:
  1. Sheet에 저장된 데이터 확인
  2. 중복 데이터 없는지 검증
  3. 필수 필드 누락 없는지 확인
- **완료 조건**: 모든 데이터 정합성 검증 완료

---

## 수집 데이터 스키마

### 목록 페이지에서 수집 (Light Scraping)
| 컬럼 | 설명 | KOWORK | Komate | Klik |
|------|------|--------|--------|------|
| URL | 공고 고유 주소 (PK) | O | O | O |
| Title | 공고 제목 | O | O | O |
| Company_KOR | 한국 회사명 | O | O | O |
| Location | 근무지 | O | O | O |
| Job_Type | 고용 형태 | O | O | O |
| Job_Category | 직무 | O | O | O |
| Deadline | 마감일 (D-XX) | O | O | O |
| E7_Support | E-7 태그 여부 | O | O | O |

### 상세 페이지에서 수집 (Deep Scraping - 신규 공고만)
| 컬럼 | 설명 | KOWORK | Komate | Klik |
|------|------|--------|--------|------|
| Visa | 지원 가능 비자 상세 | O | O | 확인필요 |
| Korean_Req | 한국어 요구사항 | JD내 | O | O |
| Content_Raw | 상세 본문 전체 | O | O (iframe) | O |
| Company_ENG | 영문 회사명 | 일부 | X | X |

### 자동 생성
| 컬럼 | 설명 |
|------|------|
| Scraped_At | 스크래핑 시각 |
| Source | 출처 사이트 (kowork/komate/klik) |

---

## 핵심 파일

| 파일 | 역할 |
|------|------|
| `.env` | Google Sheets 인증 정보 (CREDENTIALS_PATH, SHEET_ID) |
| `CLAUDE.md` | 프로젝트 가이드라인 |
| `docs/jobs_scraper.md` | 요구사항 문서 |

---

## 기술적 고려사항

### Playwright MCP 사용 시 주의점
- 목록 페이지 스크롤/페이지네이션 처리
- 동적 콘텐츠 로딩 대기 (`browser_wait_for`)
- Komate의 iframe 내 콘텐츠 접근 (Deep Scraping 시)
- 각 사이트별 적절한 대기 시간 (rate limiting)

### Google Sheets API 사용
- 기존 URL 로드: A열 전체 읽기
- 중복 체크: Set 자료구조로 O(1) 검색
- 배치 쓰기로 API 호출 최소화
- 인증: Service Account JSON 키 사용

---

## 사전 준비 체크리스트

- [ ] Google Cloud Console에서 Service Account 생성
- [ ] Google Sheets API 활성화
- [ ] Service Account JSON 키 다운로드 후 프로젝트에 저장
- [ ] Master DB Google Sheet ID 확인 (URL에서 추출)
- [ ] Sheet에 Service Account 이메일 편집자 권한 부여
- [ ] .env 파일 생성 및 설정

---

## 다음 세션 실행 명령어

### 수동 실행
```
/load-context
/start-dev
```

### 자동화 실행 (Ralph Loop)
```bash
/ralph-loop "/load-context 실행 후 current-context.md의 'Playwright MCP 스크래핑' 작업을 Phase별로 진행. 각 Phase 완료 시 current-context.md 업데이트. 모든 Phase 완료 후 <promise>COMPLETE</promise>" --completion-promise "COMPLETE" --max-iterations 25
```
