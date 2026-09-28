import json
from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import providers


@pytest.fixture
def fake_vision_provider(monkeypatch) -> Callable[[dict], list[httpx.Request]]:
    def install(response_dict: dict) -> list[httpx.Request]:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": json.dumps(response_dict, ensure_ascii=False)}}
                    ]
                },
            )

        monkeypatch.setattr(
            providers, "http_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
        )
        return requests

    return install


def test_get_book_ai_initial_state(admin: TestClient, ready_book: dict):
    book_id = ready_book["id"]
    res = admin.get(f"/api/admin/books/{book_id}/ai")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["story"] is None
    assert data["read_order"] == "left_first"
    assert data["voice_ready_at"] is None
    assert data["dance_ready_at"] is None
    assert data["characters"] == []
    # ready_book has 6 pages, spread_start_page=3:
    # Spread 0: [None, 0] (single)
    # Spread 1: [None, 1] (single)
    # Spread 2: [2, 3] (separate)
    # Spread 3: [4, 5] (separate)
    assert len(data["spreads"]) == 4
    assert data["spreads"][0]["mode"] == "single"
    assert data["spreads"][1]["mode"] == "single"
    assert data["spreads"][2]["mode"] == "separate"
    assert data["spreads"][3]["mode"] == "separate"
    assert data["running_jobs"] == []


def test_patch_book_ai(admin: TestClient, ready_book: dict):
    book_id = ready_book["id"]
    res = admin.patch(
        f"/api/admin/books/{book_id}/ai",
        json={"story": "这是一个关于怪兽的故事", "read_order": "right_first"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["story"] == "这是一个关于怪兽的故事"
    assert data["read_order"] == "right_first"


def test_character_crud(admin: TestClient, ready_book: dict):
    book_id = ready_book["id"]
    # 1. Create character
    res = admin.post(
        f"/api/admin/books/{book_id}/ai/characters",
        json={"name": "波西", "voice_prompt": "5岁小女孩", "is_narrator": False},
    )
    assert res.status_code == 201, res.text
    char = res.json()
    assert char["name"] == "波西"
    char_id = char["id"]

    # 2. Update character
    res = admin.patch(
        f"/api/admin/books/{book_id}/ai/characters/{char_id}",
        json={"name": "波西小姐", "voice_prompt": "可爱小女孩"},
    )
    assert res.status_code == 200, res.text
    updated = res.json()
    assert updated["name"] == "波西小姐"

    # 3. List in book ai
    res = admin.get(f"/api/admin/books/{book_id}/ai")
    chars = res.json()["characters"]
    assert any(c["id"] == char_id and c["name"] == "波西小姐" for c in chars)

    # 4. Delete character
    res = admin.delete(f"/api/admin/books/{book_id}/ai/characters/{char_id}")
    assert res.status_code == 200, res.text

    res = admin.get(f"/api/admin/books/{book_id}/ai")
    chars = res.json()["characters"]
    assert not any(c["id"] == char_id for c in chars)


def test_ai_analyze_book_flow(
    admin: TestClient, app, worker, ready_book: dict, fake_vision_provider
):
    book_id = ready_book["id"]
    app.state.settings.dashscope_api_key = "sk-mock-key"

    fake_response = {
        "story": "波西和皮普在房间里做松饼，忽然大怪兽敲门了。",
        "characters": [
            {"name": "旁白", "is_narrator": True, "voice_prompt": "温柔女声"},
            {"name": "波西", "is_narrator": False, "voice_prompt": "活泼小兔"},
            {"name": "大怪兽", "is_narrator": False, "voice_prompt": "低沉憨厚"},
        ],
        "pages": [
            {"page_index": 0, "lines": [], "motion_prompt": "封面光影流转"},
            {
                "page_index": 1,
                "lines": [{"character": "旁白", "text": "有一天"}],
                "motion_prompt": "翻开第一页",
            },
            {
                "page_index": 2,
                "lines": [{"character": "波西", "text": "真好吃！"}],
                "motion_prompt": "波西吃松饼",
            },
            {
                "page_index": 3,
                "lines": [{"character": "大怪兽", "text": "嗷呜！"}],
                "motion_prompt": "怪兽出现",
            },
            {"page_index": 4, "lines": [], "motion_prompt": "静止画面"},
            {
                "page_index": 5,
                "lines": [{"character": "旁白", "text": "全剧终"}],
                "motion_prompt": "闭幕",
            },
        ],
        "spread_suggestions": [
            {"pages": [2, 3], "is_same_scene": True, "reason": "同一间厨房场景"},
            {"pages": [4, 5], "is_same_scene": False, "reason": "不同场景"},
        ],
    }
    requests = fake_vision_provider(fake_response)

    # Trigger analysis
    res = admin.post(f"/api/admin/books/{book_id}/ai/analyze")
    assert res.status_code == 202, res.text
    job_id = res.json()["job_id"]

    # Verify duplicate trigger returns existing job
    res_dup = admin.post(f"/api/admin/books/{book_id}/ai/analyze")
    assert res_dup.status_code == 202
    assert res_dup.json()["job_id"] == job_id

    # Run worker
    assert worker.run_once() is True
    assert len(requests) == 1

    # Verify state after analysis
    res = admin.get(f"/api/admin/books/{book_id}/ai")
    assert res.status_code == 200
    data = res.json()
    assert data["story"] == fake_response["story"]
    assert len(data["characters"]) == 3

    # Check spreads:
    # Spread 2 (pages 2, 3) should be merged!
    spread_2_3 = next(s for s in data["spreads"] if s["left_page_index"] == 2)
    assert spread_2_3["mode"] == "merged"
    assert len(spread_2_3["units"]) == 1
    merged_unit = spread_2_3["units"][0]
    assert merged_unit["page_count"] == 2
    assert len(merged_unit["lines"]) == 2
    assert merged_unit["lines"][0]["text"] == "真好吃！"
    assert merged_unit["lines"][1]["text"] == "嗷呜！"

    # Spread 3 (pages 4, 5) should be separate!
    spread_4_5 = next(s for s in data["spreads"] if s["left_page_index"] == 4)
    assert spread_4_5["mode"] == "separate"
    assert len(spread_4_5["units"]) == 2


def test_spread_mode_toggle_and_unit_edit(
    admin: TestClient, app, worker, ready_book: dict, fake_vision_provider
):
    book_id = ready_book["id"]
    app.state.settings.dashscope_api_key = "sk-mock-key"

    fake_response = {
        "story": "小故事",
        "characters": [{"name": "旁白", "is_narrator": True, "voice_prompt": "温和"}],
        "pages": [
            {
                "page_index": i,
                "lines": [{"character": "旁白", "text": f"第{i}页台词"}],
                "motion_prompt": f"第{i}页动作",
            }
            for i in range(6)
        ],
        "spread_suggestions": [
            {"pages": [2, 3], "is_same_scene": True, "reason": "同场景"},
        ],
    }
    fake_vision_provider(fake_response)
    admin.post(f"/api/admin/books/{book_id}/ai/analyze")
    assert worker.run_once() is True

    # Spread [2, 3] is initially merged
    res = admin.get(f"/api/admin/books/{book_id}/ai")
    spread_2_3 = next(s for s in res.json()["spreads"] if s["left_page_index"] == 2)
    assert spread_2_3["mode"] == "merged"

    # Toggle to separate
    res = admin.put(f"/api/admin/books/{book_id}/ai/spreads/2", json={"mode": "separate"})
    assert res.status_code == 200, res.text
    spread_sep = res.json()
    assert spread_sep["mode"] == "separate"
    assert len(spread_sep["units"]) == 2
    left_unit = spread_sep["units"][0]
    assert left_unit["first_page_index"] == 2
    assert left_unit["page_count"] == 1

    # Edit left unit
    res = admin.patch(
        f"/api/admin/ai/units/{left_unit['id']}",
        json={
            "lines": [{"character_id": None, "text": "修改后的台词"}],
            "motion_prompt": "修改后的动作",
        },
    )
    assert res.status_code == 200, res.text
    edited_unit = res.json()
    assert edited_unit["lines"][0]["text"] == "修改后的台词"
    assert edited_unit["motion_prompt"] == "修改后的动作"

    # Toggle back to merged
    res = admin.put(f"/api/admin/books/{book_id}/ai/spreads/2", json={"mode": "merged"})
    assert res.status_code == 200, res.text
    spread_merged = res.json()
    assert spread_merged["mode"] == "merged"
    assert len(spread_merged["units"]) == 1
    assert spread_merged["units"][0]["page_count"] == 2
    assert spread_merged["units"][0]["lines"][0]["text"] == "修改后的台词"


def test_ai_draft_unit(admin: TestClient, app, worker, ready_book: dict, fake_vision_provider):
    book_id = ready_book["id"]
    app.state.settings.dashscope_api_key = "sk-mock-key"

    fake_response = {
        "story": "小故事",
        "characters": [{"name": "旁白", "is_narrator": True, "voice_prompt": "温和"}],
        "pages": [{"page_index": i, "lines": [], "motion_prompt": None} for i in range(6)],
        "spread_suggestions": [],
    }
    fake_vision_provider(fake_response)
    admin.post(f"/api/admin/books/{book_id}/ai/analyze")
    assert worker.run_once() is True

    res = admin.get(f"/api/admin/books/{book_id}/ai")
    unit = res.json()["spreads"][0]["units"][0]
    unit_id = unit["id"]
    assert unit["lines"] == []

    # Mock drafting response
    draft_response = {
        "lines": [{"character": "旁白", "text": "新起点的旁白"}],
        "motion_prompt": "微风吹拂",
    }
    fake_vision_provider(draft_response)

    res = admin.post(f"/api/admin/ai/units/{unit_id}/draft")
    assert res.status_code == 202, res.text
    assert worker.run_once() is True

    # Check updated unit
    res = admin.get(f"/api/admin/books/{book_id}/ai")
    updated_unit = res.json()["spreads"][0]["units"][0]
    assert len(updated_unit["lines"]) == 1
    assert updated_unit["lines"][0]["text"] == "新起点的旁白"
    assert updated_unit["motion_prompt"] == "微风吹拂"


def test_parse_json_from_llm():
    from app.ai.vision import parse_json_from_llm

    # 1. Direct JSON
    assert parse_json_from_llm('{"a": 1}') == {"a": 1}

    # 2. Markdown code fence with conversational prefix
    text2 = '这是分析结果：\n```json\n{"story": "hello", "characters": []}\n```\n希望对你有用'
    assert parse_json_from_llm(text2) == {"story": "hello", "characters": []}

    # 3. Trailing commas in objects and arrays
    text3 = '{\n  "story": "test",\n  "list": [1, 2, ],\n}'
    assert parse_json_from_llm(text3) == {"story": "test", "list": [1, 2]}

    # 4. Unescaped control characters in string (multiline)
    text4 = '{"story": "line 1\nline 2\ttab"}'
    assert parse_json_from_llm(text4) == {"story": "line 1\nline 2\ttab"}

