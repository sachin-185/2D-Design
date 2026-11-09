import React, { useRef, useState, useMemo } from 'react';
import { 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  Download, 
  Compass, 
  Layers, 
  Maximize2,
  Move
} from 'lucide-react';
import { ROOM_SIZE_TABLE, getBuildableArea } from '../engine/contracts';
import { SQFT_TO_SQM } from '../engine/materials';

export default function Canvas({
  layout,
  input,
  selectedRoom,
  onSelectRoom,
  furniture = [],
  showGrid = true,
  showDoors = true,
  showWindows = true,
  showFurniture = true,
  showDimensions = true,
  showLabels = true,
  unitSystem = 'imperial',
}) {
  const svgRef = useRef(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [startPan, setStartPan] = useState({ x: 0, y: 0 });
  const [hoverCoords, setHoverCoords] = useState(null);

  const plotW = input.plot[0];
  const plotL = input.plot[1];
  const setbacks = input.setbacks;
  const buildable = useMemo(() => getBuildableArea(input.plot, input.setbacks), [input]);

  const scale = 24; 
  const margin = 80;

  const svgWidth = plotW * scale + margin * 2;
  const svgHeight = plotL * scale + margin * 2;

  const bX = margin + (setbacks?.left || 0) * scale;
  const bY = margin + (setbacks?.back || 0) * scale;
  const bW = buildable.width * scale;
  const bH = buildable.length * scale;
  const L_build = buildable.length;
  const W_build = buildable.width;

  const toSvgX = (x) => bX + x * scale;
  const toSvgY = (y, h = 0) => bY + (L_build - (y + h)) * scale;

  const handleWheel = (e) => {
    e.preventDefault();
    const zoomDelta = e.deltaY < 0 ? 1.1 : 0.9;
    setZoom((prev) => Math.min(3.5, Math.max(0.4, prev * zoomDelta)));
  };

  const handleMouseDown = (e) => {
    if (e.target.tagName === 'svg' || e.target.id === 'canvas-bg' || e.target.id === 'grid-layer') {
      setIsPanning(true);
      setStartPan({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e) => {
    if (isPanning) {
      setPan({
        x: e.clientX - startPan.x,
        y: e.clientY - startPan.y,
      });
    }

    if (svgRef.current) {
      const rect = svgRef.current.getBoundingClientRect();
      const mouseSvgX = (e.clientX - rect.left - pan.x) / zoom;
      const mouseSvgY = (e.clientY - rect.top - pan.y) / zoom;
      const ftX = Math.round(((mouseSvgX - bX) / scale) * 10) / 10;
      const ftY = Math.round(((bY + bH - mouseSvgY) / scale) * 10) / 10;
      setHoverCoords({ x: ftX, y: ftY });
    }
  };

  const handleMouseUp = () => setIsPanning(false);

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const fitToScreen = () => {
    setZoom(0.85);
    setPan({ x: 0, y: 0 });
  };

  const northRotation = useMemo(() => {
    const dir = input.north || 'up';
    if (dir === 'right') return 90;
    if (dir === 'down') return 180;
    if (dir === 'left') return 270;
    return 0;
  }, [input.north]);

  const hallwaySegments = layout?.hallway_segments || (layout?.hallway ? [layout.hallway] : []);

  const formatDim = (ft) => {
    if (unitSystem === 'metric') {
      return `${Math.round(ft * 0.3048 * 10) / 10}m`;
    }
    return `${ft}'`;
  };

  const formatArea = (sqft) => {
    if (unitSystem === 'metric') {
      return `${Math.round(sqft * SQFT_TO_SQM * 10) / 10} m²`;
    }
    return `${sqft} sq ft`;
  };

  return (
    <div className="cad-canvas-workbench">
      <div className="cad-floating-toolbar">
        <button type="button" className="cad-tool-btn" onClick={() => setZoom((z) => Math.min(3.5, z * 1.15))} title="Zoom In">
          <ZoomIn size={15} />
        </button>
        <button type="button" className="cad-tool-btn" onClick={() => setZoom((z) => Math.max(0.4, z * 0.85))} title="Zoom Out">
          <ZoomOut size={15} />
        </button>
        <div className="tool-sep" />
        <button type="button" className="cad-tool-btn" onClick={resetView} title="Reset View (100%)">
          <RotateCcw size={15} />
        </button>
        <button type="button" className="cad-tool-btn" onClick={fitToScreen} title="Fit Plan to Viewport">
          <Maximize2 size={15} />
        </button>
      </div>

      {hoverCoords && (
        <div className="cad-cursor-hud">
          <span>X: {hoverCoords.x >= 0 ? hoverCoords.x : 0} ft</span>
          <span className="hud-sep">|</span>
          <span>Y: {hoverCoords.y >= 0 ? hoverCoords.y : 0} ft</span>
          <span className="hud-sep">|</span>
          <span>Zoom: {Math.round(zoom * 100)}%</span>
        </div>
      )}

      <div
        className="cad-viewport-interactive"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
      >
        <svg
          ref={svgRef}
          className="cad-svg-sheet"
          width={svgWidth}
          height={svgHeight}
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center center',
          }}
        >
          <defs>
            <pattern id="grid-dots" width={scale} height={scale} patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="0.75" fill="rgba(56, 189, 248, 0.2)" />
            </pattern>

            <pattern id="major-grid" width={scale * 5} height={scale * 5} patternUnits="userSpaceOnUse">
              <rect width={scale * 5} height={scale * 5} fill="url(#grid-dots)" />
              <path d={`M ${scale * 5} 0 L 0 0 0 ${scale * 5}`} fill="none" stroke="rgba(56, 189, 248, 0.08)" strokeWidth="0.8" />
            </pattern>

            <pattern id="wall-hatch" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
              <line x1="0" y1="0" x2="0" y2="8" stroke="rgba(148, 163, 184, 0.35)" strokeWidth="1.5" />
            </pattern>

            <filter id="glow-selected" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#38bdf8" floodOpacity="0.8" />
            </filter>
          </defs>

          <rect id="canvas-bg" width="100%" height="100%" fill="#0a0e17" />

          {showGrid && (
            <rect id="grid-layer" width="100%" height="100%" fill="url(#major-grid)" />
          )}

          <g id="plot-boundaries">
            <rect
              x={margin}
              y={margin}
              width={plotW * scale}
              height={plotL * scale}
              fill="rgba(15, 23, 42, 0.4)"
              stroke="#334155"
              strokeWidth="1.5"
              strokeDasharray="6 4"
            />
            <text x={margin + 12} y={margin + 20} className="cad-note-text" fill="#64748b">
              PROPERTY BOUNDARY: {plotW}' × {plotL}' ({plotW * plotL} sq ft)
            </text>

            <rect
              x={bX}
              y={bY}
              width={bW}
              height={bH}
              fill="rgba(30, 41, 59, 0.3)"
              stroke="#38bdf8"
              strokeWidth="1"
              strokeDasharray="4 2"
            />
            <text x={bX + 8} y={bY + 16} className="cad-note-text" fill="#38bdf8">
              BUILDABLE ENVELOPE: {buildable.width}' × {buildable.length}' ({buildable.area} sq ft)
            </text>
          </g>

          <g id="setback-labels">
            <text x={margin + (plotW * scale) / 2} y={margin + plotL * scale - 8} textAnchor="middle" className="setback-text">
              FRONT SETBACK ({setbacks?.front || 5}')
            </text>
            <text x={margin + (plotW * scale) / 2} y={margin + 14} textAnchor="middle" className="setback-text">
              BACK SETBACK ({setbacks?.back || 3}')
            </text>
            <text
              x={margin + 10}
              y={margin + (plotL * scale) / 2}
              textAnchor="middle"
              transform={`rotate(-90 ${margin + 10} ${margin + (plotL * scale) / 2})`}
              className="setback-text"
            >
              LEFT SETBACK ({setbacks?.left || 3}')
            </text>
            <text
              x={margin + plotW * scale - 10}
              y={margin + (plotL * scale) / 2}
              textAnchor="middle"
              transform={`rotate(90 ${margin + plotW * scale - 10} ${margin + (plotL * scale) / 2})`}
              className="setback-text"
            >
              RIGHT SETBACK ({setbacks?.right || 3}')
            </text>
          </g>

          <g id="hallways-layer">
            {hallwaySegments.map((hw, idx) => {
              const hx = toSvgX(hw.x);
              const hy = toSvgY(hw.y, hw.h);
              const hwWidth = hw.w * scale;
              const hwHeight = hw.h * scale;

              return (
                <g key={`hw-${idx}`}>
                  <rect
                    x={hx}
                    y={hy}
                    width={hwWidth}
                    height={hwHeight}
                    fill="rgba(30, 41, 59, 0.6)"
                    stroke="#475569"
                    strokeWidth="1.5"
                  />
                  <text
                    x={hx + hwWidth / 2}
                    y={hy + hwHeight / 2}
                    textAnchor="middle"
                    fill="#94a3b8"
                    fontSize="10"
                    fontWeight="500"
                    letterSpacing="1"
                  >
                    HALLWAY
                  </text>
                </g>
              );
            })}
          </g>

          <g id="rooms-layer">
            {layout?.rooms?.map((room) => {
              const rx = toSvgX(room.x);
              const ry = toSvgY(room.y, room.h);
              const rw = room.w * scale;
              const rh = room.h * scale;
              const isSelected = selectedRoom?.name === room.name;
              const config = ROOM_SIZE_TABLE[room.type] || { color: '#38bdf8', lightColor: 'rgba(56, 189, 248, 0.12)' };

              return (
                <g
                  key={room.name}
                  className="cad-room-group"
                  onClick={() => onSelectRoom(room)}
                  style={{ cursor: 'pointer' }}
                >
                  <rect
                    x={rx}
                    y={ry}
                    width={rw}
                    height={rh}
                    fill={config.lightColor || 'rgba(56, 189, 248, 0.12)'}
                    stroke={isSelected ? '#38bdf8' : config.color || '#475569'}
                    strokeWidth={isSelected ? 3 : 1.8}
                    filter={isSelected ? 'url(#glow-selected)' : undefined}
                  />

                  {showLabels && (
                    <g className="room-info-label" pointerEvents="none">
                      <text
                        x={rx + rw / 2}
                        y={ry + rh / 2 - 12}
                        textAnchor="middle"
                        fill="#f8fafc"
                        fontSize="12"
                        fontWeight="700"
                        letterSpacing="0.5"
                      >
                        {room.name.toUpperCase()}
                      </text>
                      <text
                        x={rx + rw / 2}
                        y={ry + rh / 2 + 6}
                        textAnchor="middle"
                        fill="#94a3b8"
                        fontSize="10.5"
                        fontWeight="500"
                      >
                        {formatDim(room.w)} × {formatDim(room.h)}
                      </text>
                      <text
                        x={rx + rw / 2}
                        y={ry + rh / 2 + 20}
                        textAnchor="middle"
                        fill={config.color}
                        fontSize="10"
                        fontWeight="600"
                      >
                        {formatArea(room.w * room.h)}
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </g>

          {showFurniture && furniture && furniture.length > 0 && (
            <g id="furniture-layer" pointerEvents="none">
              {furniture.map((item) => {
                const fx = toSvgX(item.x);
                const fy = toSvgY(item.y, item.h);
                const fw = item.w * scale;
                const fh = item.h * scale;

                return (
                  <g key={item.id} className="cad-furniture-symbol" opacity="0.85">
                    <rect
                      x={fx}
                      y={fy}
                      width={fw}
                      height={fh}
                      fill={item.color || '#1e293b'}
                      stroke={item.accentColor || '#475569'}
                      strokeWidth="1.2"
                      rx="2"
                    />

                    {item.type === 'bed' && (
                      <g>
                        <rect x={fx + 2} y={fy + 2} width={fw - 4} height={fh * 0.22} fill={item.accentColor} rx="1" />
                        <rect x={fx + fw * 0.08} y={fy + fh * 0.26} width={fw * 0.38} height={fh * 0.24} fill="#ffffff" rx="2" stroke="#94a3b8" strokeWidth="0.8" />
                        <rect x={fx + fw * 0.54} y={fy + fh * 0.26} width={fw * 0.38} height={fh * 0.24} fill="#ffffff" rx="2" stroke="#94a3b8" strokeWidth="0.8" />
                        <line x1={fx + 2} y1={fy + fh * 0.58} x2={fx + fw - 2} y2={fy + fh * 0.58} stroke={item.accentColor} strokeWidth="1" strokeDasharray="2 2" />
                      </g>
                    )}

                    {item.type === 'sofa' && (
                      <g>
                        <rect x={fx + 2} y={fy + 2} width={fw - 4} height={fh * 0.28} fill={item.accentColor} rx="1" />
                        <line x1={fx + fw * 0.33} y1={fy + fh * 0.28} x2={fx + fw * 0.33} y2={fy + fh - 2} stroke="#334155" strokeWidth="0.8" />
                        <line x1={fx + fw * 0.66} y1={fy + fh * 0.28} x2={fx + fw * 0.66} y2={fy + fh - 2} stroke="#334155" strokeWidth="0.8" />
                      </g>
                    )}

                    {item.type === 'bath' && (
                      <g>
                        <ellipse cx={fx + fw / 2} cy={fy + fh / 2} rx={fw * 0.32} ry={fh * 0.32} fill="none" stroke="#64748b" strokeWidth="1" />
                        <circle cx={fx + fw / 2} cy={fy + fh / 2} r="1.5" fill="#38bdf8" />
                      </g>
                    )}

                    {item.type === 'counter' && (
                      <g>
                        <circle cx={fx + fw * 0.25} cy={fy + fh / 2} r={Math.min(fw, fh) * 0.22} fill="none" stroke="#64748b" strokeWidth="1" />
                        <rect x={fx + fw * 0.55} y={fy + fh * 0.18} width={fw * 0.3} height={fh * 0.64} fill="none" stroke="#64748b" strokeWidth="1" rx="1" />
                      </g>
                    )}

                    <text
                      x={fx + fw / 2}
                      y={fy + fh / 2 + 3}
                      textAnchor="middle"
                      fill="#e2e8f0"
                      fontSize="7.5"
                      fontWeight="600"
                    >
                      {item.name}
                    </text>
                  </g>
                );
              })}
            </g>
          )}

          {showWindows && layout?.windows?.map((win, idx) => {
            const wLen = (win.width || 3.5) * scale;
            let wx, wy;

            if (win.wall === 'S') {
              wx = toSvgX(win.x);
              wy = toSvgY(0, 0);
              return (
                <g key={`win-${idx}`} className="cad-window-mark">
                  <rect x={wx} y={wy - 4} width={wLen} height="8" fill="#0a0e17" stroke="#38bdf8" strokeWidth="1" />
                  <line x1={wx} y1={wy - 2} x2={wx + wLen} y2={wy - 2} stroke="#38bdf8" strokeWidth="1.5" />
                  <line x1={wx} y1={wy + 2} x2={wx + wLen} y2={wy + 2} stroke="#38bdf8" strokeWidth="1.5" />
                  <text x={wx + wLen / 2} y={wy + 15} textAnchor="middle" className="opening-tag" fill="#38bdf8">
                    W {formatDim(win.width || 3.5)}
                  </text>
                </g>
              );
            } else if (win.wall === 'N') {
              wx = toSvgX(win.x);
              wy = toSvgY(L_build, 0);
              return (
                <g key={`win-${idx}`} className="cad-window-mark">
                  <rect x={wx} y={wy - 4} width={wLen} height="8" fill="#0a0e17" stroke="#38bdf8" strokeWidth="1" />
                  <line x1={wx} y1={wy - 2} x2={wx + wLen} y2={wy - 2} stroke="#38bdf8" strokeWidth="1.5" />
                  <line x1={wx} y1={wy + 2} x2={wx + wLen} y2={wy + 2} stroke="#38bdf8" strokeWidth="1.5" />
                  <text x={wx + wLen / 2} y={wy - 8} textAnchor="middle" className="opening-tag" fill="#38bdf8">
                    W {formatDim(win.width || 3.5)}
                  </text>
                </g>
              );
            } else if (win.wall === 'W') {
              wx = toSvgX(0);
              wy = toSvgY(win.y, win.width || 3.5);
              return (
                <g key={`win-${idx}`} className="cad-window-mark">
                  <rect x={wx - 4} y={wy} width="8" height={wLen} fill="#0a0e17" stroke="#38bdf8" strokeWidth="1" />
                  <line x1={wx - 2} y1={wy} x2={wx - 2} y2={wy + wLen} stroke="#38bdf8" strokeWidth="1.5" />
                  <line x1={wx + 2} y1={wy} x2={wx + 2} y2={wy + wLen} stroke="#38bdf8" strokeWidth="1.5" />
                  <text x={wx - 14} y={wy + wLen / 2} textAnchor="middle" className="opening-tag" fill="#38bdf8">
                    W
                  </text>
                </g>
              );
            } else {
              wx = toSvgX(W_build);
              wy = toSvgY(win.y, win.width || 3.5);
              return (
                <g key={`win-${idx}`} className="cad-window-mark">
                  <rect x={wx - 4} y={wy} width="8" height={wLen} fill="#0a0e17" stroke="#38bdf8" strokeWidth="1" />
                  <line x1={wx - 2} y1={wy} x2={wx - 2} y2={wy + wLen} stroke="#38bdf8" strokeWidth="1.5" />
                  <line x1={wx + 2} y1={wy} x2={wx + 2} y2={wy + wLen} stroke="#38bdf8" strokeWidth="1.5" />
                  <text x={wx + 14} y={wy + wLen / 2} textAnchor="middle" className="opening-tag" fill="#38bdf8">
                    W
                  </text>
                </g>
              );
            }
          })}

          {showDoors && layout?.doors?.map((door, idx) => {
            const dLen = (door.width || 3.0) * scale;

            if (door.orientation === 'horizontal') {
              const dx = toSvgX(door.x);
              const dy = toSvgY(door.y, 0);
              const arcY = dy - dLen;

              return (
                <g key={`door-${idx}`} className="cad-door-mark">
                  <rect x={dx} y={dy - 4} width={dLen} height="8" fill="#0a0e17" />
                  <line x1={dx} y1={dy} x2={dx} y2={arcY} stroke="#f59e0b" strokeWidth="2.5" />
                  <path
                    d={`M ${dx} ${arcY} A ${dLen} ${dLen} 0 0 1 ${dx + dLen} ${dy}`}
                    fill="none"
                    stroke="#f59e0b"
                    strokeWidth="1.2"
                    strokeDasharray="2 2"
                  />
                  {door.isMainEntrance && (
                    <text x={dx + dLen / 2} y={dy + 16} textAnchor="middle" className="entrance-label-cad">
                      MAIN ENTRANCE
                    </text>
                  )}
                </g>
              );
            } else {
              const dx = toSvgX(door.x);
              const dy = toSvgY(door.y, door.width || 3.0);
              const arcX = dx + dLen;

              return (
                <g key={`door-${idx}`} className="cad-door-mark">
                  <rect x={dx - 4} y={dy} width="8" height={dLen} fill="#0a0e17" />
                  <line x1={dx} y1={dy} x2={arcX} y2={dy} stroke="#f59e0b" strokeWidth="2.5" />
                  <path
                    d={`M ${arcX} ${dy} A ${dLen} ${dLen} 0 0 1 ${dx} ${dy + dLen}`}
                    fill="none"
                    stroke="#f59e0b"
                    strokeWidth="1.2"
                    strokeDasharray="2 2"
                  />
                  {door.isMainEntrance && (
                    <text x={arcX + 14} y={dy + dLen / 2} textAnchor="middle" className="entrance-label-cad">
                      ENTRANCE
                    </text>
                  )}
                </g>
              );
            }
          })}

          {showDimensions && (
            <g id="dimension-strings">
              <line x1={bX} y1={bY - 24} x2={bX + bW} y2={bY - 24} stroke="#94a3b8" strokeWidth="1" />
              <line x1={bX - 4} y1={bY - 20} x2={bX + 4} y2={bY - 28} stroke="#94a3b8" strokeWidth="1.5" />
              <line x1={bX + bW - 4} y1={bY - 20} x2={bX + bW + 4} y2={bY - 28} stroke="#94a3b8" strokeWidth="1.5" />
              <text x={bX + bW / 2} y={bY - 30} textAnchor="middle" className="cad-dim-text">
                {formatDim(buildable.width)} (BUILDABLE WIDTH)
              </text>

              <line x1={bX - 24} y1={bY} x2={bX - 24} y2={bY + bH} stroke="#94a3b8" strokeWidth="1" />
              <line x1={bX - 28} y1={bY - 4} x2={bX - 20} y2={bY + 4} stroke="#94a3b8" strokeWidth="1.5" />
              <line x1={bX - 28} y1={bY + bH - 4} x2={bX - 20} y2={bY + bH + 4} stroke="#94a3b8" strokeWidth="1.5" />
              <text
                x={bX - 32}
                y={bY + bH / 2}
                textAnchor="middle"
                transform={`rotate(-90 ${bX - 32} ${bY + bH / 2})`}
                className="cad-dim-text"
              >
                {formatDim(buildable.length)} (BUILDABLE LENGTH)
              </text>
            </g>
          )}

          <g id="entrance-indicator">
            {input.entrance === 'S' && (
              <g transform={`translate(${margin + (plotW * scale) / 2}, ${margin + plotL * scale + 24})`}>
                <polygon points="0,0 -8,12 8,12" fill="#10b981" />
                <text y="24" textAnchor="middle" className="cad-entrance-tag" fill="#10b981">
                  MAIN ENTRANCE (SOUTH)
                </text>
              </g>
            )}
            {input.entrance === 'N' && (
              <g transform={`translate(${margin + (plotW * scale) / 2}, ${margin - 30})`}>
                <polygon points="0,0 -8,-12 8,-12" fill="#10b981" />
                <text y="-16" textAnchor="middle" className="cad-entrance-tag" fill="#10b981">
                  MAIN ENTRANCE (NORTH)
                </text>
              </g>
            )}
            {input.entrance === 'E' && (
              <g transform={`translate(${margin + plotW * scale + 30}, ${margin + (plotL * scale) / 2})`}>
                <polygon points="0,0 12,-8 12,8" fill="#10b981" />
                <text x="18" y="4" textAnchor="start" className="cad-entrance-tag" fill="#10b981">
                  ENTRANCE (EAST)
                </text>
              </g>
            )}
            {input.entrance === 'W' && (
              <g transform={`translate(${margin - 30}, ${margin + (plotL * scale) / 2})`}>
                <polygon points="0,0 -12,-8 -12,8" fill="#10b981" />
                <text x="-18" y="4" textAnchor="end" className="cad-entrance-tag" fill="#10b981">
                  ENTRANCE (WEST)
                </text>
              </g>
            )}
          </g>

          <g id="compass-rose" transform={`translate(${svgWidth - 52}, 52)`}>
            <circle r="24" fill="rgba(15, 23, 42, 0.9)" stroke="#334155" strokeWidth="1.5" />
            <g transform={`rotate(${northRotation})`}>
              <polygon points="0,-18 5,-2 0,0 -5,-2" fill="#ef4444" />
              <polygon points="0,18 5,2 0,0 -5,2" fill="#94a3b8" />
              <polygon points="18,0 2,5 0,0 2,-5" fill="#475569" />
              <polygon points="-18,0 -2,5 0,0 -2,-5" fill="#475569" />
              <text y="-7" textAnchor="middle" fill="#f8fafc" fontSize="8" fontWeight="bold">N</text>
            </g>
          </g>
        </svg>
      </div>

      <div className="cad-canvas-bottom-bar">
        <div className="cad-stat-pills">
          <span className="cad-pill">Plot: {plotW}' × {plotL}' ({plotW * plotL} sq ft)</span>
          <span className="cad-pill highlight">Buildable: {buildable.width}' × {buildable.length}' ({buildable.area} sq ft)</span>
          <span className="cad-pill">Rooms: {layout?.rooms?.length || 0}</span>
          <span className="cad-pill">Doors: {layout?.doors?.length || 0}</span>
          <span className="cad-pill">Windows: {layout?.windows?.length || 0}</span>
        </div>
        <div className="cad-hint-text">
          Click any room to inspect &amp; pin · Scroll wheel to zoom · Drag to pan sheet
        </div>
      </div>
    </div>
  );
}
