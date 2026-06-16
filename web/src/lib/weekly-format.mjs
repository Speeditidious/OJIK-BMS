/** @type {Record<string, Record<string, string>>} */
const DOW = {
  ko: { mon: "월요일", tue: "화요일", wed: "수요일", thu: "목요일", fri: "금요일", sat: "토요일", sun: "일요일" },
  en: { mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday", fri: "Friday", sat: "Saturday", sun: "Sunday" },
  ja: { mon: "月曜日", tue: "火曜日", wed: "水曜日", thu: "木曜日", fri: "金曜日", sat: "土曜日", sun: "日曜日" },
};

/**
 * Build a human-readable rollover schedule string for the given locale.
 *
 * @param {{ timezone: string, day_of_week: string, hour: number, minute: number }} info
 * @param {string} language  BCP-47 language tag (ko | en | ja; others fall back to en)
 * @returns {string}
 */
export function formatRollover(info, language) {
  const { timezone, day_of_week, hour, minute } = info;
  const tz  = timezone === "Asia/Seoul" ? "KST" : timezone;
  const dow  = DOW[language] ?? DOW.en;
  const day  = dow[day_of_week] ?? day_of_week;
  const h12  = hour % 12 || 12;
  const lang = DOW[language] ? language : "en";

  if (lang === "ja") {
    const period = hour < 12 ? "午前" : "午後";
    return minute === 0
      ? `毎週${day} ${period}${h12}時 ${tz} 更新`
      : `毎週${day} ${period}${h12}時${minute}分 ${tz} 更新`;
  }
  if (lang === "en") {
    const ampm = hour < 12 ? "AM" : "PM";
    const time = `${h12}:${minute.toString().padStart(2, "0")} ${ampm}`;
    return `Updates every ${day} at ${time} ${tz}`;
  }
  // ko (default)
  const period = hour < 12 ? "오전" : "오후";
  return minute === 0
    ? `매주 ${day} ${period} ${h12}시 ${tz} 갱신`
    : `매주 ${day} ${period} ${h12}시 ${minute}분 ${tz} 갱신`;
}
