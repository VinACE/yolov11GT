# Multi-Camera Geometry Gating - Design Note

Purpose: reduce cross-camera ID mistakes (splits/merges) by constraining matches using camera layout knowledge and overlap timing.

Scope (phase 1 - low risk, additive):
- Camera adjacency graph: which cameras can logically hand-off to which.
- Temporal overlap gating: only allow cross-camera reassignment if time since last seen ≤ handoff window.
- Overlap zones (optional): simple polygons per camera defining overlapping FoVs; boosts trust for handoffs occurring inside overlapping areas.

Data model (config file, e.g. YAML/JSON):
- cameras: ["cam1", "cam2", ...]
- adjacency:
  - cam1: [cam2]
  - cam2: [cam1, cam3]
- handoff_seconds: default 10 (per-edge override allowed)
- overlap_zones (optional):
  - cam1: [{ name: "north_overlap", polygon: [[x,y], ...] }]
  - cam2: [{ name: "north_overlap", polygon: [[x,y], ...] }]

Gating logic (informative, non-blocking to start):
1) When a local track on camera B wants to reuse a global_id last seen on camera A:
   - Check adjacency: A ∈ adjacency[B]. If not, down-rank or reject.
   - Check time gap: (now - last_seen[A]) ≤ handoff_seconds(A→B). Otherwise, down-rank.
   - If both B and A have overlap_zones with the same name and the detection is inside that polygon on both views (projected/approx.), add a score bonus.

Integration plan:
- Phase 1: Load config, compute a gating weight (bonus/penalty) added to the composite similarity used by the reranker. Log decisions in `reid_assignment_log.jsonl`.
- Phase 2: Make gating hard (reject) for impossible handoffs; keep soft for borderline.

Runtime configuration:
- GEOMETRY_CONFIG_PATH=/app/config/geometry.yaml (optional)
- GEOMETRY_GATING_WEIGHT=0.05 (bonus) / GEOMETRY_PENALTY=0.05 (penalty)

Testing:
- Synthetic handoffs between adjacent vs non-adjacent cameras.
- A/B compare split/merge rates before/after gating.


