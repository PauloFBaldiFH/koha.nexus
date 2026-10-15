import pytest

from nexus_core import health as H
from nexus_core.status import parse_status
from nexus_core.tests.fixtures import HEALTHY, status_json

OK = parse_status(status_json())


def with_services(**units):
    services = dict(HEALTHY["services"])
    services.update({k.replace("_", "-"): v for k, v in units.items()})
    return parse_status(status_json(services=services))


def test_rows_of_a_healthy_koha():
    rows = H.component_rows(True, OK)
    assert [r.unit for r in rows] == ["wsl", "mariadb", "apache2", "rabbitmq-server", "memcached", "koha-common", "http"]
    assert all(r.state == H.RUNNING for r in rows)
    assert rows[-1].detail == "200"
    s = H.summarize(rows, "running")
    assert (s.level, s.text, s.broken) == ("ok", "All services are running", [])


def test_debian_stopped_names_only_debian():
    rows = H.component_rows(False, None)
    assert {r.state for r in rows} == {H.STOPPED}
    s = H.summarize(rows, "stopped")
    assert (s.level, s.text, s.broken) == ("fault", "Attention: Debian (WSL) is offline", ["wsl"])


def test_one_service_down():
    s = H.summarize(H.component_rows(True, with_services(mariadb="failed")), "not_responding")
    assert (s.level, s.text, s.broken) == ("fault", "Attention: MariaDB is offline", ["mariadb"])


def test_staff_page_not_answering():
    rows = H.component_rows(True, parse_status(status_json(http={"staff": 0, "opac": 0})))
    assert rows[-1].state == H.FAILED and rows[-1].detail == "000"
    assert H.summarize(rows, "not_responding").text == "Attention: the staff interface does not answer"
    rows = H.component_rows(True, parse_status(status_json(http={"staff": 503, "opac": 200})))
    assert rows[-1].state == H.FAILED


def test_several_down():
    s = H.summarize(H.component_rows(True, with_services(apache2="inactive", memcached="failed")), "not_responding")
    assert s.text == "Attention: 2 components are offline (Apache, Memcached)"
    assert s.broken == ["apache2", "memcached"]


def test_starting_rows_are_not_faults():
    rows = H.component_rows(True, with_services(koha_common="activating"))
    assert H.summarize(rows, "running").level == "starting"
    rows = H.component_rows(True, with_services(apache2="failed"))
    assert H.summarize(rows, "starting").level == "starting"


def test_no_status_from_a_running_debian_reads_unknown():
    rows = H.component_rows(True, None)
    assert [r.state for r in rows[1:6]] == [H.UNKNOWN] * 5
    assert rows[-1].state == H.FAILED
    assert H.summarize(rows, "not_responding").level == "fault"


@pytest.mark.parametrize("state, text", [("stopped_by_user", "Koha is stopped (you stopped it)"),
                                         ("not_installed", "Koha is not installed")])
def test_stopped_on_purpose_highlights_nothing(state, text):
    s = H.summarize(H.component_rows(False, None), state)
    assert (s.level, s.text, s.broken) == ("stopped", text, [])


def test_no_rows_is_checking():
    assert H.summarize([], "running").text == "Checking..."


@pytest.mark.parametrize("active, state", [("active", "running"), ("activating", "starting"), ("reloading", "starting"),
                                           ("failed", "failed"), ("inactive", "stopped"), ("deactivating", "stopped"),
                                           ("unknown", "unknown"), ("", "unknown")])
def test_service_state(active, state):
    assert H.service_state(active) == state


def test_row_texts():
    rows = H.component_rows(True, OK)
    assert H.row_name(rows[-1]) == "HTTP response"
    assert H.row_state_text(rows[-1]) == "Answers (HTTP 200)"
    assert H.row_state_text(H.Row("http", "staff", H.FAILED, "000")) == "Does not answer"
    assert H.row_state_text(rows[1]) == "Running"
    assert H.row_state_text(H.Row("mariadb", "MariaDB", "weird")) == "Unknown"
