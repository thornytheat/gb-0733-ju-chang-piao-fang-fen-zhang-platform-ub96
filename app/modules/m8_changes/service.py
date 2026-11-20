from collections import Counter, defaultdict

from app.contracts import key, text, timestamp
from app.deduplicate import unique_records
from app.errors import Problem
from app.manifest import change_identifier
from app.modules.m3_scans.service import check_scan, scan_records
from app.modules.m5_refunds.rules import check_refund


def utc_stamp(value):
    """归一为 UTC 的 ISO 秒级字符串，与场次目录其余时间口径一致。"""
    from datetime import UTC, datetime
    return datetime.fromisoformat(value).astimezone(UTC).isoformat(timespec='seconds')


ENTRY_FIELDS = ('change_id', 'old_show', 'new_show', 'title', 'venue', 'effective_at', 'opens', 'closes',
                'registered_at')


def parse_registration(values, registered_at):
    """把表单/JSON 输入归一为换场登记，全部字段必填。"""
    entry = {
        'old_show': key(values['old_show']), 'new_show': key(values['new_show']),
        'title': text(values['title']), 'venue': text(values['venue']),
        'effective_at': utc_stamp(timestamp(values['effective_at'])),
        'opens': utc_stamp(timestamp(values['opens'])),
        'closes': utc_stamp(timestamp(values['closes'])),
        'registered_at': utc_stamp(registered_at),
    }
    if entry['old_show'] == entry['new_show']:
        raise Problem(422, 'CHANGE_NEW_SHOW_EXISTS', {'new_show': entry['new_show']})
    if not entry['opens'] < entry['closes'] or entry['effective_at'] > entry['opens']:
        raise Problem(422, 'CHANGE_WINDOW_INVALID',
                      {'effective_at': entry['effective_at'], 'opens': entry['opens'], 'closes': entry['closes']})
    entry['change_id'] = change_identifier('', entry)
    return entry


def validate_registration(entry, shows, changes):
    """登记写入前的全部校验；任何失败都不触碰账册。"""
    old_show, new_show = entry['old_show'], entry['new_show']
    if old_show not in shows:
        raise Problem(422, 'CHANGE_OLD_SHOW_UNKNOWN', {'old_show': old_show})
    old = shows[old_show]
    if old.get('superseded_by'):
        raise Problem(422, 'CHANGE_TARGET_SUPERSEDED', {'old_show': old_show})
    if old.get('transferred_from'):
        raise Problem(422, 'CHANGE_CHAIN_UNSUPPORTED', {'old_show': old_show})
    if old['cancelled_at']:
        raise Problem(422, 'CHANGE_TARGET_SUPERSEDED', {'old_show': old_show, 'cancelled_at': old['cancelled_at']})
    if new_show in shows:
        raise Problem(422, 'CHANGE_NEW_SHOW_EXISTS', {'new_show': new_show})
    for change in changes:
        if change['old_show'] == old_show:
            raise Problem(409, 'CHANGE_ALREADY_REGISTERED', {'change_id': change['change_id']})
        if change['new_show'] == new_show:
            raise Problem(422, 'CHANGE_NEW_SHOW_EXISTS', {'new_show': new_show})
        if change['new_show'] == old_show:
            raise Problem(422, 'CHANGE_CHAIN_UNSUPPORTED', {'old_show': old_show})
    entry['change_id'] = change_identifier('', entry)
    return entry


def apply_changes(publication, shows, rights, changes, old_scans, old_refunds):
    """生成换场后的场次目录、结转权益、调整后原分账与结转行。资金不在新旧场之间重分。

    旧场保留额 = 旧场核销锁定的应收（正常场）+ 已入账退款；其余原分账结转到新场。
    """
    if not changes:
        return shows, rights, list(publication['allocations']), []
    change_map = {change['old_show']: change for change in changes}
    rights_index = {(item['ticket'], item['show']): item for item in rights}
    catalogue = dict(shows)
    for change in changes:
        old = catalogue[change['old_show']]
        catalogue[change['old_show']] = {**old, 'superseded_by': change['new_show'],
                                         'superseded_at': change['effective_at'],
                                         'change_id': change['change_id']}
        catalogue[change['new_show']] = {
            'show': change['new_show'], 'title': change['title'], 'venue': change['venue'],
            'publication_status': 'open', 'opens': change['opens'], 'closes': change['closes'],
            'cancelled_at': None, 'line': old['line'], 'transferred_from': change['old_show'],
            'effective_at': change['effective_at'], 'change_id': change['change_id'],
        }
    scanned_pairs = {(scan['ticket'], scan['show']) for scan in old_scans}
    refunded = Counter()
    for refund in old_refunds:
        refunded[(refund['ticket'], refund['show'])] += -refund['reversal_cents']
    adjusted, carries = [], []
    for original in publication['allocations']:
        change = change_map.get(original['show'])
        if not change:
            adjusted.append(dict(original))
            continue
        pair = (original['ticket'], original['show'])
        locked = original['allocated_cents'] if pair in scanned_pairs and not shows[original['show']]['cancelled_at'] else 0
        retained = min(original['allocated_cents'], refunded[pair] + locked)
        carried = original['allocated_cents'] - retained
        adjusted.append({**original, 'retained_cents': retained, 'carried_cents': carried,
                         'allocated_cents': retained, 'change_id': change['change_id'],
                         'new_show': change['new_show']})
        if carried <= 0:
            continue
        source_right = rights_index.get(pair, {'weight': original['weight'], 'line': original['right_line']})
        carries.append({
            'ticket': original['ticket'], 'show': change['new_show'], 'old_show': original['show'],
            'venue': change['venue'], 'weight': source_right['weight'],
            'allocated_cents': carried, 'carried_cents': carried, 'retained_cents': retained,
            'floor_cents': carried, 'remainder': 0, 'denominator': source_right['weight'],
            'rank': 0, 'extra_cents': 0, 'sale_line': original['sale_line'],
            'right_line': source_right['line'], 'show_line': original['show_line'],
            'change_id': change['change_id'], 'source': 'transfer', 'line': source_right['line'],
            'end_line': source_right['line'], 'raw': [change['change_id']],
            'eligible': True,
        })
    carried_rights = [{k: item[k] for k in ('ticket', 'show', 'weight', 'eligible', 'source', 'line',
                                            'end_line', 'raw', 'change_id', 'old_show')}
                      for item in carries]
    extended_rights = [*rights, *carried_rights]
    return catalogue, extended_rights, adjusted, carries


def admit_with_changes(rows, tickets, catalogue, rights, isolates, changes):
    """换场核销：生效后旧场拒收（SCAN_SUPERSEDED），新场只认结转权益（SCAN_NO_CARRY）。"""
    change_map = {change['old_show']: change for change in changes}
    carried_pairs = {(item['ticket'], item['show']) for item in rights if item.get('source') == 'transfer'}
    candidates = unique_records(scan_records(rows, isolates), lambda item: item['scan_id'],
                                'SCAN_ID_DUPLICATE', 'SCAN_ID_CONFLICT', isolates)
    accepted = {}
    eligible_pairs = {(item['ticket'], item['show']) for item in rights if item['eligible']}
    for entry in sorted(candidates, key=lambda item: (item['scanned_at'], item['scan_id'])):
        ticket, show = entry['ticket'], entry['show']
        pair = (ticket, show)
        code = None
        if show in change_map and entry['scanned_at'] >= change_map[show]['effective_at']:
            code = 'SCAN_SUPERSEDED'
        elif show in catalogue and catalogue[show].get('transferred_from') and pair not in carried_pairs:
            code = 'SCAN_NO_CARRY'
        if code is None:
            code = check_scan(entry, tickets, catalogue, eligible_pairs, accepted)
        if code:
            earlier = accepted.get(pair)
            detail = {'retained_scan': earlier['scan_id'], 'retained_line': earlier['line']} if earlier else {}
            if code == 'SCAN_SUPERSEDED':
                detail['new_show'] = change_map[show]['new_show']
            isolates.add_record(entry, code, entry['scan_id'], **detail)
        else:
            accepted[pair] = entry
    return list(accepted.values())


def _refund_origins(publication, carries, changes):
    effective = {change['new_show']: change['effective_at'] for change in changes}
    origins = {(row['ticket'], row['show']): dict(row) for row in publication['allocations']}
    for row in carries:
        origins[(row['ticket'], row['show'])] = {
            **row, 'floor_at': effective[row['show']], 'cancelled_at': None, 'kind': 'carry'}
    return origins


def reverse_with_changes(rows, tickets, catalogue, publication, carries, changes, isolates):
    """退款冲正：旧场仍以原分账为限额；新场以结转额为限额，且不得早于换场生效。"""
    from app.modules.m5_refunds.service import refund_records
    origins = _refund_origins(publication, carries, changes)
    running, approved = {}, []
    candidates = unique_records(refund_records(rows, isolates), lambda item: item['refund_id'],
                                'REFUND_ID_DUPLICATE', 'REFUND_ID_CONFLICT', isolates)
    for event in sorted(candidates, key=lambda item: (item['refunded_at'], item['refund_id'])):
        pair = (event['ticket'], event['show'])
        origin = origins.get(pair)
        if event['ticket'] not in tickets:
            code, detail = 'TICKET_UNKNOWN', {}
        elif event['show'] not in catalogue:
            code, detail = 'SHOW_UNKNOWN', {}
        elif not origin:
            code, detail = 'REFUND_NO_ORIGINAL', {}
        elif origin.get('kind') == 'carry':
            code, detail = _check_carry_refund(event, tickets, catalogue, origin, running.get(pair, 0))
        else:
            code, detail = check_refund(event, tickets, catalogue, origins, running)
        if code:
            isolates.add_record(event, code, event['refund_id'], **detail)
            continue
        running[pair] = detail['used_cents'] + event['requested_cents']
        show = catalogue[event['show']]
        approved.append({**event, **detail, 'reversal_cents': -event['requested_cents'],
                         'cumulative_cents': running[pair],
                         'remaining_cents': detail['original_cents'] - running[pair],
                         'publication_id': publication['publication_id'],
                         'right_line': origin['right_line'], 'show_line': show['line'],
                         'cancelled_at': show['cancelled_at'],
                         'change_id': origin.get('change_id', '')})
    return approved


def _check_carry_refund(event, tickets, catalogue, origin, used):
    cap = origin['allocated_cents']
    floor = max(tickets[event['ticket']]['paid_at'], origin['floor_at'])
    if event['refunded_at'] < floor:
        return 'REFUND_TOO_EARLY', {'cancelled_at': origin['floor_at']}
    detail = {'original_cents': cap, 'used_cents': used, 'available_cents': cap - used,
              'requested_cents': event['requested_cents']}
    if event['requested_cents'] > detail['available_cents']:
        return 'REFUND_CARRY_EXCEEDED', detail
    return None, detail


def build_review(changes, publication, carries, scans, refunds):
    """换场核对视图：逐场汇总 + 逐票结转明细 + 守恒校验。

    核对范围覆盖旧场的全部原分账票：全额保留（无结转行）的票也单列，保证
    「原分账 = 旧场保留 + 结转」在页面和凭证上逐票可验。
    """
    carry_index = {(row['ticket'], row['old_show']): row for row in carries}
    scan_pairs = Counter((row['ticket'], row['show']) for row in scans)
    refund_pairs = Counter()
    for refund in refunds:
        refund_pairs[(refund['ticket'], refund['show'])] += -refund['reversal_cents']
    cards, balanced = [], True
    for change in changes:
        originals = [row for row in publication['allocations'] if row['show'] == change['old_show']]
        original_total = retained_total = carried_total = new_payable = new_refunded = 0
        entries = []
        for original in sorted(originals, key=lambda row: row['ticket']):
            old_pair = (original['ticket'], change['old_show'])
            new_pair = (original['ticket'], change['new_show'])
            carry = carry_index.get(old_pair)
            retained = carry['retained_cents'] if carry else original['allocated_cents']
            carried = carry['carried_cents'] if carry else 0
            entry_refund = refund_pairs[new_pair]
            entry_payable = carried - entry_refund if carried and scan_pairs[new_pair] else 0
            entry_pending = carried - entry_refund - entry_payable
            entries.append({'ticket': original['ticket'], 'old_show': change['old_show'],
                            'new_show': change['new_show'],
                            'original_cents': original['allocated_cents'], 'retained_cents': retained,
                            'carried_cents': carried, 'old_refunded_cents': refund_pairs[old_pair],
                            'new_refunded_cents': entry_refund, 'new_payable_cents': entry_payable,
                            'new_unsettled_cents': entry_pending,
                            'new_scan_count': scan_pairs[new_pair], 'change_id': change['change_id'],
                            'sale_line': original['sale_line'], 'right_line': original['right_line']})
            original_total += original['allocated_cents']
            retained_total += retained
            carried_total += carried
            new_payable += entry_payable
            new_refunded += entry_refund
        conserved = original_total == retained_total + carried_total
        balanced = balanced and conserved
        old_scan_count = sum(count for (ticket, show), count in scan_pairs.items()
                             if show == change['old_show'])
        cards.append({'change': {k: change[k] for k in ENTRY_FIELDS}, 'entries': entries,
                      'totals': {'original_cents': original_total, 'retained_cents': retained_total,
                                 'carried_cents': carried_total, 'new_payable_cents': new_payable,
                                 'new_refunded_cents': new_refunded, 'old_scan_count': old_scan_count,
                                 'new_scan_count': sum(item['new_scan_count'] for item in entries),
                                 'ticket_count': len(entries)},
                      'conserved': conserved})
    return {'cards': cards, 'balanced': balanced,
            'totals': {'change_count': len(changes),
                       'carried_cents': sum(card['totals']['carried_cents'] for card in cards),
                       'retained_cents': sum(card['totals']['retained_cents'] for card in cards),
                       'new_payable_cents': sum(card['totals']['new_payable_cents'] for card in cards)}}
