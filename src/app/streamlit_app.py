import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from sqlalchemy.orm import Session
from datetime import datetime

from core.storage.db import get_db, init_db
from core.storage.models import Visitor, VisitEvent, ActivityEvent


def load_stats(db: Session):
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)
    total_today = db.query(VisitEvent).filter(VisitEvent.in_time >= start).count()
    active = db.query(VisitEvent).filter(VisitEvent.out_time.is_(None)).count()
    return active, total_today


def main() -> None:
    st.set_page_config(page_title="Retail Analytics Dashboard", layout="wide")
    st.title("Retail Analytics Dashboard")

    init_db()
    with get_db() as db:
        active, total_today = load_stats(db)

    col1, col2 = st.columns(2)
    col1.metric("Active Visitors", active)
    col2.metric("Total Visits Today", total_today)

    st.info("This is a minimal dashboard scaffold. Extend with zone heatmaps, journeys, charts.")


if __name__ == "__main__":
    main()


