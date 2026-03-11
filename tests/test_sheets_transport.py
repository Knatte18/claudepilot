"""Tests for sheets_transport retry logic."""
from unittest.mock import MagicMock, patch

import pytest
from gspread.exceptions import APIError

from src.sheets_transport import _retry_api_call


def _make_api_error(status_code: int) -> APIError:
    """Build a gspread APIError with the given HTTP status code."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {
        "error": {"code": status_code, "message": "transient", "status": "ERROR"}
    }
    return APIError(response)


class TestRetryApiCall:
    def test_succeeds_on_first_attempt(self):
        func = MagicMock(return_value="ok")
        assert _retry_api_call(func) == "ok"
        assert func.call_count == 1

    def test_retries_on_429_then_succeeds(self):
        func = MagicMock(side_effect=[_make_api_error(429), "ok"])
        with patch("src.sheets_transport.time.sleep"):
            result = _retry_api_call(func)
        assert result == "ok"
        assert func.call_count == 2

    def test_retries_on_503_then_succeeds(self):
        func = MagicMock(side_effect=[_make_api_error(503), "ok"])
        with patch("src.sheets_transport.time.sleep"):
            result = _retry_api_call(func)
        assert result == "ok"
        assert func.call_count == 2

    def test_raises_after_max_attempts(self):
        error = _make_api_error(429)
        func = MagicMock(side_effect=[error, error, error])
        with patch("src.sheets_transport.time.sleep"):
            with pytest.raises(APIError):
                _retry_api_call(func)
        assert func.call_count == 3

    def test_does_not_retry_on_non_transient_error(self):
        func = MagicMock(side_effect=_make_api_error(403))
        with pytest.raises(APIError):
            _retry_api_call(func)
        assert func.call_count == 1

    def test_exponential_backoff_delays(self):
        error = _make_api_error(429)
        func = MagicMock(side_effect=[error, error, "ok"])
        with patch("src.sheets_transport.time.sleep") as mock_sleep:
            _retry_api_call(func)
        assert mock_sleep.call_args_list == [
            ((1,),),
            ((2,),),
        ]
