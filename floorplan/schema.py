"""
floorplan/schema.py
Data contracts for Input and Output JSON schemas using Pydantic.
Owner: P3 (Input and Glue)
"""

import re
from typing import List, Optional, Tuple, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# 1. Input Schema Definitions
# ============================================================================

class Setbacks(BaseModel):
    front: int = Field(default=0, ge=0, description="Front setback in feet")
    back: int = Field(default=0, ge=0, description="Back setback in feet")
    left: int = Field(default=0, ge=0, description="Left setback in feet")
    right: int = Field(default=0, ge=0, description="Right setback in feet")


class RoomInput(BaseModel):
    name: str = Field(..., description="Unique room identifier (e.g., 'living_room', 'bedroom_1')")
    type: Literal["living", "kitchen", "bedroom", "bathroom", "other"] = Field(
        ..., description="Standard room type for dimension table lookup"
    )
    zone: Optional[Literal["NW", "N", "NE", "W", "Mid", "E", "SW", "S", "SE"]] = Field(
        None, description="Preferred cell in 3x3 compass zone map"
    )
    zone_mode: Literal["must", "try"] = Field(
        default="try", description="Constraint priority: 'must' for hard rule, 'try' for soft penalty"
    )
    attached_to: Optional[str] = Field(
        default=None,
        description="Target bedroom name for ensuite bathrooms (connects to bedroom only)",
    )


class Pin(BaseModel):
    room: str = Field(..., description="Target room name to constrain")
    width: Optional[int] = Field(None, gt=0, description="Pinned width in feet")
    height: Optional[int] = Field(None, gt=0, description="Pinned height in feet")
    locked: Optional[bool] = Field(False, description="Whether coordinates are frozen during re-solve")


class FloorPlanInput(BaseModel):
    plot: Tuple[int, int] = Field(..., description="Plot dimensions (width, height) in whole feet")
    setbacks: Setbacks = Field(default_factory=Setbacks)
    entrance: Literal["N", "S", "E", "W"] = Field(default="S", description="Plot boundary entrance side")
    north: Literal["up", "down", "left", "right"] = Field(default="up", description="North orientation")
    rooms: List[RoomInput] = Field(
        ..., min_length=1, max_length=10, description="Rooms list (max 10 for MVP timeout guarantee)"
    )
    pins: List[Pin] = Field(default_factory=list, description="Pins/locks for room edits")

    @field_validator("plot")
    @classmethod
    def validate_plot(cls, v: Tuple[int, int]) -> Tuple[int, int]:
        w, h = v
        if w <= 0 or h <= 0:
            raise ValueError("Plot width and plot height must be positive integers.")
        return v

    @model_validator(mode="after")
    def validate_room_rules(self) -> "FloorPlanInput":
        names_seen = set()
        room_types = {r.name: r.type for r in self.rooms}

        for r in self.rooms:
            clean_name = r.name.strip()
            # 1. Unique room names
            if clean_name in names_seen:
                raise ValueError(f"Duplicate room name: '{r.name}'. All room names must be unique.")
            names_seen.add(clean_name)

            # 2. Block reserved hallway names
            if re.match(r"^hallway(_\d+|_seg_\d+)?$", clean_name, re.IGNORECASE):
                raise ValueError(f"Room name '{r.name}' is reserved for circulation corridors.")

            # 3. Attached bathroom checks
            if r.attached_to:
                if r.type != "bathroom":
                    raise ValueError(
                        f"Only bathrooms can specify 'attached_to'. '{r.name}' is of type '{r.type}'."
                    )
                if r.attached_to not in room_types:
                    raise ValueError(
                        f"Room '{r.name}' references non-existent room: '{r.attached_to}'."
                    )
                if room_types[r.attached_to] != "bedroom":
                    raise ValueError(
                        f"attached_to must point to a bedroom. '{r.attached_to}' is a '{room_types[r.attached_to]}'."
                    )
        return self


# ============================================================================
# 2. Output Schema Definitions
# ============================================================================

class PlacedRoom(BaseModel):
    name: str
    type: Literal["living", "kitchen", "bedroom", "bathroom", "other"]
    x: int = Field(..., ge=0, description="Bottom-left X relative to buildable area")
    y: int = Field(..., ge=0, description="Bottom-left Y relative to buildable area")
    w: int = Field(..., gt=0, description="Width in feet")
    h: int = Field(..., gt=0, description="Height in feet")


class HallwaySegment(BaseModel):
    id: str = Field(..., description="Unique segment identifier (e.g., 'hallway_1')")
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    w: int = Field(..., gt=0)
    h: int = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_segment_short_side(self) -> "HallwaySegment":
        """Ensures the short dimension is between 3 and 4 ft directly via min(w, h)."""
        short_side = min(self.w, self.h)
        if not (3 <= short_side <= 4):
            raise ValueError(
                f"Hallway segment '{self.id}' short side must be between 3 and 4 ft. Got short side of {short_side} ft ({self.w}x{self.h})."
            )
        return self


class Door(BaseModel):
    between: List[str] = Field(..., min_length=2, max_length=2, description="Connected boundaries/rooms")
    x: int
    y: int


class Window(BaseModel):
    room: str
    wall: Literal["N", "S", "E", "W"]
    x: int


class Layout(BaseModel):
    score: int = Field(default=0, description="Penalty score from P2 (lower is better)")
    rooms: List[PlacedRoom]
    hallway_segments: List[HallwaySegment] = Field(
        default_factory=list,
        description="List of hallway segments forming the circulation network"
    )
    doors: List[Door] = Field(default_factory=list)
    windows: List[Window] = Field(default_factory=list)
    messages: List[str] = Field(default_factory=list, description="Solver warnings/relaxation notes")

    @model_validator(mode="after")
    def validate_total_hallway_length(self) -> "Layout":
        """Combined long-side length across all segments must be at least 12 ft."""
        if not self.hallway_segments:
            return self

        total_length = sum(max(seg.w, seg.h) for seg in self.hallway_segments)
        if total_length < 12:
            raise ValueError(
                f"Combined hallway length must be >= 12 ft across all segments. Current total: {total_length} ft."
            )
        return self


class FloorPlanOutput(BaseModel):
    layouts: List[Layout] = Field(..., description="List of valid generated layouts (up to 3)")


class ErrorResponse(BaseModel):
    status: Literal["error", "infeasible", "unknown"] = "error"
    error_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)