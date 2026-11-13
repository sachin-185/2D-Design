"""
floorplan/schema.py
Data contracts for Input and Output JSON schemas using Pydantic.
Owner: P3 (Input and Glue)
"""

import re
from typing import List, Optional, Tuple, Literal, Dict, Any, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    @field_validator("name", "attached_to", mode="before")
    @classmethod
    def strip_names(cls, v: Any) -> Any:
        # " Kitchen" and "Kitchen" must be the same room everywhere (lookups, pins, P1 keys).
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Room name cannot be blank.")
        return v


class Pin(BaseModel):
    room: str = Field(..., description="Target room name to constrain")
    width: Optional[int] = Field(None, gt=0, description="Pinned width in feet")
    height: Optional[int] = Field(None, gt=0, description="Pinned height in feet")
    locked: Optional[bool] = False

    @field_validator("room", mode="before")
    @classmethod
    def strip_room(cls, v: Any) -> Any:
        return v.strip() if isinstance(v, str) else v


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

        pinned_rooms = [p.room for p in self.pins]
        duplicate_pins = sorted({n for n in pinned_rooms if pinned_rooms.count(n) > 1})
        if duplicate_pins:
            raise ValueError(f"Room(s) pinned more than once: {', '.join(duplicate_pins)}. Use one pin per room.")

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
    x: Union[int, float] = Field(..., ge=0)
    y: Union[int, float] = Field(..., ge=0)
    w: int = Field(..., gt=0)
    h: int = Field(..., gt=0)


class HallwaySegment(BaseModel):
    id: str = "hallway_1"
    x: Union[int, float] = Field(..., ge=0)
    y: Union[int, float] = Field(..., ge=0)
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
    y: Optional[Union[int, float]] = None


class Layout(BaseModel):
    # extra="allow": P2's engine adds archetype / penalties / coverage_percent per layout,
    # and P5 can show them. Without this they were silently dropped.
    model_config = ConfigDict(extra="allow")

    score: float = 0  # P1/P2 may return fractional scores; int rejected e.g. 87.5
    rooms: List[PlacedRoom]
    hallway_segments: List[HallwaySegment] = Field(default_factory=list)
    doors: List[Door] = Field(default_factory=list)
    windows: List[Window] = Field(default_factory=list)
    messages: List[str] = Field(default_factory=list)


class FloorPlanOutput(BaseModel):
    layouts: List[Layout]
    coordinate_system: Literal["plot"] = "plot"

    # Run-level notes from the engine, e.g. "Dropped a layout the checker rejected: ...".
    messages: List[str] = Field(default_factory=list)

    # After /edit-layout: the updated input (with the edit turned into pins). P5 sends this
    # back as the "input" of the next edit so pins accumulate.
    input: Optional[Dict[str, Any]] = None
    

class ErrorResponse(BaseModel):
    status: Literal["error", "infeasible", "unknown", "invalid", "conflict", "timeout"] = "error"
    error_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

class EditLayoutRequest(BaseModel):
    """Body for POST /edit-layout, mapped onto engine.edit_layout(inp, layout, edits, lock)."""
    model_config = ConfigDict(extra="forbid")

    input: FloorPlanInput
    layout: Layout
    edits: Dict[str, Dict[Literal["width", "height"], int]] = Field(
        ..., min_length=1, description='e.g. {"Bedroom": {"width": 14}}'
    )
    lock: List[str] = Field(default_factory=list, description="Rooms that must not move")

    @model_validator(mode="after")
    def validate_edit(self) -> "EditLayoutRequest":
        names = {r.name for r in self.input.rooms}
        unknown = sorted((set(self.edits) | set(self.lock)) - names)
        if unknown:
            raise ValueError(f"Unknown room(s) in edit: {', '.join(unknown)}.")
        for room, sides in self.edits.items():
            if not sides:
                raise ValueError(f"Edit for '{room}' must set width and/or height.")
            for side, value in sides.items():
                if value <= 0:
                    raise ValueError(f"{room} {side} must be a positive number of feet.")
        placed = {r.name for r in self.layout.rooms}
        if placed != names:
            raise ValueError("layout does not match input: send the layout returned for this input.")
        return self
