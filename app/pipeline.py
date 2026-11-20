from collections import Counter
from time import perf_counter

from app.config import REPORT_ZONE, RULE_VERSION
from app.errors import Problem
from app.manifest import changes_digest, input_manifest, publication_digest, utc_now
from app.modules.m1_intake.service import intake
from app.modules.m2_rights.service import resolve
from app.modules.m3_scans.service import admit
from app.modules.m4_allocation.service import allocate
from app.modules.m5_refunds.service import preserve_approved, reverse
from app.modules.m6_reconcile.service import count_sources, reconcile
from app.modules.m8_changes.service import (
    admit_with_changes,
    apply_changes,
    build_review,
    reverse_with_changes,
)
from app.records import Isolations
from app.sources import SourceSet


def _business_events(rows, isolates, key_field):
    """源行守恒口径：同业务键的重复/冲突组只算一个有效事件，其余进隔离。"""
    seen, events, isolated_lines = set(), 0, {(row['source'], row['line']) for row in isolates.rows}
    for row in rows:
        value = row.values[key_field]
        if value in seen:
            continue
        seen.add(value)
        if (row.source, row.line) not in isolated_lines:
            events += 1
    return events


def scans_event_count(rows, isolates):
    return _business_events(rows, isolates, 'scan_id')


def refunds_event_count(rows, isolates):
    return _business_events(rows, isolates, 'refund_id')


def compute(book, run_id, files, changes=None, publication=None, head=None):
    started = perf_counter()
    changes = changes or []
    inputs = input_manifest(files)
    isolates = Isolations()
    sources = SourceSet(files, isolates)
    tickets = intake(sources.rows('tickets.csv'), isolates)
    shows, rights = resolve(sources.rows('shows.csv'), sources.rows('rights.csv'), tickets, isolates)
    digest = publication_digest(tickets, shows, rights)
    if publication is None:
        allocations, unassigned = allocate(tickets, shows, rights)
        publication = {'publication_id': 'pub_' + digest[:20], 'digest': digest, 'origin_run': run_id,
                       'allocations': allocations, 'unassigned': unassigned,
                       'inputs': [item for item in inputs if item['source'] in {'tickets.csv', 'shows.csv', 'rights.csv'}]}
    elif publication['digest'] != digest:
        raise Problem(409, 'PUBLICATION_CHANGED', {'publication_id': publication['publication_id']})

    scan_rows = list(sources.rows('scans.csv'))
    refund_rows = list(sources.rows('refunds.csv'))
    if changes:
        # 第一遍只用于确定旧场已核销/已退款的保留事实，隔离结果不进正式账册。
        preflight = Isolations()
        old_scans = admit(scan_rows, tickets, shows, rights, preflight)
        old_refunds = reverse(refund_rows, tickets, shows, publication, preflight)
        catalogue, extended_rights, adjusted, carries = apply_changes(
            publication, shows, rights, changes, old_scans, old_refunds)
        scans = admit_with_changes(scan_rows, tickets, catalogue, extended_rights, isolates, changes)
        refunds = reverse_with_changes(refund_rows, tickets, catalogue, publication,
                                       carries, changes, isolates)
        allocations_for_ledger = adjusted + carries
    else:
        catalogue, extended_rights, carries = shows, rights, []
        adjusted = list(publication['allocations'])
        allocations_for_ledger = publication['allocations']
        scans = admit(scan_rows, tickets, catalogue, extended_rights, isolates)
        refunds = reverse(refund_rows, tickets, catalogue, publication, isolates)
    if head:
        preserve_approved(head['refunds'], refunds)
    accepted = {'tickets.csv': len(tickets), 'shows.csv': len(shows), 'rights.csv': len(rights),
                'scans.csv': scans_event_count(scan_rows, isolates),
                'refunds.csv': refunds_event_count(refund_rows, isolates)}
    quarantine = sorted(isolates.rows, key=lambda row: (row['source'], row['line']))
    counts = count_sources(sources.stats, accepted, quarantine)
    accounts = reconcile(tickets, catalogue, scans, refunds, allocations_for_ledger, counts,
                         publication, changes, adjusted, carries)
    if not accounts['balanced']:
        raise Problem(409, 'RECONCILE_FAILED', accounts['checks'])
    review = build_review(changes, publication, carries, scans, refunds)
    manifest = {
        'run_id': run_id, 'book': book, 'rule_version': RULE_VERSION, 'inputs': inputs,
        'publication_id': publication['publication_id'], 'origin_run': publication['origin_run'],
        'changes_digest': changes_digest(changes) if changes else None,
        'change_count': len(changes),
        'parameters': {'time_zone': REPORT_ZONE, 'currency': 'CNY', 'money_unit': '分',
                       'tie_break': 'show_ascending', 'scan_window': '[opens,closes)'},
        'generated_at': utc_now(), 'duration_ms': round((perf_counter() - started) * 1000),
        'previous_run': head['manifest']['run_id'] if head else None,
    }
    return {'manifest': manifest, 'publication': publication, 'quarantine': quarantine, 'funding': accounts,
            'tickets': list(tickets.values()), 'shows': list(catalogue.values()), 'rights': extended_rights,
            'scans': scans, 'refunds': refunds, 'changes': changes, 'change_review': review,
            'carries': carries, 'adjusted_allocations': adjusted,
            'reason_counts': dict(sorted(Counter(row['code'] for row in quarantine).items()))}
