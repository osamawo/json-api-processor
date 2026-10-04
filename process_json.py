"""Select nested JSON fields from a local file or a read-only HTTP API. Python 3.10+."""
import argparse
import csv
import ipaddress
import json
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

MAX_BYTES = 5 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect refused. Use the final API URL explicitly.')


def load_json(source=None, url=None):
    if (source is None) == (url is None):
        raise ValueError('Choose exactly one source: file or URL.')
    if source is not None:
        with Path(source).open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
    else:
        parsed = urlsplit(url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('URLs with credentials, queries or fragments are not supported.')
        try:
            loopback = parsed.hostname == 'localhost' or ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            loopback = False
        if parsed.scheme != 'https' and not (parsed.scheme == 'http' and loopback):
            raise ValueError('Use HTTPS; HTTP is allowed only for a local demo API.')
        request = urllib.request.Request(url, headers={'Accept': 'application/json'})
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=10) as response:
            raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('Input exceeds the 5 MiB demo limit.')
    return json.loads(raw.decode('utf-8-sig'))


def at_path(value, path):
    if not path:
        return value
    for part in path.split('.'):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def cell_value(value):
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + value
    return value


def process(payload, destination: Path, fields, records_path='', required=(), dedupe=()):
    destination = destination.resolve()
    if destination.exists():
        raise ValueError('Output already exists. Choose a new output directory.')
    records = at_path(payload, records_path)
    if not isinstance(records, list):
        raise ValueError('Records path must point to a JSON array.')
    headers = [header for header, _ in fields]
    if not fields or len(set(headers)) != len(headers) or any(not h or not p for h, p in fields):
        raise ValueError('Fields must have unique, nonempty output headers and JSON paths.')
    if (set(required) | set(dedupe)) - set(headers):
        raise ValueError('Required/dedupe columns must be declared fields.')
    output, rejected, duplicates, seen = [], [], [], set()
    escaped = 0
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            rejected.append({'record': index, 'reason': 'record is not an object'})
            continue
        row = {header: at_path(record, path) for header, path in fields}
        absent = [header for header in required if row[header] is None or row[header] == '']
        if absent:
            rejected.append({'record': index, 'reason': 'missing required fields', 'fields': absent})
            continue
        if dedupe:
            identity = tuple(json.dumps(row[h], sort_keys=True, ensure_ascii=False) for h in dedupe)
            if identity in seen:
                duplicates.append(index)
                continue
            seen.add(identity)
        escaped += sum(isinstance(v, str) and cell_value(v) != v for v in row.values())
        output.append({header: cell_value(value) for header, value in row.items()})
    report = {'input_records': len(records), 'exported_records': len(output),
              'rejected_records': rejected, 'duplicate_record_indexes': duplicates,
              'csv_formula_cells_escaped': escaped, 'fields': dict(fields),
              'records_path': records_path, 'required': list(required), 'dedupe': list(dedupe)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='json_process_', dir=destination.parent) as staging:
        work = Path(staging) / 'result'
        work.mkdir()
        with (work / 'data.csv').open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, fieldnames=[cell_value(h) for h in headers])
            writer.writeheader()
            # Header values can be escaped too, without changing field selection.
            for row in output:
                writer.writerow({cell_value(k): v for k, v in row.items()})
        (work / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        work.rename(destination)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--input', type=Path)
    source.add_argument('--url')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--records-path', default='')
    parser.add_argument('--field', action='append', required=True, metavar='HEADER:JSON.PATH')
    parser.add_argument('--required', action='append', default=[])
    parser.add_argument('--dedupe', action='append', default=[])
    args = parser.parse_args()
    try:
        fields = []
        for rule in args.field:
            header, sep, path = rule.partition(':')
            if not sep:
                raise ValueError('Each field must use HEADER:JSON.PATH.')
            fields.append((header, path))
        payload = load_json(args.input, args.url)
        report = process(payload, args.output, fields, args.records_path, args.required, args.dedupe)
    except Exception as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f'Output: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
