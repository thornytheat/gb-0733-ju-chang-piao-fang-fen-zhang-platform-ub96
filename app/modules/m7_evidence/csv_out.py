import csv
import io
import json


def spreadsheet_value(value):
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    if isinstance(value, str) and (value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n'))):
        return "'" + value
    return value


def make_csv(rows, fields):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(fields)
    for row in rows:
        writer.writerow([spreadsheet_value(row.get(field)) for field in fields])
    return stream.getvalue().encode('utf-8-sig')
