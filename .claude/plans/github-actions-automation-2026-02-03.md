# GitHub Actions 일일 스크래퍼 자동화 계획

## 개요
Komate와 Klik 스크래퍼를 GitHub Actions로 매일 자동 실행하여 채용 공고를 수집합니다.
KOWORK는 세션 인증 문제로 제외 (로컬 수동 실행).

---

## 구현 범위

### 포함
- ✅ Komate 스크래퍼 (인증 불필요)
- ✅ Klik 스크래퍼 (인증 불필요)
- ✅ 일일 스케줄링 (cron)
- ✅ 수동 실행 지원 (workflow_dispatch)
- ✅ 결과 아티팩트 저장

### 제외
- ❌ KOWORK (1시간 세션 만료 문제)
- ❌ Google Sheets 연동 (Phase 2)

---

## 워크플로우 설계

### 파일: `.github/workflows/daily-scrape.yml`

```yaml
name: Daily Job Scraper

on:
  schedule:
    # 매일 오전 9시 KST (UTC 0시)
    - cron: '0 0 * * *'
  workflow_dispatch:
    inputs:
      sites:
        description: 'Sites to scrape'
        required: false
        default: 'komate klik'
        type: string
      deep_scrape:
        description: 'Enable deep scraping'
        required: false
        default: true
        type: boolean

jobs:
  scrape:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install chromium --with-deps

      - name: Run scraper
        run: |
          python main.py --sites ${{ inputs.sites || 'komate klik' }} \
            ${{ inputs.deep_scrape == false && '--no-deep' || '' }}

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: job-postings-${{ github.run_number }}
          path: data/job_postings.xlsx
          retention-days: 30

      - name: Summary
        run: |
          python main.py --stats
```

---

## 핵심 파일

### 생성
| 파일 | 설명 |
|------|------|
| `.github/workflows/daily-scrape.yml` | GitHub Actions 워크플로우 |

### 수정 없음
- `main.py` - 이미 CLI 지원
- `requirements.txt` - 의존성 완비
- `src/scrapers/` - 변경 불필요

---

## 구현 단계

### Phase 1: 워크플로우 파일 생성
1. `.github/workflows/` 디렉토리 생성
2. `daily-scrape.yml` 작성

### Phase 2: 테스트
1. 로컬에서 동일한 명령어 실행 확인
2. GitHub에 push 후 수동 실행 (workflow_dispatch)
3. 결과 아티팩트 다운로드 확인

### Phase 3: 스케줄 활성화
1. cron 스케줄 확인 (매일 오전 9시 KST)
2. 첫 자동 실행 결과 모니터링

---

## 검증 방법

### 1. 로컬 테스트
```bash
# 동일한 명령어 실행
python main.py --sites komate klik
python main.py --stats
```

### 2. GitHub Actions 수동 실행
1. Repository > Actions 탭
2. "Daily Job Scraper" 워크플로우 선택
3. "Run workflow" 클릭
4. 완료 후 Artifacts에서 결과 다운로드

### 3. 스케줄 확인
- Actions 탭에서 다음 날 실행 기록 확인
- 실패 시 이메일 알림 자동 발송 (GitHub 기본)

---

## 예상 실행 시간

| 사이트 | 예상 시간 |
|--------|----------|
| Komate | ~4-5분 |
| Klik | ~1분 |
| **Total** | **~6분** |

---

## 향후 확장 (Phase 2)

1. **Google Sheets 연동**: 결과를 자동으로 스프레드시트에 저장
2. **Slack 알림**: 새 공고 발견 시 알림
3. **KOWORK 추가**: 세션 자동 갱신 방법 발견 시
