import io
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from app.manifest import canonical, checksum
from app.modules.m7_evidence.csv_out import make_csv
from app.modules.m8_changes.service import ENTRY_FIELDS

CHANGE_FIELDS = (*ENTRY_FIELDS,)
CARRY_FIELDS = ('ticket', 'old_show', 'show', 'venue', 'weight', 'allocated_cents', 'retained_cents',
                'carried_cents', 'change_id', 'sale_line', 'right_line', 'show_line')
REVIEW_FIELDS = ('ticket', 'old_show', 'new_show', 'original_cents', 'retained_cents', 'carried_cents',
                 'old_refunded_cents', 'new_refunded_cents', 'new_payable_cents', 'new_unsettled_cents',
                 'new_scan_count', 'change_id', 'sale_line', 'right_line')
TOTALS_FIELDS = ('change_id', 'old_show', 'new_show', 'venue', 'effective_at', 'ticket_count',
                 'original_cents', 'retained_cents', 'carried_cents', 'new_refunded_cents',
                 'new_payable_cents', 'old_scan_count', 'new_scan_count')


def change_tables(snapshot):
    review = snapshot['change_review']
    entries, totals = [], []
    for card in review['cards']:
        entries.extend(card['entries'])
        totals.append({'change_id': card['change']['change_id'], 'old_show': card['change']['old_show'],
                       'new_show': card['change']['new_show'], 'venue': card['change']['venue'],
                       'effective_at': card['change']['effective_at'], **card['totals']})
    return {
        'show-changes.csv': (snapshot['changes'], CHANGE_FIELDS),
        'carry-ledger.csv': (snapshot['carries'], CARRY_FIELDS),
        'change-review.csv': (entries, REVIEW_FIELDS),
        'change-totals.csv': (totals, TOTALS_FIELDS),
    }


def build_change_bundle(snapshot):
    files = {}
    for name, (rows, fields) in change_tables(snapshot).items():
        files[f'evidence/{name}'] = make_csv(rows, fields)
    manifest = {'run_id': snapshot['manifest']['run_id'], 'book': snapshot['manifest']['book'],
                'publication_id': snapshot['manifest']['publication_id'],
                'changes_digest': snapshot['manifest']['changes_digest'],
                'change_count': len(snapshot['changes']),
                'checks': snapshot['funding']['checks'], 'review_totals': snapshot['change_review']['totals'],
                'hashes': {name: checksum(data) for name, data in files.items()}}
    files['manifest.json'] = canonical(manifest)
    stream = io.BytesIO()
    with ZipFile(stream, 'w', compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)
    return stream.getvalue()
