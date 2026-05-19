from plugin.Summarizer.model_view.model_toolbar import toolbar_visuals_visible_count


def test_toolbar_visuals_visible_count_keeps_all_buttons_when_space_is_sufficient():
    assert (
        toolbar_visuals_visible_count(220, [32, 32, 32, 32, 32], spacing=2, padding=8)
        == 5
    )


def test_toolbar_visuals_visible_count_hides_one_button_at_a_time():
    assert (
        toolbar_visuals_visible_count(170, [32, 32, 32, 32, 32], spacing=2, padding=8)
        == 4
    )
    assert (
        toolbar_visuals_visible_count(136, [32, 32, 32, 32, 32], spacing=2, padding=8)
        == 3
    )
