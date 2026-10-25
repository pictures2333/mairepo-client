from src import schema
from src.database import model
from . import manifest

# State snapshots


def build_chart_states(
    remote_charts: list[schema.Chart],
    local_charts: list[model.Chart],
) -> list[schema.ChartState]:
    remote_by_id = {chart.id: chart for chart in remote_charts}
    local_by_id = {chart.id: chart for chart in local_charts}
    states = []

    # Remote charts, including subscribed charts
    for remote_chart in remote_charts:
        local_chart = local_by_id.get(remote_chart.id)
        subscribed = local_chart is not None
        states.append(
            schema.ChartState(
                id=remote_chart.id,
                name=remote_chart.name,
                subscribed=subscribed,
                missing=False,
                outdated=(
                    subscribed
                    and chart_needs_sync(
                        local_chart,
                        remote_chart,
                    )
                ),
            )
        )

    # Subscriptions missing from the remote index
    for local_chart in local_charts:
        if local_chart.id in remote_by_id:
            continue
        states.append(
            schema.ChartState(
                id=local_chart.id,
                name=local_chart.name,
                subscribed=True,
                missing=True,
                outdated=False,
            )
        )

    return states


# State comparison


def chart_needs_sync(
    local_chart: model.Chart,
    remote_chart: schema.Chart,
) -> bool:
    try:
        chart_directory = manifest.resolve_chart_directory(
            local_chart.id,
            local_chart.folder_name,
        )
        remote_files = manifest.validate_remote_files(remote_chart.files)
    except RuntimeError:
        return True

    if local_chart.name != remote_chart.name or not chart_directory.is_dir():
        return True

    local_files = {file.id: file for file in local_chart.files}
    if local_files.keys() != remote_files.keys():
        return True

    for file_id, remote_file in remote_files.items():
        local_file = local_files[file_id]
        blobs = sorted(remote_file.blobs, key=lambda blob: blob.id, reverse=True)
        if (
            not blobs
            or local_file.filename != remote_file.filename
            or local_file.blob_id != blobs[0].id
            or not manifest.is_regular_file(chart_directory / local_file.filename)
        ):
            return True
    return False
