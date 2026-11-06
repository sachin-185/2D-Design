"""
floorplan/schema.py
Data contracts for Input and Output JSON schemas using Pydantic.
Owner: P3 (Input and Glue)
"""

import re
from typing import List, Optional, Tuple, Literal, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator

try:
    from floorplan.config import (
        MAX_ROOMS_ALLOWED,
        ROOM_SIZE_TABLE,
        resolve_room_type,
    )
except ModuleNotFoundError:
    from config import (
        MAX_ROOMS_ALLOWED,
        ROOM_SIZE_TABLE,
        resolve_room_type,
    )


class Setbacks(BaseModel):
    front: int = Field(default=0, ge=0, description="Front setback in feet")
    back: int = Field(default=0, ge=0, description="Back setback in feet")
    left: int = Field(default=0, ge=0, description="Left setback in feet")
    right: int = Field(default=0, ge=0, description="Right setback in feet")


class RoomInput(BaseModel):
    name: str = Field(..., min_length=1, description="Unique room identifier")
    type: Literal[
        "living", "kitchen", "bedroom", "bathroom",
        "dining", "study", "utility", "store", "storage", "laundry"
    ] = Field(..., description="Canonical type or recognized alias")
    zone: Optional[Literal["NW", "N", "NE", "W", "Mid", "E", "SW", "S", "SE"]] = None
    zone_mode: Literal["must", "try"] = "try"
    attached_to: Optional[str] = None


class Pin(BaseModel):
    room: str = Field(..., description="Target room name to constrain")
    width: Optional[int] = Field(None, gt=0, description="Pinned width in feet")
    height: Optional[int] = Field(None, gt=0, description="Pinned height in feet")
    locked: Optional[bool] = False


class FloorPlanInput(BaseModel):
    plot: Tuple[int, int] = Field(..., description="Plot dimensions (width, height) in whole feet")
    setbacks: Setbacks = Field(default_factory=Setbacks)
    entrance: Literal["N", "S", "E", "W"] = "S"
    north: Literal["up", "down", "left", "right"] = "up"
    rooms: List[RoomInput] = Field(
        ..., min_length=1, max_length=MAX_ROOMS_ALLOWED, description=f"Rooms list (max {MAX_ROOMS_ALLOWED})"
    )
    pins: List[Pin] = Field(default_factory=list)

    @field_validator("plot")
    @classmethod
    def validate_plot(cls, v: Tuple[int, int]) -> Tuple[int, int]:
        w, h = v
        if w <= 0 or h <= 0:
            raise ValueError("Plot width and plot height must be positive integers.")
        return v

    @model_validator(mode="after")
    def validate_rules(self) -> "FloorPlanInput":
        plot_w, plot_h = self.plot
        buildable_w = plot_w - self.setbacks.left - self.setbacks.right
        buildable_h = plot_h - self.setbacks.front - self.setbacks.back
        if buildable_w <= 0 or buildable_h <= 0:
            raise ValueError("Setbacks eliminate or exceed the usable buildable area.")

        # Require explicit 'living' room for P1's entrance anchor
        if not any(r.type == "living" for r in self.rooms):
            raise ValueError("Layout must contain at least one room with type 'living'.")

        names_seen = set()
        room_map = {r.name: r for r in self.rooms}

        for r in self.rooms:
            clean_name = r.name.strip()
            if clean_name in names_seen:
                raise ValueError(f"Duplicate room name: '{r.name}'. All room names must be unique.")
            names_seen.add(clean_name)

            # Match checker reserved pattern: "hallway" or "hallway_<number>" (case-insensitive)
            if re.match(r"^hallway(_\d+)?$", clean_name, re.IGNORECASE):
                raise ValueError(f"Room name '{r.name}' is reserved for circulation corridors.")

            if r.attached_to:
                if r.type != "bathroom":
                    raise ValueError(f"Only bathrooms can have 'attached_to'. Found in '{r.name}'.")
                if r.attached_to not in room_map:
                    raise ValueError(f"Room '{r.name}' references non-existent room: '{r.attached_to}'.")
                target_room = room_map[r.attached_to]
                if resolve_room_type(target_room.type) != "bedroom":
                    raise ValueError(f"attached_to must point to a bedroom. '{r.attached_to}' is a {target_room.type}.")

        for pin in self.pins:
            if pin.room not in room_map:
                raise ValueError(f"Pin references non-existent room: '{pin.room}'.")
            target_room = room_map[pin.room]
            canonical = resolve_room_type(target_room.type)
            bounds = ROOM_SIZE_TABLE[canonical]

            if pin.width is not None:
                if pin.width > buildable_w:
                    raise ValueError(f"Pinned width ({pin.width} ft) for '{pin.room}' exceeds buildable width ({buildable_w} ft).")
                if pin.width < bounds["min"][0] or pin.width > bounds["max"][0]:
                    raise ValueError(f"Pinned width ({pin.width} ft) for '{pin.room}' outside valid range {bounds['min'][0]}-{bounds['max'][0]} ft.")

            if pin.height is not None:
                if pin.height > buildable_h:
                    raise ValueError(f"Pinned height ({pin.height} ft) for '{pin.room}' exceeds buildable depth ({buildable_h} ft).")
                if pin.height < bounds["min"][1] or pin.height > bounds["max"][1]:
                    raise ValueError(f"Pinned height ({pin.height} ft) for '{pin.room}' outside valid range {bounds['min'][1]}-{bounds['max'][1]} ft.")

        return self


class PlacedRoom(BaseModel):
    name: str
    type: str
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    w: int = Field(..., gt=0)
    h: int = Field(..., gt=0)


class HallwaySegment(BaseModel):
    id: str = "hallway_1"
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    w: int = Field(..., gt=0)
    h: int = Field(..., gt=0)


class Door(BaseModel):
    between: List[str] = Field(..., min_length=2, max_length=2)
    x: Union[int, float]
    y: Union[int, float]


class Window(BaseModel):
    room: str
    wall: Literal["N", "S", "E", "W"]
    x: Union[int, float]


class Layout(BaseModel):
    score: int = 0
    rooms: List[PlacedRoom]
    hallway_segments: List[HallwaySegment] = Field(default_factory=list)
    doors: List[Door] = Field(default_factory=list)
    windows: List[Window] = Field(default_factory=list)
    messages: List[str] = Field(default_factory=list)


class FloorPlanOutput(BaseModel):
    layouts: List[Layout]


class ErrorResponse(BaseModel):
    status: Literal["error", "infeasible", "unknown", "invalid", "conflict", "timeout"] = "error"
    error_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)