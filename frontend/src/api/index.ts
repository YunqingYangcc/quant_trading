import axios from 'axios'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1',
  timeout: 30000,
})

request.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(err),
)

export default request
