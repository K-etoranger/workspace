// 論理日は sb が決める（`sb day`）。ここでは計算しない。
import { sbRead } from "./sb.mjs";

// その時刻の論理日 {date, start, end}（start・end はタイムゾーン付き ISO）。
export function sbDay(at = new Date()) {
  const { date, start, end } = sbRead(["day", "--at", at.toISOString()]);
  return { date, start, end };
}

// 暦の日付（YYYY-MM-DD）の足し引き。時刻・論理日の境目は扱わない。
export function addDays(date, days) {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

// 表示用の JST の日時（論理日ではない）。
export function jstDisplay(now = new Date()) {
  const v = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(now).map((p) => [p.type, p.value]));
  return `${v.year}-${v.month}-${v.day} ${v.hour}:${v.minute} JST`;
}
