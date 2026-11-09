
from typing import List, Optional, Tuple, Literal

from pydantic import BaseModel, Field

class Setbacks(BaseModel):
    front: int = 5
    back: int = 3
    left: int = 3
    right: int = 3

class RoomRequest(BaseModel):
    name: str
    type: str
    zone: Optional[str] = None
    zone_mode: Optional[Literal["must", "try"]] = "try"


class RoomPin(BaseModel):
    room: str
    width: Optional[int] = None
    height: Optional[int] = None
    locked: Optional[bool] = False


class InputFloorplan(BaseModel):
    plot: Tuple[int, int] = (30, 40)
    setbacks: Setbacks = Field(default_factory=Setbacks)
    entrance: Literal["N", "S", "E", "W"] = "S"
    north: Literal["up", "down", "left", "right"] = "up"
    rooms: List[RoomRequest]
    pins: Optional[List[RoomPin]] = Field(default_factory=list)


class RoomLayout(BaseModel):
    name: str
    type: Optional[str] = "room"
    x: int
    y: int
    w: int
    h: int


class HallwayLayout(BaseModel):
    x: int
    y: int
    w: int
    h: int


class Door(BaseModel):
    between: List[str]
    x: float
    y: float
    width: Optional[float] = 3.0
    orientation: Optional[str] = "horizontal"
    swingDir: Optional[str] = "in"
    isMainEntrance: Optional[bool] = False


class Window(BaseModel):
    room: str
    wall: Literal["N", "S", "E", "W"]
    x: float
    y: Optional[float] = 0.0
    width: Optional[float] = 3.5
    orientation: Optional[str] = "horizontal"


class LayoutVariant(BaseModel):
    id: Optional[str] = "layout-1"
    variantNumber: Optional[int] = 1
    archetype: Optional[str] = "Central Hallway"
    score: int
    rooms: List[RoomLayout]
    hallway: Optional[HallwayLayout] = None
    doors: List[Door] = Field(default_factory=list)
    windows: List[Window] = Field(default_factory=list)
    messages: List[str] = Field(default_factory=list)


class OutputFloorplan(BaseModel):
    layouts: List[LayoutVariant]
    messages: List[str] = Field(default_factory=list)
