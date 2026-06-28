import React from 'react';

export default function StatCard({ icon, value, label, color }) {
  return React.createElement('div', { className: 'stat-card' },
    React.createElement('div', { className: 'stat-icon', style: { background: color + '20', color } }, icon),
    React.createElement('div', null,
      React.createElement('div', { className: 'stat-value' }, value),
      React.createElement('div', { className: 'stat-label' }, label)
    )
  );
}
