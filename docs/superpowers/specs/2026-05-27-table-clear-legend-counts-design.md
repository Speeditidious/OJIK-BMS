# Design: 난이도표 클리어 타입 카운트 레전드 표시

**Date:** 2026-05-27  
**Feature:** 유저 대시보드 난이도표 클리어 분포 — 레전드에 전체 램프 개수 표시

---

## 요구사항

- 선택된 난이도표 전체(난이도 레벨 상관없이)에서 클리어 타입별 곡 수를 합산한다.
- 합산된 개수를 히스토그램 하단 `ClearTypeLegend`의 각 클리어 타입 항목 옆에 작게 표시한다.
- 표시 방식: 라벨 오른쪽에 인라인으로 숫자 배치 (Option B — "배지" 스타일).

---

## 데이터 흐름

새 API 호출 없이 기존 데이터로 처리 가능하다.

`TableClearHistogram`은 이미 `levels: TableClearLevel[]` prop을 수신한다.  
각 `TableClearLevel`은 `counts: Record<string, number>` (클리어 타입 문자열 → 곡 수)를 갖는다.

계산 단계:
1. `is_spacer` 행은 건너뛴다.
2. 각 레벨의 `counts`를 순회하며 raw 클리어 타입별 합계를 구한다.
3. `getDisplayClearType`이 제공된 경우, raw ct를 display ct로 리매핑한 뒤 합산한다.
4. 결과: `Record<number, number>` — display clear type → 전체 곡 수

이 집계를 `TableClearHistogram` 내부 `useMemo`로 계산하고 `ClearTypeLegend`에 prop으로 전달한다.

---

## 컴포넌트 변경

### `ClearTypeLegend` (`TableClearHistogram.tsx`)

**추가 prop:**
```ts
clearTypeTotals?: Record<number, number>
```

**레전드 아이템 변경:**
```
변경 전:  ■ HARD
변경 후:  ■ HARD  73
```

- 숫자는 `toLocaleString()` 포맷 (예: `1,234`)
- 스타일: `font-size: var(--text-caption)`, `color: hsl(var(--muted-foreground)/0.6)` 수준으로 라벨보다 더 흐리게
- `clearTypeTotals`가 없으면 기존과 동일하게 렌더 (하위 호환)

### `TableClearHistogram` (`TableClearHistogram.tsx`)

**내부 계산 추가:**
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

`ClearTypeLegend`에 `clearTypeTotals={clearTypeTotals}` 전달.

---

## 표시 규칙

| 상황 | 처리 |
|------|------|
| 해당 클리어 타입 곡 수 = 0 | `0` 표시 (숨기지 않음) |
| `hiddenClearTypes`에 포함된 타입 | 레전드에서 이미 제외됨 → 자동 미표시 |
| `getDisplayClearType` 리매핑 | 병합된 타입의 합계가 display ct에 누적됨 |
| `clearTypeTotals` prop 미제공 | 숫자 표시 없음 (기존 동작 유지) |

---

## 변경 파일 목록

- `web/src/components/charts/TableClearHistogram.tsx`
  - `ClearTypeLegendProps`에 `clearTypeTotals?: Record<number, number>` 추가
  - `ClearTypeLegend` 렌더링 로직: 라벨 옆에 숫자 표시
  - `TableClearHistogram` 내부: `clearTypeTotals` useMemo 계산 + `ClearTypeLegend` prop 전달

변경 파일: **1개**. 외부 API, 훅, 라우터 변경 없음.

---

## 범위 외

- 클릭으로 필터 적용 — 기존 `FilterPanel`로 충분함
- 백분율 표시 — 숫자만으로 명확함
- 모바일 반응형 레이아웃 변경 — flex-wrap으로 자동 처리됨
