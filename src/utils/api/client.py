import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from pydantic import ValidationError

from src import schema

# Limits

REQUEST_TIMEOUT_SECONDS = 20
MAX_INDEX_BYTES = 16 * 1024 * 1024

# Chart index


def fetch_chart_index(
    settings: schema.ConnectionSettings,
) -> list[schema.Chart]:
    # Request
    url = urljoin(f"{settings.normalized_server_url}/", "chart/")
    headers = {"Accept": "application/json"}
    if settings.token:
        headers["MAIREPO_TOKEN"] = settings.token

    request = Request(url, headers=headers, method="GET")

    # Network
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = response.read(MAX_INDEX_BYTES + 1)
    except HTTPError as error:
        if error.code == 403:
            raise RuntimeError("Authentication failed. Check the token.") from error
        raise RuntimeError(f"Server returned HTTP {error.code}.") from error
    except URLError as error:
        raise RuntimeError(
            "Could not connect to the server. Check the URL and network."
        ) from error
    except TimeoutError as error:
        raise RuntimeError("The request timed out. Try again later.") from error

    # Response size
    if len(payload) > MAX_INDEX_BYTES:
        raise RuntimeError("The server index is too large.")

    # Validation
    try:
        decoded = json.loads(payload)
        return schema.chart_index_adapter.validate_python(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as error:
        raise RuntimeError("The server returned an invalid chart index.") from error
