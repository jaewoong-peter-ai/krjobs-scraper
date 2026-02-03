# 현재 작업 컨텍스트

## 마지막 업데이트
2026-02-03 20:00

---

## 프로젝트 상태

### 인프라 구성

| 구성 요소 | 상태 | 비고 |
|----------|------|------|
| **GitHub 저장소** | ✅ | `jaewoong-peter-ai/krjobs-scraper` |
| **GitHub Actions** | ✅ | 매일 KST 09:00 자동 실행 |
| **Supabase DB** | ✅ | 18개 공고 저장됨 |
| **SSH 키** | ✅ | `~/.ssh/id_ed25519_peter_ai` |

### 스크래퍼 현황

| Site | 구현 | 자동화 | 비고 |
|------|------|--------|------|
| KOWORK | ✅ | ❌ | 세션 만료 이슈 |
| Komate | ✅ | ❌ | **클라우드 IP 차단** (로컬에서만 실행) |
| Klik | ✅ | ✅ | GitHub Actions 자동 실행 |

---

## 저장소 현황

### Supabase DB (`job_postings` 테이블)
| 소스 | 공고 수 |
|------|--------|
| klik | 18 |
| **Total** | **18** |

### 로컬 파일 (`data/job_postings.xlsx`)
| 소스 | 공고 수 |
|------|--------|
| kowork | 15 |
| komate | 78 |
| klik | 6 |
| **Total** | **99** |

---

## 실행 명령어

### 자동 실행 (GitHub Actions)
- **스케줄**: 매일 KST 09:00
- **사이트**: Klik만
- **저장소**: Supabase

### 수동 실행 (로컬)
```bash
# Supabase에 저장 (Klik)
python main.py --sites klik --storage supabase

# Supabase에 저장 (Komate) - 로컬에서만 가능
python main.py --sites komate --storage supabase

# 로컬 파일에 저장
python main.py --sites komate klik --storage local

# 통계 확인
python main.py --stats --storage supabase
```

---

## Git 설정

### SSH 호스트 별칭 (jaewoong-peter-ai 계정)
```
Host github-peter-ai
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_peter_ai
    IdentitiesOnly yes
```

### Remote URL
```
origin  git@github-peter-ai:jaewoong-peter-ai/krjobs-scraper.git
```

---

## 알려진 이슈

### Komate 클라우드 IP 차단
- **증상**: GitHub Actions, GCP Cloud Run 모두 타임아웃
- **원인**: 사람인(Komate)이 클라우드 IP 대역 차단
- **해결**: 로컬 PC에서 수동 실행

### KOWORK 세션 만료
- **증상**: 로그인 세션 만료로 스크래핑 실패
- **상태**: 미해결 (우선순위 낮음)

---

## 환경 변수 (.env)

```
SUPABASE_URL=https://ujxfzprxoowuufiicpey.supabase.co
SUPABASE_ANON_KEY=<JWT_TOKEN>
```

---

## 참조
- GitHub: https://github.com/jaewoong-peter-ai/krjobs-scraper
- Supabase: https://supabase.com/dashboard/project/ujxfzprxoowuufiicpey
- 코딩 가이드: `CLAUDE.md`
