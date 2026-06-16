// clear_type integer -> label + tailwind text color class.
// Mapping follows clear_type_display.py: 9=MAX, 8=PFC, 7=AP, 5=FC, 4=HARD, 3=NORMAL, 2=EASY, 1=FAILED
export function clearTypeLabel(ct: number | null): { label: string; className: string } {
  switch (ct) {
    case 9: return { label: "MAX", className: "text-yellow-300" };
    case 8: return { label: "PFC", className: "text-yellow-400" };
    case 7: return { label: "AP", className: "text-lime-400" };
    case 5: return { label: "FC", className: "text-green-400" };
    case 4: return { label: "HARD", className: "text-yellow-500" };
    case 3: return { label: "NORMAL", className: "text-emerald-300" };
    case 2: return { label: "EASY", className: "text-emerald-300" };
    case 1: return { label: "FAILED", className: "text-pink-400" };
    default: return { label: "NO PLAY", className: "text-muted-foreground" };
  }
}
