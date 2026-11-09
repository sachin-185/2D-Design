import React, { useState, useEffect } from 'react';
import {
  Lock, Unlock, Pin, RotateCcw, Play,
  Info,
  AlertTriangle
} from 'lucide-react';
import { ROOM_SIZE_TABLE, getBuildableArea } from '../engine/contracts';

export default function EditPanel({
  selectedRoom,
  input,
  onApplyPin,
  onClearPins,
  isSolving
}) {
  const [pinnedW, setPinnedW] = useState('');
  const [pinnedH, setPinnedH] = useState('');
  const [isLocked, setIsLocked] = useState(false);

  useEffect(() => {
    if (selectedRoom) {
      const existingPin = input.pins?.find((p) => p.room === selectedRoom.name);
      setPinnedW(existingPin?.width || selectedRoom.w || '');
      setPinnedH(existingPin?.height || selectedRoom.h || '');
      setIsLocked(Boolean(existingPin?.locked));
    }
  }, [selectedRoom, input.pins]);

  if (!selectedRoom) {
    return (
      <div className="edit-panel-empty">
        <Info size={24} className="text-slate-400" />
        <h4>Interactive Room Inspector</h4>
        <p>Click any room on the 2D floorplan to inspect properties, pin exact dimensions, lock accepted rooms, and re-solve cleanly.</p>
      </div>
    );
  }

  const roomConfig = ROOM_SIZE_TABLE[selectedRoom.type] || ROOM_SIZE_TABLE.bedroom;
  const buildable = getBuildableArea(input.plot, input.setbacks);

  const numericW = parseInt(pinnedW, 10) || selectedRoom.w;
  const numericH = parseInt(pinnedH, 10) || selectedRoom.h;

  const isWidthValid = numericW >= roomConfig.min.w && numericW <= roomConfig.max.w && numericW <= buildable.width;
  const isHeightValid = numericH >= roomConfig.min.h && numericH <= roomConfig.max.h && numericH <= buildable.length;

  const handleApplyAndSolve = () => {
    onApplyPin({
      room: selectedRoom.name,
      width: parseInt(pinnedW, 10) || undefined,
      height: parseInt(pinnedH, 10) || undefined,
      locked: isLocked,
    });
  };

  const handleSetNearestValid = () => {
    setPinnedW(roomConfig.preferred.w);
    setPinnedH(roomConfig.preferred.h);
  };

  return (
    <div className="edit-panel-card">
      <div className="panel-header">
        <div className="panel-title-group">
          <Pin size={16} className="text-amber" />
          <h3>Edit & Pin Room: {selectedRoom.name}</h3>
        </div>
        <span className="room-type-pill" style={{ color: roomConfig.color, borderColor: roomConfig.color }}>
          {selectedRoom.type}
        </span>
      </div>

      <div className="current-stats-box">
        <div className="stat-item">
          <span className="stat-label">Current Size:</span>
          <span className="stat-value">{selectedRoom.w}' × {selectedRoom.h}'</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Area:</span>
          <span className="stat-value">{selectedRoom.w * selectedRoom.h} sq ft</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Table Range:</span>
          <span className="stat-value">{roomConfig.min.w}'-{roomConfig.max.w}' × {roomConfig.min.h}'-{roomConfig.max.h}'</span>
        </div>
      </div>

      <div className="pin-controls-grid">
        <div className="pin-field">
          <label className="pin-label">Pin Width (ft):</label>
          <input
            type="number"
            min={roomConfig.min.w}
            max={Math.min(roomConfig.max.w, buildable.width)}
            value={pinnedW}
            onChange={(e) => setPinnedW(e.target.value)}
            className={`number-input ${!isWidthValid ? 'border-error' : ''}`}
          />
        </div>
        <div className="pin-field">
          <label className="pin-label">Pin Height (ft):</label>
          <input
            type="number"
            min={roomConfig.min.h}
            max={Math.min(roomConfig.max.h, buildable.length)}
            value={pinnedH}
            onChange={(e) => setPinnedH(e.target.value)}
            className={`number-input ${!isHeightValid ? 'border-error' : ''}`}
          />
        </div>
      </div>

      <div className="lock-toggle-row" onClick={() => setIsLocked(!isLocked)}>
        {isLocked ? (
          <Lock size={16} className="text-amber" />
        ) : (
          <Unlock size={16} className="text-slate-400" />
        )}
        <span className="lock-text">
          {isLocked ? 'Room is Locked (will not move or resize)' : 'Lock Room (freeze position in next solve)'}
        </span>
      </div>

      {(!isWidthValid || !isHeightValid) && (
        <div className="validation-warning">
          <AlertTriangle size={14} />
          <span>
            Dimensions outside allowed table range ({roomConfig.min.w}x{roomConfig.min.h} to {roomConfig.max.w}x{roomConfig.max.h}).
          </span>
          <button type="button" className="btn-link" onClick={handleSetNearestValid}>
            Use Nearest Preferred ({roomConfig.preferred.w}'×{roomConfig.preferred.h}')
          </button>
        </div>
      )}

      <div className="panel-actions-row">
        <button
          type="button"
          className="btn-resolve"
          onClick={handleApplyAndSolve}
          disabled={isSolving}
        >
          <Play size={15} />
          <span>{isSolving ? 'Re-solving...' : 'Re-solve Model (S6)'}</span>
        </button>

        <button
          type="button"
          className="btn-clear-pins"
          onClick={onClearPins}
          title="Clear all pinned sizes"
        >
          <RotateCcw size={14} /> Clear Pins
        </button>
      </div>

      <div className="helper-note">
        <Info size={12} />
        <span>Rule S6: Pinned dimensions trigger CP-SAT re-solve with minimal changes to adjacent rooms.</span>
      </div>
    </div>
  );
}
