from kei_panel.views.dashboard import COMPONENTS, OVERALL, unit_state


def test_overall_ok_is_green():
    # --status-json says "ok" (kei_overall_state), never "running".
    assert OVERALL["ok"] == ("Running", "ok")
    assert OVERALL["degraded"][1] == "warn" and OVERALL["stopped"][1] == "bad"


def test_components_match_the_windows_window():
    assert [u for u, _ in COMPONENTS] == ["mariadb", "apache2", "rabbitmq-server", "memcached", "koha-common"]
    assert unit_state("active") == ("Running", "ok")
    assert unit_state("failed")[1] == unit_state("inactive")[1] == "bad"
    assert unit_state(None)[1] == "warn"
