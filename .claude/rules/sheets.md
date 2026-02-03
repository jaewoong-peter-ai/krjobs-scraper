# Google Sheets 연동 규칙

**적용 대상**: `src/sheets/**/*.py`

이 파일에서 작업할 때:

## 인증
- Service Account JSON 키 사용
- 환경변수: `GOOGLE_SHEETS_CREDENTIALS_PATH`
- 키 파일 절대 커밋 금지 (.gitignore)

## 배치 처리
```python
# Bad: 개별 쓰기
for row in rows:
    sheet.append_row(row)  # API 호출 N번

# Good: 배치 쓰기
sheet.append_rows(rows)  # API 호출 1번
```

## 중복 체크
- URL 컬럼(A열)으로 중복 확인
- 새 데이터 추가 전 기존 URL 목록 로드
- Set 자료구조로 O(1) 검색

## 에러 처리
- API quota 초과 시 재시도 로직
- 네트워크 에러 시 로컬 캐시 저장

## 컬럼 순서
```
A: URL
B: Title
C: Company(kor)
D: Company(eng)
E: Location
F: Visa
G: E-7 Support
H: Korean Requirement
I: Job Category
J: Job Type
K: Content Raw
L: Scraped At
M: Source
```
