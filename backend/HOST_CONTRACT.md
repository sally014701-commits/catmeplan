# HOST_CONTRACT.md — 얇은 호스트 계약 (ai-platform playground)

(NOTE: this is a near-duplicate of the top-level HOST_CONTRACT.md, apparently left over from
an earlier scaffold layout where `ap_host.py` and `backend/` were siblings. It differs from the
top-level version mainly in: a simpler `host.drive()` section without the resolve_folders() app-key
API, mock config path `backend/.ap_mock.json` instead of `.ap_mock.json`, and the quick-start
example importing `from backend.ap_host import make_host` instead of `from ap_host import
make_host`. The actual runtime code (`backend/app/routers/calendar.py`) imports
`from ap_host import make_host` — i.e. the TOP-LEVEL `ap_host.py`, not a `backend/ap_host.py`
module — so this backend copy of the doc (and the co-located `backend/ap_host.py`,
`backend/.ap_mock.json.example`) appear to be a stale/duplicate artifact from scaffolding and are
not what's wired into the running FastAPI app.)

> **누가 읽나**: 학생 / 프로젝트 Codex. 플랫폼 *내부 코드*를 몰라도, 이 한 문서대로
> 빌드하면 ① 노트북 오프라인에서 돌고 ② 플랫폼 미리보기(임베드)에서 돌고 ③ 나중에
> 정식 모듈로 **거의 0줄 수정으로 승격**된다.
>
> **단 하나의 규칙(가장 중요)**: 앱은 `host.*` 만 부른다.
> **`X-AP-*` 헤더를 직접 읽지 마라. Supabase 토큰/키를 앱에 두지 마라.**
> 이 둘을 어기면 위 ③(매끄러운 승격)이 깨진다. 헤더를 직접 읽으면 승격 시 모든
> 라우트를 고쳐야 하고, 토큰을 앱에 두면 RLS 가 무의미해진다.

---

## 0. 큰 그림 — 환경 3개, 같은 앱 코드

```
 host = make_host(request) ← 앱 코드는 이 한 줄 + host.* 호출뿐
 ┌─────────────┬──────────────────────────┬─────────────────────────┐
 │ 환경 │ host 가 자동으로 고르는 백엔드 │ 신원 출처 │
 ├─────────────┼──────────────────────────┼─────────────────────────┤
 │ 오프라인 개발 │ MockHost (.ap_mock/ 로컬) │ .ap_mock.json 고정값 │
 │ 플랫폼 미리보기│ ProxyHost (X-AP-* 헤더 파싱) │ 프록시 주입(위조불가) │
 │ 정식 모듈(승격)│ (승격 티켓 때 host 가 in-process 로) │ register(host) 의 host │
 └─────────────┴──────────────────────────┴─────────────────────────┘
```

앱은 **자기가 어느 환경인지 모른다.** `make_host(request)` 가 자동 감지해서
같은 인터페이스의 host 객체를 돌려준다. 분기(`if 플랫폼:`)를 앱 코드에 **쓰지 마라**
(그게 승격을 깨는 주범).

감지 규칙(`make_host` 내부, 앱은 신경 X):
- 요청에 `X-AP-User-Id` 헤더 있음 → **ProxyHost**.
- 환경변수 `AP_HOST_MODE=mock` 또는 헤더 없음 → **MockHost**.

---

## 1. 임베드 계약 (이미 동작 중)

- 앱이 **`/` 루트에 UI 를 서빙**하고 `0.0.0.0:$PORT` 로 바인드하면 끝.
  (`$PORT` 는 플랫폼이 준다. `run.sh` 에 실행 명령을 넣어라.)
- 플랫폼이 `/m/playground/p/<pid>/preview/` 에서 iframe 으로 임베드한다.
- 앱 포트는 **127.0.0.1 외부 비노출**. 프록시만 접근한다 → 프록시가 주는 신원은
  앱이 신뢰해도 된다(브라우저는 못 끼어든다).

```sh
# run.sh 예 (FastAPI)
uvicorn app:app --host 0.0.0.0 --port $PORT
# run.sh 예 (정적)
python3 -m http.server $PORT
```

---

## 2. 호스트가 매 요청에 주입하는 신원 헤더 (`X-AP-*`)

플랫폼 프록시는 **브라우저가 보낸 모든 `x-ap-*` 를 버리고**, 인증된 현재 사용자
값으로 **다시 세팅**해 앱에 전달한다(위조 불가). 앱은 이걸 **직접 읽지 말고
`host.user()` 로** 받는다.

| 헤더 | 뜻 | 비고 |
|---|---|---|
| `X-AP-User-Id` | 플랫폼 사용자 uuid | 항상 존재(로그인 강제) |
| `X-AP-User-Email` | 플랫폼 로그인 이메일 | 항상 존재 |
| `X-AP-Project-Id` | 현재 프로젝트 pid | 항상 존재 |
| `X-AP-Google-Email` | **검증된** 구글 이메일 | `app_user_google.verified=true` 일 때만. 없으면 미연동 |

> `X-AP-Roles` 는 **v1 에 없다.** standalone 단계에서 `host.user().role` 은 `None`
> 이다(아래 §3). 역할 기반 권한 분기는 mock 으로 연습하고, 실제 강제는 승격 후
> 플랫폼이 `pg_project_members` 로 채운다.

---

## 3. `host` 인터페이스 (Python — JS 동형)

```python
host = make_host(request)  # FastAPI: request, Flask: request, plain: None+env

# ── 방향1: 앱이 플랫폼 자원 사용 ───────────────────────────
host.user() -> User | None
# User(id, email, google_email|None, project_id, role)
# role: 'owner'|'codex'|'viewer'|None (standalone/proxy 에선 None — §2 참고)

host.data(name) -> DataScope  # name = 내 앱의 컬렉션(논리 테이블) 이름
#   .get(id)            -> dict | None
#   .list(**where)      -> list[dict]   # where 는 동등 필터 (col=value)
#   .put(row)           -> dict         # row 에 id 없으면 생성, 있으면 upsert
#   .delete(id)         -> bool
#   ★ 모든 행에 owner(=user.id) 가 자동 주입/자동 필터된다(아래 §4 IDOR 안전).

host.drive() -> Drive | None   # 구글 미연동(google_email 없음)이면 None
#   .list()             -> list[dict]   # 내가 공유받은 폴더의 파일들
#   .get(file_id)       -> bytes        # 다운로드

host.config(key, default=None) -> str | None   # 배포 설정값(읽기전용, 시크릿 제외)

# ── 방향2: 앱이 다른 모듈 능력 사용 (v1 = 얇은 자리만) ────────
host.service(name) -> ServiceProxy | None
#   v1 에선 항상 None 을 반환한다(레지스트리 미구현, '각자 섬').
#   → 반드시 graceful 분기: `svc = host.service("x"); if svc: ...`
```

**graceful 패턴(외워라):**
```python
svc = host.service("mailer")
if svc:                       # 승격+승인된 경우만 truthy
    svc.call("send", to=..., body=...)
else:
    ...                        # standalone fallback (직접 처리 또는 안내)
```

---

## 4. `host.data()` 의 데이터 격리 (IDOR 안전을 기본값으로)

- **`put(row)`**: `row` 가 보낸 `owner` 값을 **무시**하고 host 가 현재
  `user().id` 로 **덮어쓴다**.
- **`list()` / `get()`**: 항상 `owner = 내 user.id` 로 자동 필터. 내 행만 보인다.
- **standalone/mock**: 로컬 SQLite(`.ap_mock.db`)에 `owner` 컬럼으로 같은 격리를
  코드로 흉내.
- **승격(티켓)**: 같은 `put/list/get` 이 플랫폼 테이블(+ `owner`/`project_id` + RLS)로
  간다. 앱 코드 0줄 수정.

> 공유 스코프(프로젝트 멤버 전체가 보는 데이터)는 **v1 비제공**.

---

## 5. 권한 모델 (앱이 권한을 *결정*하지 않는다)

1. **신원 단일 출처 = 프록시**. `X-AP-*` 는 프록시가 strip 후 재주입 → 위조 불가.
2. **쓰기 격리 = host.data 의 owner 자동주입/필터** (§4).
3. **viewer 는 쓰기 불가**: 승격 후 플랫폼이 `role='viewer'` 의 `host.data().put`·
   `host.service().call` 을 거부한다.
4. **능력 게이트**: `host.service` 는 v1 에 능력 0개 → 전부 None(안전 기본값).

---

## 6. Mock = "세 번째 백엔드" (별도 코드경로 아님)

`backend/.ap_mock.json` (backend 폴더, gitignore. `.ap_mock.json.example` 동봉):
```json
{
  "user": {
    "id": "dev-user", "email": "dev@local",
    "google_email": "dev@gmail.com", "project_id": "dev-proj",
    "role": "owner"
  },
  "services": {}
}
```
- `host.user()` → 위 고정값. **`role` 을 `"viewer"` 로 바꿔** 권한거부 경로를 미리 타라.
- `host.data()` → `.ap_mock.db`(SQLite). owner 자동주입/필터 = 실제와 동일.
- `host.drive()` → `.ap_mock/drive/` 폴더를 list/get. `google_email` 이 null 이면 None.
- `host.service(name)` → `services[name]` 에 stub 있으면 그 고정응답, **없으면 None**.

---

## 7. 승격 (티켓제 — 자동 아님)

1. 앱이 standalone 으로 쓸만해지면 프로젝트 페이지 **"운영자에게 요청(티켓)"** 으로
   승격 요청.
2. 운영자 검토/승인 후, 플랫폼이 앱을 `register(host)` 형태로 장착한다.
3. **앱 비즈니스 코드는 0줄 수정**(전제: §1 규칙 — `host.*` 만 썼을 때).

---

## 8. v1 비포함 (의도적으로 안 만듦 — over-engineering 금지)

- **WebSocket**: 프록시는 HTTP 전용.
- **`host.service` 라우팅/레지스트리**: v1 능력 0개.
- **공유 스코프 / cross-group**: 각자 섬. v1 없음.
- **단명 capability 토큰·서명**: 불필요.

---

## 9. 빠른 시작 (FastAPI 앱 예)

```python
from fastapi import FastAPI, Request
from backend.ap_host import make_host  # 동봉 헬퍼

app = FastAPI()

@app.get("/")
def home(request: Request):
    host = make_host(request)
    u = host.user()
    notes = host.data("notes").list()          # 내 노트만
    return {"me": u.email if u else None, "notes": notes}

@app.post("/notes")
def add(request: Request, text: str):
    host = make_host(request)
    return host.data("notes").put({"text": text})   # owner 자동주입
```
오프라인 실행: `AP_HOST_MODE=mock python3 -m uvicorn app:app --port 8000`
