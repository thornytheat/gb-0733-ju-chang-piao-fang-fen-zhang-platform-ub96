def split_cents(total, weights):
    """最大余数法，余数相同按场次键升序分发。"""
    denominator = sum(weights.values())
    shares = {show: divmod(total * value, denominator) for show, value in weights.items()}
    leftover = total - sum(floor for floor, _ in shares.values())
    order = sorted(shares, key=lambda show: (-shares[show][1], show))
    for rank, show in enumerate(order, 1):
        floor, remainder = shares[show]
        extra = int(rank <= leftover)
        yield show, {
            'allocated_cents': floor + extra, 'floor_cents': floor, 'remainder': remainder,
            'denominator': denominator, 'rank': rank, 'extra_cents': extra,
        }
