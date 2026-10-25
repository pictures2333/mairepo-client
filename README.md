# mairepo client

mairepo client is a desktop application for subscribing to and synchronizing AstroDX charts from a mairepo repository. It works with [mairepo-server](https://github.com/pictures2333/mairepo-server) and manages downloaded charts inside an AstroDX `levels` directory.

The client can browse available charts, subscribe or unsubscribe, and synchronize chart files.

## Usage

Python 3.13 or later and [uv](https://docs.astral.sh/uv/) are required.

Install the dependencies and start the application:

```sh
uv sync
uv run python main.py
```

When connecting, provide:

- the AstroDX `levels` directory
- the mairepo server URL
- the server token, if required

Choose charts with **Subscribe** or **Unsubscribe**, then use **Sync** to apply the selected subscriptions to the local chart files. **Refresh** only reloads the latest chart information from the server.

**The client does not coordinate file access with a running AstroDX instance. Close AstroDX before synchronizing or unsubscribing, then reopen it after the operation finishes.**

Saved connections include the token in a local settings file. Keep the application directory private if this feature is used.

## Development guide

Create the development environment and run the application with:

```sh
uv sync
uv run python main.py
```

### Database migrations

After changing the SQLAlchemy models, generate a revision with:

```sh
uv run alembic revision -m "describe the change"
```

Implement and review the generated file in `migrations/versions/` before committing it.

Database upgrades are handled automatically by the application when it connects to a storage directory.
