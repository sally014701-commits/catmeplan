"""sdk/ap_host.py — 얇은 호스트 헬퍼 (학생 앱이 import).

규칙(HOST_CONTRACT §0): 앱은 make_host(request) 한 줄 + host.* 만 쓴다.
X-AP-* 직접 읽기·Supabase 토큰 보관 금지. 그래야 승격 0줄.

백엔드 3종(앱은 어느 건지 모름):
  ProxyHost  플랫폼 미리보기 — X-AP-* 헤더 파싱(위조불가, 프록시 주입)
  MockHost   오프라인 — .ap_mock.json + .ap_mock.db(SQLite) + .ap_mock/drive/
  (ModuleHost  승격 후 in-process — 플랫폼이 register(host) 때 주입. 여기엔 없음)
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

_MOCK_JSON = Path(".ap_mock.json")
_MOCK_DB = Path(".ap_mock.db")
_MOCK_DRIVE = Path(".ap_mock/drive")


@dataclass
class User:
    id: str
    email: str
    google_email: str | None
    project_id: str
    role: str | None          # 'owner'|'codex'|'viewer'|None (standalone 은 None)


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

# ── Phase A: per-user Drive folder resolution — ★S10 신뢰 폴더 레지스트리(read-only)★ ──────────
# resolve_folders = root-owned SQLite 레지스트리의 ★read-only lookup★(계약 round-017, sha c4e83643).
# 요청 경로는 Drive/OAuth 를 절대 호출하지 않는다(token exchange·list·search·create·repair·rename 0).
# 유일 writer = 별도 provisioner(scripts/s10_provision_folders.py: files.generateIds + CAS + crash-resume).
# 미스/disabled/repairing/principal-mismatch/malformed/spec-mismatch → 단일 sanitized
# `folder_registry_unavailable`(fail-closed). ★email-local-part fallback·request-time 폴더생성 절대 없음★
# (구 프로세스 캐시 339cab38 의 3결함 제거: nested-ref poisoning / concurrent cold-miss 중복생성 / local-part alias).
_REGISTRY_UNAVAILABLE = "folder_registry_unavailable"
_REGISTRY_DB_ENV = "AP_FOLDER_REGISTRY_DB"     # root-owned SQLite(WAL) 경로 = host.config env. 미설정 → fail-closed.

# 앱별 Drive 폴더 트리(플랫폼 per-user 네임스페이스 ai-platform-files/acct-<hash>/ 밑).
# 반환 dict 의 key(root/inbox/recordings/minutes) = 계약, value = 그 폴더의 실제 표시이름.
# ★v1 folder_registry row = ai-record 의 role set(inbox/recordings/minutes)에 컬럼 고정.
#   같은 3 role 을 쓰는 2번째 앱만 여기 1줄 추가 가능. ★다른 role set = registry 스키마+provisioner 확장 필요★
#   (_app_spec 이 real/mock 동일하게 다른 role set 을 fail-fast 거부 = mock-works-prod-KeyErrors 방지).★
_APP_FOLDERS = {
    "ai-record": {
        "root": "AI회의록",
        "children": {"inbox": "inbox", "recordings": "녹음", "minutes": "회의록"},
    },
}


def _app_spec(app_key):
    """앱 폴더 spec 조회 + ★fail-fast 검증(네트워크/폴더 생성 前)★. real·mock 공통 진입.
    unknown / 비-str(unhashable 포함) / malformed(root·children 형식 위반) → 전부 ValueError
    (프로즌 'unknown app → ValueError' 시맨틱 보존). ★검증이 user 조회·Drive 호출보다 먼저라 부분생성 없음.★"""
    if not isinstance(app_key, str):                       # unhashable(list/dict/set) → TypeError 대신 ValueError
        raise ValueError("resolve_folders: unknown app " + repr(app_key))
    spec = _APP_FOLDERS.get(app_key)
    if spec is None:
        raise ValueError("resolve_folders: unknown app " + repr(app_key))
    root = spec.get("root") if isinstance(spec, dict) else None
    children = spec.get("children") if isinstance(spec, dict) else None
    if not (isinstance(root, str) and root and isinstance(children, dict) and children
            and all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in children.items())):
        raise ValueError("resolve_folders: malformed app spec for " + repr(app_key))
    if "root" in children:                             # ★'root' 은 예약 출력키 → child 키로 쓰면 app-root 참조를 덮음
        raise ValueError("resolve_folders: 'root' is a reserved role key (children may not use it) for " + repr(app_key))
    if len(set(children.values())) != len(children):   # ★중복 표시이름 = 두 role 이 한 폴더로 alias(모호) → 거부
        raise ValueError("resolve_folders: duplicate child folder display-names not allowed (would alias to one folder) for " + repr(app_key))
    if set(children) != {"inbox", "recordings", "minutes"}:   # ★M5: v1 folder registry row = 이 3 role 고정.
        raise ValueError("resolve_folders: v1 registry supports only {inbox,recordings,minutes} roles for " + repr(app_key))
    return spec


def _spec_sha256(spec):
    """앱 폴더 role(root + children 의 key/표시이름)의 canonical(sorted) JSON 해시.
    ★read(ap_host)·write(provisioner) 가 동일 계산이어야 registry 키가 일치한다.★"""
    canon = {"root": spec["root"], "children": dict(spec["children"])}
    return hashlib.sha256(
        json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _open_registry_ro(db_path):
    """레지스트리를 ★순수 read-only(?mode=ro)★ 로 연다. registry 는 rollback-journal(DELETE) 모드라 reader 가
    -wal/-shm 를 만들 필요가 없어 read-only open 으로 충분 — request 경로는 어떤 파일도 write 안 함(★rw 폴백 없음★).
    write 차단 이중: FS(provisioner harden_perms 가 파일을 0640 root:<reader-grp> 강제 → group w 없음) + SQL(mode=ro).
    write 는 provisioner(root)만. ★★격리(어느 프로세스가 group-read 하나)는 <reader-grp> 정책 = 배포 아키텍처:
    sibling(같은 owner) 격리는 ★project별 distinct group + preview setgroups★ 필요(per-owner group 은 형제 공유).
    이 reader 는 FS 격리를 만들지 않고 전제만 함 — 격리 실효는 platform-admin 배포(group 배정)+live probe.★★
    ?mode=ro 실패(정상 DELETE db 면 안 남)=상위 resolve_folders fail-closed — ★절대 rw 로 owner-write 요구 안 함★."""
    conn = sqlite3.connect("file:" + db_path + "?mode=ro", uri=True, timeout=5)
    conn.execute("PRAGMA query_only=ON")         # SQL 레벨 write 금지(FS mode 와 이중방어)
    return conn


def _fref(fid, name):
    return {"provider": "google-drive", "folder_id": fid, "id": fid, "name": name}


class _HostDrive:
    """Phase A host-drive facade: per-user folder resolution bound to host.user identity."""

    def __init__(self, host):
        self._host = host

    def resolve_folders(self, app_key="ai-record"):
        # ★S10 read-only 레지스트리 lookup(계약 round-017). Drive/OAuth 호출 0. 정확히 5단계.★
        spec = _app_spec(app_key)                           # (1) spec fail-fast(네트워크 前). unknown/malformed→ValueError
        u = self._host.user()                               # (2) 신뢰 host 컨텍스트만. ★브라우저 파라미터·앱 페이로드 불참여★
        project_id = (u.project_id if u else "") or ""      #     project_id = x-ap-project-id(프록시 주입=위조불가)
        actor_id = (u.id if u else "") or ""                #     platform_actor_id = x-ap-user-id
        if not project_id or not actor_id:
            raise RuntimeError(_REGISTRY_UNAVAILABLE)        # 신원 없음 → fail-closed
        db_path = _config_from_env(_REGISTRY_DB_ENV)
        if not db_path or not os.path.exists(db_path):
            raise RuntimeError(_REGISTRY_UNAVAILABLE)        # 레지스트리 미프로비저닝 → fail-closed
        spec_hash = _spec_sha256(spec)
        try:
            conn = _open_registry_ro(db_path)
            try:
                # (3) server-provisioned OAuth principal(Drive User.permissionId) 로컬 read. ★token/Drive 호출 없음★
                pr = conn.execute(
                    "select oauth_permission_id from credential_principal "
                    "where project_id=? and platform_actor_id=?", (project_id, actor_id)).fetchone()
                perm = pr[0] if pr else None
                if not perm:
                    raise RuntimeError(_REGISTRY_UNAVAILABLE)
                # (4) 정확한 active row(5-part key). disabled/repairing/provisioning/미스는 여기서 걸러짐
                row = conn.execute(
                    "select app_root_id, inbox_id, recordings_id, minutes_id, generation, spec_sha256, state "
                    "from folder_registry where project_id=? and platform_actor_id=? and oauth_permission_id=? "
                    "and app_key=? and spec_sha256=? and state='active'",
                    (project_id, actor_id, perm, app_key, spec_hash)).fetchone()
            finally:
                conn.close()
        except RuntimeError:
            raise
        except Exception:                                    # DB 락/손상/CANTINIT 등 → 단일 fail-closed
            raise RuntimeError(_REGISTRY_UNAVAILABLE) from None   # ★M4: __context__ 체이닝 차단(sqlite 원문/SQL/db경로 미노출)★
        if row is None:
            raise RuntimeError(_REGISTRY_UNAVAILABLE)
        app_root, inbox_id, rec_id, min_id, generation, row_spec, state = row
        ids = [app_root, inbox_id, rec_id, min_id]
        if (state != "active" or row_spec != spec_hash or not isinstance(generation, int)
                or generation < 1 or any(not x for x in ids) or len(set(ids)) != len(ids)):
            raise RuntimeError(_REGISTRY_UNAVAILABLE)        # malformed/role 중복/spec mismatch → fail-closed
        # (5) fresh canonical refs — ★매 호출 새 dict, 공유 nested 없음★. 표시이름=현재 서버 spec.
        return {
            "root": _fref(app_root, spec["root"]),
            "inbox": _fref(inbox_id, spec["children"]["inbox"]),
            "recordings": _fref(rec_id, spec["children"]["recordings"]),
            "minutes": _fref(min_id, spec["children"]["minutes"]),
        }


# ── record_sync_trigger 3-shape canonical validator (broker·client 공용 단일 정의) ──
# 정확 key-set + bool identity(is True/is False) + exact-str 만 통과. 그 외(누락키/추가키/비-bool/
# unknown code) 전부 → unavailable(canonical). broker 도 ap_host 에서 이걸 import(단일 소스). malformed
# success 는 절대 success 로 새지 않음(coalesce timestamp 미갱신의 근거).
_TRIGGER_OK = {"ok": True, "queued": True, "coalesced": True}
_TRIGGER_DENIED = {"ok": False, "code": "denied"}
_TRIGGER_UNAVAILABLE = {"ok": False, "code": "unavailable"}


def _canonical_trigger_response(resp):
    """record_sync_trigger 3-shape 만 정확 통과. 그 외 전부 → canonical unavailable."""
    if isinstance(resp, dict):
        keys = set(resp.keys())
        if keys == {"ok", "queued", "coalesced"}:
            if resp["ok"] is True and resp["queued"] is True and resp["coalesced"] is True:
                return dict(_TRIGGER_OK)
        elif keys == {"ok", "code"}:
            if resp["ok"] is False and resp["code"] == "denied":
                return dict(_TRIGGER_DENIED)
            if resp["ok"] is False and resp["code"] == "unavailable":
                return dict(_TRIGGER_UNAVAILABLE)
    return dict(_TRIGGER_UNAVAILABLE)


# ── record_sync_trigger broker client (async-upload A) ──────────────────────
# 앱(owner-uid, env -i)은 broad residual 토큰을 못/안 갖는다: 토큰은 root broker 안에만 있고, 앱은
# root-owned AF_UNIX 소켓(0660 root:apreg_<hex>)으로 ★고정 op 1개★만 보내 트리거를 당긴다. 소켓
# DAC(apreg traverse)+broker SO_PEERCRED(uid==owner) 가 admission. 이 클라이언트는 신뢰경계가 아니다
# (owner-editable 앱 코드 영역) — 모든 강제는 broker(server-side). 여기선 래퍼일 뿐.
_RECORD_TRIGGER_PROJECT_ID = "ff5beb6f-3f97-47df-8195-5227db7d27c6"   # v1 single-project pin
_RECORD_TRIGGER_SOCK = "/run/ap-record-trigger-broker/%s.sock" % _RECORD_TRIGGER_PROJECT_ID
_RECORD_TRIGGER_OP = b"enqueue_self\n"


def _record_trigger_broker_client(project_id):
    """host.service('record_sync_trigger') 반환(ProxyHost). ★project_id 가 정확히 pinned canonical
    lowercase UUID 일 때만★ 클라이언트(아니면 None=graceful). 임의 문자열을 소켓 경로에 보간 안 함."""
    if str(project_id or "") != _RECORD_TRIGGER_PROJECT_ID:
        return None
    return _RecordTriggerBrokerClient()


class _RecordTriggerBrokerClient:
    """★call("enqueue_self") 만★ 노출 — ProxyHost service 규약(다른 서비스 _MockService/_Doubleman…
    과 동일한 .call(verb)). 앱(record_core)은 host.service("record_sync_trigger").call("enqueue_self")
    로 호출한다. 소켓 연결→고정 op 송신→canonical 3-shape 수신. ★토큰 자격물질 0★. 소켓 부재(브로커
    미가동/다른 프로젝트=apreg dir EACCES)·타임아웃·malformed·미지원 verb → canonical unavailable.
    앱은 record_sync_trigger·토큰 경로를 전혀 import 안 함."""

    def call(self, verb, **_kw):
        if verb != "enqueue_self":                 # ProxyHost .call 규약: enqueue_self 만 지원
            return dict(_TRIGGER_UNAVAILABLE)
        import socket as _socket
        buf = b""
        try:
            c = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            c.settimeout(15)                       # > broker read(3s)+upstream(10s) 여유
            try:
                c.connect(_RECORD_TRIGGER_SOCK)
                c.sendall(_RECORD_TRIGGER_OP)
                c.shutdown(_socket.SHUT_WR)
                while len(buf) < 128:
                    chunk = c.recv(128 - len(buf))
                    if not chunk:
                        break
                    buf += chunk
            finally:
                c.close()
        except Exception:  # noqa: BLE001 — connect/EACCES/timeout 등 → canonical(자격 미노출)
            return dict(_TRIGGER_UNAVAILABLE)
        try:
            resp = json.loads(buf.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return dict(_TRIGGER_UNAVAILABLE)
        return _canonical_trigger_response(resp)


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
        return _SqliteScope(name, owner=(u.id if u else "anon"), role=(u.role if u else None))

    def drive(self) -> "Drive | None":
        # 코어 drive 위임은 승격 시점 기능. standalone 미리보기는 미연동 취급.
        return _HostDrive(self)

    def config(self, key: str, default=None):
        return _config_from_env(key, default)

    def service(self, name: str):
        # v1 각자 섬 기본 = None(graceful). 예외: 운영자 승인된 host-service 만 등록.
        # 'doubleman' = signal-developer 승격 계약(2026-07-02, 형진 배포승인). 토큰/URL 은
        # 서버측 /lab/sdk/doubleman.env(root:owner)에만 두고, pid 게이트로 승인 프로젝트만 부여.
        if name == "doubleman":
            return _doubleman_service_for(self._h("x-ap-project-id"), self._h("x-ap-user-email"))
        # 'finance-data' = finance-data-api 데이터모듈(2026-07-03, agent-khj 계약 승인).
        # loopback 전용 read API(127.0.0.1:8901). 토큰/URL/allowlist = /lab/sdk/finance-data.env.
        if name == "finance-data":
            return _finance_data_service_for(self._h("x-ap-project-id"))
        # 'portfolio-value' = PVC 계산모듈(Alpha Tester 계약 v1.1 §4, PVC 요청 2026-07-09, khj 오케스트레이션).
        # loopback persistent(127.0.0.1:8902, portfolio-value.service). env=/lab/sdk/portfolio-value.env.
        if name == "portfolio-value":
            return _portfolio_value_service_for(self._h("x-ap-project-id"))
        # 'record_tombstone_cleanup' = ai-record R2 P2 durable-cleanup ★request-bound signer★.
        # 요청 경로(ProxyHost)에서만 sign_create_identity 제공(공유 아티팩트 서명). key/pid-gate =
        # /lab/sdk/record-tombstone-cleanup.env. dev-user/미키/미허용 project → fail-closed None.
        # worker ops(list_pending/drain/reconcile)는 여기 없음 — poller 가 CleanupWorker 직접 사용.
        if name == "record_tombstone_cleanup":
            try:
                from record_cleanup import signer_for
                return signer_for(self._h("x-ap-user-id") or "", self._h("x-ap-project-id") or "")
            except Exception:  # noqa: BLE001 — 모듈 미배치 시 graceful None
                return None
        # 'record_admin_read' = R6 관리자 전역읽기(goal300 round-006 계약). request-bound reader.
        #   pid=고정 ai-record pid 게이트 + records.read_all(플랫폼 DB SECDEF record_admin_can_read_all) 권한.
        #   자격=서버측 /lab/sdk/record-admin-read.env(root:owner). env/pid/actor 미충족 → None(fail-closed no-op).
        #   크로스오너 read-only(list_jobs/read_minutes/read_transcript) + IDOR 동일거부 + 전용 감사 + write 0.
        if name == "record_admin_read":
            try:
                from record_admin_read import reader_for
                return reader_for(self._h("x-ap-user-id") or "", self._h("x-ap-project-id") or "")
            except Exception:  # noqa: BLE001 — 모듈 미배치 시 graceful None
                return None
        # 'record_sync_trigger' = async-upload A(round-009). ★request-bound enqueue_self★(zero-payload).
        #   owner/project 는 ★host-derived x-ap-*★(client-supplied 아님) — platform 이 활성 S10 registry 재도출.
        #   pid-gate + fail-closed(dev-user/anon/미허용→None or denied) = /lab/sdk/record-sync-trigger.env(least-priv role).
        #   worker(lease/drain/CAS clear/reconcile)는 여기 없음 — poller 가 WorkerDrain 직접 사용.
        if name == "record_sync_trigger":
            # ★async-upload A: broad residual 토큰은 root broker 안에만★. 앱은 토큰 파일
            #   (/lab/sdk/record-sync-trigger.env, 0600 root:root)을 절대 안 읽는다 — owner-uid EACCES
            #   (503 sync_trigger_unavailable) 원인 제거. per-project root-owned AF_UNIX 소켓으로 고정
            #   op(enqueue_self) 하나만 보내고 canonical 3-shape 응답을 받는다(자격물질 0). owner/project
            #   는 broker 가 server-side 재도출. 소켓 DAC(apreg)+SO_PEERCRED 가 admission.
            #   project_id 가 pinned UUID 아니면 None(fail-closed·임의 문자열 소켓경로 보간 안 함).
            return _record_trigger_broker_client(self._h("x-ap-project-id") or "")
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
        return _SqliteScope(name, owner=(u.id if u else "dev-user"), role=(u.role if u else None))

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
        # 'record_tombstone_cleanup': MockHost(오프라인 dev / systemd 워커) 컨텍스트에서는 signer 가
        #   owner=dev-user 라 sign_create_identity 가 ★항상 refuse(None)★ = fail-closed(dev-user 서명
        #   금지·no unsigned fallback). worker drain/reconcile 는 poller 가 CleanupWorker 직접 인스턴스화.
        #   테스트/스텁이 services 에 정의돼 있으면 그걸 우선(기존 mock 경로 보존).
        if name == "record_tombstone_cleanup":
            stub = (self._cfg.get("services") or {}).get(name)
            if stub is not None:
                return _MockService(stub)
            try:
                from record_cleanup import RequestBoundSigner
                return RequestBoundSigner("dev-user")
            except Exception:  # noqa: BLE001
                return None
        # 'record_sync_trigger': MockHost 는 owner=dev-user 라 enqueue_self()=denied(fail-closed). 대칭.
        if name == "record_sync_trigger":
            stub = (self._cfg.get("services") or {}).get(name)
            if stub is not None:
                return _MockService(stub)
            try:
                from record_sync_trigger import mock_refuse_enqueuer
                return mock_refuse_enqueuer()
            except Exception:  # noqa: BLE001
                return None
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
    owner 자동주입/필터로 IDOR 안전을 standalone 에서도 강제(승격 RLS 와 동일 동작).
    ★id 는 owner 별로만 유일 — get/list/delete/put 전부 owner 로 격리되어 owner 간 read/write 불가."""

    def __init__(self, name: str, owner: str, role: str | None = None):
        self._name = "".join(c for c in name if c.isalnum() or c == "_") or "data"
        self._owner = owner
        self._role = role                    # HOST_CONTRACT §5.3: viewer 쓰기거부(mock 충실도). proxy/live=None(§2).
        # ★isolation_level=None(autocommit) + busy_timeout: 마이그레이션을 명시적 BEGIN IMMEDIATE 로
        #   직렬화하고, 락 대기 스레드는 즉시 에러 대신 대기하게(동시 최초-open race 차단).
        self._db = sqlite3.connect(_MOCK_DB, isolation_level=None)
        self._db.execute("PRAGMA busy_timeout=5000")
        self._ensure_schema()

    def _is_composite(self, t):
        return {c[1] for c in self._db.execute(f"PRAGMA table_info({t})").fetchall()
                if c[5] > 0} == {"id", "owner"}

    def _ensure_schema(self):
        """테이블 보장 + ★구 단일 id-PK → 복합 (id,owner) PK 행 보존 마이그레이션(동시성 안전)★.
        복합 PK: owner 간 독립 id 네임스페이스로 put 의 conflict-update IDOR(남 행 body 덮기) 차단.
        ★기존 .ap_mock.db 는 단일 id-PK 라 create-if-not-exists 로는 안 바뀜 → 감지해 재구축(행 보존).
          마이그레이션 전체를 단일 writer transaction(BEGIN IMMEDIATE)으로 감싸 ThreadingHTTPServer
          동시 최초 scope 생성이 notes__mig 를 경쟁 생성하던 간헐 OperationalError 를 차단.★"""
        t = self._name
        self._db.execute(
            f"create table if not exists {t} "
            "(id text not null, owner text not null, body text not null, primary key(id, owner))")
        if self._is_composite(t):
            return                                     # 이미 복합 PK(흔한 경우) → 락 불필요
        # 구 스키마 → 단일 writer transaction 으로 행 보존 재구축
        self._db.execute("BEGIN IMMEDIATE")            # 쓰기락 획득(다른 스레드는 busy_timeout 만큼 대기)
        try:
            if self._is_composite(t):                  # 락 대기 중 다른 스레드가 이미 마이그레이션했으면 skip
                self._db.execute("COMMIT")
                return
            self._db.execute(f"drop table if exists {t}__mig")
            self._db.execute(
                f"create table {t}__mig "
                "(id text not null, owner text not null, body text not null, primary key(id, owner))")
            old_cols = {c[1] for c in self._db.execute(f"PRAGMA table_info({t})").fetchall()}
            if {"id", "owner", "body"} <= old_cols:    # 구 테이블에 owner 없을 수도 → 존재 컬럼만 복사
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
        for k, v in where.items():           # 동등 필터만 (쿼리빌더로 키우지 않는다)
            out = [d for d in out if d.get(k) == v]
        return out

    def put(self, row: dict):
        if str(self._role or "").strip().lower() == "viewer":  # ★§5.3: viewer 쓰기 불가(대소문자·공백 무시 — role 오타도 fail-closed)★
            raise PermissionError("viewer 는 쓰기 불가 (host.data.put) — HOST_CONTRACT §5.3")
        d = dict(row)
        d.pop("owner", None)                 # ★ 앱이 보낸 owner 무시(IDOR 차단)
        rid = d.get("id") or str(uuid.uuid4())
        d["id"] = rid
        self._db.execute(
            f"insert into {self._name}(id,owner,body) values(?,?,?) "
            # ★conflict target=(id,owner): 같은 owner 의 같은 id 만 update. 다른 owner 가 같은 id 로
            #   put 하면 충돌 안 나 자기 소유 새 행이 insert 됨 → 남의 행 절대 안 덮음(IDOR 차단).
            "on conflict(id,owner) do update set body=excluded.body",
            (rid, self._owner, json.dumps({k: v for k, v in d.items() if k != "id"})))
        self._db.commit()
        return d

    def delete(self, id) -> bool:
        if str(self._role or "").strip().lower() == "viewer":  # ★§5.3: viewer 쓰기 불가(대소문자·공백 무시 — role 오타도 fail-closed)★
            raise PermissionError("viewer 는 쓰기 불가 (host.data.delete) — HOST_CONTRACT §5.3")
        cur = self._db.execute(
            f"delete from {self._name} where id=? and owner=?", (id, self._owner))
        self._db.commit()
        return cur.rowcount > 0


# ── Drive / Service (mock 구현) ─────────────────────────────
class Drive:  # 인터페이스(문서용)
    def resolve_folders(self, app_key="ai-record"): ...  # 앱별 per-user 폴더트리 확보(_HostDrive=실 Drive / _LocalDrive=mock)
    def list(self): ...
    def get(self, file_id): ...


class _LocalDrive(Drive):
    def resolve_folders(self, app_key="ai-record"):
        # standalone/mock — ★mock-v1: role DISTINCT(Round15 platform-mock-layout 9aa4b2a1)★.
        # 각 role(root/inbox/recordings/minutes)이 서로 다른 mock 폴더 id 로 구분 = 실 레지스트리와 대칭
        # (구 legacy 는 전 role 을 단일 RECORD_INBOX 로 매핑 → distinct 로 교정). spec 검증(_app_spec)은
        # real 과 동일 = unknown/malformed 를 fail-fast 거부(계약 균일). 표시이름도 real 과 동일(spec).
        spec = _app_spec(app_key)
        base = _config_from_env("RECORD_INBOX_FOLDER_ID") or "mock"

        def _mock_id(role):     # 결정적·role 별 구분(같은 base→안정, role 별→상이)
            return "mock-" + hashlib.sha256((base + "|" + role).encode("utf-8")).hexdigest()[:12]

        out = {"root": _fref(_mock_id("root"), spec["root"])}
        for key, folder_name in spec["children"].items():
            out[key] = _fref(_mock_id(key), folder_name)
        return out

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
# (앱이 host.config("GOOGLE_CLIENT_ID") 처럼 자기 .env 값을 host 계약으로 받게. standalone 은
#  앱 자신의 env(.env 로 로드)를 읽고, 승격 시엔 플랫폼이 같은 키로 주입한다.)
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


# ── doubleman host-service (플랫폼 등록, 운영자 승인 2026-07-02) ──
# ProxyHost.service("doubleman") 가 반환. 토큰/URL 은 서버측 /lab/sdk/doubleman.env
# (root:owner 0640)에만 두고 앱은 creds 무저장. base URL = 리버스 SSH 터널 로컬
# 엔드포인트(127.0.0.1:8900 → meta-linux doubleman eval API). pid 게이트로 승인 프로젝트만.
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
        return None  # 미구성 → graceful(앱은 'unavailable' 표시)
    allowed = [p.strip() for p in (cfg.get("DOUBLEMAN_ALLOWED_PIDS") or "").split(",") if p.strip()]
    if allowed and (project_id or "") not in allowed:
        return None  # 승인 안 된 프로젝트 → None
    return _DoublemanService(base, token, user_email)


class _DoublemanService:
    """doubleman eval API 포워딩 host-service. Bearer 는 host 가 붙인다(앱 무저장).
    call(verb, request) → POST <base><path>; verb: evaluate|detector_evaluate. 항상 dict 반환."""

    _VERB_PATHS = {
        "evaluate": "/api/backtest/evaluate",
        "detector_evaluate": "/api/backtest/detector-evaluate",
        "prices": "/api/backtest/prices",  # 경로2: 학생 창작신호용 가격데이터(columnar; urlopen 기본 identity→비압축)
        "validate_strategy": "/api/strategy/validate",  # 전략 제출: 검수
        "submit_strategy": "/api/strategy/submit",      # 전략 제출: 최종 submit(author 귀속)
        # Alpha Tester 입력단(khj 스펙 2026-07-09): 7-key 전략셋 형식검증 / 큐 적재(version 자동증가).
        # submitter.email 은 아래 _IDENTITY_KEYS 로직이 로그인 신원으로 강제(스푸핑 방지 동일 적용).
        "alpha_tester_validate": "/api/alpha-tester/validate",
        "alpha_tester_submit": "/api/alpha-tester/submit",
        # 조회(khj 라우트 2026-07-10): {project,strategy_name[,version]} 또는 request_id(at-*) → complete 시
        # result.metrics.portfolio(effective_weights·turnoverAnnualPct)+crosscheck+portfolio_value+weights_timeseries.
        "alpha_tester_result": "/api/alpha-tester/result",
        # 비영속 프리뷰(khj 2026-07-10): {weights_timeseries,capital?} → {preview:true,persistent:false,
        # result:{portfolio_value,metrics.portfolio,crosscheck,reliability}}. weight-source-agnostic(오케스트레이터가 WG /weights 주입).
        "alpha_tester_backtest_preview": "/api/alpha-tester/backtest-preview",
    }
    # 신원귀속 서브객체: 로그인 신원(X-AP-User-Email)으로 email 강제 오버라이드(스푸핑 방지). 있을 때만.
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
        # ★스푸핑 방지(2026-07-02, 형진 지시): save/submitter 같은 신원귀속 객체의 email 을
        #  ★플랫폼 로그인 신원(X-AP-User-Email)★으로 강제 오버라이드 — 앱 자율입력 무시.
        #  해당 객체 없으면 미주입(저장/제출 author 귀속 안 함).
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
        except _ue.HTTPError as e:                      # 4xx/5xx: JSON 본문이면 그대로 전달
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"ok": False, "error": f"doubleman http {e.code}", "verb": verb}
        except Exception as e:                          # 연결 실패 등 → graceful dict
            return {"ok": False, "error": f"doubleman call failed: {type(e).__name__}", "verb": verb}


# ── finance-data host-service (플랫폼 등록, agent-khj 계약 승인 2026-07-03) ──
# ProxyHost.service("finance-data") 가 반환. read-only 데이터 API(주가/유니버스/상장상태).
# base URL = loopback 전용 persistent 서비스(127.0.0.1:8901, finance-data-api.service).
# 토큰/URL/allowlist 는 서버측 /lab/sdk/finance-data.env(root:owner 0640)에만. pid 게이트로 승인 프로젝트만.
_FINANCE_ENV = "/lab/sdk/finance-data.env"


def _finance_data_service_for(project_id):
    cfg = _read_env_file(_FINANCE_ENV)
    base = cfg.get("FINANCE_DATA_BASE_URL")
    if not base:
        return None  # 미구성(예: 콜리 서버엔 없음) → graceful None
    allowed = [p.strip() for p in (cfg.get("FINANCE_DATA_ALLOWED_PIDS") or "").split(",") if p.strip()]
    if allowed and (project_id or "") not in allowed:
        return None  # 승인 안 된 프로젝트 → None
    return _FinanceDataService(base, cfg.get("FINANCE_DATA_TOKEN"))


class _FinanceDataService:
    """finance-data-api 포워딩 host-service(read-only). Bearer 는 host 가 붙인다(앱 무저장).
    call(verb, request) → verb 별 GET/POST. 항상 dict 반환(신원귀속 없음 = read-only)."""

    # verb → (method, path). prices 만 POST(JSON body), 나머지는 GET(query = request).
    _VERB_SPECS = {
        "prices": ("POST", "/prices"),
        "universe": ("GET", "/universe"),
        "listing_status": ("GET", "/listing-status"),
        "health": ("GET", "/health"),
        "freshness": ("GET", "/freshness"),  # 데이터 최신성 게이트(Alpha Tester 계약 v1.1 §2/§6-10, agent-khj 요청 2026-07-09)
        "yearly_returns": ("POST", "/yearly-returns"),  # 연도별(캘린더) 수익률(Alpha Tester, agent-khj dispatch 2026-07-10)
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
        except _ue.HTTPError as e:                      # 4xx/5xx: JSON 본문이면 그대로 전달
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"ok": False, "error": f"finance-data http {e.code}", "verb": verb}
        except Exception as e:                          # 연결 실패 등 → graceful dict
            return {"ok": False, "error": f"finance-data call failed: {type(e).__name__}", "verb": verb}


# ── portfolio-value host-service (Alpha Tester 계약 v1.1 §4, PVC 요청·khj 오케스트레이션 2026-07-09) ──
# ProxyHost.service("portfolio-value") 가 반환. 계산 API(POST /value — 웨이트→포트폴리오 가치 시뮬).
# base URL = loopback 전용 persistent 서비스(127.0.0.1:8902, portfolio-value.service).
# 토큰/URL/allowlist 는 서버측 /lab/sdk/portfolio-value.env(root:owner 0640)에만. pid 게이트.
_PVC_ENV = "/lab/sdk/portfolio-value.env"


def _portfolio_value_service_for(project_id):
    cfg = _read_env_file(_PVC_ENV)
    base = cfg.get("PVC_BASE_URL")
    if not base:
        return None  # 미구성(예: 콜리 서버) → graceful None
    allowed = [p.strip() for p in (cfg.get("PVC_ALLOWED_PIDS") or "").split(",") if p.strip()]
    if allowed and (project_id or "") not in allowed:
        return None
    return _PortfolioValueService(base, cfg.get("PVC_BEARER_TOKEN"))


class _PortfolioValueService:
    """PVC 포워딩 host-service. Bearer 는 host 가 붙인다(앱 무저장). call(verb, request) → dict."""

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
            with _u.urlopen(req, timeout=300) as resp:   # 계산 API 라 타임아웃 여유(백테스트 구간에 비례)
                return json.loads(resp.read().decode("utf-8"))
        except _ue.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"ok": False, "error": f"portfolio-value http {e.code}", "verb": verb}
        except Exception as e:
            return {"ok": False, "error": f"portfolio-value call failed: {type(e).__name__}", "verb": verb}
