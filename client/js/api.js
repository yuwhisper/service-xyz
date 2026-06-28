import axios from 'axios';

const http = axios.create({ baseURL: '', timeout: 30000 });
http.interceptors.request.use(c => {
  const t = localStorage.getItem('token');
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});
http.interceptors.response.use(r => r, err => {
  if (err.response?.status === 401) { localStorage.removeItem('token'); window.location.reload(); }
  return Promise.reject(err);
});
export default http;
