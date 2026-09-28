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

# 台词适度扩充后（D93）整本分析的输出明显变长：一本 36 页的书约需 1 万 token
VISION_ANALYSIS_TIMEOUT = 300.0
VISION_DRAFT_TIMEOUT = 60.0
ANALYSIS_MAX_TOKENS = 16384
DRAFT_MAX_TOKENS = 8192


def script_rules(language: str | None) -> str:
    """朗读稿的写法（D93）：原文逐字保留，结合画面适度扩充。整本分析和单元重写共用。"""
    lang_desc = "英文" if language == "en" else "中文"
    return f"""lines 是这一页的朗读稿，按朗读顺序排列，每行标注说话人：
   - 画面上印的故事文字要完整保留、逐字不改，按原文分行；
   - 在此基础上结合画面补充 2–3 句简短的内容（每句不超过 20 字，英文不超过 12 个词），
     这些行加 "added": true：可以是旁白对画面、动作、心情的描写，拟声词，
     或角色贴合情节的简短对白和语气词；
     补充的行插在原文前后合适的位置，不要重复原文，不要编造与画面和故事不符的情节；
   - 画面上没有故事文字的页面，写 1–2 句简短旁白（"added": true）；
   - 封面只读书名，不补充；版权页、空白页等不讲故事的页面 lines 为 []；
   - 补充内容与原文同一语言（{lang_desc}），用词适合 3–6 岁孩子听。"""


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
        {{"character": "角色名", "text": "原文"}},
        {{"character": "角色名", "text": "补充的一句", "added": true}}
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
   {script_rules(language)}
3. spread_suggestions 必须覆盖以下开页：{spreads_str or "无"}。
   如果左右两页是同一个完整大场景（左右画面连贯是一张图），is_same_scene 为 true，否则为 false。
4. 只输出合法的 JSON 对象，不要添加任何 markdown 代码块标记或额外说明。"""


def _build_chat_payload(
    model: str,
    content: list[dict[str, Any]],
    provider: str,
    max_tokens: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    # 新一代多模态模型显式关闭思考模式，避免消耗大量 reasoning tokens 导致截断和超时
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
    max_tokens: int,
) -> dict[str, Any]:
    url = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = _build_chat_payload(config.model, content, config.provider, max_tokens)

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
                "大模型输出达到 Token 上限（finish_reason=length），内容被截断。"
                "请增大 max_tokens 或减少单次分析页数。"
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
            client,
            config,
            api_key,
            content,
            timeout=VISION_ANALYSIS_TIMEOUT,
            max_tokens=ANALYSIS_MAX_TOKENS,
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

请仔细观察附带的画面（{pages_str}），写出朗读稿，并给出画面微动作循环描述。
按以下严格 JSON 格式返回：
{{
  "lines": [
    {{"character": "角色名（必须从已有角色列表中选择，无法确定填'旁白'）", "text": "原文"}},
    {{"character": "角色名", "text": "补充的一句", "added": true}}
  ],
  "motion_prompt": "适合该画面的5秒微动作循环描述（画面中主角轻柔微动作，最后回到初始姿态）"
}}
要求：
1. 多页时把各页的朗读稿按页码顺序连在一起。
2. {script_rules(language)}
3. 只返回合法的 JSON 对象。"""

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for idx, path in zip(page_indexes, page_paths, strict=False):
        b64 = encode_page_image(path)
        content.append({"type": "text", "text": f"=== 第 {idx} 页 (page_index={idx}) ==="})
        content.append({"type": "image_url", "image_url": {"url": b64}})

    with providers.http_client() as client:
        result = _execute_vision_completion(
            client,
            config,
            api_key,
            content,
            timeout=VISION_DRAFT_TIMEOUT,
            max_tokens=DRAFT_MAX_TOKENS,
        )

    if "lines" not in result:
        result["lines"] = []
    if "motion_prompt" not in result:
        result["motion_prompt"] = None

    return result


COVER_MOTION_MAX_TOKENS = 512


def describe_cover_motion(
    cover_path: Path,
    story: str | None,
    character_names: list[str],
    config: CapabilityConfig,
    api_key: str,
) -> str:
    """看封面写封面动画的动作描述（D96）：点名画面里的角色，各写一个轻柔但看得见的小动作。"""
    names = "、".join(character_names) or "（未知）"
    prompt = f"""你是儿童绘本的动画导演。附图是一本绘本的封面，要把它做成"像魔法报纸上会动的照片"：
画还是这张画，只有里面的角色做轻柔但清楚看得见的小动作，然后回到原样，循环播放。
故事梗概：{story or "（无）"}
已知角色：{names}

请写一句动作描述：
1. 点名画面里的 1–3 个角色（用已知角色名；不知道名字就用"兔子""小老鼠"这样的称呼）；
2. 每个角色一个具体的小动作，如眨眨眼、耳朵抖一抖、轻轻点头、尾巴摆动、
   胡须颤动、手指轻挠、衣角飘动；
3. 角色不走动、不离开原位，背景、书名和其他文字都不动；
4. 50 字以内，中文。
按 JSON 返回：{{"motion": "……"}}"""
    content: list[dict[str, Any]] = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": encode_page_image(cover_path)}},
    ]
    with providers.http_client() as client:
        result = _execute_vision_completion(
            client,
            config,
            api_key,
            content,
            timeout=VISION_DRAFT_TIMEOUT,
            max_tokens=COVER_MOTION_MAX_TOKENS,
        )
    motion = str(result.get("motion") or "").strip()
    if not motion:
        raise ProviderError("大模型没有写出封面的动作描述")
    return motion
