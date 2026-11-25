import csv
from io import StringIO
import json

from app.analysis.contracts import Decision, describe_review
from app.analysis.models import Review
from app.data.repository import get_dataset
from app.errors import Problem
from domain.spec import METHOD, TITLE


def approved_report(db, run):
    review = db.get(Review, run.id)
    if review is None or review.decision != Decision.approved:
        raise Problem(409, 'report_not_approved', 'A reviewer must approve the analysis')
    dataset = get_dataset(db, run.dataset_id)
    return {'run_id': run.id, 'project': TITLE, 'method': METHOD,
            'dataset': {'id': dataset.id, 'name': dataset.name, 'checksum': dataset.checksum,
                        'row_count': dataset.row_count},
            'options': run.options, 'result': run.result, 'review': describe_review(review)}


def csv_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    # Avoid spreadsheet formula evaluation for user-controlled labels and values.
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def export_table(report, name):
    table = report['result']['tables'].get(name)
    if table is None:
        raise Problem(404, 'table_not_found', 'Report table does not exist')
    output = StringIO(newline='')
    if table:
        columns = list(dict.fromkeys(key for row in table for key in row))
        writer = csv.writer(output)
        writer.writerow([csv_value(key) for key in columns])
        writer.writerows([csv_value(row.get(key)) for key in columns] for row in table)
    return output.getvalue()
