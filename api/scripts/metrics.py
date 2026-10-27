"""Print the metric report from `DATABASE_URL`."""

import os

from sqlalchemy import create_engine

from ebookdrop.library.metrics import MetricReader

report = MetricReader(create_engine(os.environ["DATABASE_URL"])).report()

print("day         received  ready <= 2 min  share %  open failures")
for d in report.days:
    share = "-" if d.share_percent is None else f"{d.share_percent}"
    print(
        f"{d.day}  {d.received:>8}  {d.ready_in_time:>14}  {share:>7}"
        f"  {d.open_failures:>13}"
    )
print("\nlate books: book id, received, ready")
for b in report.late:
    print(f"{b.book_id}  {b.received_at:%Y-%m-%d %H:%M:%S}  {b.ready_at:%H:%M:%S}")
print("\nrejects: day, reason, count")
for r in report.rejects:
    print(f"{r.day}  {r.reason:<20}  {r.count:>5}")
