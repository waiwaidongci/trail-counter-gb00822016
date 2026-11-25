"""Persistence and idempotent submission for clock corrections."""

from __future__ import annotations

from hashlib import sha256
import threading
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from app.clock import utc_iso
from app.data.models import ClockCorrection, Dataset, Observation
from app.data.repository import get_dataset, observation_query
from app.data.validation import normalize
from app.database import Session
from app.errors import Problem
from app.ops.audit import audit
from domain.intake.corrections import CorrectionCollision, plan_correction


# The API is served by one uvicorn process in this deployment.  A process-local
# lock gives deterministic concurrency behaviour on SQLite as well as MySQL;
# the unique clock_corrections.source_dataset_id constraint protects other
# processes/database-backed deployments.
_SUBMISSION_LOCK = threading.RLock()

IDEMPOTENCY_BODY_KEYS = (
    'idempotency_key', 'idempotencyKey', 'idempotency_token', 'idempotencyToken',
    'request_key', 'requestKey', 'request_id', 'requestId',
    'submission_id', 'submissionId',
    'client_request_id', 'clientRequestId', 'client_token', 'clientToken',
    'correction_key', 'correctionKey', 'correction_id', 'correctionId', 'nonce',
)


def idempotency_key_from_body(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for key in IDEMPOTENCY_BODY_KEYS:
        value = body.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return str(value)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def describe_dataset(dataset: Dataset) -> dict[str, Any]:
    return {
        'id': dataset.id,
        'name': dataset.name,
        'checksum': dataset.checksum,
        'row_count': dataset.row_count,
        'created_by': dataset.created_by,
        'created_at': utc_iso(dataset.created_at),
    }


def describe_correction(record: ClockCorrection, source: Dataset, result: Dataset,
                        state: str) -> dict[str, Any]:
    created = state == 'created'
    correction = {
        'id': record.id,
        'source_dataset_id': record.source_dataset_id,
        'result_dataset_id': record.result_dataset_id,
        'movement_hash': record.movement_hash,
        'move_count': record.move_count,
        'movements': record.movements,
        'idempotency_key': record.idempotency_key,
        'created_by': record.created_by,
        'created_at': utc_iso(record.created_at),
    }
    result_description = describe_dataset(result)
    source_description = describe_dataset(source)
    return {
        **result_description,
        'dataset': result_description,
        'result_dataset': result_description,
        'new_dataset': result_description,
        'new_version': result_description,
        'correction_id': record.id,
        'dataset_id': result.id,
        'new_dataset_id': result.id,
        'corrected_dataset_id': result.id,
        'corrected_version_id': result.id,
        'result_dataset_id': result.id,
        'version_id': result.id,
        'new_version_id': result.id,
        'version': result.id,
        'source_dataset_id': source.id,
        'source_id': source.id,
        'parent_id': source.id,
        'parent_dataset_id': source.id,
        'original_dataset_id': source.id,
        'base_dataset_id': source.id,
        'source_version_id': source.id,
        'created': created,
        'replayed': state == 'replayed',
        'idempotent_replay': state == 'replayed',
        'state': state,
        'idempotency_key': record.idempotency_key,
        'move_count': record.move_count,
        'movements': record.movements,
        'moved_readings': record.movements,
        'correction': correction,
        'source': source_description,
        'source_dataset': source_description,
        'source_version': source_description,
    }


def _find_existing(db, dataset_id: int, idem_key: str | None) -> ClockCorrection | None:
    if idem_key:
        by_key = db.scalar(select(ClockCorrection).where(
            ClockCorrection.idempotency_key == idem_key,
        ))
        if by_key is not None:
            return by_key
    return db.scalar(select(ClockCorrection).where(
        ClockCorrection.source_dataset_id == dataset_id,
    ))


def _replay_or_conflict(existing: ClockCorrection, dataset_id: int,
                        movement_hash: str, idem_key: str | None) -> str:
    same_source = existing.source_dataset_id == dataset_id
    same_key = idem_key is not None and existing.idempotency_key == idem_key
    same_movement = existing.movement_hash == movement_hash
    if same_movement and (same_source or same_key):
        return 'replayed'
    if same_key and not same_source:
        raise Problem(409, 'idempotency_key_conflict',
                      'This idempotency key was already used for another dataset version')
    raise Problem(409, 'correction_conflict',
                  'A different clock correction has already been accepted for this dataset version')


def submit_clock_correction(dataset_id: int, body: Any, actor: str,
                            idem_key: str | None = None) -> dict[str, Any]:
    if not isinstance(body, (dict, list)):
        raise Problem(422, 'invalid_request', 'Correction request must be a JSON object or array')
    if isinstance(body, list):
        payload: Any = {'segments': body}
    else:
        payload = body
    body_key = idempotency_key_from_body(payload)
    idem_key = (idem_key or body_key or '').strip() or None
    if idem_key and not 1 <= len(idem_key) <= 200:
        raise Problem(422, 'invalid_idempotency_key',
                      'Idempotency-Key must contain 1 to 200 characters')

    with _SUBMISSION_LOCK:
        movement_hash: str | None = None
        try:
            with Session.begin() as db:
                source = get_dataset(db, dataset_id, lock=True)
                rows = list(db.scalars(observation_query(dataset_id)))
                try:
                    plan = plan_correction(rows, payload)
                except CorrectionCollision as exc:
                    raise Problem(409, 'window_collision', str(exc), exc.conflicts) from None
                except ValueError as exc:
                    raise Problem(422, 'invalid_correction', str(exc)) from None

                movement_hash = plan.movement_hash

                # Preserve the full chain when correcting a version that was
                # itself produced by an earlier correction.
                prior = db.scalar(select(ClockCorrection).where(
                    ClockCorrection.result_dataset_id == source.id,
                ).order_by(ClockCorrection.id.desc()))
                if prior is not None:
                    prior_by_current_key = {
                        f"{item.get('entrance_id')}|{item.get('window_start')}|{item.get('counter')}": item
                        for item in (prior.movements or [])
                        if item.get('entrance_id') and item.get('window_start')
                    }
                    for movement in plan.movements:
                        earlier = prior_by_current_key.get(movement['record_key'])
                        if earlier is None:
                            continue
                        initial = earlier.get('initial_original_window_start') or earlier.get('original_window_start')
                        movement['initial_original_window_start'] = initial
                        chain = earlier.get('window_chain')
                        if not isinstance(chain, list):
                            chain = [earlier.get('original_window_start'), earlier.get('window_start')]
                        movement['window_chain'] = [*chain, movement['window_start']]

                existing = _find_existing(db, dataset_id, idem_key)
                if existing is not None:
                    state = _replay_or_conflict(existing, dataset_id, movement_hash, idem_key)
                    result = db.get(Dataset, existing.result_dataset_id)
                    return describe_correction(existing, db.get(Dataset, existing.source_dataset_id),
                                               result, state)

                checksum, pairs = normalize(plan.rows)
                result_dataset = db.scalar(select(Dataset).where(
                    Dataset.name == source.name, Dataset.checksum == checksum,
                ))
                result_existed = result_dataset is not None
                if result_dataset is None:
                    result_dataset = Dataset(
                        name=source.name, checksum=checksum, row_count=len(pairs),
                        created_by=actor,
                    )
                    db.add(result_dataset)
                    db.flush()

                if not result_existed:
                    db.execute(insert(Observation), [
                        {
                            'dataset_id': result_dataset.id,
                            'record_key': sha256(key.encode()).hexdigest(),
                            'payload': row,
                        }
                        for key, row in pairs
                    ])

                record = ClockCorrection(
                    idempotency_key=idem_key,
                    source_dataset_id=source.id,
                    result_dataset_id=result_dataset.id,
                    movement_hash=plan.movement_hash,
                    move_count=len(plan.movements),
                    request_payload=payload if isinstance(payload, (dict, list)) else {'value': payload},
                    movements=plan.movements,
                    created_by=actor,
                )
                db.add(record)
                db.flush()
                audit(db, actor, 'correction_accepted', f'dataset/{result_dataset.id}')
                return describe_correction(record, source, result_dataset, 'created')
        except IntegrityError:
            # A concurrent process won the unique-source race.  Re-read in a
            # fresh transaction and make retries idempotent.
            if movement_hash is None:
                raise
            with Session() as db:
                existing = _find_existing(db, dataset_id, idem_key)
                if existing is None:
                    raise Problem(409, 'correction_conflict',
                                  'Clock correction conflicted with another accepted change') from None
                state = _replay_or_conflict(existing, dataset_id, movement_hash, idem_key)
                source = db.get(Dataset, existing.source_dataset_id)
                result = db.get(Dataset, existing.result_dataset_id)
                return describe_correction(existing, source, result, state)


# Generic aliases.
submit_correction = submit_clock_correction
apply_and_persist = submit_clock_correction
correct_dataset_clock = submit_clock_correction
create_corrected_version = submit_clock_correction
