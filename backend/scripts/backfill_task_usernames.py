#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv


backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
load_dotenv(backend_dir / ".env", override=True)

from app.core.database import SessionLocal  # noqa: E402
from app.models import EvaluationTask  # noqa: E402


def backfill_null_usernames(target_username: str, dry_run: bool) -> int:
    db = SessionLocal()
    try:
        query = db.query(EvaluationTask).filter(EvaluationTask.username.is_(None))
        count = query.count()
        print(f"待回填任务数: {count}")

        if count == 0 or dry_run:
            if dry_run:
                print("dry-run 模式，未执行更新。")
            return count

        updated = query.update(
            {EvaluationTask.username: target_username},
            synchronize_session=False,
        )
        db.commit()
        print(f"已回填任务数: {updated}")
        print(f"回填用户名: {target_username}")
        return int(updated)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="回填 evaluation_tasks.username 为空的旧任务")
    parser.add_argument(
        "--username",
        default="admin",
        help="回填使用的用户名，默认 admin",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅统计待回填数量，不执行更新",
    )
    args = parser.parse_args()

    backfill_null_usernames(
        target_username=args.username,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
