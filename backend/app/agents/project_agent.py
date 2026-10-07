import json
import logging
import os
import re

from google import genai
from google.genai import types

from app.agents.task_agent import _generate_with_fallback, parse_llm_json
from app.database import transaction
from app.services import project_service, task_service


def parse_llm_json_cot(raw: str) -> dict:
    """CoT 응답 대응 - 추론 과정은 무시하고 마지막 JSON 블록만 추출."""
    code_blocks = re.findall(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if code_blocks:
        return json.loads(code_blocks[-1].strip())
    matches = re.findall(r"\{[^{}]*\}", raw, re.DOTALL)
    if matches:
        return json.loads(matches[-1])
    raise ValueError("응답에서 JSON을 찾을 수 없음")


def _generate_json(prompt: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

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
    return parse_llm_json(response.text, expected_type=dict)


def _confirm_match(task: dict, project_id: str) -> dict:
    project = project_service.get_project(project_id)
    if project is None:
        raise ValueError(f"Project not found: {project_id}")

    merged_people = list(project["people"])
    merged_people.extend(
        person for person in task["people"] if person not in merged_people
    )

    with transaction() as connection:
        task_service.update_task_project_id(
            task["id"],
            project_id,
            connection=connection,
        )
        project_service.update_project(
            project_id,
            people=merged_people,
            connection=connection,
        )

    return {"status": "matched", "project_id": project_id}


def confirm_match(task: dict, project_id: str) -> dict:
    return _confirm_match(task, project_id)


def _llm_pick_among(task: dict, candidate_project_ids: list[str]) -> dict:
    candidates = []
    for project_id in candidate_project_ids:
        project = project_service.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")
        candidates.append(
            {
                "id": project["id"],
                "name": project["name"],
                "people": project["people"],
            }
        )

    prompt = f"""Task 내용과 후보 Project를 비교해 문맥상 가장 가까운 Project를 고르세요.
반드시 아래 후보 중 하나의 id만 선택하세요.
반드시 JSON 객체만 출력하세요: {{"project_id": "후보 id"}}

Task 내용:
{task["content"]}

후보 Project:
{json.dumps(candidates, ensure_ascii=False)}
"""
    result = _generate_json(prompt)
    selected_project_id = result.get("project_id")
    if selected_project_id not in candidate_project_ids:
        raise ValueError("Gemini selected a project outside the candidates")

    matched = _confirm_match(task, selected_project_id)
    return {**matched, "matched_by": "llm_tiebreak"}


def _llm_propose_new(task: dict) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    prompt = f"""아래 순서로 Task에 어울리는 지속적인 상위 활동과 Project 이름을 판단하세요.

1단계: 이 task를 하는 사람은 어떤 상황/신분일 것 같은가?
2단계: 그 상황을 고려하면, 이 task는 어떤 더 지속적인 상위 활동의 일부인가?
3단계: 그 활동을 가리키는 project 이름은? 이 task 하나만 가리킬 만큼 좁지도, 삶 전체를 가리킬 만큼 넓지도 않게 정하세요.

예시 1:
Task: "오늘 오후 5시에 있는 랩 연구미팅 준비해야해"
1단계: 이 사용자는 대학원생이나 연구실 소속일 가능성이 높다.
2단계: 랩 미팅 준비는 단발성이 아니라 앞으로도 계속될 연구실 활동의 일부로 보인다.
3단계: task 하나(미팅 준비)보다는 넓지만 삶 전체보다는 좁은 이름이 적절하다.
최종 출력: {{"suggested_name": "랩 연구"}}

예시 2:
Task: "내일은 요가를 새로 등록해서 수업을 갈거야"
1단계: 이 사용자는 새로운 취미/루틴을 시작하려는 사람이다.
2단계: 요가 등록은 한 번의 수업이 아니라 앞으로 반복될 루틴의 시작으로 보인다.
3단계: 특정 요일이나 한 번의 수업이 아니라, 반복되는 활동 전체를 가리키는 이름이 적절하다.
최종 출력: {{"suggested_name": "요가 수업"}}

이제 실제 Task에 대해 위와 같은 형식으로 1단계, 2단계, 3단계를 작성하세요.
마지막에는 최종 JSON을 반드시 ```json 코드블록으로 감싸서 출력하세요.
JSON 형태: {{"suggested_name": "새 Project 이름"}}

Task 내용:
{task["content"]}
"""
    client = genai.Client(api_key=api_key)
    try:
        config = types.GenerateContentConfig(temperature=0.1)
        response = _generate_with_fallback(client, prompt, config)
    finally:
        client.close()
    if not response.text:
        raise ValueError("Gemini returned an empty response")
    logging.getLogger(__name__).info(
        "Gemini project proposal reasoning: %s",
        response.text,
    )
    result = parse_llm_json_cot(response.text)
    code_blocks = list(
        re.finditer(r"```(?:json)?\s*(.*?)```", response.text, re.DOTALL)
    )
    reasoning = (
        response.text[: code_blocks[-1].start()].strip()
        if code_blocks
        else response.text[: response.text.rfind("{")].strip()
    )
    suggested_name = result.get("suggested_name")
    if not isinstance(suggested_name, str) or not suggested_name.strip():
        raise ValueError("Gemini response is missing suggested_name")
    return {
        "status": "needs_confirm",
        "suggested_name": suggested_name,
        "reasoning": reasoning,
        "task_id": task["id"],
    }


def assign_project(task: dict) -> dict:
    task_people = set(task["people"])
    candidates: list[tuple[dict, int]] = []

    for project in project_service.list_projects():
        overlap_size = len(task_people & set(project["people"]))
        if overlap_size > 0:
            candidates.append((project, overlap_size))

    if not candidates:
        return _llm_propose_new(task)

    largest_overlap = max(overlap_size for _, overlap_size in candidates)
    best_projects = [
        project
        for project, overlap_size in candidates
        if overlap_size == largest_overlap
    ]
    if len(best_projects) > 1:
        return _llm_pick_among(
            task,
            [project["id"] for project in best_projects],
        )

    matched = _confirm_match(task, best_projects[0]["id"])
    return {**matched, "matched_by": "rule"}
