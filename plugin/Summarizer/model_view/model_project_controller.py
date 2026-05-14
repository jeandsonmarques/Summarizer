from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Dict, Optional

from ..dashboard_models import DashboardPage, DashboardProject


def _payload_dict(payload: object) -> Dict[str, object]:
    if isinstance(payload, DashboardProject):
        return dict(payload.to_dict())
    if isinstance(payload, DashboardPage):
        return dict(payload.to_dict())
    if isinstance(payload, Mapping):
        return dict(payload)
    return {}


def normalize_page_payload(payload: object) -> Dict[str, object]:
    raw = _payload_dict(payload)
    normalized = dict(raw)
    normalized.update(DashboardPage.from_dict(raw).to_dict())
    return normalized


def resolve_active_page_id(payload: object, pages: Sequence[object] | None = None) -> str:
    raw = _payload_dict(payload)
    active_page_id = str(raw.get("active_page_id") or "").strip()
    if active_page_id:
        return active_page_id
    for page in list(pages or []):
        page_dict = _payload_dict(page)
        page_id = str(page_dict.get("page_id") or "").strip()
        if page_id:
            return page_id
    return ""


def normalize_project_source_meta(
    source_meta: Optional[Mapping[str, object]],
    *,
    canvas_style_normalizer: Optional[Callable[[Optional[Dict[str, object]]], Dict[str, object]]] = None,
) -> Dict[str, object]:
    payload = dict(source_meta or {})
    if canvas_style_normalizer is not None:
        try:
            payload["canvas_style"] = dict(canvas_style_normalizer(dict(payload.get("canvas_style") or {})))
        except Exception:
            payload["canvas_style"] = dict(payload.get("canvas_style") or {})
    elif "canvas_style" in payload:
        try:
            payload["canvas_style"] = dict(payload.get("canvas_style") or {})
        except Exception:
            payload["canvas_style"] = {}
    return payload


def apply_legacy_single_page_compatibility(
    payload: object,
    *,
    page_title_provider: Callable[[int], str],
) -> Dict[str, object]:
    project_payload = _payload_dict(payload)
    pages = [
        normalize_page_payload(page)
        for page in list(project_payload.get("pages") or [])
        if isinstance(page, (Mapping, DashboardPage))
    ]
    source_meta = dict(project_payload.get("source_meta") or {})
    if bool(source_meta.get("_legacy_single_page")) and len(pages) == 1:
        legacy_page = dict(pages[0])
        project_name = str(project_payload.get("name") or "").strip().lower()
        page_title = str(legacy_page.get("title") or "").strip().lower()
        if not page_title or page_title == project_name:
            legacy_page["title"] = str(page_title_provider(1) or "Page 1").strip() or "Page 1"
        pages = [legacy_page]
        project_payload["pages"] = pages
        project_payload["active_page_id"] = str(legacy_page.get("page_id") or project_payload.get("active_page_id") or "").strip()
    return project_payload


def normalize_project_payload(
    payload: object,
    *,
    page_title_provider: Callable[[int], str],
    canvas_style_normalizer: Optional[Callable[[Optional[Dict[str, object]]], Dict[str, object]]] = None,
) -> Dict[str, object]:
    raw = _payload_dict(payload)
    raw_pages = [
        normalize_page_payload(page)
        for page in list(raw.get("pages") or [])
        if isinstance(page, (Mapping, DashboardPage))
    ]
    if raw_pages:
        project_payload = DashboardProject.from_dict({**raw, "pages": raw_pages}).to_dict()
        pages_payload = [
            {**raw_page, **normalized_page}
            for raw_page, normalized_page in zip(raw_pages, list(project_payload.get("pages") or []))
        ]
    else:
        project_payload = DashboardProject.from_dict(raw).to_dict()
        pages_payload = [
            normalize_page_payload(page)
            for page in list(project_payload.get("pages") or [])
            if isinstance(page, (Mapping, DashboardPage))
        ]
    normalized = dict(raw)
    normalized.update(project_payload)
    if pages_payload:
        normalized["pages"] = pages_payload
    normalized["source_meta"] = normalize_project_source_meta(
        normalized.get("source_meta"),
        canvas_style_normalizer=canvas_style_normalizer,
    )
    normalized = apply_legacy_single_page_compatibility(normalized, page_title_provider=page_title_provider)
    pages = [
        normalize_page_payload(page)
        for page in list(normalized.get("pages") or [])
        if isinstance(page, (Mapping, DashboardPage))
    ]
    if pages:
        normalized["pages"] = pages
        normalized["active_page_id"] = resolve_active_page_id(normalized, pages)
    else:
        normalized["active_page_id"] = resolve_active_page_id(normalized)
    normalized["source_meta"] = normalize_project_source_meta(
        normalized.get("source_meta"),
        canvas_style_normalizer=canvas_style_normalizer,
    )
    return normalized


def validate_dashboard_project(project: object) -> bool:
    if not isinstance(project, DashboardProject):
        return False
    if not isinstance(project.source_meta, dict):
        return False
    if not isinstance(project.pages, list):
        return False
    return all(isinstance(page, DashboardPage) for page in list(project.pages or []))


def normalize_loaded_project(
    project: DashboardProject,
    *,
    page_title_provider: Callable[[int], str],
    canvas_style_normalizer: Optional[Callable[[Optional[Dict[str, object]]], Dict[str, object]]] = None,
) -> DashboardProject:
    if not validate_dashboard_project(project):
        return project
    payload = normalize_project_payload(
        project.to_dict(),
        page_title_provider=page_title_provider,
        canvas_style_normalizer=canvas_style_normalizer,
    )
    return DashboardProject.from_dict(payload)


def project_snapshot_payload(
    project: Optional[DashboardProject],
    *,
    page_title_provider: Callable[[int], str],
) -> Optional[Dict[str, object]]:
    if project is None or not validate_dashboard_project(project):
        return None
    pages = [page.normalized() for page in list(project.pages or [])]
    if not pages:
        pages = [DashboardPage(title=str(page_title_provider(1) or "Page 1")).normalized()]
    active_page_id = resolve_active_page_id({"active_page_id": project.active_page_id}, pages) or pages[0].page_id
    active_page = pages[0]
    for page in pages:
        if str(page.page_id or "").strip() == str(active_page_id or "").strip():
            active_page = page
            break
    payload = {
        "version": int(project.version or 2),
        "project_id": str(project.project_id or ""),
        "name": str(project.name or ""),
        "created_at": str(project.created_at or ""),
        "updated_at": str(project.updated_at or ""),
        "edit_mode": bool(project.edit_mode),
        "source_meta": dict(project.source_meta or {}),
        "active_page_id": str(active_page_id or ""),
        "pages": [page.to_dict() for page in pages],
        "items": [item.to_dict() for item in list(active_page.items or [])],
        "visual_links": [link.to_dict() for link in list(active_page.visual_links or [])],
        "chart_relations": [relation.to_dict() for relation in list(active_page.chart_relations or [])],
    }
    try:
        return json.loads(json.dumps(payload, ensure_ascii=False))
    except Exception:
        return payload


def snapshot_state(project_snapshot: Optional[Dict[str, object]], path: object, dirty: object) -> Dict[str, object]:
    return {
        "project": dict(project_snapshot or {}),
        "path": str(path or ""),
        "dirty": bool(dirty),
    }


def snapshot_signature(snapshot: Optional[Dict[str, object]]) -> str:
    payload = dict(snapshot or {})
    serial = {
        "project": payload.get("project"),
        "path": str(payload.get("path") or ""),
    }
    try:
        return json.dumps(serial, sort_keys=True, ensure_ascii=False)
    except Exception:
        return str(serial)


__all__ = [
    "apply_legacy_single_page_compatibility",
    "normalize_loaded_project",
    "normalize_page_payload",
    "normalize_project_payload",
    "normalize_project_source_meta",
    "project_snapshot_payload",
    "resolve_active_page_id",
    "validate_dashboard_project",
    "snapshot_signature",
    "snapshot_state",
]
