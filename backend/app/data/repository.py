from hashlib import sha256

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from app.data.models import Dataset, Observation
from app.data.validation import normalize
from app.database import Session
from app.errors import Problem
from app.ops.audit import audit


def import_dataset(name: str, rows: list[dict], actor: str):
    name = name.strip()
    if not 1 <= len(name) <= 120:
        raise Problem(422, 'invalid_name', 'Dataset name must contain 1 to 120 characters')
    checksum, pairs = normalize(rows)
    match = select(Dataset).where(Dataset.name == name, Dataset.checksum == checksum)
    try:
        with Session.begin() as db:
            previous = db.scalar(match)
            if previous:
                return previous, False
            dataset = Dataset(name=name, checksum=checksum, row_count=len(pairs), created_by=actor)
            db.add(dataset)
            db.flush()
            db.execute(insert(Observation), [
                {'dataset_id': dataset.id, 'record_key': sha256(key.encode()).hexdigest(), 'payload': payload}
                for key, payload in pairs
            ])
            audit(db, actor, 'dataset_imported', f'dataset/{dataset.id}')
            return dataset, True
    except IntegrityError:
        with Session() as db:
            previous = db.scalar(match)
            if previous:
                return previous, False
        raise


def get_dataset(db, dataset_id: int, lock: bool = False) -> Dataset:
    query = select(Dataset).where(Dataset.id == dataset_id)
    dataset = db.scalar(query.with_for_update() if lock else query)
    if dataset is None:
        raise Problem(404, 'dataset_not_found', 'Dataset does not exist')
    return dataset


def observation_query(dataset_id: int):
    return select(Observation.payload).where(Observation.dataset_id == dataset_id).order_by(Observation.id)
