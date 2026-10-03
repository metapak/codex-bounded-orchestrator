"""Launch the unified hub or its isolated adapter worker."""
import argparse
import sys
import webbrowser

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--adapter' in argv:
        # This branch must execute before UI/server setup, including frozen builds.
        index = argv.index('--adapter')
        from . import adapters
        worker = getattr(adapters, 'worker_main', None) or getattr(adapters, 'adapter_main', None)
        if worker is None:
            raise RuntimeError('Adapter worker entry point unavailable')
        return worker(argv[index + 1:])
    parser = argparse.ArgumentParser(description='Ustam local orchestration hub')
    parser.add_argument('--state-dir')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    from .core import Hub
    from .server import UstamServer
    hub = Hub(args.state_dir)
    try:
        from .jobs import JobManager
        hub.jobs = JobManager(hub.store.directory, hub.adapters)
    except ImportError:
        pass
    server = UstamServer(('127.0.0.1', args.port), hub)
    print(server.origin, flush=True)
    if not args.no_browser:
        webbrowser.open(server.origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
