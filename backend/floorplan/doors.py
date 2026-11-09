
from typing import List, Dict, Any, Tuple, Optional


def find_shared_wall(node_a: Dict[str, Any], node_b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    
    a_left, a_right = node_a["x"], node_a["x"] + node_a["w"]
    a_bottom, a_top = node_a["y"], node_a["y"] + node_a["h"]

    b_left, b_right = node_b["x"], node_b["x"] + node_b["w"]
    b_bottom, b_top = node_b["y"], node_b["y"] + node_b["h"]

    
    if a_right == b_left or a_left == b_right:
        shared_x = b_left if a_right == b_left else a_left
        overlap_start = max(a_bottom, b_bottom)
        overlap_end = min(a_top, b_top)
        overlap_len = overlap_end - overlap_start

        if overlap_len >= 3:
            return {
                "type": "vertical",
                "x": float(shared_x),
                "y_start": float(overlap_start),
                "y_end": float(overlap_end),
                "length": float(overlap_len),
            }

    
    if a_top == b_bottom or a_bottom == b_top:
        shared_y = b_bottom if a_top == b_bottom else a_bottom
        overlap_start = max(a_left, b_left)
        overlap_end = min(a_right, b_right)
        overlap_len = overlap_end - overlap_start

        if overlap_len >= 3:
            return {
                "type": "horizontal",
                "y": float(shared_y),
                "x_start": float(overlap_start),
                "x_end": float(overlap_end),
                "length": float(overlap_len),
            }

    return None


def place_doors(
    rooms: List[Dict[str, Any]],
    hallway_segments: Optional[List[Dict[str, Any]]] = None,
    entrance: str = "S",
    buildable_bounds: Tuple[int, int] = (24, 32),
    room_requests: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    
    doors = []
    unconnected_rooms = []
    door_width = 3.0
    segments = hallway_segments or []
    req_map = {r.get("name"): r for r in (room_requests or [])}

    living_rooms = [r for r in rooms if r.get("type") == "living" or "living" in r.get("name", "").lower()]
    first_living = living_rooms[0] if living_rooms else None

    for room in rooms:
        r_name = room.get("name", "")
        r_type = room.get("type", "")
        req = req_map.get(r_name, {})
        placed = False

        
        if room == first_living and not segments:
            continue

        
        if r_type == "bathroom" and req.get("attached_to"):
            target_bed_name = req["attached_to"]
            target_bed = next((r for r in rooms if r.get("name") == target_bed_name), None)
            if target_bed:
                shared = find_shared_wall(room, target_bed)
                if shared:
                    if shared["type"] == "vertical":
                        door_y = shared["y_start"] + 1 if shared["length"] >= 5 else shared["y_start"]
                        doors.append({
                            "between": [r_name, target_bed_name],
                            "x": shared["x"],
                            "y": round(door_y, 1),
                            "width": door_width,
                            "orientation": "vertical",
                            "swingDir": "in",
                        })
                    else:
                        door_x = shared["x_start"] + 1 if shared["length"] >= 5 else shared["x_start"]
                        doors.append({
                            "between": [r_name, target_bed_name],
                            "x": round(door_x, 1),
                            "y": shared["y"],
                            "width": door_width,
                            "orientation": "horizontal",
                            "swingDir": "in",
                        })
                    placed = True
            if not placed:
                unconnected_rooms.append(r_name)
            continue

        
        if r_type == "kitchen" and first_living:
            shared = find_shared_wall(room, first_living)
            if shared:
                if shared["type"] == "vertical":
                    door_y = shared["y_start"] + 1 if shared["length"] >= 5 else shared["y_start"]
                    doors.append({
                        "between": [r_name, first_living.get("name", "living")],
                        "x": shared["x"],
                        "y": round(door_y, 1),
                        "width": door_width,
                        "orientation": "vertical",
                        "swingDir": "in",
                    })
                else:
                    door_x = shared["x_start"] + 1 if shared["length"] >= 5 else shared["x_start"]
                    doors.append({
                        "between": [r_name, first_living.get("name", "living")],
                        "x": round(door_x, 1),
                        "y": shared["y"],
                        "width": door_width,
                        "orientation": "horizontal",
                        "swingDir": "in",
                    })
                placed = True

        
        if not placed and segments:
            for seg in segments:
                shared = find_shared_wall(room, seg)
                if shared:
                    seg_id = seg.get("id", "hallway_1")
                    if shared["type"] == "vertical":
                        door_y = shared["y_start"] + 1 if shared["length"] >= 5 else shared["y_start"]
                        doors.append({
                            "between": [r_name, seg_id],
                            "x": shared["x"],
                            "y": round(door_y, 1),
                            "width": door_width,
                            "orientation": "vertical",
                            "swingDir": "in",
                        })
                    else:
                        door_x = shared["x_start"] + 1 if shared["length"] >= 5 else shared["x_start"]
                        doors.append({
                            "between": [r_name, seg_id],
                            "x": round(door_x, 1),
                            "y": shared["y"],
                            "width": door_width,
                            "orientation": "horizontal",
                            "swingDir": "in",
                        })
                    placed = True
                    break

        
        if not placed:
            for liv in living_rooms:
                if liv.get("name") != r_name:
                    shared = find_shared_wall(room, liv)
                    if shared:
                        if shared["type"] == "vertical":
                            door_y = shared["y_start"] + 1 if shared["length"] >= 5 else shared["y_start"]
                            doors.append({
                                "between": [r_name, liv.get("name", "living")],
                                "x": shared["x"],
                                "y": round(door_y, 1),
                                "width": door_width,
                                "orientation": "vertical",
                                "swingDir": "in",
                            })
                        else:
                            door_x = shared["x_start"] + 1 if shared["length"] >= 5 else shared["x_start"]
                            doors.append({
                                "between": [r_name, liv.get("name", "living")],
                                "x": round(door_x, 1),
                                "y": shared["y"],
                                "width": door_width,
                                "orientation": "horizontal",
                                "swingDir": "in",
                            })
                        placed = True
                        break

        
        if not placed:
            unconnected_rooms.append(r_name)

    
    bw, bl = buildable_bounds
    main_door = None
    if entrance == "S":
        candidate = next((s for s in segments if abs(s.get("y", 0)) < 0.1), None) or \
                    next((r for r in rooms if abs(r.get("y", 0)) < 0.1 and (r.get("type") == "living" or r == first_living)), None)
        if candidate:
            door_x = candidate["x"] + (candidate["w"] - 3.5) / 2
            main_door = {
                "between": ["exterior", candidate.get("id") or candidate.get("name")],
                "x": round(door_x, 1),
                "y": 0.0,
                "width": 3.5,
                "orientation": "horizontal",
                "swingDir": "in",
                "isMainEntrance": True,
            }
    elif entrance == "N":
        candidate = next((s for s in segments if abs(s.get("y", 0) + s.get("h", 0) - bl) < 0.1), None) or \
                    next((r for r in rooms if abs(r.get("y", 0) + r.get("h", 0) - bl) < 0.1 and (r.get("type") == "living" or r == first_living)), None)
        if candidate:
            door_x = candidate["x"] + (candidate["w"] - 3.5) / 2
            main_door = {
                "between": ["exterior", candidate.get("id") or candidate.get("name")],
                "x": round(door_x, 1),
                "y": float(bl),
                "width": 3.5,
                "orientation": "horizontal",
                "swingDir": "in",
                "isMainEntrance": True,
            }
    elif entrance == "E":
        candidate = next((r for r in rooms if abs(r.get("x", 0) + r.get("w", 0) - bw) < 0.1 and (r.get("type") == "living" or r == first_living)), None)
        if candidate:
            door_y = candidate["y"] + (candidate["h"] - 3.5) / 2
            main_door = {
                "between": ["exterior", candidate.get("id") or candidate.get("name")],
                "x": float(bw),
                "y": round(door_y, 1),
                "width": 3.5,
                "orientation": "vertical",
                "swingDir": "in",
                "isMainEntrance": True,
            }
    elif entrance == "W":
        candidate = next((r for r in rooms if abs(r.get("x", 0)) < 0.1 and (r.get("type") == "living" or r == first_living)), None)
        if candidate:
            door_y = candidate["y"] + (candidate["h"] - 3.5) / 2
            main_door = {
                "between": ["exterior", candidate.get("id") or candidate.get("name")],
                "x": 0.0,
                "y": round(door_y, 1),
                "width": 3.5,
                "orientation": "vertical",
                "swingDir": "in",
                "isMainEntrance": True,
            }

    if main_door:
        doors.insert(0, main_door)

    return doors, unconnected_rooms
