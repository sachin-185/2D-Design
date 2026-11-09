import React from 'react';
import { CheckCircle2, Award, Eye, Sparkles } from 'lucide-react';
import { ROOM_SIZE_TABLE } from '../engine/contracts';

export default function ThreeLayoutsView({ layouts, activeLayoutId, onSelectLayout }) {
  if (!layouts || layouts.length === 0) return null;

  const isSingle = layouts.length === 1;

  return (
    <div className="three-layouts-container">
      <div className="section-header">
        <div className="header-left">
          <Sparkles size={18} className="text-amber" />
          <h3>{isSingle ? 'Generated Architectural Layout (P3 Engine)' : `${layouts.length} Valid Architectural Variants`}</h3>
        </div>
        <span className="badge-variants">
          {isSingle ? 'Active P3 Engine Solution' : 'Different Archetypes (H1-H11 Validated)'}
        </span>
      </div>

      <div className={`layouts-grid ${isSingle ? 'single-layout' : ''}`}>
        {layouts.map((item, index) => {
          const isActive = item.id === activeLayoutId;
          const isBestScore = index === 0;
          const segments = item.hallway_segments || (item.hallway ? [{ id: 'hallway_1', ...item.hallway }] : []);

          return (
            <div
              key={item.id}
              className={`layout-card ${isActive ? 'active' : ''}`}
              onClick={() => onSelectLayout(item.id)}
            >
              <div className="card-top">
                <div className="card-title-group">
                  <span className="variant-tag">Layout #{item.variantNumber || index + 1}</span>
                  <h4 className="archetype-name">{item.archetype || 'Central Core'}</h4>
                </div>
                <div className="score-container">
                  {isBestScore && layouts.length > 1 && (
                    <span className="best-badge" title="Lowest penalty score">
                      <Award size={12} /> Best Fit
                    </span>
                  )}
                  {item.score !== undefined && (
                    <span className="score-badge">
                      Penalty: <strong>{item.score}</strong>
                    </span>
                  )}
                </div>
              </div>

              <div className="mini-preview">
                <svg viewBox="0 0 160 120" className="mini-svg">
                  {segments.map((seg, sIdx) => {
                    const sx = 10 + (seg.x / 30) * 140;
                    const sy = 110 - ((seg.y + seg.h) / 40) * 100;
                    const sw = Math.max(4, (seg.w / 30) * 140);
                    const sh = Math.max(4, (seg.h / 40) * 100);
                    return (
                      <rect
                        key={seg.id || sIdx}
                        x={sx}
                        y={sy}
                        width={sw}
                        height={sh}
                        fill="rgba(148, 163, 184, 0.25)"
                        stroke="#64748b"
                        strokeWidth="0.8"
                      />
                    );
                  })}

                  {item.rooms?.map((r) => {
                    const config = ROOM_SIZE_TABLE[r.type] || ROOM_SIZE_TABLE.bedroom;
                    const mx = 10 + (r.x / 30) * 140;
                    const my = 110 - ((r.y + r.h) / 40) * 100;
                    const mw = Math.max(8, (r.w / 30) * 140);
                    const mh = Math.max(8, (r.h / 40) * 100);

                    return (
                      <rect
                        key={r.name}
                        x={mx}
                        y={my}
                        width={mw}
                        height={mh}
                        fill={config.lightColor || 'rgba(59, 130, 246, 0.2)'}
                        stroke={config.color || '#3b82f6'}
                        strokeWidth="1"
                        rx="1"
                      />
                    );
                  })}
                </svg>
              </div>

              <div className="card-footer-metrics">
                <div className="room-chips-list">
                  {item.rooms?.map((r) => (
                    <span key={r.name} className="mini-chip">
                      {r.name} ({r.w}'×{r.h}')
                    </span>
                  ))}
                </div>

                <div className="card-select-btn">
                  {isActive ? (
                    <span className="selected-indicator">
                      <CheckCircle2 size={14} /> Active In Canvas
                    </span>
                  ) : (
                    <span className="view-link">
                      <Eye size={14} /> View Layout
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
