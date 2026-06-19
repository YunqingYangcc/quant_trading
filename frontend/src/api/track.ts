/**
 * 赛道管理 API
 */
import request from './index'

export interface Track {
  id: string
  name: string
  display_name: string
  description: string | null
  sort_order: number
  is_active: number
  stock_count: number
  stocks: TrackStock[]
  created_at: string
}

export interface TrackStock {
  code: string
  name: string
  ipo_date: string | null
  status: string | null
}

export interface LabelDataPoint {
  stock_code: string
  trade_date: string
  close_px: number
  open_px: number
  high_px: number
  low_px: number
  volume: number
  amount: number
  fwd_1d_return: number | null
  fwd_5d_return: number | null
  fwd_20d_return: number | null
}

export function listTracks() {
  return request.get('/track/tracks')
}

export function getTrack(id: string) {
  return request.get(`/track/tracks/${id}`)
}

export function createTrack(data: { name: string; display_name: string; description?: string }) {
  return request.post('/track/tracks', data)
}

export function deleteTrack(id: string) {
  return request.delete(`/track/tracks/${id}`)
}

export function listStocks(trackId?: string) {
  const params = trackId ? { track_id: trackId } : {}
  return request.get('/track/stocks', { params })
}

export function assignStock(data: { stock_code: string; stock_name: string; track_ids: string[] }) {
  return request.post('/track/stocks/assign', data)
}

export function getLabels(stockCode: string) {
  return request.get(`/track/labels/${stockCode}`)
}

export function getWhitelist() {
  return request.get('/track/factors/whitelist')
}

export function getBlacklist() {
  return request.get('/track/factors/blacklist')
}

export function getTrackScore(trackName: string) {
  return request.get(`/api/ml/score/${trackName}`)
}

export function listTrackModels(trackName: string) {
  return request.get(`/api/ml/models/${trackName}`)
}

export function trainTrackModel(trackName: string) {
  return request.post(`/api/ml/train/${trackName}`)
}
