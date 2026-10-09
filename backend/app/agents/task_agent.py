from datetime import date
import json
import logging
import os
from pathlib import Path
import re

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from app.services.task_service import create_task, get_task, list_tasks


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_CANDIDATES = (
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
)
load_dotenv(PROJECT_ROOT / ".env")


def parse_llm_json(
    raw_response: str,
    *,
    expected_type: type = list,
) -> list[dict] | dict:
    """Parse JSON, removing an optional Markdown code fence."""
    cleaned = raw_response.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.exception("Failed to parse Gemini JSON response: %s", raw_response)
        raise
    if expected_type is dict:
        if not isinstance(parsed, dict):
            raise ValueError("Gemini response must be a JSON object")
        return parsed
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError("Gemini response must be a JSON array of objects")
    return parsed


def _generate_with_fallback(client, prompt: str, config):
    for index, model in enumerate(MODEL_CANDIDATES):
        try:
            return client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
        except errors.APIError as error:
            is_last_model = index == len(MODEL_CANDIDATES) - 1
            if error.code not in {404, 429, 503} or is_last_model:
                raise
            logger.warning(
                "%s is unavailable (%s); falling back to %s",
                model,
                error.code,
                MODEL_CANDIDATES[index + 1],
            )


def decompose(user_input: str) -> dict:
    """Classify input intent and split task requests into candidates."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    today = date.today().isoformat()
    prompt = f"""오늘 날짜는 {today}입니다.
먼저 사용자의 자연어 입력이 어떤 의도인지 판단하세요. 세 가지 중 하나입니다.
- "task": 할 일을 만들어 달라는 요청. 입력을 실행 가능한 Task들로 분해하세요.
- "query": 자신의 일정·할 일·기록에 대해 묻는 질문 (예: "이번 주 뭐 했어?", "내일 일정 있어?").
- "chat": 그 외 일반적인 대화 — 잡담, 감정 표현, 안부, 할 일/일정과 무관한 질문 등.
"query"와 "chat"은 tasks가 빈 배열이어야 합니다.
상대적 마감일(예: 오늘, 내일, 다음 주 금요일)은 오늘 날짜를 기준으로 계산하여 YYYY-MM-DD로 출력하세요.

반드시 아래 형태의 JSON 객체만 출력하세요.
{{"intent": "task 또는 query 또는 chat", "tasks": [{{"content": "원문의 해당 표현", "title": "짧은 요약", "due_date": "YYYY-MM-DD 또는 null", "people": ["관련 인물"]}}]}}

규칙:
- content는 사용자 원문의 해당 문구를 글자 그대로 복사하고 의역하지 마세요.
- title만 짧게 요약할 수 있습니다.
- 마감일이 없으면 due_date는 null입니다.
- 관련 인물이 없으면 people은 빈 배열입니다.
- 프로젝트를 판단하거나 생성하지 마세요.

사용자 입력:
{user_input}
"""
    client = genai.Client(api_key=api_key)
    try:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        )
        response = _generate_with_fallback(client, prompt, config)
    finally:
        client.close()
    if not response.text:
        raise ValueError("Gemini returned an empty response")
    result = parse_llm_json(response.text, expected_type=dict)
    if result.get("intent") not in {"task", "query", "chat"}:
        raise ValueError("Gemini response intent must be task, query, or chat")
    tasks = result.get("tasks")
    if not isinstance(tasks, list) or not all(isinstance(item, dict) for item in tasks):
        raise ValueError("Gemini response tasks must be a JSON array of objects")
    if result["intent"] in {"query", "chat"} and tasks:
        raise ValueError("Gemini query/chat response tasks must be empty")
    return result


def answer_query(user_input: str, tasks: list[dict]) -> str:
    """Answer using only the supplied task records."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    visible_tasks = [
        {
            key: task.get(key)
            for key in ("content", "title", "due_date", "source", "people")
        }
        for task in tasks
    ]
    prompt = (
        f"사용자 질문:\n{user_input}\n\n"
        "Task 목록:\n"
        + json.dumps(visible_tasks, ensure_ascii=False)
    )
    client = genai.Client(api_key=api_key)
    try:
        config = types.GenerateContentConfig(
            system_instruction=(
                "아래 제공된 Task 목록에 있는 내용만 근거로 답변해라. "
                "목록에 없는 내용을 지어내지 마라. 사용자의 질문 의도(특정 "
                "사람과 관련된 것, 특정 기간, 특정 프로젝트 등)에 맞게 이 목록 "
                "안에서 골라서 답하되, 목록 자체를 벗어난 정보는 절대 언급하지 "
                "마라. 구글 캘린더 관련 질문에는 source == 'google_calendar'인 "
                "Task만 사용해라. 해당하는 게 없으면 '해당하는 할 일이 없습니다'라고 "
                "답해라."
            ),
            temperature=0.1,
        )
        response = _generate_with_fallback(client, prompt, config)
    finally:
        client.close()
    if not response.text:
        raise ValueError("Gemini returned an empty response")
    return response.text


def chat_reply(user_input: str) -> str:
    """Respond conversationally as 말랑이 to small talk unrelated to tasks."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=api_key)
    try:
        config = types.GenerateContentConfig(
            system_instruction=(
                "너는 '말랑이', 사용자와 다정한 반말로 대화하는 말랑말랑한 친구 캐릭터다. "
                "할 일이나 일정과 상관없는 일반적인 대화, 감정 표현, 안부, 잡담에 짧고 "
                "따뜻하게 반말로 자연스럽게 반응해라. 모르는 사실을 지어내지 말고, "
                "사용자의 할 일이나 일정에 대한 구체적인 내용은 언급하지 마라 — 그건 "
                "다른 기능이 근거를 가지고 따로 답한다."
            ),
            temperature=0.6,
        )
        response = _generate_with_fallback(client, user_input, config)
    finally:
        client.close()
    if not response.text:
        raise ValueError("Gemini returned an empty response")
    return response.text


def process_message(user_input: str) -> list[dict] | dict:
    """Persist decomposed tasks, assign projects, and return DB-backed results."""
    from app.agents.project_agent import assign_project

    decomposition = decompose(user_input)
    if decomposition["intent"] == "query":
        tasks = [dict(task) for task in list_tasks()]
        return {"type": "answer", "text": answer_query(user_input, tasks)}
    if decomposition["intent"] == "chat":
        return {"type": "answer", "text": chat_reply(user_input)}

    results: list[dict] = []
    for item in decomposition["tasks"]:
        created = create_task(
            content=item["content"],
            due_date=item.get("due_date"),
            project_id=None,
            title=item.get("title"),
            people=item.get("people") or [],
            source="mallang",
        )
        stored = get_task(created["id"])
        if stored is None:
            raise RuntimeError(f"Stored task could not be read back: {created['id']}")
        assignment = assign_project(dict(stored))
        assigned_task = get_task(created["id"])
        if assigned_task is None:
            raise RuntimeError(f"Assigned task could not be read back: {created['id']}")
        results.append(
            {
                "type": "task_created",
                "task": dict(assigned_task),
                "assignment": assignment,
            }
        )
    return results
