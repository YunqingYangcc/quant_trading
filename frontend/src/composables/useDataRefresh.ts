/**
 * 跨页面数据刷新信号 - 当一个页面更新了数据，通知其他页面重新加载
 */
const LISTENERS: Record<string, Set<() => void>> = {}

export function useDataRefresh(key: string = 'default') {
  function notify() {
    const set = LISTENERS[key]
    if (set) set.forEach(fn => fn())
  }

  function onRefresh(fn: () => void) {
    if (!LISTENERS[key]) LISTENERS[key] = new Set()
    const set = LISTENERS[key]!
    set.add(fn)
    return () => set.delete(fn)
  }

  return { notify, onRefresh }
}
