import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

from core.storage.mongo import get_mongo_db


def load_stats_mongo(db):
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)
    # Fix for MongoDB 8: Filter out null values explicitly
    # MongoDB 8 includes null in distinct() results, MongoDB 6 excluded them
    distinct_visitor_ids = db.visit_events.distinct(
        "visitor_id", 
        {"in_time": {"$gte": start}, "visitor_id": {"$exists": True, "$ne": None}}
    )
    # Additional Python-level filtering for empty strings
    unique_today = len([v for v in distinct_visitor_ids if v])
    timeout_seconds = int(os.environ.get("VISITOR_TIMEOUT_SECONDS", "30"))
    cutoff = datetime.utcnow() - timedelta(seconds=timeout_seconds)
    recent_visitors = set(v["_id"] for v in db.visitors.find({"last_seen_at": {"$gte": cutoff}}, {"_id": 1}))
    active = db.visit_events.count_documents({"out_time": None, "visitor_id": {"$in": list(recent_visitors)}})
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

    db = get_mongo_db()
    active, total_today = load_stats_mongo(db)
    visitors = list(db.visitors.find().sort("first_seen_at", -1))

    # Build dwell dataframe for today
    if visitors:
        rows = []
        start_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        for v in visitors:
            if v.get("first_seen_at") and v.get("first_seen_at") >= start_day:
                dwell = max(0.0, (v.get("last_seen_at") - v.get("first_seen_at")).total_seconds())
                rows.append({
                    "visitor_id": v.get("global_id"),
                    "first_seen_at": v.get("first_seen_at"),
                    "last_seen_at": v.get("last_seen_at"),
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
    
    # Gender distribution with face crops
    st.markdown("---")
    st.subheader("🚻 Gender Distribution")
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    males = db.visitors.count_documents({"gender": "male"})
    females = db.visitors.count_documents({"gender": "female"})
    unknown = db.visitors.count_documents({"gender": "unknown"})
    col1.metric("👨 Males", males)
    col2.metric("👩 Females", females)
    col3.metric("👤 Unknown", unknown)
    
    # Face gallery by gender
    if males + females + unknown > 0:
        st.markdown("#### 👤 Visitor Face Gallery")
        
        tab1, tab2, tab3, tab4 = st.tabs(["👨 Males", "👩 Females", "👤 Unknown", "👤 All"])
        
        with tab1:
            male_visitors = list(db.visitors.find({"gender": "male"}).limit(20))
            if male_visitors:
                cols = st.columns(min(5, len(male_visitors)))
                for idx, visitor in enumerate(male_visitors):
                    with cols[idx % 5]:
                        crop_path = visitor.get("face_crop_path")
                        gid = visitor.get("global_id", "")
                        if crop_path:
                            # Convert relative path to absolute path
                            if not os.path.isabs(crop_path):
                                crop_path = f"/app/{crop_path}"
                            if os.path.exists(crop_path):
                                st.image(crop_path, caption=gid, width=100, use_container_width=False)
                            else:
                                st.write(f"{gid} (crop not found)")
                        else:
                            st.write(gid)
            else:
                st.info("No male visitors yet")
        
        with tab2:
            female_visitors = list(db.visitors.find({"gender": "female"}).limit(20))
            if female_visitors:
                cols = st.columns(min(5, len(female_visitors)))
                for idx, visitor in enumerate(female_visitors):
                    with cols[idx % 5]:
                        crop_path = visitor.get("face_crop_path")
                        gid = visitor.get("global_id", "")
                        if crop_path:
                            # Convert relative path to absolute path
                            if not os.path.isabs(crop_path):
                                crop_path = f"/app/{crop_path}"
                            if os.path.exists(crop_path):
                                st.image(crop_path, caption=gid, width=100, use_container_width=False)
                            else:
                                st.write(f"{gid} (crop not found)")
                        else:
                            st.write(gid)
            else:
                st.info("No female visitors yet")
        
        with tab3:
            unknown_visitors = list(db.visitors.find({"gender": "unknown"}).limit(20))
            if unknown_visitors:
                cols = st.columns(min(5, len(unknown_visitors)))
                for idx, visitor in enumerate(unknown_visitors):
                    with cols[idx % 5]:
                        crop_path = visitor.get("face_crop_path")
                        gid = visitor.get("global_id", "")
                        if crop_path:
                            # Convert relative path to absolute path
                            if not os.path.isabs(crop_path):
                                crop_path = f"/app/{crop_path}"
                            if os.path.exists(crop_path):
                                st.image(crop_path, caption=gid, width=100, use_container_width=False)
                            else:
                                st.write(f"{gid} (crop not found)")
                        else:
                            st.write(gid)
            else:
                st.info("No unknown gender visitors yet")
        
        with tab4:
            all_visitors = list(db.visitors.find().limit(30))
            if all_visitors:
                cols = st.columns(6)
                for idx, visitor in enumerate(all_visitors):
                    with cols[idx % 6]:
                        crop_path = visitor.get("face_crop_path")
                        gender = visitor.get("gender", "unknown")
                        gender_icon = "👨" if gender == "male" else "👩" if gender == "female" else "👤"
                        gid = visitor.get('global_id', '')
                        if crop_path:
                            # Convert relative path to absolute path
                            if not os.path.isabs(crop_path):
                                crop_path = f"/app/{crop_path}"
                            if os.path.exists(crop_path):
                                st.image(crop_path, caption=f"{gender_icon} {gid}", width=80, use_container_width=False)
                            else:
                                st.write(f"{gender_icon} {gid} (crop not found)")
                        else:
                            st.write(f"{gender_icon} {gid}")
            else:
                st.info("No visitors yet")

    st.markdown("---")
    
    # Entry/Exit Balance Monitor
    st.subheader("🚪 Entry/Exit Balance Monitor")
    try:
        today = datetime.utcnow().date()
        start = datetime(today.year, today.month, today.day)
        all_visits = list(db.visit_events.find({"in_time": {"$gte": start}}))
        
        total_entries = len(all_visits)
        total_exits = len([v for v in all_visits if v.get('out_time') is not None])
        currently_inside = total_entries - total_exits
        balance_ratio = total_exits / total_entries if total_entries > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📥 Entries", total_entries)
        col2.metric("📤 Exits", total_exits)
        col3.metric("👤 Inside Now", currently_inside)
        
        if 0.85 <= balance_ratio <= 1.15:
            balance_status = "🟢 Normal"
        elif balance_ratio < 0.85:
            balance_status = "🟡 More Entries"
            st.warning(f"⚠️ {currently_inside} people may still be inside")
        else:
            balance_status = "🔴 Imbalanced"
            st.error("⚠️ More exits than entries - check system!")
        
        col4.metric("⚖️ Balance", f"{balance_ratio:.1%}", delta=balance_status)
    except Exception as e:
        st.info(f"Entry/Exit balance: {e}")
    
    # Camera Health Monitor
    st.markdown("---")
    st.subheader("📹 Camera Health Status")
    try:
        import requests
        resp = requests.get("http://localhost:8000/system/camera-health", timeout=3)
        if resp.ok:
            health_data = resp.json()
            st.write(f"**{health_data['overall_status']}**")
            
            if health_data['cameras']:
                cols = st.columns(len(health_data['cameras']))
                for idx, cam in enumerate(health_data['cameras']):
                    with cols[idx]:
                        st.metric(f"📷 {cam['camera_id']}", cam['status'])
                        st.caption(f"Last: {cam['last_detection']}")
                        st.caption(f"Recent: {cam['detections_last_5min']}")
                        st.caption(f"ReID: {cam['reid_match_rate']:.0%}")
        else:
            st.info("Camera health API unavailable")
    except Exception as e:
        st.info(f"Camera health: {e}")
    
    # Peak Hours Analysis
    st.markdown("---")
    st.subheader("⏰ Peak Hours Analysis")
    try:
        import requests
        resp = requests.get("http://localhost:8000/analytics/peak-hours", timeout=3)
        if resp.ok:
            peak_data = resp.json()
            peak_df = pd.DataFrame(peak_data['peak_hours'])
            
            if not peak_df.empty and peak_df['visitor_count'].sum() > 0:
                peak_df = peak_df.set_index('hour')
                
                col1, col2, col3 = st.columns(3)
                col1.metric("🔥 Busiest Hour", peak_data['busiest_hour'])
                col2.metric("😴 Quietest Hour", peak_data['quietest_hour'])
                col3.metric("Peak Visitors", int(peak_df['visitor_count'].max()))
                
                st.write("**Visitor Arrivals by Hour**")
                st.bar_chart(peak_df['visitor_count'])
                
                st.write("**Average Dwell Time by Hour (minutes)**")
                st.line_chart(peak_df['avg_dwell_minutes'])
            else:
                st.info("No peak hour data yet")
        else:
            st.info("Peak hours API unavailable")
    except Exception as e:
        st.info(f"Peak hours: {e}")
    
    st.markdown("---")
    
    # Visitor time spent table with gender
    st.subheader("⏰ Time Spent by Each Visitor (ReID-based)")
    
    if len(dwell_df) > 0:
        visitor_data = []
        for _, r in dwell_df.sort_values("first_seen_at", ascending=False).iterrows():
            time_spent = calculate_time_spent(r["first_seen_at"], r["last_seen_at"])
            status = "🟢 In Premises" if r["first_seen_at"] == r["last_seen_at"] else "🔴 Exited"
            
            # Get gender from database
            visitor_doc = db.visitors.find_one({"global_id": r["visitor_id"]})
            gender = visitor_doc.get("gender", "unknown") if visitor_doc else "unknown"
            gender_icon = "👨" if gender == "male" else "👩" if gender == "female" else "👤"
            
            visitor_data.append({
                "Visitor ID": r["visitor_id"],
                "Gender": f"{gender_icon} {gender.capitalize()}",
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
            arrivals = ts_df["visitor_id"].resample("5T").count().rename("arrivals")
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

    # Hourly presence analytics
    st.markdown("---")
    st.subheader("🕒 Hourly Presence (Today)")
    try:
        import requests
        resp = requests.get("http://localhost:8000/presence-hourly", timeout=3)
        if resp.ok:
            data = resp.json()
            buckets = data.get("buckets", [])
            if buckets:
                ph_df = pd.DataFrame(buckets)
                ph_df["hour"] = pd.to_datetime(ph_df["hour_start"]).dt.strftime("%H:00")
                cols = st.columns(2)
                with cols[0]:
                    st.write("Presence minutes per hour")
                    st.bar_chart(ph_df.set_index("hour")["presence_minutes"])
                with cols[1]:
                    st.write("Arrivals and unique visitors per hour")
                    st.line_chart(ph_df.set_index("hour")[["arrivals", "unique_visitors"]])
            else:
                st.info("No hourly data available yet.")
        else:
            st.info("/presence-hourly not available yet.")
    except Exception:
        st.info("Unable to reach API for hourly presence.")
    else:
        st.info("No visitors detected yet. Start the pipeline to begin tracking!")
    
    # Phase 2 Features
    st.markdown("---")
    st.header("🔍 Phase 2 Advanced Analytics")
    
    tab1, tab2, tab3, tab4 = st.tabs(["🚨 Anomalies", "🗺️ Visitor Journey", "📊 Weekly Trends", "📥 Export Reports"])
    
    with tab1:
        st.subheader("🚨 Real-Time Anomaly Detection")
        try:
            import requests
            resp = requests.get("http://localhost:8000/analytics/anomalies?hours=24", timeout=5)
            if resp.ok:
                anomaly_data = resp.json()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Anomalies", anomaly_data['total_count'])
                col2.metric("Critical", anomaly_data['critical_count'], delta="🔴")
                col3.metric("Warnings", anomaly_data['total_count'] - anomaly_data['critical_count'], delta="🟡")
                
                if anomaly_data['anomalies']:
                    st.write("**Recent Anomalies:**")
                    for anomaly in anomaly_data['anomalies'][:10]:
                        with st.expander(f"{anomaly['severity']} - {anomaly['type'].replace('_', ' ').title()} ({anomaly['timestamp'][:16]})"):
                            st.write(f"**Description:** {anomaly['description']}")
                            if anomaly.get('camera_id'):
                                st.write(f"**Camera:** {anomaly['camera_id']}")
                            if anomaly.get('zone'):
                                st.write(f"**Zone:** {anomaly['zone']}")
                            if anomaly.get('value'):
                                st.write(f"**Value:** {anomaly['value']}")
                else:
                    st.success("✅ No anomalies detected - all systems normal")
            else:
                st.info("Anomaly detection API unavailable")
        except Exception as e:
            st.info(f"Anomaly detection: {e}")
    
    with tab2:
        st.subheader("🗺️ Visitor Journey Tracker")
        
        # Get list of visitors
        try:
            visitor_id = st.text_input("Enter Visitor ID (e.g., PERSON_001):", "")
            
            if visitor_id and st.button("Track Journey"):
                import requests
                resp = requests.get(f"http://localhost:8000/analytics/visitor-journey/{visitor_id}", timeout=5)
                if resp.ok:
                    journey_data = resp.json()
                    
                    col1, col2 = st.columns(2)
                    col1.metric("Cameras Visited", journey_data['total_cameras'])
                    col2.metric("Zones Visited", journey_data['total_zones'])
                    
                    st.write("**Path Timeline:**")
                    for i, step in enumerate(journey_data['path'], 1):
                        st.write(f"{i}. 📹 **{step['camera_id']}** at {step['timestamp'][:19]}")
                        if step.get('zone'):
                            st.write(f"   └─ 🏷️ Zone: {step['zone']}")
                else:
                    st.error(f"Visitor {visitor_id} not found")
        except Exception as e:
            st.info(f"Journey tracker: {e}")
    
    with tab3:
        st.subheader("📊 Weekly Trend Analysis")
        try:
            import requests
            resp = requests.get("http://localhost:8000/analytics/weekly-trend", timeout=5)
            if resp.ok:
                trend_data = resp.json()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Week Total", trend_data['week_total'])
                col2.metric("Avg Dwell Time", f"{trend_data['week_avg_dwell']:.1f} min")
                col3.metric("Trend", trend_data['trend'])
                
                if trend_data['days']:
                    trend_df = pd.DataFrame(trend_data['days'])
                    trend_df['date'] = pd.to_datetime(trend_df['date'])
                    
                    st.write("**Daily Visitor Count:**")
                    st.line_chart(trend_df.set_index('date')['total_visitors'])
                    
                    st.write("**Daily Statistics:**")
                    st.dataframe(trend_df[['date', 'total_visitors', 'avg_dwell_minutes', 'peak_hour', 'busiest_camera']])
                else:
                    st.info("Not enough data for trend analysis")
            else:
                st.info("Weekly trend API unavailable")
        except Exception as e:
            st.info(f"Weekly trends: {e}")
    
    with tab4:
        st.subheader("📥 Export Reports")
        st.write("Download analytics data as CSV files:")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**📊 Visitor Reports:**")
            if st.button("Export Visitors CSV"):
                st.markdown("[Download Visitors Report](http://localhost:8000/export/visitors.csv)")
            
            if st.button("Export Peak Hours CSV"):
                st.markdown("[Download Peak Hours Report](http://localhost:8000/export/peak-hours.csv)")
        
        with col2:
            st.write("**📹 System Reports:**")
            if st.button("Export Camera Health CSV"):
                st.markdown("[Download Camera Health](http://localhost:8000/export/camera-health.csv)")
            
            if st.button("Export Zone Stats CSV"):
                st.markdown("[Download Zone Statistics](http://localhost:8000/export/zone-stats.csv)")
        
        st.info("💡 Tip: Click the buttons above to generate download links. Files will be named with today's date.")


if __name__ == "__main__":
    main()

