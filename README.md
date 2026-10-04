# JSON & API Data Processor

## Project overview
A small Python CLI that maps selected fields from a JSON array to CSV and reports rejected or duplicate records.
This is an original personal portfolio demo. The included JSON is synthetic; API tests use a temporary local HTTP server.

## Features

- Read UTF-8 JSON from a local file or a read-only HTTP GET endpoint.
- Select a nested array and map nested object fields to named CSV columns.
- Check required fields, reject non-object records and optionally keep the first matching dedupe key.
- Preserve Unicode and zero values; export nested values as JSON text when selected.
- Produce UTF-8-BOM CSV and a JSON processing report.
- Escape formula-like CSV strings and refuse existing output directories.

## Requirements

Python 3.14 was tested on Windows. The CLI uses only the standard library; pytest is needed for tests.
`requirements.lock.txt` records the exact tested test dependencies.

## Installation

Open PowerShell in the repository folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
```

On macOS/Linux, create the environment with `python3` and use `.venv/bin/python`
instead of `.\.venv\Scripts\python.exe`. Recreate environments after cloning.

## Usage

```powershell
.\.venv\Scripts\python.exe process_json.py --input examples/response.json --output output/demo --records-path data.items --field id:id --field name:profile.name --field city:profile.city --field total:stats.total --required id --dedupe id
.\.venv\Scripts\python.exe process_json.py --help
```

`--field HEADER:JSON.PATH` maps a field. Repeat `--field`, `--required` or `--dedupe` as needed.
For an authorized API, replace `--input` with `--url` and its endpoint. HTTPS is required except for loopback HTTP testing.
The included tests exercise a real temporary loopback server; no external API account or key is needed.
Choose a new output directory. Input errors and existing output return exit code 1.

## Example input/output

`examples/response.json` contains six synthetic records under `data.items`. An excerpt:

```json
{"data":{"items":[{"id":"001","profile":{"name":"Sample A","city":"Lab City"},"stats":{"total":12}}]}}
```

For the full included sample, the command above exports **4 of 6 records**, removes one duplicate
and rejects one record with a missing ID. Output files: `data.csv` and `report.json`.
A CSV excerpt:

```csv
id,name,city,total
001,Sample A,Lab City,12
002,Sample B,,0
```

The report includes record counts, rejected-record reasons, duplicate indexes and the selected mapping.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Eight tests cover mappings, required fields, deduplication, Unicode/zero values, malformed JSON,
size limits, disallowed URL credentials, bad paths/headers, output preservation, real local HTTP GET,
redirect rejection and CLI failures. Some tests check several related conditions.

## Limitations

- Maximum input size: 5 MiB; request timeout: 10 seconds.
- GET only. No authentication, redirects, URL query parameters, pagination or retry policy.
- Dotted paths traverse object fields, not array indexes or keys containing literal dots.
- Validation checks structure and required-field presence, not a complete typed JSON schema.
- Only access APIs you are authorized to use; do not pass client data without permission.

## Technologies used

Python standard library (`json`, `csv`, `urllib`, `pathlib`), pytest and a local HTTP test server.
Private `input/` files and generated `output/` files are ignored by Git; reviewed synthetic examples are in `examples/`.
