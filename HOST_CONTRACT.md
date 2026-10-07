# HOST_CONTRACT.md — 얇은 호스트 계약 (ai-platform playground)

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
> 플랫폼이 `pg_project_members` 로 채운다. (헤더 표면을 지금 늘리지 않는다 = 위조면·
> 동기화부채 회피.)

---

## 3. `host` 인터페이스 (Python — JS 동형)

앱이 쓰는 메서드는 이게 전부다. 시그니처 고정 — 승격해도 안 바뀐다.

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

host.drive() -> Drive | None   # 시그니처 불변. MockHost: google_email 없으면 None.
#   ProxyHost: facade 반환(non-None) — 미연동은 아래 resolve_folders 가 fail-closed
#   .list()             -> list[dict]   # 내가 공유받은 폴더의 파일들 (MockHost/legacy)
#   .get(file_id)       -> bytes        # 다운로드 (MockHost/legacy)
#   .resolve_folders(app_key="ai-record")   # ★Drive 인터페이스에 선언됨(_HostDrive 실 Drive / _LocalDrive mock 구현)★
#       -> {role: {"provider":"google-drive","folder_id","id","name"}}
#   # 앱별 per-user Drive 폴더트리를 ★멱등 확보(find-or-create)★하고 폴더참조를 돌려준다.
#   # role 집합 = {"root"}(앱 root 폴더, ★예약키★) + spec.children 키. ★'root' 은 예약 → children 키로 못 씀(spec 검증서 ValueError).★
#   # ★children 표시이름(값)은 유일해야 함★ — 중복이면 두 role 이 결정적으로 한 폴더로 alias 되므로 _app_spec 이 거부(ValueError, 모호성 방지).
#   # ★ai-record 기준★: role ∈ {root, inbox, recordings, minutes},
#   #   name = 실폴더 표시이름(root=AI회의록·recordings=녹음·minutes=회의록). 다른 앱은 그 앱 spec 대로.
#   # folder_id == id (별칭: 소비자 관례 호환). 폴더트리 = ai-platform-files/<이메일 local-part>/<app root>/<children…>(플랫폼 통제).
#   # MockHost(_LocalDrive): role-KEY 집합만 real 과 parity, 값은 legacy 단일폴더(RECORD_INBOX)·name=placeholder.
#   # app_key: str 만(비-str/미지원/malformed spec → ValueError) · 미연동·무이메일 → RuntimeError(fail-closed) · 크레덴셜=서버측 .env 만(앱 무저장).

host.config(key, default=None) -> str | None   # 배포 설정값(읽기전용, 시크릿 제외)

# ── 방향2: 앱이 다른 모듈 능력 사용 (v1 = 얇은 자리만) ────────
host.service(name) -> ServiceProxy | None
#   v1 에선 항상 None 을 반환한다(레지스트리 미구현, '각자 섬').
#   → 반드시 graceful 분기: `svc = host.service("x"); if svc: ...`
#   승격 후 운영자가 능력을 승인하면 그때 ServiceProxy 가 온다(.call(verb, **kw)).
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

`host.data()` 는 **추상 컬렉션**이다. Supabase 테이블/PostgREST 쿼리스트링을
**노출하지 않는다**(노출하면 승격 시 테이블 RLS 가 앱에 새고 화이트리스트 우회 위험).

- **`put(row)`**: `row` 가 보낸 `owner` 값을 **무시**하고 host 가 현재
  `user().id` 로 **덮어쓴다**. → 학생이 실수로 남의 데이터를 쓰는 IDOR 이 구조적으로 막힘.
- **`list()` / `get()`**: 항상 `owner = 내 user.id` 로 자동 필터. 내 행만 보인다.
- **standalone/mock**: 로컬 SQLite(`.ap_mock.db`)에 `owner` 컬럼으로 같은 격리를
  코드로 흉내. → 학생이 *오프라인에서도 IDOR 안전한 습관*을 들인다.
- **승격(티켓)**: 같은 `put/list/get` 이 플랫폼 테이블(+ `owner`/`project_id` + RLS)로
  간다. 앱 코드 0줄 수정.

> 공유 스코프(프로젝트 멤버 전체가 보는 데이터)는 **v1 비제공**. 필요하면 승격
> 티켓으로 요청하라(각자 섬 원칙).

---

## 5. 권한 모델 (앱이 권한을 *결정*하지 않는다)

다중 방어선(HANDOFF §4)을 SDK 가 대신 판단하지 않는다:

1. **신원 단일 출처 = 프록시**. `X-AP-*` 는 프록시가 strip 후 재주입 → 위조 불가.
   `host.user()` 는 *파싱만* 한다. 새 신원을 만들지 않는다.
2. **쓰기 격리 = host.data 의 owner 자동주입/필터** (§4). standalone 은 SQLite
   `owner` 컬럼, 승격은 RLS 가 이중으로 잠근다. 앱에 Supabase 토큰/service_role 을
   **절대 주지 않는다**(토큰이 앱으로 새면 RLS 무의미 + 타 프로젝트 IDOR).
3. **viewer 는 쓰기 불가**: 승격 후 플랫폼이 `role='viewer'` 의 `host.data().put`·
   `host.service().call` 을 거부한다(기존 `_owned` vs `_access` 분리 패턴 그대로).
   mock 에서도 `role` 을 `viewer` 로 두면 **같은 거부**를 재현한다(아래 §6 — 중요).
4. **능력 게이트**: `host.service` 는 v1 에 능력 0개 → 전부 None(안전 기본값). 승격
   시 (호출자 manifest `uses` 선언 + 운영자 승인 + 사용자 role) 2단 게이트를 플랫폼이
   검사한다. 앱에 우회 API 없음.

---

## 6. Mock = "세 번째 백엔드" (별도 코드경로 아님)

mock 은 디버그 모드가 아니라 **실제 백엔드 하나**다. 그래서 mock 에서 되던 코드가
승격 후 안 깨진다 — **단, mock 이 권한거부도 충실히 재현할 때만.**

`.ap_mock.json` (프로젝트 루트, gitignore. `.ap_mock.example.json` 동봉):
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
- `host.service(name)` → `services[name]` 에 stub 있으면 그 고정응답, **없으면 None**
  (= v1 실제 동작과 동일). graceful 분기를 개발 때부터 검증하게 한다.

> ❌ mock 을 "전부 통과"로 만들지 마라. viewer 거부·service None·owner 덮어쓰기가
> 실제와 다르면, 학생이 mock 에선 되던 코드가 승격 후 권한거부로 깨진다.

---

## 7. 승격 (티켓제 — 자동 아님)

1. 앱이 standalone 으로 쓸만해지면 프로젝트 페이지 **"운영자에게 요청(티켓)"** 으로
   승격 요청(유형·제목·왜·어떻게·맥락 작성).
2. 운영자 검토/승인 후, 플랫폼이 앱을 `register(host)` 형태로 장착한다.
   이때 host 백엔드가 ProxyHost/Mock → **in-process host** 로 바뀐다.
3. **앱 비즈니스 코드는 0줄 수정**(전제: §1 규칙 — `host.*` 만 썼을 때).
   `host.data` 는 플랫폼 테이블+RLS 로, `host.drive` 는 코어 drive 로, `host.service`
   는 승인된 능력으로 살아난다.

승격 시 **플랫폼 쪽** 작업(앱이 아니라 운영자/플랫폼 관리자가 함):
- `host.data` 컬렉션 → `owner`/`project_id` 컬럼 + RLS 정책을 가진 앱별 테이블 프로비저닝.
- `register(host) -> ModuleManifest(key, label, section, required_perms, uses[], provides[])`.
- `host.service` 능력 레지스트리 채우기(둘째 모듈이 실제로 부를 때).

---

## 8. v1 비포함 (의도적으로 안 만듦 — over-engineering 금지)

- **WebSocket**: 프록시는 HTTP 전용(DECISIONS 2026-06-09). `host` 도 v1 은 HTTP 가정.
  실시간 앱의 ws 승격은 별 트랙.
- **`host.service` 라우팅/레지스트리**: v1 능력 0개. 시그니처+manifest 필드만.
- **공유 스코프 / cross-group**: 각자 섬. v1 없음.
- **단명 capability 토큰·서명**: 프록시 strip+재주입이 이미 위조를 막으므로 불필요.

---

## 9. 빠른 시작 (FastAPI 앱 예)

```python
from fastapi import FastAPI, Request
from ap_host import make_host  # 동봉 헬퍼 (sdk/ap_host.py)

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
(헤더 없으면 자동으로 mock 이라 `AP_HOST_MODE` 도 사실 생략 가능.)
