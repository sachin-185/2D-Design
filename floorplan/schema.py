"""
floorplan/schema.py
Data contracts for Input and Output JSON schemas using Pydantic.
Owner: P3 (Input and Glue)
"""

from typing import List, Optional, Tuple, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# ==========================================
# 1. Input Schema Definitions
# ==========================================

class Setbacks(BaseModel):
    """Matches calculate_buildable_area setbacks from geometry.py."""
    front: int = Field(default=0, ge=0, description="Front setback in feet")
    back: int = Field(default=0, ge=0, description="Back setback in feet")
    left: int = Field(default=0, ge=0, description="Left setback in feet")
    right: int = Field(default=0, ge=0, description="Right setback in feet")


class RoomInput(BaseModel):
    """Individual room specifications to replace hardcoded room specs."""
    name: str = Field(..., description="Unique room name (e.g., 'living_room', 'bedroom_1')")
    type: Literal["living", "kitchen", "bedroom", "bathroom", "other"] = Field(
        ..., description="Standard room type for size table lookup"
    )
    zone: Optional[Literal["NW", "N", "NE", "W", "Mid", "E", "SW", "S", "SE"]] = Field(
        None, description="Preferred cell in 3x3 zone map"
    )
    zone_mode: Literal["must", "try"] = Field(
        default="try", description="Constraint priority: 'must' for hard rule, 'try' for soft penalty"
    )
    attached_to: Optional[str] = Field(
        default=None,
        description="Target bedroom for attached bathrooms (connects to bedroom, not hallway)",
    )


class Pin(BaseModel):
    """Enables locking and resizing rooms during edit/re-solve flows."""
    room: str = Field(..., description="Target room name to constrain")
    width: Optional[int] = Field(None, gt=0, description="Pinned width in feet")
    height: Optional[int] = Field(None, gt=0, description="Pinned height in feet")
    locked: Optional[bool] = Field(False, description="Whether coordinates are fixed during re-solve")


class FloorPlanInput(BaseModel):
    """Primary input model replacing validate_inputs from geometry.py."""
    plot: Tuple[int, int] = Field(..., description="Plot dimensions [Width, Length] in whole feet")
    setbacks: Setbacks = Field(default_factory=Setbacks)
    entrance: Literal["N", "S", "E", "W"] = Field(default="S", description="Plot boundary entrance side")
    north: Literal["up", "down", "left", "right"] = Field(default="up", description="North orientation")
    rooms: List[RoomInput] = Field(..., min_length=1, description="List of rooms to place")
    pins: List[Pin] = Field(default_factory=list, description="Pins/locks for edits")

    @field_validator("plot")
    @classmethod
    def validate_plot(cls, v: Tuple[int, int]) -> Tuple[int, int]:
        w, l = v
        if w <= 0 or l <= 0:
            raise ValueError("Plot width and length must be positive integers.")
        return v

    @model_validator(mode="after")
    def validate_attached_bathrooms(self) -> "FloorPlanInput":
        """Ensures attached_to points to an existing room of type bedroom."""
        room_types = {r.name: r.type for r in self.rooms}
        for r in self.rooms:
            if r.attached_to:
                if r.attached_to not in room_types:
                    raise ValueError(f"attached_to references non-existent room: '{r.attached_to}'")
                if room_types[r.attached_to] != "bedroom":
                    raise ValueError(
                        f"attached_to must reference a bedroom. '{r.attached_to}' is a {room_types[r.attached_to]}."
                    )
        return self


# ==========================================
# 2. Output Schema Definitions
# ==========================================

class PlacedRoom(BaseModel):
    """Standardized representation of solved room rectangles."""
    name: str
    type: Literal["living", "kitchen", "bedroom", "bathroom", "other"]
    x: int = Field(..., ge=0, description="Grid coordinate X in feet")
    y: int = Field(..., ge=0, description="Grid coordinate Y in feet")
    w: int = Field(..., gt=0, description="Room width in feet")
    h: int = Field(..., gt=0, description="Room height in feet")


class Hallway(BaseModel):
    """Primary circulation corridor supporting horizontal and vertical orientations."""
    id: str = Field(default="hallway_1", description="Identifier for circulation")
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    w: int = Field(..., gt=0)
    h: int = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_hallway_orientation(self) -> "Hallway":
        """Enforces short side in [3, 4] ft and long side >= 12 ft."""
        vert = (3 <= self.w <= 4) and (self.h >= 12)
        horiz = (3 <= self.h <= 4) and (self.w >= 12)
        if not (vert or horiz):
            raise ValueError(
                f"Hallway must have one side in [3, 4] ft and the other >= 12 ft. Got {self.w}x{self.h} ft."
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
    score: int = Field(default=0, description="Soft rule penalty score (lower is better)")
    rooms: List[PlacedRoom]
    hallway: Optional[Hallway] = None
    doors: List[Door] = Field(default_factory=list)
    windows: List[Window] = Field(default_factory=list)
    messages: List[str] = Field(default_factory=list, description="Solver status/relaxation notes")


class FloorPlanOutput(BaseModel):
    layouts: List[Layout] = Field(..., description="List of valid generated layouts (up to 3)")
