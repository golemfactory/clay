from pathlib import Path

import enum
import sqlite3

from typing import List, Optional


class SubtaskStatus(enum.Enum):
    PENDING = 'pending'
    COMPUTING = 'computing'
    VERIFYING = 'verifying'
    FINISHED = 'finished'


def get_db_connection(work_dir: Path):
    return sqlite3.connect(str(work_dir / 'task.db'))


def init_tables(db, subtasks_count: int) -> None:
    with db:
        db.execute('CREATE TABLE subtask_status(num int, status text)')
        values = list(zip(
            range(subtasks_count),
            [SubtaskStatus.PENDING.value] * subtasks_count,
        ))
        db.executemany(
            'INSERT INTO subtask_status VALUES (?,?)',
            values,
        )


def set_subtask_status(db, subtask_num: int, status: SubtaskStatus):
    with db:
        db.execute(
            'UPDATE subtask_status SET status = ? WHERE num = ?',
            (status.value, subtask_num),
        )


def get_subtasks_with_status(db, status: SubtaskStatus) -> List[int]:
    cursor = db.cursor()
    cursor.execute(
        "SELECT num FROM subtask_status WHERE status = ?",
        (status.value,),
    )
    rows = cursor.fetchall()
    return list(map(lambda r: r[0], rows))


def get_next_pending_subtask(db) -> Optional[int]:
    cursor = db.cursor()
    cursor.execute(
        'SELECT num FROM subtask_status WHERE status = ? LIMIT 1',
        (SubtaskStatus.PENDING.value,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def string_to_frames(s):
    frames = []
    after_split = s.split(";")
    for i in after_split:
        inter = i.split("-")
        if len(inter) == 1:
            # single frame (e.g. 5)
            frames.append(int(inter[0]))
        elif len(inter) == 2:
            inter2 = inter[1].split(",")
            # frame range (e.g. 1-10)
            if len(inter2) == 1:
                start_frame = int(inter[0])
                end_frame = int(inter[1]) + 1
                frames += list(range(start_frame, end_frame))
            # every nth frame (e.g. 10-100,5)
            elif len(inter2) == 2:
                start_frame = int(inter[0])
                end_frame = int(inter2[0]) + 1
                step = int(inter2[1])
                frames += list(range(start_frame, end_frame, step))
            else:
                raise ValueError("Wrong frame step")
        else:
            raise ValueError("Wrong frame range")
    return sorted(frames)
