import React from 'react';
import { 
  AlertTriangle, 
  AlertCircle, 
  CheckCircle, 
  Info, 
  ShieldCheck, 
  ShieldAlert, 
  Terminal 
} from 'lucide-react';

const TEAM_CODES = [
  { code: 'I1', label: 'I1: Input Validation' },
  { code: 'H1', label: 'H1: Fit (Buildable Bounds)' },
  { code: 'H2', label: 'H2: Size Limits' },
  { code: 'H3', label: 'H3: No Overlap' },
  { code: 'H4', label: 'H4: Coverage (Advisory)' },
  { code: 'H6', label: 'H6: Required Adjacency' },
  { code: 'HW1', label: 'HW1: Hallway Width >= 3ft' },
  { code: 'HW2', label: 'HW2: Hallway Continuity' },
  { code: 'HW3', label: 'HW3: Hallway Reachability' },
  { code: 'E1', label: 'E1: Entrance Side Alignment' },
  { code: 'F1', label: 'F1: Circulation Reachability' },
  { code: 'F2', label: 'F2: Door on Shared Wall' },
  { code: 'F3', label: 'F3: Door Width Clearance' },
  { code: 'F4', label: 'F4: Door Swing Clearance' },
  { code: 'F5', label: 'F5: Forbidden Patterns' },
];

export default function MessagesPanel({ messages, feasibility, layout, problems = [], apiError }) {
  const allProblems = problems && problems.length > 0 ? problems : (layout?.problems || []);
  const errors = allProblems.filter((p) => p.severity === 'error');
  const warnings = allProblems.filter((p) => p.severity === 'warning');

  const isValid = errors.length === 0 && (!feasibility || feasibility.feasible) && !apiError;

  return (
    <div className="messages-panel-card">
      <div className="panel-header">
        <div className="panel-title-group">
          <Terminal size={16} className="text-cyan" />
          <h3>Engine Diagnostics &amp; Real Checker Results (P4)</h3>
        </div>
        <div className="status-badges-group">
          {isValid ? (
            <span className="badge-status-valid">
              <CheckCircle size={13} /> VALID LAYOUT ({warnings.length} warnings)
            </span>
          ) : (
            <span className="badge-status-invalid">
              <AlertCircle size={13} /> INVALID LAYOUT ({errors.length} errors)
            </span>
          )}
        </div>
      </div>

      {apiError && (
        <div className="api-error-banner">
          <AlertCircle size={18} />
          <div>
            <strong>Solver / API Error:</strong>
            <p>{apiError}</p>
          </div>
        </div>
      )}

      <div className="messages-stream">
        {feasibility && (
          <div className={`message-item ${feasibility.feasible ? 'info' : 'danger'}`}>
            {feasibility.feasible ? <Info size={16} /> : <AlertCircle size={16} />}
            <div className="message-content">
              <strong>Feasibility Status:</strong>
              <p>{feasibility.message}</p>
            </div>
          </div>
        )}

        {allProblems.map((prob, idx) => (
          <div key={`prob-${idx}`} className={`message-item ${prob.severity === 'error' ? 'danger' : 'warning'}`}>
            {prob.severity === 'error' ? <AlertCircle size={16} /> : <AlertTriangle size={16} />}
            <div className="message-content">
              <div className="problem-title-row">
                <span className={`code-badge ${prob.severity}`}>{prob.code}</span>
                <span className="severity-tag">{prob.severity.toUpperCase()}</span>
                {prob.rooms && prob.rooms.length > 0 && (
                  <div className="affected-rooms-tags">
                    {prob.rooms.map((rm) => (
                      <span key={rm} className="room-tag">{rm}</span>
                    ))}
                  </div>
                )}
              </div>
              <p>{prob.message}</p>
            </div>
          </div>
        ))}

        {allProblems.length === 0 && !apiError && feasibility?.feasible && (
          <div className="message-item success">
            <CheckCircle size={16} />
            <div className="message-content">
              <strong>Zero Checker Violations:</strong>
              <p>All hard rules (H1, H2, H3, H6, HW1, E1, F1, F2, F3, F5) and soft advisories are fully satisfied.</p>
            </div>
          </div>
        )}
      </div>

      <div className="rules-compliance-section">
        <div className="rules-heading">
          <ShieldCheck size={14} className="text-emerald" />
          <span>Team Rule Checker Matrix (Codes: I1, H1-H6, HW1-HW3, E1, F1-F5)</span>
        </div>
        <div className="rules-pills">
          {TEAM_CODES.map(({ code, label }) => {
            const hasError = errors.some((p) => p.code === code);
            const hasWarning = warnings.some((p) => p.code === code);
            let statusClass = 'pass';
            if (hasError) statusClass = 'fail';
            else if (hasWarning) statusClass = 'warn';

            return (
              <span key={code} className={`rule-pill ${statusClass}`}>
                {label} {hasError ? '✖' : hasWarning ? '⚠' : '✓'}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
