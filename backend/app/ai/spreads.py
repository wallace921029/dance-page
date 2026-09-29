from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.book_schemas import AiUnitOut, LineItem, SpreadOut
from app.ai.settings import CapabilityConfig
from app.ai.speech import audio_outdated
from app.ai.video import unit_source_hash
from app.books.service import video_by_cover
from app.books.storage import delete_ai_unit_files
from app.config import Settings
from app.models import AiUnit, Book


@dataclass
class SpreadLayoutItem:
    index: int
    left_page_index: int | None
    right_page_index: int | None


def calculate_spread_layout(
    page_count: int, orientation: str | None, spread_start_page: int
) -> list[SpreadLayoutItem]:
    """计算绘本的所有开页结构（与前端 toSpreads 逻辑对齐）。"""
    if orientation == "landscape":
        return [
            SpreadLayoutItem(index=i, left_page_index=i, right_page_index=None)
            for i in range(page_count)
        ]

    # 竖版书：封面单独在右边（左侧空）
    layout: list[SpreadLayoutItem] = [
        SpreadLayoutItem(index=0, left_page_index=None, right_page_index=0)
    ]
    if page_count <= 1:
        return layout

    s_idx = 1
    if spread_start_page == 3:
        # 第 2 页（索引 1）单独在右边，左侧空白
        layout.append(SpreadLayoutItem(index=s_idx, left_page_index=None, right_page_index=1))
        s_idx += 1
        cur = 2
    else:
        cur = 1

    while cur < page_count:
        left = cur
        right = cur + 1 if cur + 1 < page_count else None
        layout.append(SpreadLayoutItem(index=s_idx, left_page_index=left, right_page_index=right))
        cur += 2
        s_idx += 1

    return layout


def unit_audio_url(unit: AiUnit) -> str | None:
    if unit.audio_source_hash is None:
        return None
    return f"/api/admin/ai/units/{unit.id}/audio?v={unit.audio_version}"


def unit_video_url(unit: AiUnit) -> str | None:
    if unit.video_source_hash is None:
        return None
    return f"/api/admin/ai/units/{unit.id}/video?v={unit.video_version}"


def video_outdated(unit: AiUnit, video: CapabilityConfig | None) -> bool:
    """动作描述改过或换了视频模型；按单元生成时的时长和清晰度比较，临时换清晰度（D79）不算。"""
    if unit.video_source_hash is None or video is None:
        return False
    current = unit_source_hash(
        unit.motion_prompt,
        video,
        unit.video_duration_s or 0,
        unit.video_resolution or "",
    )
    return current != unit.video_source_hash


def unit_to_out(
    unit: AiUnit, current_audio_hash: str | None = None, video: CapabilityConfig | None = None
) -> AiUnitOut:
    """current_audio_hash：按当前台词和音色算出的指纹，用来判断朗读是否需要重新生成；
    video：当前的动画视频设置，用来判断动画是否需要重新生成。"""
    return AiUnitOut(
        id=unit.id,
        book_id=unit.book_id,
        first_page_index=unit.first_page_index,
        page_count=unit.page_count,
        lines=[LineItem(**line) for line in (unit.lines or [])],
        motion_prompt=unit.motion_prompt,
        audio_enabled=unit.audio_enabled,
        video_enabled=unit.video_enabled,
        audio_status=unit.audio_status,
        video_status=unit.video_status,
        audio_error=unit.audio_error,
        video_error=unit.video_error,
        audio_source_hash=unit.audio_source_hash,
        video_source_hash=unit.video_source_hash,
        audio_duration_ms=unit.audio_duration_ms,
        video_duration_s=unit.video_duration_s,
        video_resolution=unit.video_resolution,
        audio_version=unit.audio_version,
        video_version=unit.video_version,
        created_at=unit.created_at,
        updated_at=unit.updated_at,
        audio_url=unit_audio_url(unit),
        audio_outdated=audio_outdated(unit, current_audio_hash),
        video_url=unit_video_url(unit),
        video_outdated=video_outdated(unit, video),
        video_by_cover=video_by_cover(unit.book, unit),
    )


def build_spreads_out(
    book: Book,
    units: Sequence[AiUnit],
    audio_hashes: Mapping[str, str | None] | None = None,
    video: CapabilityConfig | None = None,
) -> list[SpreadOut]:
    """把绘本和它的 AiUnits 组装为前端所需的开页列表。audio_hashes：单元 ID → 当前朗读指纹；
    video：当前的动画视频设置。"""
    hashes = audio_hashes or {}

    def out(unit: AiUnit) -> AiUnitOut:
        return unit_to_out(unit, hashes.get(unit.id), video)

    def spread(item: SpreadLayoutItem, mode: str, spread_units: list[AiUnitOut]) -> SpreadOut:
        return SpreadOut(
            index=item.index,
            left_page_index=item.left_page_index,
            right_page_index=item.right_page_index,
            mode=mode,  # type: ignore[arg-type]
            audio_enabled=all(u.audio_enabled for u in spread_units),
            video_enabled=all(u.video_enabled for u in spread_units),
            units=spread_units,
        )

    layout = calculate_spread_layout(book.page_count, book.orientation, book.spread_start_page)
    unit_map: dict[int, AiUnit] = {u.first_page_index: u for u in units}

    spreads: list[SpreadOut] = []
    for item in layout:
        left_p = item.left_page_index
        right_p = item.right_page_index

        if left_p is None or right_p is None:
            # 单页开页
            single_p = right_p if left_p is None else left_p
            unit = unit_map.get(single_p)
            spreads.append(spread(item, "single", [out(unit)] if unit is not None else []))
        else:
            # 双页对开
            left_unit = unit_map.get(left_p)
            if left_unit is not None and left_unit.page_count == 2:
                spreads.append(spread(item, "merged", [out(left_unit)]))
            else:
                right_unit = unit_map.get(right_p)
                spread_units = [out(u) for u in (left_unit, right_unit) if u is not None]
                spreads.append(spread(item, "separate", spread_units))

    return spreads


def change_spread_mode(
    db: Session, settings: Settings, book: Book, first_page: int, target_mode: str
) -> SpreadOut:
    """切换指定开页的分别 / 合并模式。"""
    layout = calculate_spread_layout(book.page_count, book.orientation, book.spread_start_page)
    target_spread = next((s for s in layout if s.left_page_index == first_page), None)
    if target_spread is None or target_spread.right_page_index is None:
        raise ValueError("该开页为单页，无法更改分别/合并模式")

    second_page = target_spread.right_page_index

    if target_mode == "merged":
        u_left = db.scalar(
            select(AiUnit).where(AiUnit.book_id == book.id, AiUnit.first_page_index == first_page)
        )
        u_right = db.scalar(
            select(AiUnit).where(AiUnit.book_id == book.id, AiUnit.first_page_index == second_page)
        )

        if u_left and u_left.page_count == 2:
            # 已经是合并模式
            return next(
                s for s in build_spreads_out(book, book.ai_units) if s.left_page_index == first_page
            )

        lines_l = u_left.lines if u_left else []
        lines_r = u_right.lines if u_right else []
        combined_lines = (
            lines_r + lines_l if book.read_order == "right_first" else lines_l + lines_r
        )

        prompts = [
            p
            for p in (
                u_left.motion_prompt if u_left else None,
                u_right.motion_prompt if u_right else None,
            )
            if p
        ]
        combined_prompt = "；".join(prompts) if prompts else None

        existing = [u for u in (u_left, u_right) if u is not None]
        audio_enabled = all(u.audio_enabled for u in existing)
        video_enabled = all(u.video_enabled for u in existing)

        if u_left:
            delete_ai_unit_files(settings, book.id, u_left.id)
            u_left.audio_enabled = audio_enabled
            u_left.video_enabled = video_enabled
            u_left.page_count = 2
            u_left.lines = combined_lines
            u_left.motion_prompt = combined_prompt
            u_left.audio_status = "none"
            u_left.video_status = "none"
            u_left.audio_error = None
            u_left.video_error = None
            u_left.audio_source_hash = None
            u_left.video_source_hash = None
        else:
            u_left = AiUnit(
                book_id=book.id,
                first_page_index=first_page,
                page_count=2,
                lines=combined_lines,
                motion_prompt=combined_prompt,
                audio_enabled=audio_enabled,
                video_enabled=video_enabled,
            )
            db.add(u_left)

        if u_right:
            delete_ai_unit_files(settings, book.id, u_right.id)
            db.delete(u_right)

    elif target_mode == "separate":
        u_merged = db.scalar(
            select(AiUnit).where(AiUnit.book_id == book.id, AiUnit.first_page_index == first_page)
        )
        if u_merged and u_merged.page_count == 2:
            delete_ai_unit_files(settings, book.id, u_merged.id)
            u_merged.page_count = 1
            u_merged.audio_status = "none"
            u_merged.video_status = "none"
            u_merged.audio_error = None
            u_merged.video_error = None
            u_merged.audio_source_hash = None
            u_merged.video_source_hash = None

            u_right = db.scalar(
                select(AiUnit).where(
                    AiUnit.book_id == book.id, AiUnit.first_page_index == second_page
                )
            )
            if not u_right:
                # 拆开后右页沿用原来开页的开关
                u_right = AiUnit(
                    book_id=book.id,
                    first_page_index=second_page,
                    page_count=1,
                    lines=[],
                    motion_prompt=None,
                    audio_enabled=u_merged.audio_enabled,
                    video_enabled=u_merged.video_enabled,
                )
                db.add(u_right)
        else:
            if not u_merged:
                u_left = AiUnit(
                    book_id=book.id,
                    first_page_index=first_page,
                    page_count=1,
                    lines=[],
                    motion_prompt=None,
                )
                db.add(u_left)
            u_right = db.scalar(
                select(AiUnit).where(
                    AiUnit.book_id == book.id, AiUnit.first_page_index == second_page
                )
            )
            if not u_right:
                u_right = AiUnit(
                    book_id=book.id,
                    first_page_index=second_page,
                    page_count=1,
                    lines=[],
                    motion_prompt=None,
                )
                db.add(u_right)
    else:
        raise ValueError(f"未知的模式：{target_mode}")

    db.commit()
    # 重新加载 units
    db.refresh(book)
    return next(
        s for s in build_spreads_out(book, book.ai_units) if s.left_page_index == first_page
    )


def find_spread(book: Book, first_page: int) -> SpreadLayoutItem | None:
    """按开页的第一页（左页，没有左页时为右页）找开页。"""
    layout = calculate_spread_layout(book.page_count, book.orientation, book.spread_start_page)
    return next(
        (
            s
            for s in layout
            if (s.left_page_index if s.left_page_index is not None else s.right_page_index)
            == first_page
        ),
        None,
    )


def units_in_spread(book: Book, spread: SpreadLayoutItem) -> list[AiUnit]:
    pages = {spread.left_page_index, spread.right_page_index} - {None}
    return sorted(
        (u for u in book.ai_units if u.first_page_index in pages),
        key=lambda u: u.first_page_index,
    )
