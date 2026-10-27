"""Piped native launcher protocol. Never put credentials on argv or in logs."""
import asyncio
import json
import logging
import logging.handlers
import socket
import sys
import threading

import uvicorn

from .desktop import create_desktop_app


def _logging(directory):
    handler = logging.handlers.RotatingFileHandler(
        directory / 'desktop.log', maxBytes=2 * 1024 * 1024, backupCount=3, encoding='utf8',
    )
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stderr), handler], force=True)
    # Access logs include query strings, including the one-time bootstrap token.
    logging.getLogger('uvicorn.access').disabled = True


async def _serve(app, input_stream, output_stream):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.setblocking(False)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            app, host='127.0.0.1', port=port, log_config=None, access_log=False,
            proxy_headers=False, timeout_graceful_shutdown=10,
        ))
        loop = asyncio.get_running_loop()

        def watch_parent():
            try:
                for line in input_stream:
                    if not line.strip():
                        break
            finally:
                loop.call_soon_threadsafe(setattr, server, 'should_exit', True)

        threading.Thread(target=watch_parent, name='dayframe-parent-pipe', daemon=True).start()
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            while not server.started:
                if task.done():
                    await task
                    return 1
                await asyncio.sleep(.01)
            if server.should_exit:
                await task
                return 0
            output_stream.write('DAYFRAME_READY ' + json.dumps({'port': port}) + '\n')
            output_stream.flush()
            await task
            return 0
        finally:
            if not task.done():
                server.should_exit = True
                await task


def main():
    input_stream, output_stream = sys.stdin, sys.stdout
    if input_stream is None or output_stream is None:
        return 1
    # A frozen executable inherits the Windows console codepage by default.
    if hasattr(input_stream, 'reconfigure'):
        input_stream.reconfigure(encoding='utf-8')
    if hasattr(output_stream, 'reconfigure'):
        output_stream.reconfigure(encoding='utf-8', line_buffering=True)
    # Reserve original stdout for the readiness line, even if a dependency prints.
    sys.stdout = sys.stderr
    try:
        raw = input_stream.readline(16 * 1024 + 1)
        if not raw or len(raw) > 16 * 1024:
            raise ValueError('invalid desktop launch message')
        message = json.loads(raw)
        if not isinstance(message, dict) or set(message) - {'token', 'data_home'}:
            raise ValueError('invalid desktop launch message')
        app = create_desktop_app(message.get('token'), message.get('data_home'))
        _logging(app.state.desktop.logs)
        return asyncio.run(_serve(app, input_stream, output_stream))
    except (Exception, SystemExit):
        # Do not interpolate the incoming message, token, or exception payload.
        print('DayFrame desktop startup failed; check directory permissions and whether the archive is already open.', file=sys.stderr)
        return 1
    finally:
        sys.stdout = output_stream


if __name__ == '__main__':
    raise SystemExit(main())
