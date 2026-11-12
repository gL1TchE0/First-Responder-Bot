"""
Reactive Navigation Engine for AI Vision-Based Navigation Robot
Features:
- Pure software decision logic completely independent of GPIO (100% unit testable).
- 3-zone visual risk spatial decomposition (Left, Center, Right) with ground ROI filtering.
- Strict human hazard protocol: immediately halts or veers away from people (never follows).
- Conservative fail-safe default: commands STOP unless verified clear evidence permits motion.
- Detailed audit logging with structured reasoning for every navigation decision.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import config
from ai_detector import Detection


@dataclass
class NavigationDecision:
    """Encapsulates the decision made by the perception-navigation pipeline."""
    action: str                        # FORWARD, TURN_LEFT, TURN_RIGHT, STOP
    reason: str                        # Human-readable justification for the action
    confidence: float                  # Decision confidence [0.0, 1.0]
    zone_risks: Dict[str, float] = field(default_factory=dict) # {'left': 0.0, 'center': 0.0, 'right': 0.0}
    is_emergency: bool = False         # True if triggered by safety hazard or stream failure


class ReactiveNavigator:
    """
    Evaluates visual detections across Left, Center, and Right image zones
    to produce safe, conservative skid-steer navigation commands.
    """
    def __init__(
        self,
        center_obstruction_thresh: float = config.OBSTRUCTION_THRESHOLD_CENTER,
        side_obstruction_thresh: float = config.OBSTRUCTION_THRESHOLD_SIDE,
        ground_y_min: float = config.GROUND_ROI_Y_MIN
    ):
        self.center_thresh = center_obstruction_thresh
        self.side_thresh = side_obstruction_thresh
        self.ground_y_min = ground_y_min
        self.last_action = config.ACTION_STOP

    def compute_zone_risks(
        self,
        detections: List[Detection]
    ) -> Tuple[Dict[str, float], List[Detection]]:
        """
        Calculates aggregate visual obstruction risk for Left, Center, and Right zones.
        Weights each detection by bounding box area and hazard severity.
        """
        risks = {"left": 0.0, "center": 0.0, "right": 0.0}
        ground_hazards = []

        for det in detections:
            # Check if detection reaches into ground ROI (hazards on the floor)
            if not det.is_ground_hazard:
                continue

            hazard_weight = config.HAZARD_CLASSES.get(det.label, 0.4)
            # People carry extra risk weight
            if det.is_person:
                hazard_weight = 1.5

            cx, _ = det.center
            impact = det.area_fraction * hazard_weight
            ground_hazards.append(det)

            # Assign risk to zone based on bounding box horizontal centroid
            if cx < config.ZONE_LEFT_END:
                risks["left"] += impact
            elif cx > config.ZONE_RIGHT_START:
                risks["right"] += impact
            else:
                risks["center"] += impact

            # If an object is wide and spans into center, distribute impact
            x1, _, x2, _ = det.box
            # Note: For normalized comparison, box coordinates are also normalized by caller or area
            if det.area_fraction > 0.15:
                # Large object overlaps multiple zones
                risks["center"] += impact * 0.5

        # Normalize risks to [0.0, 1.0] ceiling
        for zone in risks:
            risks[zone] = min(1.0, float(risks[zone]))

        return risks, ground_hazards

    def evaluate(
        self,
        camera_ok: bool,
        frame_age: float,
        detections: List[Detection],
        inference_ok: bool = True
    ) -> NavigationDecision:
        """
        Main decision function.
        Evaluates perception health, human presence, and spatial zone clearance.
        """
        # 1. Perception Health Fail-Safe Checks
        if not camera_ok or frame_age > config.FRAME_TIMEOUT_S:
            self.last_action = config.ACTION_STOP
            return NavigationDecision(
                action=config.ACTION_STOP,
                reason=f"FAIL-SAFE: Camera signal dropped or stale (age={frame_age*1000:.1f}ms)",
                confidence=1.0,
                zone_risks={"left": 1.0, "center": 1.0, "right": 1.0},
                is_emergency=True
            )

        if not inference_ok:
            self.last_action = config.ACTION_STOP
            return NavigationDecision(
                action=config.ACTION_STOP,
                reason="FAIL-SAFE: AI object detector inference error",
                confidence=1.0,
                zone_risks={"left": 1.0, "center": 1.0, "right": 1.0},
                is_emergency=True
            )

        # 2. Strict Human Safety Protocol
        # Check if any person is detected in the visual field
        for det in detections:
            if det.is_person and det.is_ground_hazard:
                cx, _ = det.center
                # If person is directly in center zone or filling the screen, STOP immediately
                if config.ZONE_LEFT_END <= cx <= config.ZONE_RIGHT_START or det.area_fraction >= 0.25:
                    self.last_action = config.ACTION_STOP
                    return NavigationDecision(
                        action=config.ACTION_STOP,
                        reason=f"HUMAN SAFETY PROTOCOL: Person detected in path (conf={det.confidence*100:.0f}%, area={det.area_fraction*100:.1f}%)",
                        confidence=0.95,
                        zone_risks={"left": 0.5, "center": 1.0, "right": 0.5},
                        is_emergency=True
                    )
                elif cx < config.ZONE_LEFT_END:
                    # Person on left -> veer right away from person
                    self.last_action = config.ACTION_TURN_RIGHT
                    return NavigationDecision(
                        action=config.ACTION_TURN_RIGHT,
                        reason=f"HUMAN SAFETY PROTOCOL: Turning away from person on left",
                        confidence=0.90,
                        zone_risks={"left": 0.9, "center": 0.2, "right": 0.1}
                    )
                else:
                    # Person on right -> veer left away from person
                    self.last_action = config.ACTION_TURN_LEFT
                    return NavigationDecision(
                        action=config.ACTION_TURN_LEFT,
                        reason=f"HUMAN SAFETY PROTOCOL: Turning away from person on right",
                        confidence=0.90,
                        zone_risks={"left": 0.1, "center": 0.2, "right": 0.9}
                    )

        # 3. Calculate Spatial Obstruction Risks
        risks, hazards = self.compute_zone_risks(detections)

        # 4. Evaluate Center Path Clearance
        center_is_blocked = risks["center"] >= self.center_thresh

        if center_is_blocked:
            # Center is obstructed! Evaluate side alternatives
            left_risk = risks["left"]
            right_risk = risks["right"]

            # Both sides also blocked -> DEAD END / TRAP
            if left_risk >= self.side_thresh and right_risk >= self.side_thresh:
                self.last_action = config.ACTION_STOP
                return NavigationDecision(
                    action=config.ACTION_STOP,
                    reason=f"ALL PATHS BLOCKED: Center={risks['center']:.2f}, Left={left_risk:.2f}, Right={right_risk:.2f}",
                    confidence=0.85,
                    zone_risks=risks,
                    is_emergency=False
                )

            # Choose the side with strictly lower risk
            if left_risk < right_risk:
                self.last_action = config.ACTION_TURN_LEFT
                return NavigationDecision(
                    action=config.ACTION_TURN_LEFT,
                    reason=f"OBSTACLE AVOIDANCE: Center blocked ({risks['center']:.2f}), Left opening clearer ({left_risk:.2f} < {right_risk:.2f})",
                    confidence=0.80,
                    zone_risks=risks
                )
            else:
                self.last_action = config.ACTION_TURN_RIGHT
                return NavigationDecision(
                    action=config.ACTION_TURN_RIGHT,
                    reason=f"OBSTACLE AVOIDANCE: Center blocked ({risks['center']:.2f}), Right opening clearer ({right_risk:.2f} <= {left_risk:.2f})",
                    confidence=0.80,
                    zone_risks=risks
                )

        # 5. Center is Clear: Verify Side Lateral Proximity
        # If left side is heavily crowded, apply slight right correction
        if risks["left"] > self.side_thresh and risks["left"] > risks["right"] + 0.1:
            self.last_action = config.ACTION_TURN_RIGHT
            return NavigationDecision(
                action=config.ACTION_TURN_RIGHT,
                reason=f"WALL/OBJECT BUFFERING: Left side crowded ({risks['left']:.2f}), steering toward open center",
                confidence=0.75,
                zone_risks=risks
            )

        # If right side is heavily crowded, apply slight left correction
        if risks["right"] > self.side_thresh and risks["right"] > risks["left"] + 0.1:
            self.last_action = config.ACTION_TURN_LEFT
            return NavigationDecision(
                action=config.ACTION_TURN_LEFT,
                reason=f"WALL/OBJECT BUFFERING: Right side crowded ({risks['right']:.2f}), steering toward open center",
                confidence=0.75,
                zone_risks=risks
            )

        # 6. Clear Corridor Ahead -> Permitted Forward Motion
        self.last_action = config.ACTION_FORWARD
        return NavigationDecision(
            action=config.ACTION_FORWARD,
            reason=f"CLEAR CORRIDOR: Center clear ({risks['center']:.2f} < {self.center_thresh:.2f}), forward motion permitted",
            confidence=0.90,
            zone_risks=risks
        )
