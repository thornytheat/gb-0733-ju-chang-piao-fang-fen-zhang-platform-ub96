import io
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from app.manifest import canonical, checksum
from app.modules.m7_evidence.csv_out import make_csv
from app.reasons import REASONS

ORIGIN = ('source', 'line', 'end_line', 'raw')
ALLOCATION = ('ticket', 'show', 'venue', 'weight', 'allocated_cents', 'floor_cents', 'remainder', 'denominator',
              'rank', 'extra_cents', 'sale_line', 'right_line', 'show_line')
MONEY = ('allocated_cents', 'refunded_cents', 'net_cents', 'payable_cents', 'unsettled_cents')


def evidence_tables(snapshot):
    pub = snapshot['publication']
    accounts = snapshot['funding']
    quarantine = [{**row, 'reason': REASONS[row['code']]} for row in snapshot['quarantine']]
    return {
        'tickets.csv': (snapshot['tickets'], ('ticket', 'paid_at', 'paid_cents', 'status', *ORIGIN)),
        'rights.csv': (snapshot['rights'], ('ticket', 'show', 'weight', 'eligible', *ORIGIN)),
        'show-definitions.csv': (snapshot['shows'], ('show', 'title', 'venue', 'publication_status', 'opens',
                                                     'closes', 'cancelled_at', *ORIGIN)),
        'scans.csv': (snapshot['scans'], ('scan_id', 'ticket', 'show', 'scanned_at', 'gate', *ORIGIN)),
        'original-allocation.csv': (pub['allocations'], ALLOCATION),
        'unassigned.csv': (pub['unassigned'], ('ticket', 'unsettled_cents', 'sale_line', 'code')),
        'refunds.csv': (snapshot['refunds'], ('refund_id', 'ticket', 'show', 'refunded_at', 'cancelled_at',
                                             'publication_id', 'right_line', 'show_line', 'original_cents',
                                             'used_cents', 'requested_cents', 'reversal_cents',
                                             'cumulative_cents', 'remaining_cents', *ORIGIN)),
        'settlement.csv': (accounts['ledger'], (*ALLOCATION, 'refunded_cents', 'net_cents', 'payable_cents',
                                               'unsettled_cents', 'code', 'scan_id', 'scan_line', 'cancelled_at')),
        'show-totals.csv': (accounts['shows'], ('show', 'title', 'venue', 'cancelled_at', 'scan_count', 'shares',
                                               *MONEY, 'gap_cents', 'difference_cents')),
        'venue-totals.csv': (accounts['venues'], ('venue', 'shows', 'scan_count', *MONEY)),
        'ticket-totals.csv': (accounts['tickets'], ('ticket', 'sale_line', 'paid_cents', 'refunded_cents',
                                                   'net_cents', 'payable_cents', 'unsettled_cents', 'difference_cents')),
        'source-counts.csv': (accounts['sources'], ('source', 'encoding', 'status', 'rows', 'headers', 'blank',
                                                   'accepted', 'isolated', 'difference')),
        'quarantine.csv': (quarantine, ('key', 'code', 'reason', *ORIGIN, 'detail')),
    }


def build_bundle(snapshot, current, original):
    files = {f'source/{name}': data for name, data in current.items()}
    files.update({f'original-source/{item["source"]}': original[item['source']]
                  for item in snapshot['publication']['inputs']})
    for name, (rows, fields) in evidence_tables(snapshot).items():
        files[f'evidence/{name}'] = make_csv(rows, fields)
    manifest = {**snapshot['manifest'], 'original_inputs': snapshot['publication']['inputs'],
                'checks': snapshot['funding']['checks'], 'totals': snapshot['funding']['totals'],
                'reason_counts': snapshot['reason_counts'], 'hashes': {name: checksum(data) for name, data in files.items()}}
    files['manifest.json'] = canonical(manifest)
    stream = io.BytesIO()
    with ZipFile(stream, 'w', compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)
    return stream.getvalue()
