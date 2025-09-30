import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

from core.storage.db import get_db, init_db
from core.storage.models import Visitor, VisitEvent, ActivityEvent


def load_stats(db: Session):
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)

    # Unique visitors today
    q = (
        db.query(Visitor.id)
        .join(VisitEvent, VisitEvent.visitor_id == Visitor.id)
        .filter(VisitEvent.in_time >= start)
        .distinct()
    )
    unique_today = q.count()

    # Active visitors with timeout
    timeout_seconds = int(os.environ.get("VISITOR_TIMEOUT_SECONDS", "30"))
    cutoff = datetime.utcnow() - timedelta(seconds=timeout_seconds)
    active = (
        db.query(Visitor.id)
        .join(VisitEvent, VisitEvent.visitor_id == Visitor.id)
        .filter(VisitEvent.out_time.is_(None))
        .filter(Visitor.last_seen_at >= cutoff)
        .distinct()
        .count()
    )
    return active, unique_today

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

        # Build dwell dataframe for today
        if visitors:
            rows = []
            start_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            for v in visitors:
                if v.first_seen_at >= start_day:
                    dwell = max(0.0, (v.last_seen_at - v.first_seen_at).total_seconds())
                    rows.append({
                        "visitor_id": v.global_id,
                        "first_seen_at": v.first_seen_at,
                        "last_seen_at": v.last_seen_at,
                        "dwell_seconds": dwell,
                        "dwell_minutes": dwell / 60.0,
                    })
            dwell_df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["visitor_id","first_seen_at","last_seen_at","dwell_seconds","dwell_minutes"])
        else:
            dwell_df = pd.DataFrame(columns=["visitor_id","first_seen_at","last_seen_at","dwell_seconds","dwell_minutes"])

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Active", active)
    col2.metric("🧑‍🤝‍🧑 Unique Today", total_today)
    if len(dwell_df) > 0:
        avg_time = dwell_df["dwell_seconds"].mean()
        p50 = int(np.percentile(dwell_df["dwell_seconds"], 50))
        p95 = int(np.percentile(dwell_df["dwell_seconds"], 95))
        col3.metric("⏱️ Avg Dwell", f"{int(avg_time//60)}m {int(avg_time%60)}s")
        col4.metric("P95 Dwell", f"{p95//60}m {p95%60}s")
    else:
        col3.metric("⏱️ Avg Dwell", "0s")
        col4.metric("P95 Dwell", "0s")

    st.markdown("---")
    
    # Visitor time spent table
    st.subheader("⏰ Time Spent by Each Visitor (ReID-based)")
    
    if len(dwell_df) > 0:
        visitor_data = []
        for _, r in dwell_df.sort_values("first_seen_at", ascending=False).iterrows():
            time_spent = calculate_time_spent(r["first_seen_at"], r["last_seen_at"])
            status = "🟢 In Premises" if r["first_seen_at"] == r["last_seen_at"] else "🔴 Exited"
            visitor_data.append({
                "Visitor ID": r["visitor_id"],
                "Entry Time": r["first_seen_at"].strftime("%Y-%m-%d %H:%M:%S"),
                "Last Seen": r["last_seen_at"].strftime("%Y-%m-%d %H:%M:%S"),
                "Time Spent": time_spent,
                "Dwell (min)": round(r["dwell_minutes"], 2),
                "Status": status
            })
        st.dataframe(visitor_data, use_container_width=True)
        
        # Download button
        df = pd.DataFrame(visitor_data)
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Report",
            data=csv,
            file_name="visitor_time_report.csv",
            mime="text/csv"
        )

        # Time series plots
        st.subheader("📈 Time Series (Today)")
        try:
            ts_df = dwell_df.set_index("first_seen_at").sort_index()
            # Arrivals per 5 min
            arrivals = ts_df["visitor_id"].resample("5T").count().rename("arrivals")
            # Average dwell per 5 min
            avg_dwell = ts_df["dwell_minutes"].resample("5T").mean().rename("avg_dwell_min")
            st.line_chart(pd.concat([arrivals, avg_dwell], axis=1).fillna(0))
            st.bar_chart(arrivals)
        except Exception:
            st.info("Not enough data yet for time series plot.")

        # Campus dwell insights
        st.subheader("🏫 Campus Dwell Insights")
        try:
            exited = dwell_df[dwell_df["dwell_minutes"].notna()].copy()
            if len(exited) > 0:
                # Histogram of dwell minutes (5-min bins)
                max_minutes = exited["dwell_minutes"].max()
                if pd.isna(max_minutes):
                    max_minutes = 0
                max_minutes = int(np.ceil(max_minutes))
                max_minutes = max(5, max_minutes)
                bin_edges = list(range(0, max_minutes + 5, 5))
                hist_counts, edges = np.histogram(exited["dwell_minutes"], bins=bin_edges)
                bin_labels = [f"{int(edges[i])}-{int(edges[i+1])}" for i in range(len(edges)-1)]
                st.write("Dwell time distribution (5-min bins):")
                st.bar_chart(pd.DataFrame({"count": hist_counts}, index=bin_labels))

                # Top dwellers (top 20)
                st.write("Top dwellers (exited visitors)")
                top = exited.sort_values("dwell_minutes", ascending=False).head(20)[["visitor_id", "dwell_minutes"]]
                st.bar_chart(top.set_index("visitor_id"))
            else:
                st.info("No completed visits yet to show campus dwell insights.")
        except Exception:
            st.info("Not enough data yet for campus dwell insights.")

    # Server-side dwell stats API (aggregated)
    st.subheader("🧮 Dwell Summary (Server)")
    try:
        import requests
        resp = requests.get("http://localhost:8000/dwell-stats", timeout=3)
        if resp.ok:
            data = resp.json()
            colA, colB, colC = st.columns(3)
            colA.metric("Unique Today", data.get("total_visitors", 0))
            colB.metric("Avg Dwell", f"{int(data.get('avg_dwell_seconds',0)//60)}m {int(data.get('avg_dwell_seconds',0)%60)}s")
            colC.metric("P95 Dwell", f"{int(data.get('p95_dwell_seconds',0)//60)}m {int(data.get('p95_dwell_seconds',0)%60)}s")
        else:
            st.info("/dwell-stats not available yet.")
    except Exception:
        st.info("Unable to reach API for dwell summary.")
    else:
        st.info("No visitors detected yet. Start the pipeline to begin tracking!")


if __name__ == "__main__":
    main()


