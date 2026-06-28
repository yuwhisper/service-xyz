import React from 'react';

export default function Modal({ title, onClose, children, footer }) {
  return React.createElement('div', { className: 'modal-overlay', onClick: (e) => { if (e.target === e.currentTarget) onClose(); } },
    React.createElement('div', { className: 'modal-box' },
      React.createElement('div', { className: 'modal-header' },
        React.createElement('h2', null, title),
        React.createElement('button', { className: 'modal-close', onClick: onClose }, '✕')
      ),
      React.createElement('div', null, children),
      footer ? React.createElement('div', { className: 'modal-footer' }, footer) : null
    )
  );
}
