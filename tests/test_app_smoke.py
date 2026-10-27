"""Headless smoke tests: run the Streamlit app and make sure it does not crash."""

import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def run_app() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=60).run()


def test_app_runs_without_errors():
    app = run_app()
    assert not app.exception
    assert len(app.metric) >= 4  # the KPI cards render


def test_clearing_a_filter_shows_friendly_warning_not_crash():
    app = run_app()
    app.sidebar.multiselect[0].set_value([]).run()  # Region -> nothing selected
    assert not app.exception
    assert any("No records match" in warning.value for warning in app.warning)


def test_invalid_date_range_shows_error_not_crash():
    app = run_app()
    # Both dates are inside the dataset's range, but start is after end.
    app.sidebar.date_input[0].set_value(datetime.date(2025, 12, 20))  # start
    app.sidebar.date_input[1].set_value(datetime.date(2025, 1, 5))  # end
    app.run()
    assert not app.exception
    assert any("Start date" in error.value for error in app.sidebar.error)


def test_narrow_filter_still_renders():
    app = run_app()
    app.sidebar.multiselect[0].set_value(["East"]).run()
    assert not app.exception
