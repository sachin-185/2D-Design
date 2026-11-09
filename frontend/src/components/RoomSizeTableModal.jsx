import React from 'react';
import { X, Table } from 'lucide-react';
import { ROOM_SIZE_TABLE } from '../engine/contracts';

export default function RoomSizeTableModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <Table size={18} className="text-cyan" />
            <h3>P3 Room Size Reference Contract (10 Standard Types)</h3>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-subtitle">
            Shared contract standards agreed for P3 schema and solver. The engine picks sizes within these ranges.
          </p>

          <table className="room-table">
            <thead>
              <tr>
                <th>Room Type</th>
                <th>Minimum (ft)</th>
                <th>Preferred (ft)</th>
                <th>Maximum (ft)</th>
                <th>Outer Wall Access</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(ROOM_SIZE_TABLE).map((key) => {
                const item = ROOM_SIZE_TABLE[key];
                return (
                  <tr key={key}>
                    <td>
                      <div className="room-cell">
                        <span className="color-dot" style={{ backgroundColor: item.color }} />
                        <span className="font-semibold">{item.name}</span>
                      </div>
                    </td>
                    <td>{item.min.w} × {item.min.h} ({item.min.area} sq ft)</td>
                    <td>{item.preferred.w} × {item.preferred.h} ({item.preferred.area} sq ft)</td>
                    <td>{item.max.w} × {item.max.h} ({item.max.area} sq ft)</td>
                    <td>
                      {item.outerWallRequired ? (
                        <span className="badge-required">Required (H8)</span>
                      ) : (
                        <span className="badge-optional">Optional</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="modal-footer-note">
            <em>Note: Pinned values in the Edit Panel take precedence over table defaults. P3 schema strictly allows these 10 types.</em>
          </div>
        </div>
      </div>
    </div>
  );
}
