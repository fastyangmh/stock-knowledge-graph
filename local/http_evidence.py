"""Small HTTP evidence values shared by reviewed-source collectors.

A bytes-compatible result preserves existing parsers. Missing response headers
are explicit; metadata never invents an HTTP status for injected/offline bytes.
"""


class ResponseBytes(bytes):
    def __new__(cls, body, metadata):
        result = super().__new__(cls, body)
        result.metadata = metadata
        return result


def response_metadata(response, requested_url):
    headers = response.headers or {}
    content_type = headers.get('Content-Type')
    return {
        'http_status': getattr(response, 'status', None) or getattr(response, 'code', None),
        'content_type': content_type,
        'content_type_status': 'present' if content_type is not None else 'missing',
        'response_url': response.geturl() or requested_url,
    }


def body_metadata(body, requested_url):
    return getattr(body, 'metadata', {
        'http_status': None, 'content_type': None,
        'content_type_status': 'unavailable', 'response_url': None,
    })


def capture_response(response, requested_url, max_bytes):
    """Read bounded bytes; on overflow ValueError carries a captured prefix.

    Callers retain HTTPError semantics and decide retry/CSV policies themselves.
    """
    if max_bytes <= 0:
        raise ValueError('max_bytes must be positive')
    body = response.read(max_bytes + 1)
    declared = (response.headers or {}).get('Content-Length')
    invalid_length = declared is not None and (not declared.isascii() or not declared.isdigit())
    declared_bytes = int(declared) if declared is not None and not invalid_length else None
    oversized = len(body) > max_bytes or (declared_bytes is not None and declared_bytes > max_bytes)
    incomplete = declared_bytes is not None and len(body) < declared_bytes
    captured = ResponseBytes(body[:max_bytes], {
        **response_metadata(response, requested_url), 'body_truncated': bool(oversized or incomplete),
        'declared_bytes': declared_bytes,
    })
    if oversized or incomplete or invalid_length:
        error = ValueError('Dataset exceeds size limit' if oversized else 'Invalid/incomplete response content length')
        error.response_body = captured
        error.error_category = 'response_size' if oversized else 'response_length'
        raise error
    return captured


def capture_failure_response(response, requested_url, max_bytes):
    """Retain bounded error bytes without replacing the original HTTP error."""
    try:
        return capture_response(response, requested_url, max_bytes)
    except ValueError as exc:
        if not hasattr(exc, 'response_body'):
            raise
        return exc.response_body
