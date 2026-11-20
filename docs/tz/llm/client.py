#!/usr/bin/env python3
"""One model API call. Connection settings come from environment or a local env file."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--request', type=Path, default=Path(__file__).with_name('request.example.json'))
    args = parser.parse_args()
    settings = {}
    if args.env_file:
        settings = dict(line.split('=', 1) for line in args.env_file.read_text().splitlines()
                        if '=' in line and not line.lstrip().startswith('#'))
    settings.update({key: os.environ[key] for key in ['LLM_BASE_URL', 'LLM_MODEL', 'LLM_API_KEY', 'LLM_USER_AGENT'] if key in os.environ})
    key = settings.get('LLM_API_KEY', '')
    if not key:
        parser.error('Set LLM_API_KEY locally using the key provided by the organizer.')
    address = settings.get('LLM_BASE_URL', '')
    base = urlsplit(address)
    local = base.hostname in ('localhost', '127.0.0.1', '::1')
    if not base.hostname or base.scheme != 'https' and not (local and base.scheme == 'http') or base.username or base.password or base.query or base.fragment:
        parser.error('Use an HTTPS API base URL, or HTTP on loopback for local checks.')
    body = json.loads(args.request.read_text())
    if settings.get('LLM_MODEL'):
        body['model'] = settings['LLM_MODEL']
    request = urllib.request.Request(address.rstrip('/') + '/chat/completions', data=json.dumps(body, ensure_ascii=False).encode(), headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
        'User-Agent': settings.get('LLM_USER_AGENT', 'hackathon-client/1.0'),
    })
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=110) as response:
            status, raw = response.status, response.read(1000000)
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read(1000000)
    except urllib.error.URLError:
        print(json.dumps({'error': 'Could not connect to the API. No automatic retry was made.'}))
        return 2
    text = raw.decode('utf-8', errors='replace').replace(key, '[REDACTED]')
    try:
        data = json.loads(text)
    except ValueError:
        print(json.dumps({'http_status': status, 'error': 'Non-JSON response; check User-Agent and service availability.'}))
        return 2
    print(json.dumps({'http_status': status, 'response': data}, ensure_ascii=False, indent=2))
    return 0 if status == 200 else 1


if __name__ == '__main__':
    raise SystemExit(main())
