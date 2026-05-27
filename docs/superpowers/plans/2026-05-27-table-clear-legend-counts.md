# Table Clear Legend Counts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 난이도표 클리어 분포 히스토그램 레전드에 클리어 타입별 전체 곡 수를 인라인으로 표시한다.

**Architecture:** `TableClearHistogram`이 이미 수신하는 `levels` prop에서 클리어 타입별 합계를 `useMemo`로 계산하고, `ClearTypeLegend`에 `clearTypeTotals` prop으로 전달한다. 새 API 호출 없음. 변경 파일 1개.

**Tech Stack:** React, TypeScript, Recharts (기존), `useMemo`

---

### Task 1: `ClearTypeLegend`에 카운트 표시 추가

**Files:**
- Modify: `web/src/components/charts/TableClearHistogram.tsx`

- [ ] **Step 1: `ClearTypeLegendProps`에 `clearTypeTotals` prop 추가**

`ClearTypeLegendProps` 인터페이스 (현재 line ~450)를 찾아 prop을 추가한다.

```ts
interface ClearTypeLegendProps {
  clientType?: string;
  className?: string;
  hiddenClearTypes?: Set<number>;
  legendAction?: LegendAction;
  clearTypeTotals?: Record<number, number>;  // 추가
}
```

- [ ] **Step 2: `ClearTypeLegend` 함수 시그니처에 `clearTypeTotals` 구조분해 추가**

```ts
export function ClearTypeLegend({ clientType, className, hiddenClearTypes, legendAction = { kind: "settings_link" }, clearTypeTotals }: ClearTypeLegendProps) {
```

- [ ] **Step 3: 레전드 아이템 렌더링에 카운트 표시 추가**

`items.map((ct) => ...)` 블록 안의 아이템 렌더링을 변경한다.  
현재 (line ~522):
```tsx
{items.map((ct) => (
  <div key={ct} className="flex items-center gap-1.5">
    <div
      className="w-3 h-3 rounded-sm flex-shrink-0"
      style={{ background: CLEAR_TYPE_COLORS[ct] }}
    />
    <span className="text-caption text-muted-foreground">{labelMap[ct] ?? String(ct)}</span>
  </div>
))}
```

변경 후:
```tsx
{items.map((ct) => (
  <div key={ct} className="flex items-center gap-1.5">
    <div
      className="w-3 h-3 rounded-sm flex-shrink-0"
      style={{ background: CLEAR_TYPE_COLORS[ct] }}
    />
    <span className="text-caption text-muted-foreground">{labelMap[ct] ?? String(ct)}</span>
    {clearTypeTotals !== undefined && (
      <span
        className="text-caption"
        style={{ color: "hsl(var(--muted-foreground) / 0.6)", fontSize: "10px" }}
      >
        {(clearTypeTotals[ct] ?? 0).toLocaleString()}
      </span>
    )}
  </div>
))}
```

- [ ] **Step 4: `TableClearHistogram`에 `clearTypeTotals` useMemo 추가**

`TableClearHistogram` 컴포넌트 내부의 기존 `useMemo` 블록들 다음에 추가한다 (line ~290 부근, `chartHeight` useMemo 이후).

```ts
const clearTypeTotals = useMemo(() => {
  const totals: Record<number, number> = {};
  for (const l of levels) {
    if (l.is_spacer) continue;
    for (const [ctStr, count] of Object.entries(l.counts)) {
      const raw = Number(ctStr);
      const display = getDisplayClearType ? getDisplayClearType(raw) : raw;
      totals[display] = (totals[display] ?? 0) + count;
    }
  }
  return totals;
}, [levels, getDisplayClearType]);
```

- [ ] **Step 5: `ClearTypeLegend` 호출부에 `clearTypeTotals` prop 전달**

`TableClearHistogram` return문 맨 아래의 `ClearTypeLegend` 호출 (line ~440):

```tsx
<ClearTypeLegend
  clientType={clientType}
  className="mb-8"
  hiddenClearTypes={hiddenClearTypes}
  legendAction={legendAction}
  clearTypeTotals={clearTypeTotals}
/>
```

- [ ] **Step 6: 타입스크립트 빌드 확인**

```bash
cd web && npx tsc --noEmit 2>&1 | head -30
```

에러 없으면 성공. 에러가 있으면 타입 불일치를 수정한다.

- [ ] **Step 7: 커밋**

```bash
git add web/src/components/charts/TableClearHistogram.tsx
git commit -m "feat: show total clear count per type in histogram legend"
```

---

## Self-Review

**Spec coverage:**
- [x] 난이도표 전체 램프 개수 카운팅 → `clearTypeTotals` useMemo
- [x] 클리어 타입별 개수 → `Record<number, number>` 키 = display clear type
- [x] 레전드 하단에 작게 표시 → 인라인 `<span>` with small font
- [x] `getDisplayClearType` 리매핑 반영 → useMemo에서 display ct 기준 합산
- [x] `hiddenClearTypes` 자동 제외 → 레전드 자체가 필터하므로 별도 처리 불필요
- [x] `clearTypeTotals` 미전달 시 기존 동작 유지 → `clearTypeTotals !== undefined` 조건

**Placeholder scan:** 없음

**Type consistency:**
- `clearTypeTotals: Record<number, number>` — props, useMemo 반환 타입, 전달부 모두 동일
- `ct` 변수: `ClearTypeLegendProps`의 `items.map` 내부에서 항상 `number`
