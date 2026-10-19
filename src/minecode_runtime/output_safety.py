"""Shared best-effort redaction before model-visible output is truncated."""
import re
from .diagnostics import bounded_log


def sanitize_data(value: object) -> tuple[object, bool]:
    """Keep structured values useful without detaching sensitive keys from values."""
    omitted = False

    def visit(item: object, depth: int) -> object:
        nonlocal omitted
        if depth > 32:
            omitted = True
            return "[nested data omitted]"
        if isinstance(item, dict):
            return {key: "[redacted]" if (re.fullmatch(
                r"authorization|access[_-]?token|token|password|secret|api[_-]?key", str(key), re.I)
                or isinstance(content, str) and re.fullmatch(r"username|user|player", str(key), re.I))
                    else visit(content, depth + 1) for key, content in item.items()}
        if isinstance(item, list):
            return [visit(content, depth + 1) for content in item]
        if isinstance(item, str):
            bounded, truncated = bounded_log(item)
            omitted |= truncated
            return sanitize(bounded)
        return item

    cleaned = visit(value, 0)
    return cleaned, omitted


def _private_path_tail(match: re.Match[str]) -> str:
    path = match.group(0)
    separator = '\\' if '\\' in path else '/'
    parts = re.split(r'[\\/]', path)
    start = next((index for index, part in enumerate(parts) if part.lower() == 'src'), len(parts) - 1)
    return '[local-path]' + separator + separator.join(parts[start:])


def _redact_address(match: re.Match[str]) -> str:
    address = match.group(0)
    host = address.partition(':')[0]
    if any(int(part) > 255 for part in host.split('.')):
        return address
    context = match.string[max(0, match.start() - 32):match.start()]
    if ':' not in address and re.search(r'(?i)(?:minecraft|version|mappings?|loader)\s*[=: -]*$', context):
        return address
    return '[address]'


def sanitize(text: str) -> str:
    text, _ = bounded_log(text)
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    text = re.sub(r'(?im)^.*(?:\[CHAT\]|\[Not Secure\]).*$', '[chat omitted]', text)
    text = re.sub(r'(?i)(--(?:accessToken|token|password|username)(?:=|\s+))(?:"[^"\n]*"|\x27[^\x27\n]*\x27|\S+)', r'\1[redacted]', text)
    text = re.sub(
        r'(?i)((?:authorization|access[_-]?token|token|password|secret|api[_-]?key)'
        r'\s*["\x27]?\s*[:=]\s*(?:bearer\s+)?)'
        r'("(?:\\.|[^"\\\n])*"|\x27(?:\\.|[^\x27\\\n])*\x27|[^\s,;}]+)',
        lambda m: m[1] + (m[2][0] + '[redacted]' + m[2][0] if m[2].startswith(('"', "'")) else '[redacted]'), text)
    text = re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b', '[token]', text)
    text = re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)\b', '[token]', text)
    text = re.sub(r'(?i)https?://[^\s)\]}]+', '[url]', text)
    text = re.sub(r'(?i)\b[A-Z]:[\\/][^\r\n]*?(?=:\d+(?::\d+)?(?:[: ]|$)|[\"\x27]|$)', _private_path_tail, text, flags=re.M)
    text = re.sub(r'/(?:home|Users|tmp|var|opt)/[^\s:]+', _private_path_tail, text)
    text = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', _redact_address, text)
    text = re.sub(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', '[email]', text, flags=re.I)
    text = re.sub(r'\b[\w.-]+\.(?:com|net|org|io|gg|dev|local)(?::\d+)?(?![\w.-])', '[host]', text)
    text = re.sub(r'\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b', '[uuid]', text)
    text = re.sub(r'(?i)((?:username|user|player)\s*[:=]\s*)[^\s,;]+', r'\1[name]', text)
    text = re.sub(r'(?m)\b\S+(?= (?:joined|left) the game)', '[player]', text)
    return text


