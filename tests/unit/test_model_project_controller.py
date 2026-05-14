from plugin.Summarizer.dashboard_models import DashboardPage, DashboardProject
from plugin.Summarizer.model_view.model_canvas_style_dialog import normalize_canvas_style
from plugin.Summarizer.model_view.model_project_controller import (
    normalize_loaded_project,
    normalize_page_payload,
    normalize_project_payload,
    project_snapshot_payload,
    resolve_active_page_id,
    snapshot_signature,
    snapshot_state,
    validate_dashboard_project,
)


def _page(page_id: str, title: str, **extra):
    payload = DashboardPage(page_id=page_id, title=title).to_dict()
    payload.update(extra)
    return payload


def test_single_page_project_snapshot_preserves_active_page_and_source_meta():
    project = DashboardProject(
        name="Painel",
        pages=[DashboardPage(page_id="page-1", title="Resumo").normalized()],
        active_page_id="page-1",
        source_meta={
            "canvas_style": {
                "background": "#111111",
                "grid_color": "#222222",
                "show_grid": True,
                "grid_size": 12,
                "grid_opacity": 0.5,
            },
            "custom_meta": "keep",
        },
    )

    snapshot = project_snapshot_payload(project, page_title_provider=lambda index: f"Pagina {index}")

    assert snapshot is not None
    assert snapshot["active_page_id"] == "page-1"
    assert len(snapshot["pages"]) == 1
    assert snapshot["source_meta"]["custom_meta"] == "keep"
    assert snapshot["source_meta"]["canvas_style"]["grid_size"] == 12
    assert validate_dashboard_project(project) is True


def test_multiple_page_project_round_trip_preserves_active_page_and_unknown_keys():
    payload = {
        "project_id": "proj-1",
        "name": "Painel",
        "active_page_id": "page-2",
        "source_meta": {
            "canvas_style": {
                "background": "#111111",
                "grid_color": "#222222",
                "show_grid": False,
                "grid_size": 12,
                "grid_opacity": 0.5,
            },
            "custom_meta": "keep",
        },
        "pages": [
            _page("page-1", "Resumo", custom_page="keep"),
            _page("page-2", "Detalhe"),
        ],
        "custom_top_level": "keep",
    }

    normalized = normalize_project_payload(
        payload,
        page_title_provider=lambda index: f"Pagina {index}",
        canvas_style_normalizer=normalize_canvas_style,
    )
    loaded = normalize_loaded_project(
        DashboardProject.from_dict(normalized),
        page_title_provider=lambda index: f"Pagina {index}",
        canvas_style_normalizer=normalize_canvas_style,
    )

    assert normalized["active_page_id"] == "page-2"
    assert normalized["source_meta"]["custom_meta"] == "keep"
    assert normalized["source_meta"]["canvas_style"]["grid_size"] == 12
    assert normalized["pages"][0]["custom_page"] == "keep"
    assert normalized["custom_top_level"] == "keep"
    assert loaded.active_page_id == "page-2"
    assert loaded.source_meta["custom_meta"] == "keep"
    assert loaded.source_meta["canvas_style"]["grid_size"] == 12
    assert loaded.to_dict()["pages"][1]["title"] == "Detalhe"


def test_legacy_single_page_payload_keeps_compatibility_and_title_provider():
    payload = {
        "project_id": "legacy-proj",
        "name": "Painel",
        "page_title": "Painel",
        "active_page_id": "legacy-page",
        "source_meta": {
            "_legacy_single_page": True,
            "canvas_style": {
                "background": "#111111",
                "grid_color": "#222222",
                "show_grid": True,
                "grid_size": 8,
                "grid_opacity": 1.0,
            },
            "custom_meta": "keep",
        },
        "custom_top_level": "keep",
    }

    normalized = normalize_project_payload(
        payload,
        page_title_provider=lambda index: f"Pagina {index}",
        canvas_style_normalizer=normalize_canvas_style,
    )

    assert normalized["active_page_id"] == normalized["pages"][0]["page_id"]
    assert normalized["pages"][0]["title"] == "Pagina 1"
    assert normalized["source_meta"]["_legacy_single_page"] is True
    assert normalized["source_meta"]["custom_meta"] == "keep"
    assert normalized["custom_top_level"] == "keep"


def test_page_normalization_and_snapshot_helpers_keep_project_state_stable():
    page_payload = normalize_page_payload(_page("page-1", "Resumo", custom_page="keep"))
    state = snapshot_state({"name": "Painel"}, "models/demo.pbsdash", True)

    assert page_payload["custom_page"] == "keep"
    assert resolve_active_page_id({"active_page_id": ""}, [page_payload]) == "page-1"
    assert state["path"] == "models/demo.pbsdash"
    assert state["dirty"] is True
    assert snapshot_signature(state) == snapshot_signature(dict(state))
