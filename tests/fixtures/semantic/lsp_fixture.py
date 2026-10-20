"""Original protocol simulator, NOT a Java/Kotlin semantic engine."""
import json
import sys
import time

mode = sys.argv[1] if len(sys.argv) > 1 else 'normal'
uri = ''
source = ''


def send(value):
    data = json.dumps({'jsonrpc': '2.0', **value}, ensure_ascii=False).encode('utf-8')
    sys.stdout.buffer.write(f'Content-Length: {len(data)}\r\n\r\n'.encode() + data)
    sys.stdout.buffer.flush()


def read():
    length = 0
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            raise SystemExit
        if line == b'\r\n':
            break
        if line.lower().startswith(b'content-length:'):
            length = int(line.split(b':')[1])
    return json.loads(sys.stdin.buffer.read(length))


while True:
    request = read()
    method = request.get('method')
    if method == 'initialize':
        if mode == 'oversize':
            sys.stdout.buffer.write(b'Content-Length: 999999999\r\n\r\n')
            sys.stdout.buffer.flush()
            continue
        send({'id': 'edit', 'method': 'workspace/applyEdit', 'params': {'edit': {'changes': {}}}})
        assert read()['result']['applied'] is False
        send({'id': request['id'], 'result': {'serverInfo': {'name': 'protocol fixture'}, 'capabilities': {
            'textDocumentSync': {'openClose': True, 'change': 1},
            'definitionProvider': {}, 'referencesProvider': True,
            'implementationProvider': mode != 'unsupported', 'callHierarchyProvider': True}}})
    elif method == 'textDocument/didOpen':
        uri = request['params']['textDocument']['uri']
        source = request['params']['textDocument']['text']
    elif method in {'initialized', 'textDocument/didClose'}:
        pass
    elif method == 'shutdown':
        if mode == 'slow_shutdown':
            time.sleep(10)
        send({'id': request['id'], 'result': None})
    elif method == 'exit':
        break
    elif method:
        if mode == 'slow':
            time.sleep(10)
        if mode == 'error':
            send({'id': request['id'], 'error': {'code': -32603, 'message': 'token=DO_NOT_EXPOSE'}})
            continue
        span = {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 1}}
        location = {'uri': uri, 'range': span}
        symbol = {'name': source.strip(), 'kind': 6, 'uri': uri, 'range': span,
                  'selectionRange': span, 'data': {'token': 'DO_NOT_EXPOSE'}}
        if method == 'textDocument/prepareCallHierarchy':
            value = [symbol]
        elif method.startswith('callHierarchy/'):
            assert request['params']['item']['data']['token'] == 'DO_NOT_EXPOSE'
            value = [{'from' if method.endswith('incomingCalls') else 'to': symbol, 'fromRanges': [span]}]
        elif method == 'textDocument/definition':
            value = [{'targetUri': uri, 'targetRange': span, 'targetSelectionRange': span}]
        else:
            if method == 'textDocument/references':
                assert request['params']['context']['includeDeclaration'] is False
            value = [location] * (60 if mode == 'many' else 1)
        send({'id': request['id'], 'result': value})
