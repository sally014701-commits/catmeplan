"""backend/ap_host.py — 얇은 호스트 헬퍼 (학생 앱이 import).

규칙(HOST_CONTRACT §0): 앱은 make_host(request) 한 줄 + host.* 만 쓴다.
X-AP-* 직접 읽기·Supabase 토큰 보관 금지. 그래야 승격 0줄.

백엔드 3종(앱은 어느 건지 모름):
  ProxyHost  플랫폼 미리보기 — X-AP-* 헤더 파싱(위조불가, 프록시 주입)
  MockHost   오프라인 — .ap_mock.json + .ap_mock.db(SQLite) + .ap_mock/drive/
  (ModuleHost 승격 후 in-process — 플랫폼이 register(host) 때 주입. 여기엔 없음)

NOTE: this file appears to be a stale/duplicate copy of a generic platform SDK
(it references unrelated course host-services: "doubleman", "finance-data",
"portfolio-value" — none of which FocusPlan uses). The FastAPI app actually
imports `from ap_host import make_host` (the TOP-LEVEL ap_host.py), not this
backend/ap_host.py module, so this file is very likely dead/vestigial.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
_MOCK_JSON = _BACKEND_DIR / ".ap_mock.json"
_MOCK_DB = _BACKEND_DIR / ".ap_mock.db"
_MOCK_DRIVE = _BACKEND_DIR / ".ap_mock/drive"


@dataclass
class User:
    id: str
    email: str
    google_email: str | None
    project_id: str
    role: str | None  # 'owner'|'codex'|'viewer'|None (standalone 은 None)


# ── 공개 진입점 ────────────────────────────────────────────
def make_host(request=None):
    """환경 자동 감지. request 는 FastAPI/Flask Request (헤더 접근용) 또는 None."""
    hdr = _header_getter(request)
    if os.environ.get("AP_HOST_MODE") != "mock" and hdr("x-ap-user-id"):
        return ProxyHost(hdr)
    return MockHost()


def _header_getter(request):
    if request is None:
        return lambda k: None
    h = getattr(request, "headers", {})
    normalized = {str(name).lower(): value for name, value in getattr(h, "items", lambda: [])()}
    def get(key):
        return h.get(key) or h.get(key.title()) or normalized.get(str(key).lower())
    return get


# ── ProxyHost: 플랫폼 미리보기 ──────────────────────────────
class ProxyHost:
    """X-AP-* 헤더만 파싱. 신원은 프록시가 보증(위조불가)."""

    def __init__(self, hdr):
        self._h = hdr

    def user(self) -> User | None:
        uid = self._h("x-ap-user-id")
        if not uid:
            return None
        return User(
            id=uid,
            email=self._h("x-ap-user-email") or "",
            google_email=self._h("x-ap-google-email"),  # 미연동이면 None
            project_id=self._h("x-ap-project-id") or "",
            role=None,  # v1: standalone 헤더에 역할 없음. 승격 후 플랫폼이 채움.
        )

    def data(self, name: str) -> "DataScope":
        # v1 standalone: 데이터는 앱 로컬 SQLite (owner = 현재 사용자).
        # 승격 시 이 한 곳이 플랫폼 테이블+RLS 어댑터로 바뀐다(앱 코드 불변).
        u = self.user()
        return _SqliteScope(name, owner=(u.id if u else "anon"))

    def drive(self) -> "Drive | None":
        # 코어 drive 위임은 승격 시점 기능. standalone 미리보기는 미연동 취급.
        return None

    def config(self, key: str, default=None):
        return _config_from_env(key, default)

    def service(self, name: str):
        # v1 각자 섬 기본 = None(graceful). 예외: 운영자 승인된 host-service 만 등록.
        if name == "doubleman":
            return _doubleman_service_for(self._h("x-ap-project-id"), self._h("x-ap-user-email"))
        if name == "finance-data":
            return _finance_data_service_for(self._h("x-ap-project-id"))
        if name == "portfolio-value":
            return _portfolio_value_service_for(self._h("x-ap-project-id"))
        return None


# ── MockHost: 오프라인 개발 ─────────────────────────────────
class MockHost:
    def __init__(self):
        self._cfg = json.loads(_MOCK_JSON.read_text()) if _MOCK_JSON.exists() else {}

    def user(self) -> User | None:
        u = self._cfg.get("user")
        if not u:
            return None
        return User(
            id=u.get("id", "dev-user"), email=u.get("email", "dev@local"),
            google_email=u.get("google_email"), project_id=u.get("project_id", "dev-proj"),
            role=u.get("role", "owner"),  # ★ "viewer" 로 바꿔 권한거부 경로를 미리 타라
        )

    def data(self, name: str) -> "DataScope":
        u = self.user()
        return _SqliteScope(name, owner=(u.id if u else "dev-user"))

    def drive(self) -> "Drive | None":
        u = self.user()
        if not u or not u.google_email:
            return None  # 실제와 동일: 구글 미연동이면 None
        return _LocalDrive()

    def config(self, key: str, default=None):
        cfg = self._cfg.get("config") or {}
        for candidate in _config_keys(key):
            if candidate in cfg:
                return cfg[candidate]
        return _config_from_env(key, default)

    def service(self, name: str):
        stub = (self._cfg.get("services") or {}).get(name)
        return _MockService(stub) if stub is not None else None  # 없으면 None(실제와 동일)


# ── DataScope: get/list/put/delete (owner 자동주입·필터) ─────
class DataScope:  # 인터페이스(문서용)
    def get(self, id): ...
    def list(self, **where): ...
    def put(self, row): ...
    def delete(self, id): ...


class _SqliteScope(DataScope):
    """로컬 SQLite. 모든 행 = ((id, owner) 복합 PK, body JSON).
    owner 자동주입/필터로 IDOR 안전을 standalone 에서도 강제(승격 RLS 와 동일 동작)."""

    def __init__(self, name: str, owner: str):
        self._name = "".join(c for c in name if c.isalnum() or c == "_") or "data"
        self._owner = owner
        self._db = sqlite3.connect(_MOCK_DB, isolation_level=None)
        self._db.execute("PRAGMA busy_timeout=5000")
        self._ensure_schema()

    def _is_composite(self, t):
        return {c[1] for c in self._db.execute(f"PRAGMA table_info({t})").fetchall()
                if c[5] > 0} == {"id", "owner"}

    def _ensure_schema(self):
        """테이블 보장 + 구 단일 id-PK → 복합 (id,owner) PK 행 보존 마이그레이션(동시성 안전)."""
        t = self._name
        self._db.execute(
            f"create table if not exists {t} "
            "(id text not null, owner text not null, body text not null, primary key(id, owner))")
        if self._is_composite(t):
            return  # 이미 복합 PK(흔한 경우) → 락 불필요
        self._db.execute("BEGIN IMMEDIATE")  # 쓰기락 획득(다른 스레드는 busy_timeout 만큼 대기)
        try:
            if self._is_composite(t):  # 락 대기 중 다른 스레드가 이미 마이그레이션했으면 skip
                self._db.execute("COMMIT")
                return
            self._db.execute(f"drop table if exists {t}__mig")
            self._db.execute(
                f"create table {t}__mig "
                "(id text not null, owner text not null, body text not null, primary key(id, owner))")
            old_cols = {c[1] for c in self._db.execute(f"PRAGMA table_info({t})").fetchall()}
            if {"id", "owner", "body"} <= old_cols:
                self._db.execute(f"insert or ignore into {t}__mig(id,owner,body) select id,owner,body from {t}")
            self._db.execute(f"drop table {t}")
            self._db.execute(f"alter table {t}__mig rename to {t}")
            self._db.execute("COMMIT")
        except Exception:
            self._db.execute("ROLLBACK")
            raise

    def _row(self, r):
        d = json.loads(r[2]); d["id"] = r[0]; return d

    def get(self, id):
        r = self._db.execute(
            f"select id,owner,body from {self._name} where id=? and owner=?",
            (id, self._owner)).fetchone()
        return self._row(r) if r else None

    def list(self, **where):
        rows = self._db.execute(
            f"select id,owner,body from {self._name} where owner=?", (self._owner,)).fetchall()
        out = [self._row(r) for r in rows]
        for k, v in where.items():  # 동등 필터만 (쿼리빌더로 키우지 않는다)
            out = [d for d in out if d.get(k) == v]
        return out

    def put(self, row: dict):
        d = dict(row)
        d.pop("owner", None)  # ★ 앱이 보낸 owner 무시(IDOR 차단)
        rid = d.get("id") or str(uuid.uuid4())
        d["id"] = rid
        self._db.execute(
            f"insert into {self._name}(id,owner,body) values(?,?,?) "
            "on conflict(id,owner) do update set body=excluded.body",
            (rid, self._owner, json.dumps({k: v for k, v in d.items() if k != "id"})))
        self._db.commit()
        return d

    def delete(self, id) -> bool:
        cur = self._db.execute(
            f"delete from {self._name} where id=? and owner=?", (id, self._owner))
        self._db.commit()
        return cur.rowcount > 0


# ── Drive / Service (mock 구현) ─────────────────────────────
class Drive:  # 인터페이스(문서용)
    def list(self): ...
    def get(self, file_id): ...


class _LocalDrive(Drive):
    def list(self):
        _MOCK_DRIVE.mkdir(parents=True, exist_ok=True)
        return [{"id": p.name, "name": p.name, "size": p.stat().st_size}
                for p in _MOCK_DRIVE.iterdir() if p.is_file()]

    def get(self, file_id) -> bytes:
        p = _MOCK_DRIVE / file_id
        return p.read_bytes() if p.is_file() else b""


class _MockService:
    def __init__(self, stub):
        self._stub = stub  # {verb: fixed_response}

    def call(self, verb, **kw):
        return self._stub.get(verb) if isinstance(self._stub, dict) else self._stub


# ── config 키 해석: 대소문자 무관 + AP_CFG_*/plain env fallback ──
def _config_keys(key: str) -> list[str]:
    raw = str(key or "")
    upper = raw.upper()
    lower = raw.lower()
    return list(dict.fromkeys([raw, upper, lower]))


def _config_from_env(key: str, default=None):
    upper = str(key or "").upper()
    for candidate in (f"AP_CFG_{upper}", upper):
        value = os.environ.get(candidate)
        if value not in (None, ""):
            return value
    return default


# ── doubleman / finance-data / portfolio-value host-services ──
# (Generic-platform, unrelated-course integrations. Not used by FocusPlan.
#  Left in verbatim for completeness — see module docstring.)
_DOUBLEMAN_ENV = "/lab/sdk/doubleman.env"


def _read_env_file(path):
    cfg = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    except OSError:
        pass
    return cfg


def _doubleman_service_for(project_id, user_email=None):
    cfg = _read_env_file(_DOUBLEMAN_ENV)
    base = cfg.get("DOUBLEMAN_BASE_URL")
    token = cfg.get("DOUBLEMAN_TOKEN")
    if not base or not token:
        return None
    allowed = [p.strip() for p in (cfg.get("DOUBLEMAN_ALLOWED_PIDS") or "").split(",") if p.strip()]
    if allowed and (project_id or "") not in allowed:
        return None
    return _DoublemanService(base, token, user_email)


class _DoublemanService:
    _VERB_PATHS = {
        "evaluate": "/api/backtest/evaluate",
        "detector_evaluate": "/api/backtest/detector-evaluate",
        "prices": "/api/backtest/prices",
        "validate_strategy": "/api/strategy/validate",
        "submit_strategy": "/api/strategy/submit",
        "alpha_tester_validate": "/api/alpha-tester/validate",
        "alpha_tester_submit": "/api/alpha-tester/submit",
        "alpha_tester_result": "/api/alpha-tester/result",
        "alpha_tester_backtest_preview": "/api/alpha-tester/backtest-preview",
    }
    _IDENTITY_KEYS = ("save", "submitter")

    def __init__(self, base_url, token, user_email=None):
        self._base = base_url.rstrip("/")
        self._token = token
        self._user_email = user_email or ""

    def call(self, verb, request=None, **_ignored):
        import urllib.request as _u
        import urllib.error as _ue
        path = self._VERB_PATHS.get(verb)
        if not path:
            return {"ok": False, "error": f"unknown doubleman verb: {verb}", "verb": verb}
        payload = dict(request or {})
        for _idk in self._IDENTITY_KEYS:
            _obj = payload.get(_idk)
            if isinstance(_obj, dict):
                _obj = dict(_obj)
                _obj["email"] = self._user_email
                payload[_idk] = _obj
        body = json.dumps(payload).encode("utf-8")
        req = _u.Request(self._base + path, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + self._token)
        try:
            with _u.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except _ue.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"ok": False, "error": f"doubleman http {e.code}", "verb": verb}
        except Exception as e:
            return {"ok": False, "error": f"doubleman call failed: {type(e).__name__}", "verb": verb}


_FINANCE_ENV = "/lab/sdk/finance-data.env"


def _finance_data_service_for(project_id):
    cfg = _read_env_file(_FINANCE_ENV)
    base = cfg.get("FINANCE_DATA_BASE_URL")
    if not base:
        return None
    allowed = [p.strip() for p in (cfg.get("FINANCE_DATA_ALLOWED_PIDS") or "").split(",") if p.strip()]
    if allowed and (project_id or "") not in allowed:
        return None
    return _FinanceDataService(base, cfg.get("FINANCE_DATA_TOKEN"))


class _FinanceDataService:
    _VERB_SPECS = {
        "prices": ("POST", "/prices"),
        "universe": ("GET", "/universe"),
        "listing_status": ("GET", "/listing-status"),
        "health": ("GET", "/health"),
        "freshness": ("GET", "/freshness"),
        "yearly_returns": ("POST", "/yearly-returns"),
    }

    def __init__(self, base_url, token):
        self._base = base_url.rstrip("/")
        self._token = token or ""

    def call(self, verb, request=None, **_ignored):
        import urllib.request as _u
        import urllib.error as _ue
        import urllib.parse as _up
        spec = self._VERB_SPECS.get(verb)
        if not spec:
            return {"ok": False, "error": f"unknown finance-data verb: {verb}", "verb": verb}
        method, path = spec
        params = dict(request or {})
        if method == "GET":
            qs = _up.urlencode({
                k: (",".join(str(x) for x in v) if isinstance(v, (list, tuple)) else v)
                for k, v in params.items() if v is not None})
            req = _u.Request(self._base + path + (("?" + qs) if qs else ""), method="GET")
        else:
            req = _u.Request(self._base + path, data=json.dumps(params).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        if self._token:
            req.add_header("Authorization", "Bearer " + self._token)
        try:
            with _u.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except _ue.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"ok": False, "error": f"finance-data http {e.code}", "verb": verb}
        except Exception as e:
            return {"ok": False, "error": f"finance-data call failed: {type(e).__name__}", "verb": verb}


_PVC_ENV = "/lab/sdk/portfolio-value.env"


def _portfolio_value_service_for(project_id):
    cfg = _read_env_file(_PVC_ENV)
    base = cfg.get("PVC_BASE_URL")
    if not base:
        return None
    allowed = [p.strip() for p in (cfg.get("PVC_ALLOWED_PIDS") or "").split(",") if p.strip()]
    if allowed and (project_id or "") not in allowed:
        return None
    return _PortfolioValueService(base, cfg.get("PVC_BEARER_TOKEN"))


class _PortfolioValueService:
    _VERB_SPECS = {
        "value": ("POST", "/value"),
        "health": ("GET", "/health"),
    }

    def __init__(self, base_url, token):
        self._base = base_url.rstrip("/")
        self._token = token or ""

    def call(self, verb, request=None, **_ignored):
        import urllib.request as _u
        import urllib.error as _ue
        import urllib.parse as _up
        spec = self._VERB_SPECS.get(verb)
        if not spec:
            return {"ok": False, "error": f"unknown portfolio-value verb: {verb}", "verb": verb}
        method, path = spec
        params = dict(request or {})
        if method == "GET":
            qs = _up.urlencode({k: v for k, v in params.items() if v is not None})
            req = _u.Request(self._base + path + (("?" + qs) if qs else ""), method="GET")
        else:
            req = _u.Request(self._base + path, data=json.dumps(params).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        if self._token:
            req.add_header("Authorization", "Bearer " + self._token)
        try:
            with _u.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except _ue.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"ok": False, "error": f"portfolio-value http {e.code}", "verb": verb}
        except Exception as e:
            return {"ok": False, "error": f"portfolio-value call failed: {type(e).__name__}", "verb": verb}
