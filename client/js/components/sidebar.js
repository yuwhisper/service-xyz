import React from 'react';
import { useAuth } from '../auth.js';

const navItems = [
  { key: 'dashboard', icon: '📊', label: '数据中心' },
  { key: 'dispatch', icon: '⚡', label: '调度任务' },
  { key: 'schedule', icon: '⏰', label: '定时任务' },
];

export default function Sidebar({ active, onNavigate }) {
  const { user, logout } = useAuth();
  const initial = (user?.username || 'A')[0].toUpperCase();

  return React.createElement('aside', { className: 'sidebar' },
    React.createElement('div', { className: 'sidebar-logo' },
      React.createElement('span', { className: 'logo-icon' }, '⚙'),
      'Service XYZ'
    ),
    React.createElement('nav', { className: 'sidebar-nav' },
      ...navItems.map(item =>
        React.createElement('div', {
          key: item.key,
          className: `sidebar-item${active === item.key ? ' active' : ''}`,
          onClick: () => onNavigate(item.key),
        },
          React.createElement('span', { className: 'nav-icon' }, item.icon),
          React.createElement('span', null, item.label)
        )
      )
    ),
    React.createElement('div', { className: 'sidebar-user' },
      React.createElement('div', { className: 'avatar' }, initial),
      React.createElement('span', null, user?.username || 'User'),
      React.createElement('button', { className: 'logout-btn', onClick: logout }, '退出')
    )
  );
}
