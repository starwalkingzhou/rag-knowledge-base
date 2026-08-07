import type { CSSProperties } from 'react'
import { Select } from 'antd'
import type { BadCaseCategory } from '@/api/evaluation'
import { BAD_CASE_CATEGORY_LABELS } from '@/utils/badCaseCategory'

interface Props {
    value: BadCaseCategory | null | undefined
    onChange: (value: BadCaseCategory | null) => void
    allowClear?: boolean
    style?: CSSProperties
    placeholder?: string
}

export function BadCaseCategorySelect({
    value,
    onChange,
    allowClear = true,
    style,
    placeholder,
}: Props) {
    return (
        <Select
            value={value ?? undefined}
            onChange={(v) => onChange((v as BadCaseCategory) ?? null)}
            onClear={() => onChange(null)}
            allowClear={allowClear}
            placeholder={placeholder}
            style={{ minWidth: 200, ...style }}
            options={(Object.keys(BAD_CASE_CATEGORY_LABELS) as BadCaseCategory[]).map((key) => ({
                value: key,
                label: BAD_CASE_CATEGORY_LABELS[key],
            }))}
        />
    )
}