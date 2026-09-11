"""Composition root for local review and the persistent Phase 2 service."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

from .config import AppConfig, load_config
from .domain import ConfigurationError, XAutopilotError
from .model import FakeModelProvider, ModelGateway, OpenAIResponsesProvider
from .pipeline import Pipeline
from .sources import FeedSource, GitHubSource, HackerNewsSource
from .storage import SQLiteRepository
from .scheduler import Scheduler
from .web import create_server


def build_sources(config: AppConfig):
    result=[]
    hn=config.sources.get("hacker_news",{})
    if hn.get("enabled",False): result.append(HackerNewsSource(feed=str(hn.get("feed","topstories")),timeout=float(hn.get("timeout_seconds",15))))
    feeds=config.sources.get("feeds",{})
    if feeds.get("enabled",False): result.append(FeedSource([str(url) for url in feeds.get("urls",[])],timeout=float(feeds.get("timeout_seconds",15))))
    github=config.sources.get("github",{})
    if github.get("enabled",False): result.append(GitHubSource([str(query) for query in github.get("queries",[])],token_env=str(github.get("token_env","GITHUB_TOKEN")),timeout=float(github.get("timeout_seconds",15))))
    return result


def parser() -> argparse.ArgumentParser:
    result=argparse.ArgumentParser(description="X Autopilot: Luna-only, human-approved publishing")
    result.add_argument("--config",default="config/x-autopilot.toml")
    sub=result.add_subparsers(dest="command",required=True)
    for command in ("init-db","research","generate","run","review","serve","worker","scheduler-tick"):
        sub.add_parser(command)
    verify=sub.add_parser("verify"); verify.add_argument("draft_id",type=int); verify.add_argument("--revision",type=int)
    migrate=sub.add_parser("import-sqlite"); migrate.add_argument("source", type=Path)
    return result


def build_repository(config: AppConfig):
    url = os.environ.get(config.database_url_env)
    if url:
        if not url.startswith(("postgres://", "postgresql://")):
            raise ConfigurationError("DATABASE_URL must be a PostgreSQL connection URL.")
        from .postgres import PostgresRepository
        return PostgresRepository(url)
    if config.cloud:
        raise ConfigurationError("Cloud mode requires PostgreSQL.")
    return SQLiteRepository(config.database_path)


def build_pipeline(config, repository):
    provider = config.route("luna").provider
    providers = {}
    if provider == "openai":
        providers["openai"] = OpenAIResponsesProvider()
    elif provider == "fake":
        providers["fake"] = FakeModelProvider()
    return Pipeline(config, repository, ModelGateway(config, providers), build_sources(config))


def initialize_repository(repository, attempts: int = 1):
    for attempt in range(attempts):
        try:
            repository.initialize()
            return
        except Exception:
            if attempt + 1 == attempts:
                raise ConfigurationError("Database initialization failed; check connectivity and migrations.") from None
            time.sleep(min(2 ** attempt, 5))


def main(argv: list[str] | None = None) -> int:
    args=parser().parse_args(argv)
    try:
        config=load_config(args.config); repository=build_repository(config)
        if args.command == "import-sqlite":
            from .migration import import_sqlite_to_postgres
            url = os.environ.get(config.database_url_env)
            if not url:
                raise ConfigurationError("DATABASE_URL is required for import-sqlite.")
            output = import_sqlite_to_postgres(args.source, url)
            print(json.dumps(output, sort_keys=True)); return 0
        initialize_repository(repository, attempts=5 if config.cloud else 1)
        if args.command=="init-db": print("Database migrations applied."); return 0
        pipeline=build_pipeline(config, repository)
        if args.command in {"review", "serve", "worker", "scheduler-tick"}:
            from .publishing import PublishService, XPublisher
            publisher = PublishService(repository, XPublisher(), enabled=config.publish_enabled)
            scheduler = Scheduler(config, repository, pipeline, publisher)
            if args.command == "scheduler-tick":
                print(json.dumps(scheduler.tick(), ensure_ascii=False, indent=2)); return 0
            if args.command == "worker":
                signal.signal(signal.SIGTERM, lambda *_: scheduler.stop_event.set())
                scheduler.run_forever(); return 0
            def ready():
                db_ready = repository.healthcheck()
                worker_ready = args.command != "serve" or not config.scheduler_enabled or scheduler.healthy()
                return bool(db_ready and worker_ready)
            server = create_server(repository, config.host, config.port, config=config,
                                   publisher=publisher, verify_callback=pipeline.verify_draft, readiness=ready)
            try:
                if args.command == "serve" and config.scheduler_enabled:
                    if config.cloud and config.route("luna").provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
                        raise ConfigurationError("OPENAI_API_KEY is required for cloud draft generation.")
                    scheduler.start()
                # A short request timeout lets SIGTERM stop the combined process cleanly.
                server.timeout = 1
                signal.signal(signal.SIGTERM, lambda *_: scheduler.stop_event.set())
                print(f"Review UI listening on port {server.server_port}.", flush=True)
                while not scheduler.stop_event.is_set():
                    server.handle_request()
            finally:
                scheduler.stop()
                server.server_close()
            return 0
        if args.command=="research": output=pipeline.research()
        elif args.command=="generate": output=pipeline.generate()
        elif args.command=="run": output=pipeline.run()
        else:
            draft=repository.get_draft(args.draft_id)
            if not draft: raise KeyError(args.draft_id)
            output=pipeline.verify_draft(args.draft_id,args.revision or draft.revision)
        print(json.dumps(output,ensure_ascii=False,indent=2,sort_keys=True)); return 0
    except (ValueError,KeyError,XAutopilotError) as exc:
        print(f"x-autopilot error: {exc}",file=sys.stderr); return 2
    except Exception:
        # Driver/network exception messages can contain DSNs or authorization data.
        print("x-autopilot error: operation failed; inspect configuration and service health.", file=sys.stderr); return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
