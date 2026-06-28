import React from 'react';
import api from './api.js';

const AuthContext = React.createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = React.useState(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      api.get('/service/zyx/auth/user/me')
        .then(r => setUser(r.data.data))
        .catch(() => localStorage.removeItem('token'))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = React.useCallback(async (username, password) => {
    const r = await api.post('/service/zyx/auth/login', { username, password });
    const { token, user: u } = r.data.data;
    localStorage.setItem('token', token);
    setUser(u);
  }, []);

  const logout = React.useCallback(() => {
    localStorage.removeItem('token');
    setUser(null);
  }, []);

  return React.createElement(AuthContext.Provider, { value: { user, loading, login, logout } }, children);
}

export function useAuth() {
  return React.useContext(AuthContext);
}
