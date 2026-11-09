import React, { useState, useEffect } from 'react';
import { 
  Pin, 
  Unlock, 
  CheckCircle2, 
  AlertTriangle, 
  DollarSign, 
  Layers, 
  Maximize2,
  Table,
  ShieldCheck,
  X
} from 'lucide-react';
import { calculateFlooringEstimate, FLOORING_MATERIALS, SQFT_TO_SQM } from '../engine/materials';
import { ROOM_SIZE_TABLE } from '../engine/contracts';

export default function RightSidebar({
  layout,
  input,
  selectedRoom,
  onSelectRoom,
  onApplyPin,
  unitSystem = 'imperial',
  customRoomFlooring = {},
  onChangeRoomFlooring,
  problems = [],
}) {
  const rooms = layout?.rooms || [];
  const estimate = calculateFlooringEstimate(rooms, customRoomFlooring);

  const [pinWidth, setPinWidth] = useState(selectedRoom?.w || 12);
  const [pinHeight, setPinHeight] = useState(selectedRoom?.h || 12);

  useEffect(() => {
    if (selectedRoom) {
      setPinWidth(selectedRoom.w || 12);
      setPinHeight(selectedRoom.h || 12);
    }
  }, [selectedRoom]);

  const handleSavePin = () => {
    if (!selectedRoom) return;
    onApplyPin({
      room: selectedRoom.name,
      width: parseInt(pinWidth, 10),
      height: parseInt(pinHeight, 10),
      locked: true,
    });
  };

  const handleUnpin = () => {
    if (!selectedRoom) return;
    const filtered = (input.pins || []).filter((p) => p.room !== selectedRoom.name);
    onApplyPin({ room: selectedRoom.name, clear: true, remaining: filtered });
  };

  const isRoomPinned = input.pins?.some((p) => p.room === selectedRoom?.name);

  const formatArea = (sqft, sqm) => {
    if (unitSystem === 'metric') {
      return `${sqm} m²`;
    }
    return `${sqft} sq ft`;
  };

  return (
    <aside className="cad-right-panel">
      {selectedRoom && (
        <div className="cad-right-section inspector-section">
          <div className="section-title-bar">
            <span className="section-heading">Room Inspector: {selectedRoom.name}</span>
            <button
              type="button"
              className="btn-close-mini"
              onClick={() => onSelectRoom(null)}
            >
              <X size={12} />
            </button>
          </div>

          <div className="inspector-grid">
            <div className="input-group-half">
              <span className="field-hint">Width (ft)</span>
              <input
                type="number"
                min="5"
                max="40"
                className="cad-input-num"
                value={pinWidth}
                onChange={(e) => setPinWidth(e.target.value)}
              />
            </div>
            <div className="input-group-half">
              <span className="field-hint">Height (ft)</span>
              <input
                type="number"
                min="5"
                max="40"
                className="cad-input-num"
                value={pinHeight}
                onChange={(e) => setPinHeight(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group-compact">
            <span className="field-hint">Floor Finish Material</span>
            <select
              className="cad-input-select"
              value={customRoomFlooring[selectedRoom.name] || estimate.rooms.find((r) => r.name === selectedRoom.name)?.materialId || 'oak'}
              onChange={(e) => onChangeRoomFlooring(selectedRoom.name, e.target.value)}
            >
              {Object.values(FLOORING_MATERIALS).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} (${m.ratePerSqm}/m²)
                </option>
              ))}
            </select>
          </div>

          <div className="pin-action-buttons">
            <button
              type="button"
              className="btn-pin-solid"
              onClick={handleSavePin}
              title="Pin room dimensions for minimal-change re-solve (S6)"
            >
              <Pin size={12} /> {isRoomPinned ? 'Update Pin' : 'Pin Dimensions'}
            </button>
            {isRoomPinned && (
              <button
                type="button"
                className="btn-unpin-ghost"
                onClick={handleUnpin}
                title="Remove pin"
              >
                <Unlock size={12} /> Unpin
              </button>
            )}
          </div>
        </div>
      )}

      <div className="cad-right-section">
        <div className="section-title-bar">
          <span className="section-heading">Space Schedule</span>
          <span className="section-meta-tag">{rooms.length} Spaces</span>
        </div>

        <div className="space-schedule-table">
          <div className="schedule-header-row">
            <span>Room</span>
            <span>Dimensions</span>
            <span className="col-right">Area</span>
          </div>

          {estimate.rooms.map((room) => {
            const isSelected = selectedRoom?.name === room.name;
            const rColor = ROOM_SIZE_TABLE[room.type]?.color || '#38bdf8';
            const matchedRoom = rooms.find((r) => r.name === room.name);

            return (
              <div
                key={room.name}
                className={`schedule-data-row ${isSelected ? 'active' : ''}`}
                onClick={() => onSelectRoom(matchedRoom)}
              >
                <div className="schedule-room-name">
                  <span className="room-color-tag" style={{ backgroundColor: rColor }} />
                  <span className="name-str">{room.name}</span>
                </div>
                <div className="schedule-dim-str">
                  {matchedRoom?.w}' × {matchedRoom?.h}'
                </div>
                <div className="schedule-area-val col-right">
                  {formatArea(room.sqft, room.sqm)}
                </div>
              </div>
            );
          })}

          <div className="schedule-total-row">
            <span className="total-label">Total Net Usable Area</span>
            <span className="total-val col-right">
              {formatArea(estimate.totalNetSqft, estimate.totalNetSqm)}
            </span>
          </div>
        </div>
      </div>

      <div className="cad-right-section">
        <div className="section-title-bar">
          <span className="section-heading">Flooring Takeoff &amp; BOQ</span>
          <span className="section-meta-tag">+5% Waste</span>
        </div>

        <div className="boq-table">
          {estimate.breakdown.map((item) => (
            <div key={item.material.id} className="boq-row">
              <div className="boq-name-cell">
                <span className="boq-material-dot" style={{ backgroundColor: item.material.color }} />
                <span>{item.material.name}</span>
              </div>
              <div className="boq-data-cell">
                <span className="boq-qty">{item.withWasteSqm} m²</span>
                <span className="boq-cost">${item.totalCost.toLocaleString()}</span>
              </div>
            </div>
          ))}

          <div className="boq-total-row">
            <span className="boq-total-title">Total Flooring Estimate</span>
            <span className="boq-total-price">${estimate.totalCost.toLocaleString()}</span>
          </div>
        </div>
      </div>

      <div className="cad-right-section diagnostics-section">
        <div className="section-title-bar">
          <span className="section-heading">Architectural Checker</span>
          <span className={`checker-badge ${problems.length === 0 ? 'clean' : 'notices'}`}>
            {problems.length === 0 ? 'Pass' : `${problems.length} Notices`}
          </span>
        </div>

        <div className="checker-problems-list">
          {problems.length === 0 ? (
            <div className="checker-clean-message">
              <ShieldCheck size={14} className="text-emerald" />
              <span>All H1-H11 architectural constraints satisfied.</span>
            </div>
          ) : (
            problems.map((p, idx) => (
              <div key={idx} className={`checker-problem-item ${p.severity}`}>
                <span className="problem-code">{p.code}</span>
                <span className="problem-text">{p.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </aside>
  );
}
