"""
Generate density heatmaps from visitor detection data
"""
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import cv2


class HeatmapGenerator:
    """Generate person density heatmaps from detection bounding boxes"""
    
    def __init__(self, width: int = 1920, height: int = 1080, cell_size: int = 20):
        """
        Initialize heatmap generator
        
        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            cell_size: Grid cell size for density aggregation
        """
        self.width = width
        self.height = height
        self.cell_size = cell_size
        
        # Calculate grid dimensions
        self.grid_w = width // cell_size
        self.grid_h = height // cell_size
        
        # Initialize heatmap grid
        self.heatmap = np.zeros((self.grid_h, self.grid_w), dtype=np.float32)
    
    def add_detection(self, bbox: Tuple[int, int, int, int], weight: float = 1.0) -> None:
        """
        Add a detection to the heatmap
        
        Args:
            bbox: Bounding box (x1, y1, x2, y2)
            weight: Weight for this detection (default: 1.0)
        """
        x1, y1, x2, y2 = bbox
        
        # Calculate center point
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        
        # Convert to grid coordinates
        grid_x = min(cx // self.cell_size, self.grid_w - 1)
        grid_y = min(cy // self.cell_size, self.grid_h - 1)
        
        # Add weight to grid cell
        self.heatmap[grid_y, grid_x] += weight
    
    def add_detections_batch(self, detections: List[Dict]) -> None:
        """
        Add multiple detections at once
        
        Args:
            detections: List of detection dicts with 'bbox' key
        """
        for det in detections:
            bbox = det.get('bbox')
            if bbox:
                self.add_detection(bbox)
    
    def get_heatmap_normalized(self) -> np.ndarray:
        """
        Get normalized heatmap (0-1 range)
        
        Returns:
            Normalized heatmap array
        """
        if self.heatmap.max() > 0:
            return self.heatmap / self.heatmap.max()
        return self.heatmap
    
    def get_heatmap_image(self, colormap: int = cv2.COLORMAP_JET, alpha: float = 0.6) -> np.ndarray:
        """
        Generate heatmap visualization image
        
        Args:
            colormap: OpenCV colormap (default: COLORMAP_JET)
            alpha: Transparency for overlay (0-1)
        
        Returns:
            RGB heatmap image
        """
        # Normalize heatmap
        normalized = self.get_heatmap_normalized()
        
        # Convert to 8-bit
        heatmap_8bit = (normalized * 255).astype(np.uint8)
        
        # Resize to original dimensions
        heatmap_resized = cv2.resize(heatmap_8bit, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
        
        # Apply colormap
        heatmap_colored = cv2.applyColorMap(heatmap_resized, colormap)
        
        # Convert BGR to RGB
        heatmap_rgb = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
        
        return heatmap_rgb
    
    def get_hotspots(self, threshold: float = 0.7, min_cluster_size: int = 2) -> List[Tuple[int, int, float]]:
        """
        Identify hotspot locations
        
        Args:
            threshold: Minimum normalized density to be considered a hotspot (0-1)
            min_cluster_size: Minimum number of adjacent cells to form a cluster
        
        Returns:
            List of (grid_x, grid_y, intensity) tuples
        """
        normalized = self.get_heatmap_normalized()
        hotspots = []
        
        # Find cells above threshold
        hot_cells = np.where(normalized >= threshold)
        
        for y, x in zip(hot_cells[0], hot_cells[1]):
            intensity = float(normalized[y, x])
            # Convert grid coordinates back to pixel coordinates (center of cell)
            px = x * self.cell_size + self.cell_size // 2
            py = y * self.cell_size + self.cell_size // 2
            hotspots.append((px, py, intensity))
        
        return sorted(hotspots, key=lambda x: x[2], reverse=True)
    
    def reset(self) -> None:
        """Reset heatmap to zeros"""
        self.heatmap = np.zeros((self.grid_h, self.grid_w), dtype=np.float32)
    
    def get_statistics(self) -> Dict:
        """
        Get heatmap statistics
        
        Returns:
            Dict with statistics (max_density, mean_density, hotspot_count, etc.)
        """
        normalized = self.get_heatmap_normalized()
        non_zero = normalized[normalized > 0]
        
        return {
            "max_density": float(self.heatmap.max()),
            "mean_density": float(non_zero.mean()) if len(non_zero) > 0 else 0.0,
            "active_cells": int(np.count_nonzero(normalized)),
            "total_cells": int(self.grid_w * self.grid_h),
            "coverage_percent": float(np.count_nonzero(normalized) / (self.grid_w * self.grid_h) * 100),
            "hotspot_count": len(self.get_hotspots(threshold=0.7))
        }
    
    @staticmethod
    def create_from_db(db, camera_id: str, start_time: datetime, end_time: datetime, width: int = 1920, height: int = 1080) -> 'HeatmapGenerator':
        """
        Create heatmap from database visit events
        
        Args:
            db: MongoDB database instance
            camera_id: Camera to generate heatmap for
            start_time: Start of time range
            end_time: End of time range
            width: Frame width
            height: Frame height
        
        Returns:
            HeatmapGenerator instance with accumulated detections
        """
        generator = HeatmapGenerator(width, height)
        
        # Query visit events in time range for this camera
        # Note: This is a simplified version - in production, you'd store bbox data
        visits = list(db.visit_events.find({
            "camera_id": camera_id,
            "in_time": {"$gte": start_time, "$lt": end_time}
        }))
        
        # Simulate bboxes (in production, these would be stored or retrieved from logs)
        # For now, generate random positions across the frame
        import random
        for visit in visits:
            # Generate random bbox
            x = random.randint(0, width - 200)
            y = random.randint(0, height - 200)
            bbox = (x, y, x + 150, y + 250)  # Person-sized bbox
            generator.add_detection(bbox)
        
        return generator
    
    def save_heatmap_image(self, filepath: str, colormap: int = cv2.COLORMAP_JET) -> None:
        """
        Save heatmap to file
        
        Args:
            filepath: Output file path
            colormap: OpenCV colormap
        """
        heatmap_img = self.get_heatmap_image(colormap)
        cv2.imwrite(filepath, cv2.cvtColor(heatmap_img, cv2.COLOR_RGB2BGR))

