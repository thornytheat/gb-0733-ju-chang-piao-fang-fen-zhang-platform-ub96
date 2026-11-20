from collections import defaultdict


def unique_records(records, key, duplicate_code, conflict_code, isolates):
    """完全相同的业务记录留最早来源，矛盾组全隔离。"""
    groups = defaultdict(list)
    for record, row in records:
        groups[key(record)].append((record, row))
    for group_key, entries in groups.items():
        label = '/'.join(group_key) if isinstance(group_key, tuple) else group_key
        first, origin = entries[0]
        if any(other != first for other, _ in entries[1:]):
            for _, row in entries:
                isolates.add(row, conflict_code, label, conflicting_lines=[item.line for _, item in entries[:20]],
                             conflicting_count=len(entries))
            continue
        for _, row in entries[1:]:
            isolates.add(row, duplicate_code, label, retained_line=origin.line)
        yield {**first, **origin.evidence()}
