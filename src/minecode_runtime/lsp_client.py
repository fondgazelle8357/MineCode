"""Bounded sequential LSP transport for one trusted backend process per query."""
import asyncio
import json
import os
from pathlib import Path
from .executables import resolve_executable
from .gradle import stop_tree

MAX_MESSAGE = 4 * 1024 * 1024


class LspError(Exception):
    """Protocol/backend failure; backend text is intentionally not exposed."""


class LspClient:
    def __init__(self, root: Path, command: list[str]):
        self.root = root
        self.command = command
        self.process = None
        self.sequence = 0

    async def __aenter__(self):
        executable = resolve_executable(self.command[0], blocked_dirs=(self.root, Path.cwd()))
        if executable is None:
            raise LspError('Configured language-server executable is missing.')
        # Do not interpret batch files or arbitrary command strings through a shell.
        if Path(executable).suffix.lower() in {'.bat', '.cmd'}:
            raise LspError('Use a native executable (for example java.exe), not a batch launcher.')
        self.process = await asyncio.create_subprocess_exec(
            executable, *self.command[1:], cwd=self.root,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, start_new_session=os.name != 'nt',
            creationflags=0x08000000 if os.name == 'nt' else 0,
        )
        return self

    async def __aexit__(self, exception_type, *_):
        if self.process is not None:
            try:
                if exception_type is None and self.process.returncode is None:
                    try:
                        async with asyncio.timeout(2):
                            await self.request('shutdown', None)
                            await self.send({'method': 'exit'})
                            await self.process.wait()
                    except (TimeoutError, LspError, OSError, ValueError, asyncio.IncompleteReadError):
                        pass
            finally:
                # Also runs if an outer provider timeout cancels graceful shutdown.
                if self.process.returncode is None and not await stop_tree(self.process):
                    raise LspError('Backend process-tree cleanup could not be confirmed.')

    async def send(self, message: dict):
        assert self.process is not None and self.process.stdin is not None
        body = json.dumps({'jsonrpc': '2.0', **message}, ensure_ascii=False).encode('utf-8')
        if len(body) > MAX_MESSAGE:
            raise LspError('Outgoing language-server message exceeds the size limit.')
        self.process.stdin.write(f'Content-Length: {len(body)}\r\n\r\n'.encode('ascii') + body)
        await self.process.stdin.drain()

    async def notify(self, method: str, params: dict):
        await self.send({'method': method, 'params': params})

    async def receive(self) -> dict:
        assert self.process is not None and self.process.stdout is not None
        length = None
        total = 0
        while True:
            line = await self.process.stdout.readline()
            total += len(line)
            if not line or total > 8192:
                raise LspError('Invalid language-server header.')
            if line == b'\r\n':
                break
            key, separator, value = line.partition(b':')
            if not separator:
                raise LspError('Invalid language-server header.')
            if key.lower() == b'content-length':
                if length is not None:
                    raise LspError('Duplicate language-server content length.')
                length = int(value.strip())
        if length is None or not 0 < length <= MAX_MESSAGE:
            raise LspError('Language-server message exceeds the size limit or has no length.')
        message = json.loads(await self.process.stdout.readexactly(length))
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
            raise LspError('Invalid language-server JSON-RPC message.')
        return message

    async def request(self, method: str, params):
        self.sequence += 1
        request_id = self.sequence
        await self.send({'id': request_id, 'method': method, 'params': params})
        while True:
            message = await self.receive()
            if 'method' in message:
                if 'id' in message:
                    await self.server_request(message)
                # Notifications (including diagnostics) are not a readiness guarantee.
                continue
            if message.get('id') != request_id:
                raise LspError('Unexpected language-server response id.')
            if 'error' in message:
                raise LspError('Language-server request failed; inspect backend diagnostics locally.')
            if 'result' not in message:
                raise LspError('Language-server response has no result.')
            return message['result']

    async def server_request(self, message: dict):
        method = message['method']
        if method == 'workspace/configuration':
            params = message.get('params')
            if not isinstance(params, dict):
                raise LspError('Invalid backend configuration request.')
            items = params.get('items', [])
            if not isinstance(items, list) or len(items) > 100:
                raise LspError('Invalid backend configuration request.')
            result = [None for _ in items]
        elif method == 'workspace/workspaceFolders':
            result = [{'uri': self.root.as_uri(), 'name': self.root.name}]
        elif method == 'workspace/applyEdit':
            result = {'applied': False, 'failureReason': 'Navigation does not apply workspace edits.'}
        else:
            await self.send({'id': message['id'], 'error': {'code': -32601, 'message': 'Unsupported client request'}})
            return
        await self.send({'id': message['id'], 'result': result})
