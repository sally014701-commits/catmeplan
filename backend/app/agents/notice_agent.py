"""Find an SKKU notice for a natural-language request and turn it into todos.

Flow: Gemini picks search keywords → search the notice board → Gemini picks
the matching notice → read it → Gemini extracts todos + a project name →
tasks/project are stored → the project is classified into a 기록 category.
"""

from concurrent.futures import ThreadPoolExecutor
import html
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.agents.project_agent import _generate_json, classify_project_goal
from app.services import goal_service, project_service, task_service


BOARD_URL = "https://www.skku.edu/skku/campus/skk_comm/notice01.do"


def _fetch(params: dict) -> str:
    request = Request(
        f"{BOARD_URL}?{urlencode(params)}",
        headers={"User-Agent": "Mozilla/5.0 (catmeplan notice reader)"},
    )
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def search_notices(keyword: str) -> list[dict]:
    page = _fetch({"mode": "list", "srSearchKey": "article_title", "srSearchVal": keyword})
    links = re.findall(
        r'<a href="\?mode=view&amp;articleNo=(\d+)[^"]*" title="자세히 보기">(.*?)</a>',
        page,
        re.DOTALL,
    )
    return [{"article_no": number, "title": " ".join(_text(title).split())} for number, title in links]


def read_notice(article_no: str) -> dict:
    page = _fetch({"mode": "view", "articleNo": article_no})
    title = re.search(r'data-title="([^"]*)"', page)
    body = re.search(r'<pre class="pre">(.*?)</pre>', page, re.DOTALL)
    return {
        "article_no": article_no,
        "title": html.unescape(title.group(1)) if title else "",
        "body": _text(body.group(1)) if body else "",
        "url": f"{BOARD_URL}?mode=view&articleNo={article_no}",
    }


def find_notice(user_request: str) -> dict:
    keywords = _generate_json(
        f"""성균관대학교(skku.edu) 공지사항 게시판은 제목으로만 검색됩니다.
아래 요청에 맞는 공지를 찾기 위한 제목 검색어를 3~5개 만드세요.
학교 공지에서 실제로 쓰일 법한 공식 표현(예: 헬스장 → 체력증진센터)도 포함하세요.
반드시 JSON 객체만 출력하세요: {{"keywords": ["검색어"]}}

요청: {user_request}
"""
    ).get("keywords") or []

    with ThreadPoolExecutor() as pool:
        results = pool.map(search_notices, [str(keyword) for keyword in keywords[:5]])
    candidates: dict[str, dict] = {}
    for notices in results:
        for notice in notices:
            candidates.setdefault(notice["article_no"], notice)
    if not candidates:
        raise ValueError(f"No notices found for keywords: {keywords}")

    titles = [notice["title"] for notice in candidates.values()]
    index = _generate_json(
        f"""아래 공지 제목 목록 중 요청에 가장 맞는 공지 하나를 고르고 그 순번(0부터)을 답하세요.
반드시 JSON 객체만 출력하세요: {{"index": 0}}

요청: {user_request}
공지 제목 목록: {json.dumps(dict(enumerate(titles)), ensure_ascii=False)}
"""
    ).get("index")
    if not isinstance(index, int) or not 0 <= index < len(titles):
        raise ValueError(f"Gemini selected a notice outside the search results: {index} of {titles}")
    return read_notice(list(candidates)[index])


def import_notice(user_request: str) -> dict:
    notice = find_notice(user_request)
    plan = _generate_json(
        f"""아래 학교 공지를 읽은 사용자가 실제로 해야 할 일(Task)을 뽑고, 이 일들을 묶을 Project 이름을 정하세요.
- 할 일은 실행 가능한 행동 단위로, 1~5개만.
- content는 공지 원문의 근거 문구를 그대로 복사하세요.
- 날짜가 있으면 due_date를 YYYY-MM-DD로, 없으면 null.
- project_name은 이 공지 하나보다 넓고 삶 전체보다는 좁은 지속적 활동 이름(예: "헬스", "장학금 신청").
반드시 JSON 객체만 출력하세요:
{{"project_name": "이름", "tasks": [{{"title": "짧은 요약", "content": "원문 문구", "due_date": "YYYY-MM-DD 또는 null"}}]}}

공지 제목: {notice["title"]}
공지 본문:
{notice["body"][:6000]}
"""
    )
    project_name = str(plan.get("project_name") or "").strip()
    items = [item for item in plan.get("tasks") or [] if isinstance(item, dict)]
    if not project_name or not items:
        raise ValueError("Gemini did not return a project name and tasks")

    project = next(
        (existing for existing in project_service.list_projects() if existing["name"] == project_name),
        None,
    )
    if project is None:
        project = project_service.get_project(project_service.create_project(project_name))

    tasks = [
        task_service.create_task(
            content=item.get("content") or item.get("title") or "",
            due_date=item.get("due_date"),
            title=item.get("title"),
            project_id=project["id"],
            source="mallang",
        )
        for item in items
    ]

    goal_id = project["goal_id"] or classify_project_goal(project)
    goal = goal_service.get_goal(goal_id) if goal_id else None
    return {
        "notice": {"title": notice["title"], "url": notice["url"]},
        "project": {"id": project["id"], "name": project["name"], "goal": goal["name"] if goal else None},
        "tasks": tasks,
    }
