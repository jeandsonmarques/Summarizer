from pathlib import Path

from plugin.Summarizer.model_view.model_toolbar import (
    toolbar_visuals_should_be_visible,
    toolbar_visuals_visible_count,
)

ROOT = Path(__file__).resolve().parents[2]


def test_toolbar_visuals_visible_count_keeps_all_buttons_when_space_is_sufficient():
    assert toolbar_visuals_visible_count(220, [32, 32, 32, 32, 32], spacing=2, padding=8) == 5


def test_toolbar_visuals_visible_count_hides_one_button_at_a_time():
    assert toolbar_visuals_visible_count(170, [32, 32, 32, 32, 32], spacing=2, padding=8) == 4
    assert toolbar_visuals_visible_count(136, [32, 32, 32, 32, 32], spacing=2, padding=8) == 3


def test_toolbar_visuals_stay_available_while_format_panel_is_open():
    assert toolbar_visuals_should_be_visible(
        has_project=True,
        edit_enabled=True,
        create_chart_checked=False,
        builder_panel_open=False,
        visual_panel_open=True,
    )


def test_toolbar_visuals_hide_when_no_visual_panel_context_is_open():
    assert not toolbar_visuals_should_be_visible(
        has_project=True,
        edit_enabled=True,
        create_chart_checked=False,
        builder_panel_open=False,
        visual_panel_open=False,
    )


def test_model_builder_panel_open_is_preserved_until_canvas_page_is_active():
    source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")

    assert "pending_open = requested and can_edit_project and not in_canvas_page" in source
    assert "self._builder_panel_open = bool(active or pending_open)" in source
    assert "if self.create_chart_btn.isChecked() != self._builder_panel_open:" in source


def test_model_side_panels_start_collapsed_for_new_and_opened_projects():
    source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")

    assert "self._visual_side_collapsed = True" in source
    assert "self._data_panel_collapsed = True" in source
    assert "def _reset_model_side_panels_collapsed(self):" in source
    assert "self._reset_model_side_panels_collapsed()\n        page = DashboardPage" in source
    assert (
        "project = self._normalize_loaded_project(project)\n"
        "        self._reset_model_side_panels_collapsed()"
        in source
    )


def test_fields_panel_expands_when_new_chart_is_triggered():
    source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")

    assert "def _expand_data_panel_for_new_chart(self):" in source
    assert "self._data_panel_collapsed = False" in source
    assert "if checked:\n            self._expand_data_panel_for_new_chart()" in source


def test_clear_filters_button_is_available_in_preview_mode():
    source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")
    start = source.index("def _update_filters_bar")
    end = source.index("def _clear_model_filters", start)
    body = source[start:end]

    assert "if not items:" in body
    assert "if not self.edit_mode_btn.isChecked() or not items:" not in body
    assert "self.clear_filters_btn.setVisible(True)" in body


def test_model_toolbar_keeps_edit_mode_height_in_preview_mode():
    source = (ROOT / "plugin" / "Summarizer" / "model_view" / "model_header.py").read_text(
        encoding="utf-8"
    )

    assert "toolbar_strip.setMinimumHeight(44)" in source
    assert "build_visual_type_buttons(" in source
    assert "toolbar_visuals_strip" in source
    assert "toolbar_visuals_layout" in source
    assert "button_size=32" in source


def test_model_toolbar_uses_white_selected_and_black_hover_states():
    source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")
    header_source = (ROOT / "plugin" / "Summarizer" / "model_view" / "model_header.py").read_text(
        encoding="utf-8"
    )
    theme_source = (ROOT / "plugin" / "Summarizer" / "model_view" / "model_theme.py").read_text(
        encoding="utf-8"
    )

    assert "QPushButton#ModelToolbarButton:checked:hover" in source
    assert (
        "QPushButton#ModelToolbarButton:checked,\n"
        "            QToolButton#ModelToolbarButton:checked {\n"
        "                background: #F3F4F6;"
        in source
    )
    assert 'QPushButton#ModelToolbarButton[toolbarMode="database"]' in source
    assert "QPushButton#ModelToolbarButton:pressed" in source
    assert "background: #F3F4F6;" in source
    assert "min-width: 30px;" in source
    assert "icon_size: int = 20" in source
    assert "_toolbar_button_icon" in source
    assert "button.toggled.connect" in source
    assert "QToolButton#ModelVisualTypeButton:checked:hover" in source
    assert 'configure_toolbar_icon_button(data_fields_btn, "Layers.svg"' in header_source
    assert "QIcon.On" in theme_source


def test_fields_toolbar_button_sits_next_to_format_visual_and_toggles_panel():
    header_source = (ROOT / "plugin" / "Summarizer" / "model_view" / "model_header.py").read_text(
        encoding="utf-8"
    )
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")

    assert "data_fields_btn: QPushButton" in header_source
    assert 'data_fields_btn = QPushButton(_rt("Campos"))' in header_source
    assert (
        'configure_toolbar_icon_button(data_fields_btn, "Layers.svg", _rt("Campos")'
        in header_source
    )
    assert "Mostrar ou recolher campos" not in header_source
    assert "database_fields_btn: QPushButton" in header_source
    assert 'database_fields_btn = QPushButton(_rt("Banco"))' in header_source
    assert 'database_fields_btn.setProperty("toolbarMode", "database")' in header_source
    assert (
        "for button in (create_chart_btn, format_visual_btn, "
        "database_fields_btn, data_fields_btn, edit_mode_btn):"
        in header_source
    )
    assert (
        "self.database_fields_btn.toggled.connect(self._handle_database_panel_toggle)"
        in model_source
    )
    assert "self.data_fields_btn.toggled.connect(self._handle_data_fields_toggle)" in model_source
    assert "def _handle_data_fields_toggle(self, checked: bool):" in model_source
    assert "self._set_data_panel_collapsed(not bool(checked))" in model_source


def test_remote_database_project_blocks_edit_mode_without_update_permission():
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")

    assert '"can_edit": bool(getattr(record, "can_edit", False))' in model_source
    assert "project.edit_mode = False" in model_source
    assert "def _current_project_is_locked_database_project(self)" in model_source
    assert (
        "requested_enabled and self._current_project_is_locked_database_project()"
        in model_source
    )
    assert "Este painel veio do banco de dados" in model_source


def test_remote_database_project_save_writes_back_to_database_before_local_save_dialog():
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")
    save_body = model_source[
        model_source.index("def save_project"): model_source.index("def export_project")
    ]

    assert "if not save_as and self._current_project_should_save_to_remote_database():" in save_body
    assert "self._save_current_project_to_remote_database()" in save_body
    assert save_body.index("self._save_current_project_to_remote_database()") < save_body.index(
        "QFileDialog.getSaveFileName"
    )
    assert "def _save_current_project_to_remote_database(self):" in save_body
    assert "ModelRemoteProjectService(connection_meta).save_project_payload" in save_body
    assert "row_id=row_id" in save_body
    assert "Painel salvo no banco de dados." in save_body


def test_remote_project_worker_shutdown_cancels_thread_before_widget_close():
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")
    dialog_source = (ROOT / "plugin" / "Summarizer" / "data_summarizer.py").read_text(
        encoding="utf-8"
    )

    assert "_remote_project_shutting_down = False" in model_source
    assert "def cancel(self):" in model_source
    assert "thread.requestInterruption()" in model_source
    assert "worker.finished.disconnect(self._handle_remote_project_scan_result)" in model_source
    assert "thread.wait(max(0, int(wait_ms or 0)))" in model_source
    assert "def cleanup(self):" in model_source
    assert "def closeEvent(self, event):" in model_source
    assert "_REMOTE_PROJECT_THREADS_IN_FLIGHT" in model_source
    assert 'getattr(model_tab, "cleanup", None)' in dialog_source
    assert 'getattr(getattr(self, "model_tab", None), "cleanup", None)' in dialog_source


def test_clear_filters_button_floats_over_canvas_and_uses_squarer_corners():
    header_source = (ROOT / "plugin" / "Summarizer" / "model_view" / "model_header.py").read_text(
        encoding="utf-8"
    )
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")

    assert "toolbar_layout.addWidget(clear_filters_btn, 0)" not in header_source
    assert "self.clear_filters_btn.setParent(self.canvas_page)" in model_source
    assert "def _position_clear_filters_button(self):" in model_source
    assert "def _schedule_clear_filters_button_position(self):" in model_source
    assert "QPushButton#ModelActionButton {" in model_source
    assert "border-radius: 4px;" in model_source
    assert "self._schedule_clear_filters_button_position()" in model_source
    assert "for delay in (0, 40, 120):" in model_source
    assert "self._schedule_clear_filters_button_position()" in model_source


def test_builder_visual_selection_uses_cached_icons_during_programmatic_sync():
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")
    builder_source = (
        ROOT / "plugin" / "Summarizer" / "model_view" / "model_builder_panel.py"
    ).read_text(encoding="utf-8")

    assert (
        'def _sync_visual_type_button_states(self, buttons, active_chart_type: str = ""):'
        in model_source
    )
    assert "button._model_icon_normal = normal_icon" in builder_source
    assert "button._model_icon_checked = checked_icon" in builder_source
    assert "parent._model_visual_button_group = group" in builder_source
    assert "self._sync_visual_type_button_states(buttons, active_chart_type)" in model_source
    assert "QButtonGroup(parent)" in builder_source
    assert (
        "button_containers = [container for container in "
        "(buttons_container, toolbar_container) if container is not None]"
        in model_source
    )
    assert "container.setUpdatesEnabled(False)" in model_source
    assert "group.setExclusive(False)" in model_source
    assert 'self._sync_visual_type_button_states(toolbar_buttons, "")' in model_source
    assert (
        "self._sync_visual_type_button_states(toolbar_buttons, active_chart_type)" in model_source
    )


def test_model_fields_panel_uses_summary_like_compact_scale():
    data_panel_source = (
        ROOT / "plugin" / "Summarizer" / "model_view" / "model_data_panel.py"
    ).read_text(encoding="utf-8")
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")

    assert "font.setPixelSize(11)" in data_panel_source
    assert "QFrame#ModelBuilderDataPanel QLabel#ModelBuilderTitle" in model_source
    assert "QFrame#ModelBuilderDataPanel QComboBox#ModelBuilderCombo" in model_source
    assert "font-size: 11px;" in data_panel_source
    assert "min-height: 28px;" in data_panel_source
    assert "min-height: 22px;" in data_panel_source
    assert "QFrame#ModelBuilderDataPanel QListWidget#ModelBuilderFieldList::item" in model_source


def test_presentation_button_icon_is_neutral_not_purple():
    icon_source = (
        ROOT / "plugin" / "Summarizer" / "resources" / "SVG" / "PresentationMap.svg"
    ).read_text(encoding="utf-8")

    assert "#6C4CF1" not in icon_source
    assert "#7C6CFF" not in icon_source
    assert "#F5F1FF" not in icon_source
    assert "#F3F4F6" in icon_source
    assert "#374151" in icon_source


def test_model_start_page_uses_walker_database_home_pattern():
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")
    card_source = (ROOT / "plugin" / "Summarizer" / "model_view" / "model_cards.py").read_text(
        encoding="utf-8"
    )

    assert 'setObjectName("ModelHomeActions")' in model_source
    assert '_ModelCardAction(_rt("New"), "", "Walker-New.svg"' in model_source
    assert '_ModelCardAction(_rt("Open"), "", "Walker-Open.svg"' in model_source
    assert '_ModelCardAction(\n            _rt("Remote Database")' in model_source
    assert '_rt("Connect to remote database sources")' in model_source
    assert '"Dataset.svg"' in model_source
    assert '"card_sql.svg"' not in model_source
    assert '_rt("Recent Panels")' in model_source
    assert '_rt("Database Panels")' in model_source
    assert "class _CurrentPageStackedWidget(QStackedWidget):" in model_source
    assert "self.body_stack = _CurrentPageStackedWidget(self)" in model_source
    assert "current.minimumSizeHint()" in model_source
    assert 'setObjectName("ModelRecentsScroll")' in model_source
    assert 'setObjectName("ModelRemoteProjectsScroll")' in model_source
    assert "self.recents_scroll.setFixedHeight(_MODEL_RECENT_CARD_HEIGHT)" in model_source
    assert "self.remote_projects_scroll.setFixedHeight(_MODEL_RECENT_CARD_HEIGHT)" in model_source
    assert "self.recents_card.setFixedHeight(_MODEL_RECENTS_SECTION_HEIGHT)" in model_source
    assert "self.remote_projects_card.setVisible(False)" in model_source
    resize_body = model_source[
        model_source.index("def resizeEvent"): model_source.index("def _handle_canvas_changed")
    ]
    assert "QTimer.singleShot(0, self._refresh_recents)" not in resize_body
    assert 'columns != getattr(self, "_recents_columns", 0)' in resize_body
    assert "QGridLayout(self.recents_container)" in model_source
    assert "QGridLayout(self.remote_projects_container)" in model_source
    refresh_body = model_source[
        model_source.index("def _refresh_recents"): model_source.index("def _refresh_ui_state")
    ]
    assert "local_recents = self.store.load_recents()" in refresh_body
    assert (
        'remote_recents = list(getattr(self, "_remote_project_records", []) or [])'
        in refresh_body
    )
    assert "self.recents_container" in refresh_body
    assert "self.remote_projects_container" in refresh_body
    assert "self.header.setVisible(has_project)" in model_source
    assert "return 4" in model_source
    assert "def _recent_display_timestamp" in model_source
    assert 'parsed.strftime("%d/%m/%Y, %H:%M:%S")' in model_source
    assert "preview_path=" not in model_source
    assert ".preview.png" not in model_source
    assert "Comece um painel no Model" not in model_source
    assert "Use os graficos do plugin como blocos editaveis" not in model_source
    assert "QFrame#ModelRecentCardPreview" in model_source
    assert "setFixedSize(212, 238)" in card_source
    assert "metrics.elidedText" in card_source
    assert "class _ModelRecentFolderIcon(QWidget):" in card_source
    assert 'QPen(QColor("#4B5563"), 2.0)' in card_source
    assert "QPixmap" not in card_source
    assert "def set_connected(self, connected: bool):" in card_source
    assert 'QColor("#22C55E")' in card_source


def test_model_import_dataset_opens_walker_database_dialog_directly():
    model_source = (ROOT / "plugin" / "Summarizer" / "model_tab.py").read_text(encoding="utf-8")
    integration_source = (ROOT / "plugin" / "Summarizer" / "integration_panel.py").read_text(
        encoding="utf-8"
    )

    assert "def _open_model_database_menu(self):" in model_source
    menu_method = model_source[
        model_source.index("def _open_model_database_menu"): model_source.index(
            "def _open_model_import_dataset"
        )
    ]
    assert "QMenu(self)" in menu_method
    assert 'menu.setObjectName("ModelDatabaseMenu")' in menu_method
    assert "connected_database_drivers" in menu_method
    assert '_rt("Importar painel .pbsdash...")' in menu_method
    assert '"__upload_pbsdash__"' in menu_method
    assert '_rt("Atualizar paineis do banco")' in menu_method
    assert '"__refresh_remote_projects__"' in menu_method
    assert "action.setIcon(self._database_connected_icon())" in menu_method
    for driver in ("PostgreSQL", "PostGIS", "SQL Server", "Oracle", "MySQL"):
        assert f'"{driver}"' in menu_method
    assert "self._import_model_project_file_to_database()" in menu_method
    assert "self._force_refresh_remote_project_records()" in menu_method
    assert "self._open_model_import_dataset(action_data)" in menu_method

    import_method = model_source[
        model_source.index("def _open_model_import_dataset"): model_source.index(
            "def close_project", model_source.index("def _open_model_import_dataset")
        )
    ]
    assert 'preferred_driver: str = "PostgreSQL"' in import_method
    assert "DatabaseImportDialog" in import_method
    assert "open_get_data_dialog" in import_method
    assert import_method.index("DatabaseImportDialog") < import_method.index("open_get_data_dialog")
    assert "preferred_driver=preferred_driver" in import_method
    assert "self._refresh_model_database_status()" in import_method
    assert "connection_registry.replace_saved_connections(saved, persist=True)" in import_method
    assert "def _database_connected_icon(self) -> QIcon:" in model_source

    assert 'setObjectName("WalkerDatabaseDialog")' in integration_source
    assert "def _walker_database_dialog_flags" in integration_source
    assert 'sys.platform.startswith("win")' in integration_source
    assert "Qt.FramelessWindowHint" in integration_source
    assert "Qt.WindowCloseButtonHint" in integration_source
    assert "self.setWindowFlags(_walker_database_dialog_flags())" in integration_source
    assert "WA_StyledBackground" in integration_source
    assert "WA_TranslucentBackground" not in integration_source
    assert "apply_windows_rounded_corners" in integration_source
    assert "def _ensure_walker_dialog_visible" in integration_source
    assert "QTimer.singleShot(0, self._ensure_walker_dialog_visible)" in integration_source
    assert "self._walker_panel = panel" in integration_source
    assert "QGraphicsDropShadowEffect(panel)" not in integration_source
    assert "_show_walker_modal_overlay" in integration_source
    assert "QFrame#WalkerDatabasePanel" in integration_source
    assert "QDialog#WalkerDatabaseDialog" in integration_source
    assert "setFixedSize(500, 430)" in integration_source
    assert "class _WalkerDatabaseTitleIcon(QWidget):" in integration_source
    assert "def setConnected(self, connected: bool):" in integration_source
    assert 'painter.setBrush(QColor("#22C55E"))' in integration_source
    assert "self.connection_status_icon = _WalkerDatabaseTitleIcon(self)" in integration_source
    assert 'svg_icon("Dataset.svg")' not in integration_source
    assert "def _set_connection_status(self, connected: bool):" in integration_source
    assert "_CONNECTED_DATABASE_KEYS: set[str] = set()" in integration_source
    assert "_CONNECTED_DATABASE_TABLES: Dict[str, List[str]] = {}" in integration_source
    assert "_CONNECTED_DATABASE_PARAMS: Dict[str, Dict] = {}" in integration_source
    assert "def connected_database_drivers() -> set[str]:" in integration_source
    assert (
        "def _connection_status_key(self, params: Optional[Dict] = None) -> str:"
        in integration_source
    )
    assert (
        "def _remember_connected_connection("
        "self, params: Dict, tables: Optional[List[str]] = None):"
        in integration_source
    )
    assert "def _refresh_connection_status_from_fields(self):" in integration_source
    assert "def _restore_connected_tables(self, key: str):" in integration_source
    assert "_CONNECTED_DATABASE_KEYS.add(key)" in integration_source
    assert "_CONNECTED_DATABASE_PARAMS[key] = dict(params)" in integration_source
    assert "_CONNECTED_DATABASE_TABLES[key] = list(tables)" in integration_source
    assert (
        "self._remember_connected_connection(params, self._current_table_names())"
        in integration_source
    )
    assert 'if not params["password"]:' in integration_source
    assert (
        "connected = _CONNECTED_DATABASE_PARAMS.get(self._connection_status_key(params))"
        in integration_source
    )
    assert "self._set_connection_status(False)" in integration_source
    assert "class _WalkerSslModePicker(QFrame):" in integration_source
    assert "changed = pyqtSignal(str)" in integration_source
    assert 'self.setObjectName("WalkerSslPicker")' in integration_source
    assert 'self._options = ["Disable", "Prefer", "Require"]' in integration_source
    assert "def _chevron_icon(self) -> QIcon:" in integration_source
    assert "QPainter(pixmap)" in integration_source
    assert "self.button.setIcon(self._chevron_icon())" in integration_source
    assert "self.button.setLayoutDirection(Qt.RightToLeft)" in integration_source
    assert 'return f"{self._current}  v"' not in integration_source
    assert 'popup.setObjectName("WalkerSslDropdown")' in integration_source
    assert "popup.setFixedSize(self._POPUP_WIDTH, 92)" in integration_source
    assert 'item.setObjectName("WalkerSslDropdownItem")' in integration_source
    assert "self.ssl_combo = _WalkerSslModePicker(self)" in integration_source
    assert (
        "self.ssl_combo.changed.connect(lambda *_: self._set_connection_status(False))"
        in integration_source
    )
    assert "QListView" not in integration_source
    assert "QStyleFactory" not in integration_source
    assert "WalkerSslComboPopup" not in integration_source
    assert "root_layout.setContentsMargins(0, 0, 0, 0)" in integration_source
    assert "QFrame#WalkerDatabasePanel {" in integration_source
    assert "background: #FFFFFF;" in integration_source
    assert "border-radius: 14px;" in integration_source
    assert "border: 2px solid #9CA3AF;" in integration_source
    assert "QFrame#WalkerSslPicker" in integration_source
    assert "QFrame#WalkerSslDropdown" in integration_source
    assert 'QToolButton#WalkerSslDropdownItem[current="true"]' in integration_source
    assert 'self.remember_box = QCheckBox(_rt("Salvar conexão"), self)' in integration_source
    assert 'self.remember_box.setObjectName("WalkerSaveConnectionCheck")' in integration_source
    assert "self.remember_box.setVisible(False)" not in integration_source
    assert "QCheckBox#WalkerSaveConnectionCheck" in integration_source
    assert (
        'self.delete_connection_btn = QPushButton(_rt("Excluir conexão"), self)'
        in integration_source
    )
    assert (
        'self.delete_connection_btn.setObjectName("WalkerDeleteConnectionButton")'
        in integration_source
    )
    assert "def _delete_saved_connection(self):" in integration_source
    assert "connection_registry.remove_connection(fingerprint)" in integration_source
    assert "def _forget_connected_database_params(params: Dict):" in integration_source
    assert "QPushButton#WalkerDeleteConnectionButton" in integration_source
    assert 'buttons.setObjectName("WalkerDatabaseButtons")' in integration_source
    assert 'self.load_btn = buttons.addButton(_rt("Connect")' in integration_source
    assert "if not preview and not self.tables_combo.isVisible():" in integration_source
    assert 'self.load_btn.setText(_rt("Carregar"))' in integration_source
    assert "preferred_driver: Optional[str] = None" in integration_source
    assert 'self._preferred_driver = preferred_driver or "PostgreSQL"' in integration_source
    assert 'preferred_driver=preferred_driver or "PostgreSQL"' in integration_source
    assert "def _apply_driver_ui(self):" in integration_source
    assert 'use_ssl_visible = driver == "MySQL"' in integration_source
    assert 'database_label = "Service / SID"' in integration_source
    assert 'db.setConnectOptions(f"sslmode={ssl_mode}")' in integration_source
    assert 'db.setConnectOptions("CLIENT_SSL=1")' in integration_source
