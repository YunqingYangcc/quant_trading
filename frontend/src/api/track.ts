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
  return request.get(`/ml/score/${trackName}`)
}

export function getAllTrackScores() {
  return request.get('/ml/scores')
}

export function trainTrackModel(trackName: string, params?: {
  num_leaves?: number
  max_depth?: number
  learning_rate?: number
  n_estimators?: number
  reg_alpha?: number
  reg_lambda?: number
  feature_fraction?: number
  bagging_fraction?: number
  min_child_samples?: number
}) {
  return request.post(`/ml/train/${trackName}`, params || {})
}

export function trainAllModels() {
  return request.get('/ml/train/all')
}

export function listTrackModels(trackName: string) {
  return request.get(`/ml/models/${trackName}`)
}

export function getScoreHistory(trackName: string, limit = 5) {
  return request.get(`/ml/score/history/${trackName}`, { params: { limit } })
}

export function getAllModels() {
  return request.get('/ml/models/all')
}

export function getFactorData(params?: { track_name?: string; stock_code?: string; max_rows?: number }) {
  return request.get('/ml/factors/data', { params })
}

export function getPortfolioSummary() {
  return request.get('/portfolio/summary')
}

export function getBacktestReport() {
  return request.get('/backtest/report')
}

export function getBacktestEquity() {
  return request.get('/backtest/equity')
}

// ── 策略回测 ──

export function listStrategies() {
  return request.get('/backtest/strategies')
}

export function getStrategyDetail(name: string) {
  return request.get(`/backtest/strategies/${name}`)
}

export function runStrategyBacktest(strategyName: string) {
  return request.post(`/backtest/strategy/${strategyName}`)
}

export function runSingleStockBacktest(stockCode: string, strategy?: string, lookback?: number, stopLoss?: number, useAi?: boolean) {
  const params: Record<string, any> = { strategy, lookback, stop_loss: stopLoss }
  if (useAi) params.use_ai = true
  return request.post(`/backtest/single/${stockCode}`, null, { params })
}

export function runBacktest(data: {
  initial_capital: number
  top_n: number
  rebalance_freq: string
  max_single_stock: number
  max_single_track: number
}) {
  return request.post('/backtest/run', data)
}

export function computeFeatures() {
  return request.post('/ml/compute-features')
}

export function screenFactors() {
  return request.post('/ml/screen-factors')
}

export function preprocessFeatures() {
  return request.post('/ml/preprocess')
}

export function runPipeline(step: string = 'all') {
  return request.post('/ml/run-pipeline', null, { params: { step } })
}

// ── 流水线运行日志 ──

export interface PipelineRun {
  id: number
  run_type: 'train' | 'backtest'
  status: string
  params_snapshot: Record<string, any> | null
  results_summary: Record<string, any> | null
  git_commit_hash: string | null
  feature_count: number | null
  duration_seconds: number | null
  created_at: string
}

export function getPipelineRuns(limit = 10, runType?: string) {
  const params: Record<string, any> = { limit }
  if (runType) params.run_type = runType
  return request.get('/ml/pipeline-runs', { params })
}

// ── 特征配置 CRUD ──

export interface FeatureConfig {
  id: number
  feature_name: string
  display_name: string
  category: string | null
  description: string | null
  formula: string | null
  interpretation: string | null
  default_params: Record<string, any> | null
  is_enabled: number
  is_user_defined: number
  created_at: string
  updated_at: string | null
}

export interface FeatureConfigCreate {
  feature_name: string
  display_name?: string
  category?: string
  description?: string
  formula?: string
  interpretation?: string
  default_params?: Record<string, any>
  is_enabled?: number
}

export interface FeatureConfigUpdate {
  display_name?: string
  category?: string
  description?: string
  formula?: string
  interpretation?: string
  default_params?: Record<string, any>
  is_enabled?: number
}

export function listFeatureConfigs(params?: { category?: string; enabled_only?: boolean }) {
  return request.get('/features/configs', { params })
}

export function getFeatureConfig(id: number) {
  return request.get(`/features/configs/${id}`)
}

export function createFeatureConfig(data: FeatureConfigCreate) {
  return request.post('/features/configs', data)
}

export function updateFeatureConfig(id: number, data: FeatureConfigUpdate) {
  return request.put(`/features/configs/${id}`, data)
}

export function deleteFeatureConfig(id: number) {
  return request.delete(`/features/configs/${id}`)
}

export function toggleFeatureConfig(id: number) {
  return request.put(`/features/configs/${id}/toggle`)
}

export function syncFeatureConfigs() {
  return request.post('/features/sync')
}

export function incrementalCompute() {
  return request.post('/features/compute/incremental')
}

// ── 量化交易员学习和成长平台 API ──

export function compareStrategies(data: {
  strategies: string[]
  track_name: string
  initial_capital?: number
  top_n?: number
  rebalance_freq?: string
  max_single_stock?: number
  max_single_track?: number
  stop_loss_pct?: number
  take_profit_pct?: number
}) {
  return request.post('/backtest/compare', data)
}

export function getBacktestHistory(limit = 20) {
  return request.get('/backtest/history', { params: { limit } })
}

export function getBacktestDetail(runId: number) {
  return request.get(`/backtest/history/${runId}`)
}

export function getLearningStats() {
  return request.get('/learning/stats')
}
