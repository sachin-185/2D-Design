

def render_layout_to_svg(layout: dict, plot: tuple = (30, 40), setbacks: dict = None, entrance: str = "S") -> str:
    plot_w, plot_l = plot
    setbacks = setbacks or {"front": 5, "back": 3, "left": 3, "right": 3}
    scale = 20  
    margin = 60

    svg_w = plot_w * scale + margin * 2
    svg_h = plot_l * scale + margin * 2

    
    bx = margin + setbacks.get("left", 3) * scale
    by = margin + setbacks.get("back", 3) * scale
    bw = (plot_w - setbacks.get("left", 3) - setbacks.get("right", 3)) * scale
    bh = (plot_l - setbacks.get("front", 5) - setbacks.get("back", 3)) * scale
    l_build = plot_l - setbacks.get("front", 5) - setbacks.get("back", 3)

    
    def to_svg_x(x):
        return bx + x * scale

    def to_svg_y(y, h=0):
        return by + (l_build - (y + h)) * scale

    colors = {
        "living": ("#3b82f6", "rgba(59, 130, 246, 0.15)"),
        "kitchen": ("#10b981", "rgba(16, 185, 129, 0.15)"),
        "bedroom": ("#8b5cf6", "rgba(139, 92, 246, 0.15)"),
        "bathroom": ("#06b6d4", "rgba(6, 182, 212, 0.15)"),
        "dining": ("#f59e0b", "rgba(245, 158, 11, 0.15)"),
        "study": ("#ec4899", "rgba(236, 72, 153, 0.15)"),
        "utility": ("#64748b", "rgba(100, 116, 139, 0.15)"),
        "store": ("#78716c", "rgba(120, 113, 108, 0.15)"),
        "storage": ("#a8a29e", "rgba(168, 162, 158, 0.15)"),
        "laundry": ("#0284c7", "rgba(2, 132, 199, 0.15)"),
    }

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">',
        '  <rect width="100%" height="100%" fill="#0d1117" />',
        '  <defs>',
        f'    <pattern id="grid" width="{scale}" height="{scale}" patternUnits="userSpaceOnUse">',
        f'      <rect width="{scale}" height="{scale}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="0.8" />',
        '    </pattern>',
        '    <pattern id="hallway-stripe" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">',
        '      <line x1="0" y1="0" x2="0" y2="8" stroke="rgba(148, 163, 184, 0.2)" stroke-width="1.5" />',
        '    </pattern>',
        '  </defs>',
        
        f'  <rect x="{margin}" y="{margin}" width="{plot_w * scale}" height="{plot_l * scale}" fill="#0f172a" stroke="#475569" stroke-width="2" stroke-dasharray="6 4" />',
        f'  <rect x="{margin}" y="{margin}" width="{plot_w * scale}" height="{plot_l * scale}" fill="url(#grid)" />',
        
        f'  <rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="rgba(30, 41, 59, 0.9)" stroke="#38bdf8" stroke-width="1.5" />',
    ]

    
    hallway_segments = layout.get("hallway_segments") or ([{"id": "hallway_1", **layout["hallway"]}] if layout.get("hallway") else [])
    for seg in hallway_segments:
        hx = to_svg_x(seg["x"])
        hy = to_svg_y(seg["y"], seg["h"])
        hw = seg["w"] * scale
        hh = seg["h"] * scale
        svg_parts.append(
            f'  <rect x="{hx}" y="{hy}" width="{hw}" height="{hh}" fill="url(#hallway-stripe)" stroke="#64748b" stroke-width="1.2" />'
        )
        svg_parts.append(
            f'  <text x="{hx + hw/2}" y="{hy + hh/2}" fill="#94a3b8" font-family="sans-serif" font-size="11" text-anchor="middle" dominant-baseline="middle">{seg.get("id", "HALLWAY").upper()}</text>'
        )

    
    for r in layout.get("rooms", []):
        rx = to_svg_x(r["x"])
        ry = to_svg_y(r["y"], r["h"])
        rw = r["w"] * scale
        rh = r["h"] * scale
        r_type = r.get("type", "bedroom").lower()
        stroke_col, fill_col = colors.get(r_type, ("#8b5cf6", "rgba(139, 92, 246, 0.15)"))

        svg_parts.append(
            f'  <rect x="{rx}" y="{ry}" width="{rw}" height="{rh}" fill="{fill_col}" stroke="{stroke_col}" stroke-width="2" rx="2" />'
        )
        svg_parts.append(
            f'  <text x="{rx + rw/2}" y="{ry + rh/2 - 6}" fill="#f8fafc" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">{r["name"].upper()}</text>'
        )
        svg_parts.append(
            f'  <text x="{rx + rw/2}" y="{ry + rh/2 + 10}" fill="#94a3b8" font-family="monospace" font-size="10" text-anchor="middle">{r["w"]}\' x {r["h"]}\'</text>'
        )

    
    for d in layout.get("doors", []):
        d_len = d.get("width", 3.0) * scale
        is_horiz = d.get("orientation", "horizontal") == "horizontal"

        if is_horiz:
            dx = to_svg_x(d["x"])
            dy = to_svg_y(d["y"], 0)
            svg_parts.append(f'  <rect x="{dx}" y="{dy - 2}" width="{d_len}" height="4" fill="#0d1117" />')
            svg_parts.append(f'  <line x1="{dx}" y1="{dy}" x2="{dx}" y2="{dy - d_len}" stroke="#f59e0b" stroke-width="2" />')
            svg_parts.append(f'  <path d="M {dx} {dy - d_len} A {d_len} {d_len} 0 0 1 {dx + d_len} {dy}" fill="none" stroke="#f59e0b" stroke-width="1" stroke-dasharray="2 2" />')
        else:
            dx = to_svg_x(d["x"])
            dy = to_svg_y(d["y"], d.get("width", 3.0))
            svg_parts.append(f'  <rect x="{dx - 2}" y="{dy}" width="4" height="{d_len}" fill="#0d1117" />')
            svg_parts.append(f'  <line x1="{dx}" y1="{dy}" x2="{dx + d_len}" y2="{dy}" stroke="#f59e0b" stroke-width="2" />')
            svg_parts.append(f'  <path d="M {dx + d_len} {dy} A {d_len} {d_len} 0 0 1 {dx} {dy + d_len}" fill="none" stroke="#f59e0b" stroke-width="1" stroke-dasharray="2 2" />')

    
    svg_parts.append(
        f'  <g transform="translate({svg_w - 40}, 40)">'
        '    <circle r="18" fill="#1e293b" stroke="#475569" stroke-width="1.5" />'
        '    <polygon points="0,-14 4,-2 0,0 -4,-2" fill="#ef4444" />'
        '    <polygon points="0,14 4,2 0,0 -4,2" fill="#94a3b8" />'
        '    <text y="-5" text-anchor="middle" fill="#f8fafc" font-size="8" font-family="sans-serif" font-weight="bold">N</text>'
        '  </g>'
    )

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)
