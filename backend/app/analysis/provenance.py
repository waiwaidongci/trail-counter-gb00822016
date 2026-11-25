"""Attach clock-correction provenance to completed analysis results."""

from __future__ import annotations

from typing import Any

from domain.intake.records import record_key


def _origin_row(entry: dict[str, Any], moved: bool = True) -> dict[str, Any]:
    current = entry.get('window_start') or entry.get('new_window_start')
    original = entry.get('original_window_start') or entry.get('source_window_start')
    row = {
        'entrance_id': entry['entrance_id'],
        'counter': entry['counter'],
        'window_start': current,
        'new_window_start': current,
        'current_window_start': current,
        'count': entry.get('count'),
        'original_window_start': original,
        'original_window': original,
        'source_window_start': original,
        'old_window_start': original,
        'previous_window_start': original,
        'moved': moved and original != current,
    }
    if entry.get('record_key'):
        row['record_key'] = entry['record_key']
    if entry.get('record_hash'):
        row['record_hash'] = entry['record_hash']
    if entry.get('initial_original_window_start'):
        row['initial_original_window_start'] = entry['initial_original_window_start']
    if entry.get('window_chain'):
        row['window_chain'] = entry['window_chain']
    return row


def augment_result_with_origins(result: dict[str, Any], correction) -> dict[str, Any]:
    """Add original-window provenance without changing uncorrected results."""
    movements = list(getattr(correction, 'movements', None) or [])
    if not movements:
        return result

    tables = result.setdefault('tables', {})
    windows = tables.get('windows')
    if not isinstance(windows, list):
        windows = []
        tables['windows'] = windows

    by_current_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    provenance_rows: list[dict[str, Any]] = []
    for movement in movements:
        row = _origin_row(movement)
        provenance_rows.append(row)
        current = row['window_start']
        if current:
            by_current_key[(row['entrance_id'], current, row['counter'])] = row

    for window in windows:
        if not isinstance(window, dict):
            continue
        entrance = window.get('entrance_id')
        current = window.get('window_start')
        origins: dict[str, str] = {}
        nested: list[dict[str, Any]] = []
        for counter, suffix, count_key in (
            ('A', 'a', 'count_a'),
            ('B', 'b', 'count_b'),
        ):
            origin = by_current_key.get((entrance, current, counter))
            if origin is None:
                window[f'original_window_start_{suffix}'] = None
                continue
            original = origin['original_window_start']
            window[f'original_window_start_{suffix}'] = original
            # Compatibility aliases for consumers using "source/original".
            window[f'original_start_{suffix}'] = original
            window[f'source_window_start_{suffix}'] = original
            window[f'original_window_{suffix}'] = original
            window[f'old_window_start_{suffix}'] = original
            window[f'from_window_start_{suffix}'] = original
            origins[counter] = original
            nested.append({
                'counter': counter,
                'count': window.get(count_key, origin.get('count')),
                'window_start': current,
                'original_window_start': original,
                'moved': True,
            })
        if origins:
            window['original_windows'] = origins
            window['moved_readings'] = nested
            unique_origins = list(dict.fromkeys(origins.values()))
            # The story moves only the B side.  A scalar is convenient there;
            # if both sides moved from different windows, use the mapping.
            if len(unique_origins) == 1:
                original = unique_origins[0]
                window['original_window_start'] = original
                window['original_start'] = original
                window['source_window_start'] = original
                window['original_window'] = original
                window['old_window_start'] = original
                if len(origins) == 1:
                    window['original_counter'] = next(iter(origins))

    # A complete reading-level table makes every moved reading queryable even
    # when a future report does not expose window diagnostics.
    readings: list[dict[str, Any]] = []
    for window in windows:
        entrance = window.get('entrance_id')
        current = window.get('window_start')
        for counter, count_key in (('A', 'count_a'), ('B', 'count_b')):
            count = window.get(count_key)
            if count is None:
                continue
            origin = by_current_key.get((entrance, current, counter))
            original = origin['original_window_start'] if origin else current
            try:
                key = record_key({
                    'entrance_id': entrance, 'window_start': current,
                    'counter': counter, 'count': count,
                })
            except Exception:
                key = None
            readings.append({
                'entrance_id': entrance,
                'counter': counter,
                'window_start': current,
                'new_window_start': current,
                'current_window_start': current,
                'count': count,
                'original_window_start': original,
                'original_window': original,
                'source_window_start': original,
                'old_window_start': original,
                'previous_window_start': original,
                'moved': bool(origin),
                **({'record_key': key} if key else {}),
            })

    tables['readings'] = readings
    moved_table = [row for row in readings if row['moved']]
    tables['moved_readings'] = moved_table
    tables['reading_provenance'] = moved_table
    tables['reading_origins'] = moved_table
    tables['provenance'] = moved_table
    tables['window_provenance'] = provenance_rows
    tables['original_windows'] = provenance_rows
    tables['window_moves'] = provenance_rows
    tables['window_corrections'] = provenance_rows
    tables['clock_corrections'] = provenance_rows
    tables['corrections'] = provenance_rows
    tables['correction_movements'] = provenance_rows
    tables['corrected_windows'] = provenance_rows
    tables['original_window_readings'] = provenance_rows
    tables['origins'] = provenance_rows

    correction_summary = {
        'id': getattr(correction, 'id', None),
        'source_dataset_id': getattr(correction, 'source_dataset_id', None),
        'result_dataset_id': getattr(correction, 'result_dataset_id', None),
        'movement_hash': getattr(correction, 'movement_hash', None),
        'move_count': getattr(correction, 'move_count', len(movements)),
        'movements': provenance_rows,
    }
    result['correction'] = correction_summary
    result['corrections'] = [correction_summary]
    result['moved_readings'] = moved_table
    result['original_windows'] = provenance_rows
    result['reading_provenance'] = moved_table
    return result
