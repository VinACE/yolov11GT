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

def calculate_time_spent(entry: datetime, exit: datetime) -> str:
    """Calculate and format time spent"""
    if entry == exit:
        return "Just entered"
    
    time_diff = exit - entry
    total_seconds = time_diff.total_seconds()
    
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def main() -> None:
    st.set_page_config(page_title="Retail Analytics Dashboard", layout="wide")
    st.title("🏬 Retail Analytics Dashboard")

    init_db()
    with get_db() as db:
        active, total_today = load_stats(db)
        visitors = db.query(Visitor).order_by(Visitor.first_seen_at.desc()).all()

    # Top metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("👥 Active Visitors", active)
    col2.metric("📊 Total Visits Today", total_today)
    
    # Calculate average time spent
    if visitors:
        total_time = sum([(v.last_seen_at - v.first_seen_at).total_seconds() for v in visitors])
        avg_time = total_time / len(visitors)
        avg_minutes = int(avg_time // 60)
        avg_seconds = int(avg_time % 60)
        col3.metric("⏱️ Avg Time Spent", f"{avg_minutes}m {avg_seconds}s")

    st.markdown("---")
    
    # Visitor time spent table
    st.subheader("⏰ Time Spent by Each Visitor")
    
    if visitors:
        visitor_data = []
        for v in visitors:
            time_spent = calculate_time_spent(v.first_seen_at, v.last_seen_at)
            status = "🟢 In Premises" if v.first_seen_at == v.last_seen_at else "🔴 Exited"
            
            visitor_data.append({
                "Visitor ID": v.global_id,
                "Entry Time": v.first_seen_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Last Seen": v.last_seen_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Time Spent": time_spent,
                "Status": status
            })
        
        st.dataframe(visitor_data, use_container_width=True)
        
        # Download button
        import pandas as pd
        df = pd.DataFrame(visitor_data)
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Report",
            data=csv,
            file_name="visitor_time_report.csv",
            mime="text/csv"
        )
    else:
        st.info("No visitors detected yet. Start the pipeline to begin tracking!")


if __name__ == "__main__":
    main()


