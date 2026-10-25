import json
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from pydantic import ValidationError

from src import schema
from . import log, storage

# Logger

logger = log.get_logger("api")

# Limits

REQUEST_TIMEOUT_SECONDS = 20
MAX_CHART_RESPONSE_BYTES = 16 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024

# State

http_session: Optional[requests.Session] = None

# Lifecycle


def close() -> None:
    global http_session

    if http_session is not None:
        http_session.close()
    http_session = None


# Requests


def fetch_chart(
    chart_id: Optional[int] = None,
) -> list[schema.Chart]:
    path = "chart/" if chart_id is None else f"chart/{chart_id}"
    payload = bytearray()

    # Stream the response with an enforced decoded size limit
    try:
        with _get(path, "application/json") as response:
            _require_success(response)
            for chunk in response.iter_content(DOWNLOAD_CHUNK_BYTES):
                payload.extend(chunk)
                if len(payload) > MAX_CHART_RESPONSE_BYTES:
                    raise RuntimeError("The server chart response is too large.")
    except requests.Timeout as error:
        raise RuntimeError("The request timed out. Try again later.") from error
    except requests.SSLError as error:
        raise RuntimeError(
            "The server TLS certificate is not trusted by this system."
        ) from error
    except requests.ConnectionError as error:
        raise RuntimeError(
            "Could not connect to the server. Check the URL and network."
        ) from error
    except requests.RequestException as error:
        raise RuntimeError("The chart request failed.") from error

    # Validate the complete remote response
    try:
        decoded = json.loads(payload)
        charts = schema.chart_index_adapter.validate_python(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as error:
        raise RuntimeError("The server returned an invalid chart response.") from error

    chart_ids = [chart.id for chart in charts]
    if len(chart_ids) != len(set(chart_ids)):
        raise RuntimeError("The server returned duplicate chart IDs.")
    if chart_id is not None and (
        len(charts) > 1 or (charts and charts[0].id != chart_id)
    ):
        raise RuntimeError("The server returned an invalid chart response.")

    if chart_id is None:
        logger.info("Fetched %d charts from the server.", len(charts))
    elif charts:
        logger.info("Fetched chart %d from the server.", chart_id)
    else:
        logger.info("Chart %d is missing from the server.", chart_id)
    return charts


def download_blob(
    blob_id: int,
    destination: Path,
) -> bool:
    destination_created = False
    download_completed = False
    try:
        # Reject unavailable blobs before creating the temporary file
        with _get(
            f"blob/{blob_id}",
            "application/octet-stream",
        ) as response:
            if response.status_code in (404, 503):
                logger.warning(
                    "Blob %d is unavailable with HTTP %d; trying fallback.",
                    blob_id,
                    response.status_code,
                )
                return False
            _require_success(response)

            # Stream and flush the complete blob before returning success
            with destination.open("xb") as output:
                destination_created = True
                for chunk in response.iter_content(DOWNLOAD_CHUNK_BYTES):
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            download_completed = True
    except requests.Timeout as error:
        raise RuntimeError("The blob download timed out.") from error
    except requests.SSLError as error:
        raise RuntimeError(
            "The server TLS certificate is not trusted by this system."
        ) from error
    except requests.ConnectionError as error:
        raise RuntimeError(
            "Could not connect while downloading a chart file."
        ) from error
    except requests.RequestException as error:
        raise RuntimeError("The chart file request failed.") from error
    except OSError as error:
        raise RuntimeError("Could not write a downloaded chart file.") from error
    finally:
        if destination_created and not download_completed:
            destination.unlink(missing_ok=True)

    return True


# Helpers


def _get(
    path: str,
    accept: str,
) -> requests.Response:
    settings = storage.get_settings()
    url = urljoin(f"{settings.normalized_server_url}/", path)
    headers = {"Accept": accept}
    if settings.token:
        headers["MAIREPO-TOKEN"] = settings.token

    return _get_session().get(
        url,
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
        stream=True,
        allow_redirects=False,
    )


def _get_session() -> requests.Session:
    global http_session

    if http_session is None:
        http_session = requests.Session()
    return http_session


def _require_success(response: requests.Response) -> None:
    if response.status_code == 403:
        raise RuntimeError("Authentication failed. Check the token.")
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"Server returned HTTP {response.status_code}.")
