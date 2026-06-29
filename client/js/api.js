import axios from 'axios';

const http = axios.create({ baseURL: '', timeout: 30000 });
http.interceptors.request.use(c => {
  const t = localStorage.getItem('token');
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});
export default http;
