from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.settings import settings


class Base(DeclarativeBase):
    pass


if settings.database_url.startswith('sqlite'):
    memory = (
        settings.database_url in {'sqlite://', 'sqlite:///:memory:'}
        or ':memory:' in settings.database_url
        or 'mode=memory' in settings.database_url
    )
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={'check_same_thread': False},
        **({'poolclass': StaticPool} if memory else {}),
    )
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)
