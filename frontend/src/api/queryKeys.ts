/**
 * 跨组件共享的 TanStack Query key 集中定义。
 *
 * 抽出来是为了:
 * 1. 组件文件只 export 组件,满足 react-refresh/only-export-components
 * 2. 不同组件里 invalidate / removeQueries 用同一份 key,避免硬编码字符串数组散落
 */
export const conversationsQueryKey = ['conversations'] as const

export const evaluationRunsKey = ['evaluation-runs'] as const

export const evaluationRunKey = (runId: string) => ['evaluation-run', runId] as const

export const evaluationItemsKey = (
    runId: string,
    filters: { badCaseOnly: boolean; category: string | null; page: number },
) => ['evaluation-items', runId, filters] as const

export const evaluationDatasetsKey = ['evaluation-datasets'] as const