const DAY_INDEX = {
  sun: 0,
  mon: 1,
  tue: 2,
  wed: 3,
  thu: 4,
  fri: 5,
  sat: 6,
};

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

function zonedParts(date, timezone) {
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  const parts = Object.fromEntries(formatter.formatToParts(date).map((part) => [part.type, part.value]));
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour),
    minute: Number(parts.minute),
    second: Number(parts.second),
  };
}

function localPartsMs(date, timezone) {
  const parts = zonedParts(date, timezone);
  return Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
}

function timezoneOffsetMs(date, timezone) {
  return localPartsMs(date, timezone) - date.getTime();
}

function localDateTimeToUtc(localMs, timezone) {
  let utcMs = localMs;
  for (let i = 0; i < 3; i += 1) {
    utcMs = localMs - timezoneOffsetMs(new Date(utcMs), timezone);
  }
  return new Date(utcMs);
}

export function getWeeklyPeriodForOffset(now, offset, rollover) {
  const timezone = rollover.timezone || "Asia/Seoul";
  const rolloverDay = DAY_INDEX[rollover.day_of_week] ?? DAY_INDEX.mon;
  const nowLocalMs = localPartsMs(now, timezone);
  const nowLocalDate = new Date(nowLocalMs);
  const currentDay = nowLocalDate.getUTCDay();
  const daysSinceRollover = (currentDay - rolloverDay + 7) % 7;
  let periodStartLocalMs =
    Date.UTC(
      nowLocalDate.getUTCFullYear(),
      nowLocalDate.getUTCMonth(),
      nowLocalDate.getUTCDate(),
      rollover.hour,
      rollover.minute,
      0,
      0,
    ) -
    daysSinceRollover * 24 * 60 * 60 * 1000;

  if (nowLocalMs < periodStartLocalMs) {
    periodStartLocalMs -= WEEK_MS;
  }
  periodStartLocalMs += offset * WEEK_MS;

  const periodStart = localDateTimeToUtc(periodStartLocalMs, timezone);
  const periodEnd = localDateTimeToUtc(periodStartLocalMs + WEEK_MS, timezone);

  return {
    periodStart: periodStart.toISOString(),
    periodEnd: periodEnd.toISOString(),
    isCurrent: offset === 0,
  };
}
