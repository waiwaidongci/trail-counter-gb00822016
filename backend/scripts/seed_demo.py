import json

from sqlalchemy import func, select

from app.auth.models import Account
from app.auth.passwords import make_hash
from app.auth.roles import Role
from app.data.models import Dataset, Observation
from app.data.repository import import_dataset
from app.database import Session
from domain.spec import SEED_NAME, seed


DEMO_PASSWORD = 'Local-demo-2026!'


def load_demo():
    with Session.begin() as db:
        for role in Role:
            email = f'{role.value}@demo.local'
            if db.get(Account, email) is None:
                db.add(Account(email=email, role=role, password_hash=make_hash(DEMO_PASSWORD)))
    dataset, _ = import_dataset(SEED_NAME, seed(), 'seed')
    with Session() as db:
        return {'seed_dataset_id': dataset.id, 'seed_checksum': dataset.checksum,
                'seed_rows': dataset.row_count,
                'total_accounts': db.scalar(select(func.count()).select_from(Account)),
                'total_datasets': db.scalar(select(func.count()).select_from(Dataset)),
                'total_observations': db.scalar(select(func.count()).select_from(Observation))}


if __name__ == '__main__':
    print(json.dumps(load_demo(), ensure_ascii=False, sort_keys=True))
