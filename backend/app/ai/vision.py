import base64
import io
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

from app.ai import providers
from app.ai.providers import ProviderError
from app.ai.providers.common import describe_error
from app.ai.settings import CapabilityConfig

VISION_ANALYSIS_TIMEOUT = 180.0
VISION_DRAFT_TIMEOUT = 60.0


def encode_page_image(path: Path, long_edge: int = 800, quality: int = 75) -> str:
    """压缩并转为 base64 data URL。长边缩至 800px 以加快传输和降低多模态消耗。"""
    im = Image.open(path)
    if im.mode in ("RGBA", "P"):
        im = im.convert("RGB")
    w, h = im.size
    scale = long_edge / max(w, h)
    if scale < 1.0:
        im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def parse_json_from_llm(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    # 1. 尝试直接解析（strict=False 允许字符串内存在未转义的换行与控制字符）
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass

    # 2. 尝试提取 ```json ... ``` 或 ``` ... ``` 代码块
    code_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if code_match:
        try:
            return json.loads(code_match.group(1).strip(), strict=False)
        except json.JSONDecodeError:
            pass

    # 3. 寻找最外层的 { ... } 并容错修复末尾多余逗号
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            fixed = re.sub(r",\s*([\}\]])", r"\1", candidate)
            try:
                return json.loads(fixed, strict=False)
            except json.JSONDecodeError:
                pass

    raise ProviderError(f"大模型未返回合法 JSON 内容：{raw_text[:200]}") from None


def build_analysis_prompt(
    language: str | None, spreads_to_evaluate: list[list[int]], total_pages: int
) -> str:
    lang_desc = "英文" if language == "en" else "中文"
    spreads_str = ", ".join(f"[{s[0]}, {s[1]}]" for s in spreads_to_evaluate)
    return f"""你是一位专业的儿童绘本编辑和配音编导。
这是一本完整的儿童绘本（共 {total_pages} 页，索引 0 到 {total_pages - 1}），
绘本语言为：{lang_desc}。
请通读全部页面，按要求输出严格的 JSON 格式的故事分析：
{{
  "story": "整本故事的内容梗概（200-400字，生动、完整）",
  "characters": [
    {{
      "name": "角色名（如：旁白、小熊、小兔）",
      "is_narrator": false,
      "voice_prompt": "适合该角色的音色设计描述（50-100字，描述性别、年龄感、性格、音质、语调语速）"
    }}
  ],
  "pages": [
    {{
      "page_index": 0,
      "lines": [
        {{"character": "角色名", "text": "原文台词"}}
      ],
      "motion_prompt": "适合该页的5秒微动作循环描述（画面中主角轻柔微动作，最后回到初始姿态）"
    }}
  ],
  "spread_suggestions": [
    {{
      "pages": [1, 2],
      "is_same_scene": false,
      "reason": "简述原因"
    }}
  ]
}}
注意要求：
1. 必须包含一个 is_narrator: true 的旁白角色。
2. pages 必须包含从 0 到 {total_pages - 1} 的所有页面。
   如果画面无文字，lines 为 []。文字必须与画面完全一致，保持原文语言。
3. spread_suggestions 必须覆盖以下开页：{spreads_str or "无"}。
   如果左右两页是同一个完整大场景（左右画面连贯是一张图），is_same_scene 为 true，否则为 false。
4. 只输出合法的 JSON 对象，不要添加任何 markdown 代码块标记或额外说明。"""


def _build_chat_payload(
    model: str,
    content: list[dict[str, Any]],
    provider: str,
    max_tokens: int = 8192,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    # 针对百炼与火山方舟新一代多模态模型，显式关闭思考模式，避免消耗大量 reasoning tokens 导致截断和超时
    if provider == "dashscope":
        payload["enable_thinking"] = False
    elif provider == "volcengine":
        payload["thinking"] = {"type": "disabled"}
    return payload


def _execute_vision_completion(
    client: Any,
    config: CapabilityConfig,
    api_key: str,
    content: list[dict[str, Any]],
    timeout: float,
) -> dict[str, Any]:
    url = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = _build_chat_payload(config.model, content, config.provider)

    res = client.post(url, headers=headers, json=payload, timeout=timeout)
    # 如果服务商返回 400 且请求中携带了思考参数，自动剔除思考参数后重试一次
    if res.status_code == 400 and ("thinking" in payload or "enable_thinking" in payload):
        fallback_payload = dict(payload)
        fallback_payload.pop("thinking", None)
        fallback_payload.pop("enable_thinking", None)
        res = client.post(url, headers=headers, json=fallback_payload, timeout=timeout)

    if res.status_code != 200:
        raise ProviderError(describe_error(res))

    try:
        data = res.json()
        choice = data["choices"][0]
        finish_reason = choice.get("finish_reason")
        if finish_reason == "length":
            raise ProviderError(
                "大模型输出达到 Token 上限（finish_reason=length），内容被截断。请增大 max_tokens 或减少单次分析页数。"
            )
        raw_text = choice["message"]["content"]
    except KeyError as e:
        raise ProviderError(f"大模型响应格式无法解析：{describe_error(res)}") from e
    except IndexError as e:
        raise ProviderError(f"大模型未返回任何候选结果：{describe_error(res)}") from e

    return parse_json_from_llm(raw_text)


def analyze_book_story(
    page_paths: list[Path],
    language: str | None,
    spreads_to_evaluate: list[list[int]],
    config: CapabilityConfig,
    api_key: str,
) -> dict[str, Any]:
    """调用视觉模型通读全书，返回故事梗概、角色、逐页台词和开页合并建议。"""
    prompt = build_analysis_prompt(language, spreads_to_evaluate, len(page_paths))
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

    for idx, path in enumerate(page_paths):
        b64 = encode_page_image(path)
        content.append({"type": "text", "text": f"=== 第 {idx} 页 (page_index={idx}) ==="})
        content.append({"type": "image_url", "image_url": {"url": b64}})

    with providers.http_client() as client:
        result = _execute_vision_completion(
            client, config, api_key, content, timeout=VISION_ANALYSIS_TIMEOUT
        )

    if "story" not in result or "characters" not in result or "pages" not in result:
        raise ProviderError("大模型返回的 JSON 缺少 story、characters 或 pages 字段")

    return result


def draft_unit_content(
    page_paths: list[Path],
    page_indexes: list[int],
    story: str | None,
    characters: list[dict[str, Any]],
    language: str | None,
    config: CapabilityConfig,
    api_key: str,
) -> dict[str, Any]:
    """单独为某一个生成单元（单页或对开两页）重写台词草稿和动作描述。"""
    lang_desc = "英文" if language == "en" else "中文"
    char_list_str = "、".join(c["name"] for c in characters) or "旁白"
    pages_str = " 和 ".join(f"第 {idx} 页" for idx in page_indexes)

    prompt = f"""你是一位专业的儿童绘本编辑和配音编导。
绘本故事梗概：{story or "（无）"}
已有角色列表：{char_list_str}
绘本语言：{lang_desc}

请仔细观察附带的画面（{pages_str}），识别画面中的文字台词，并给出画面微动作循环描述。
按以下严格 JSON 格式返回：
{{
  "lines": [
    {{"character": "角色名（必须从已有角色列表中选择，无法确定填'旁白'）", "text": "原文台词"}}
  ],
  "motion_prompt": "适合该画面的5秒微动作循环描述（画面中主角轻柔微动作，最后回到初始姿态）"
}}
如果画面没有文字，lines 请返回 []。只返回合法的 JSON 对象。"""

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for idx, path in zip(page_indexes, page_paths, strict=False):
        b64 = encode_page_image(path)
        content.append({"type": "text", "text": f"=== 第 {idx} 页 (page_index={idx}) ==="})
        content.append({"type": "image_url", "image_url": {"url": b64}})

    with providers.http_client() as client:
        result = _execute_vision_completion(
            client, config, api_key, content, timeout=VISION_DRAFT_TIMEOUT
        )

    if "lines" not in result:
        result["lines"] = []
    if "motion_prompt" not in result:
        result["motion_prompt"] = None

    return result
