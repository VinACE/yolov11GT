"""
Zone-based analytics tracking for visitor behavior
"""
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
from pathlib import Path

from core.utils.geometry import is_point_in_polygon


class ZoneTracker:
    """Tracks visitor interactions with defined zones"""
    
    def __init__(self, zones_config_path: str = "/app/config/zones.json"):
        self.zones = self._load_zones(zones_config_path)
        # Track which zone each visitor is currently in
        self.visitor_current_zone: Dict[str, Tuple[str, str, datetime]] = {}  # visitor_id -> (zone_name, camera_id, entry_time)
        # Track zone transition history
        self.zone_transitions: List[Dict] = []
        # Track dwell time per zone per visitor
        self.zone_dwell_times: Dict[str, Dict[str, float]] = {}  # visitor_id -> {zone_name: total_seconds}
    
    def _load_zones(self, config_path: str) -> Dict:
        """Load zone definitions from JSON config"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Failed to load zones config: {e}")
            return {}
    
    def get_zone_for_point(self, camera_id: str, x: int, y: int) -> Optional[str]:
        """Determine which zone a point belongs to"""
        point = (x, y)
        
        for zone_name, zone_cameras in self.zones.items():
            if camera_id not in zone_cameras:
                continue
            
            polygon = zone_cameras[camera_id]
            if is_point_in_polygon(point, polygon):
                return zone_name
        
        return None
    
    def update_visitor_position(self, visitor_id: str, camera_id: str, bbox: Tuple[int, int, int, int], timestamp: datetime) -> Optional[Dict]:
        """
        Update visitor position and track zone transitions
        
        Args:
            visitor_id: Unique visitor identifier
            camera_id: Camera where visitor was detected
            bbox: Bounding box (x1, y1, x2, y2)
            timestamp: Detection timestamp
        
        Returns:
            Dict with transition info if zone changed, None otherwise
        """
        # Calculate center point of bounding box
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        
        # Determine current zone
        current_zone = self.get_zone_for_point(camera_id, center_x, center_y)
        
        # Check if visitor is tracked
        if visitor_id not in self.visitor_current_zone:
            # First time seeing this visitor
            if current_zone:
                self.visitor_current_zone[visitor_id] = (current_zone, camera_id, timestamp)
                self.zone_dwell_times.setdefault(visitor_id, {})
                self.zone_dwell_times[visitor_id][current_zone] = 0.0
            return None
        
        # Get previous zone
        prev_zone, prev_camera, entry_time = self.visitor_current_zone[visitor_id]
        
        # Check for zone transition
        if current_zone != prev_zone:
            # Calculate dwell time in previous zone
            dwell_seconds = (timestamp - entry_time).total_seconds()
            
            # Update dwell time accumulator
            if prev_zone:
                if visitor_id not in self.zone_dwell_times:
                    self.zone_dwell_times[visitor_id] = {}
                self.zone_dwell_times[visitor_id][prev_zone] = \
                    self.zone_dwell_times[visitor_id].get(prev_zone, 0.0) + dwell_seconds
            
            # Record transition
            transition = {
                "visitor_id": visitor_id,
                "from_zone": prev_zone,
                "to_zone": current_zone,
                "from_camera": prev_camera,
                "to_camera": camera_id,
                "timestamp": timestamp,
                "dwell_seconds": dwell_seconds
            }
            self.zone_transitions.append(transition)
            
            # Update current zone
            if current_zone:
                self.visitor_current_zone[visitor_id] = (current_zone, camera_id, timestamp)
                self.zone_dwell_times.setdefault(visitor_id, {})
                if current_zone not in self.zone_dwell_times[visitor_id]:
                    self.zone_dwell_times[visitor_id][current_zone] = 0.0
            else:
                # Visitor left all zones
                del self.visitor_current_zone[visitor_id]
            
            return transition
        
        return None
    
    def get_visitor_zone_summary(self, visitor_id: str) -> Dict:
        """Get summary of zones visited by a visitor"""
        dwell_times = self.zone_dwell_times.get(visitor_id, {})
        current_zone_info = self.visitor_current_zone.get(visitor_id)
        
        return {
            "visitor_id": visitor_id,
            "zones_visited": list(dwell_times.keys()),
            "zone_dwell_times": dwell_times,
            "total_dwell_seconds": sum(dwell_times.values()),
            "current_zone": current_zone_info[0] if current_zone_info else None,
            "current_camera": current_zone_info[1] if current_zone_info else None
        }
    
    def get_zone_statistics(self) -> Dict[str, Dict]:
        """Get statistics per zone"""
        zone_stats = {}
        
        for visitor_id, zones in self.zone_dwell_times.items():
            for zone_name, dwell_seconds in zones.items():
                if zone_name not in zone_stats:
                    zone_stats[zone_name] = {
                        "unique_visitors": set(),
                        "total_dwell_seconds": 0.0,
                        "visit_count": 0
                    }
                
                zone_stats[zone_name]["unique_visitors"].add(visitor_id)
                zone_stats[zone_name]["total_dwell_seconds"] += dwell_seconds
                zone_stats[zone_name]["visit_count"] += 1
        
        # Convert sets to counts
        for zone_name in zone_stats:
            zone_stats[zone_name]["unique_visitors"] = len(zone_stats[zone_name]["unique_visitors"])
            zone_stats[zone_name]["avg_dwell_seconds"] = (
                zone_stats[zone_name]["total_dwell_seconds"] / zone_stats[zone_name]["visit_count"]
                if zone_stats[zone_name]["visit_count"] > 0 else 0.0
            )
        
        return zone_stats
    
    def get_transition_matrix(self) -> Dict[str, Dict[str, int]]:
        """Get zone transition matrix (from_zone -> to_zone -> count)"""
        matrix = {}
        
        for transition in self.zone_transitions:
            from_zone = transition["from_zone"] or "OUTSIDE"
            to_zone = transition["to_zone"] or "OUTSIDE"
            
            if from_zone not in matrix:
                matrix[from_zone] = {}
            
            matrix[from_zone][to_zone] = matrix[from_zone].get(to_zone, 0) + 1
        
        return matrix
    
    def finalize_visitor(self, visitor_id: str, timestamp: datetime) -> None:
        """Finalize tracking for a visitor who left (close their zone dwell time)"""
        if visitor_id in self.visitor_current_zone:
            zone, camera, entry_time = self.visitor_current_zone[visitor_id]
            dwell_seconds = (timestamp - entry_time).total_seconds()
            
            if visitor_id not in self.zone_dwell_times:
                self.zone_dwell_times[visitor_id] = {}
            
            self.zone_dwell_times[visitor_id][zone] = \
                self.zone_dwell_times[visitor_id].get(zone, 0.0) + dwell_seconds
            
            del self.visitor_current_zone[visitor_id]

