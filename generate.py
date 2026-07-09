#!/usr/bin/env python3
"""
generate.py — 读取 shows.json + template.html → 生成 index.html

音乐剧 · 全女卡司演出监控
与越剧监控同架构，差异：
- 无「单演员特别关注」板块
- 新增「全女卡司」一等公民特性：卡片标签 / 统计项 / 日历徽章 / 可筛选
- 演出卡片、日历、我的演出提醒、已购标记、紧急提醒、今日新动态 保持一致
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# 配置
# ============================================================
WEEKDAYS_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# ============================================================
# 日期工具
# ============================================================
def get_today():
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

def date_str(dt):
    return dt.strftime("%Y-%m-%d")

def format_report_date(dt):
    return f"{dt.year}年{dt.month}月{dt.day}日"

def format_report_date_badge(dt):
    return f"{dt.year}年{dt.month}月{dt.day}日 {WEEKDAYS_CN[dt.weekday()]}"

def format_data_updated():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def format_show_date(date_iso, time_str):
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    weekday = WEEKDAYS_CN[dt.weekday()].replace("星期", "周")
    return f"{dt.month}月{dt.day}日（{weekday}）{time_str}"

# ============================================================
# 状态计算
# ============================================================
def compute_card_class(date_iso, today):
    if date_iso < date_str(today):
        return ""
    if date_iso == date_str(today):
        return "today"
    if date_iso == date_str(today + timedelta(days=1)):
        return "tomorrow"
    return ""

def compute_tags(date_iso, today, is_all_female):
    tags = []
    if is_all_female:
        tags.append(("tag-all-female", "💜 全女卡司"))
    if date_iso < date_str(today):
        tags.append(("tag-done", "✅ 已演"))
    elif date_iso == date_str(today):
        tags.append(("tag-urgent", "🔥 今日开演"))
        tags.append(("tag-on-sale", "售票中"))
    elif date_iso == date_str(today + timedelta(days=1)):
        tags.append(("tag-urgent", "🔥 明日开演"))
        tags.append(("tag-on-sale", "售票中"))
    else:
        tags.append(("tag-on-sale", "售票中"))
    return tags

# ============================================================
# HTML 生成
# ============================================================
def html_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def generate_card_html(show, today):
    is_af = show.get('is_all_female', False)
    card_class = compute_card_class(show['date'], today)
    tags = compute_tags(show['date'], today, is_af)

    classes = "perf-card"
    if is_af:
        classes += " all-female"
    if card_class:
        classes += f" {card_class}"

    city_html = ""
    if show.get('city'):
        city_html = f'\n<span><span class="meta-icon">🏙️</span>{show["city"]}</span>'

    cast_html = show.get('cast', '')

    tags_html = "\n".join(f'<span class="tag {tc}">{tt}</span>' for tc, tt in tags)

    price = show.get('price', '以场馆公布为准')
    if ' · ' in price:
        parts = price.split(' · ', 1)
        price_html = parts[0]
        if len(parts) > 1 and parts[1]:
            small_text = parts[1].strip('()')
            if small_text:
                price_html = f'{parts[0]}<br/><small>{small_text}</small>'
    else:
        price_html = price

    af_attr = ' data-all-female="1"' if is_af else ''

    return f"""<div class="{classes}"{af_attr} data-date="{show['date']}" data-id="{show['id']}" data-time="{show['time']}" data-title="{show['title']}" data-venue="{show['venue']}">
<div class="perf-info">
<div class="perf-title">{show['title']} <em>{show.get('subtitle', '')}</em></div>
<div class="perf-meta">
<span><span class="meta-icon">📅</span>{format_show_date(show['date'], show['time'])}</span>
<span><span class="meta-icon">📍</span>{show['venue']}</span>{city_html}
</div>
<div class="perf-cast">
<strong>卡司：</strong>{cast_html}<br/>
<strong>制作：</strong>{show.get('troupe', '')}
        </div>
</div>
<div class="perf-side">
{tags_html}
<button class="buy-btn" onclick="toggleBought(this)"><span class="btn-icon">🎟️</span><span class="btn-text">标记已购</span></button>
<div class="perf-price">{price_html}</div></div>

</div>"""


def generate_month_cards(shows, today, month):
    month_shows = [s for s in shows if s['date'].startswith(f"2026-{month:02d}")]
    month_shows.sort(key=lambda s: (s['date'], s['time']))
    return "\n".join(generate_card_html(show, today) for show in month_shows)


def generate_perf_dates(shows):
    dates = {}
    for show in shows:
        dates.setdefault(show['date'], []).append(show['id'])
    lines = []
    for d in sorted(dates.keys()):
        ids = ", ".join('"%s"' % sid for sid in dates[d])
        lines.append('  "%s": [%s],' % (d, ids))
    return "{\n" + "\n".join(lines) + "\n}"


def generate_all_female_ids(shows):
    ids = [s['id'] for s in shows if s.get('is_all_female')]
    return "[" + ", ".join(f'"{i}"' for i in ids) + "]"

# ============================================================
# 提醒生成
# ============================================================
def clean_title(title):
    prefixes = ['大型', '小剧场', '原创', '中文', '法语原版', '英文原版', '音乐剧']
    cleaned = title
    for p in prefixes:
        if cleaned.startswith(p):
            cleaned = cleaned[len(p):]
            break
    return cleaned.strip('《》').strip()

def format_show_list(shows):
    parts = []
    for s in shows:
        dt = datetime.strptime(s['date'], "%Y-%m-%d")
        parts.append(f"{dt.month}月{dt.day}日 {s['venue']}《{clean_title(s['title'])}》")
    return "、".join(parts)

def format_af_list(shows):
    parts = []
    for s in shows:
        dt = datetime.strptime(s['date'], "%Y-%m-%d")
        title_short = clean_title(s['title'])
        venue_short = s['venue'].replace('上海', '').replace('大剧院', '').replace('·大剧场', '').replace('·中剧场', '')
        parts.append(f"{dt.month}月{dt.day}日{venue_short}《{title_short}》")
    return " → ".join(parts)

def generate_alert_urgent(shows, today):
    today_str = date_str(today)
    tomorrow_str = date_str(today + timedelta(days=1))
    lines = []
    today_shows = [s for s in shows if s['date'] == today_str]
    if today_shows:
        lines.append(f"· <strong>今日开演：</strong>{format_show_list(today_shows)}。<br/>")
    tomorrow_shows = [s for s in shows if s['date'] == tomorrow_str]
    if tomorrow_shows:
        lines.append(f"· <strong>明日开演：</strong>{format_show_list(tomorrow_shows)}。<br/>")
    af_shows = [s for s in shows if s.get('is_all_female') and s['date'] >= today_str]
    if af_shows:
        lines.append(f"· <strong>💜 全女卡司近期：</strong>{format_af_list(af_shows)}。<br/>")
    week_ahead = date_str(today + timedelta(days=7))
    upcoming = [s for s in shows if today_str < s['date'] <= week_ahead and not s.get('is_all_female')]
    if upcoming:
        venues = set(s['venue'] for s in upcoming)
        lines.append(f"· <strong>一周内演出：</strong>{format_show_list(upcoming[:4])}{'等' if len(upcoming) > 4 else ''}。<br/>")
    if not lines:
        lines.append("· 暂无近期高优提醒。<br/>")
    return "\n      ".join(lines)

def generate_alert_new(shows, today):
    today_str = date_str(today)
    yesterday_str = date_str(today - timedelta(days=1))
    lines = []
    today_shows = [s for s in shows if s['date'] == today_str]
    if today_shows:
        lines.append(f"· <strong>今日开演：</strong>{format_show_list(today_shows)}。<br/>")
    yesterday_shows = [s for s in shows if s['date'] == yesterday_str]
    if yesterday_shows:
        lines.append(f"· <strong>昨日回顾：</strong>{format_show_list(yesterday_shows)} 已圆满演出。<br/>")
    af_upcoming = [s for s in shows if s.get('is_all_female') and s['date'] >= today_str]
    if af_upcoming:
        lines.append(f"· <strong>💜 全女卡司行程：</strong>共 {len(af_upcoming)} 场 — {format_af_list(af_upcoming)}。<br/>")
    shanghai = [s for s in shows if '上海' in (s.get('city','') + s.get('venue','')) and s['date'] >= today_str]
    if shanghai:
        lines.append(f"· <strong>上海近期：</strong>{format_show_list(shanghai[:3])}{'等' if len(shanghai) > 3 else ''}。<br/>")
    if not lines:
        lines.append("· 今日暂无新动态。<br/>")
    return "\n      ".join(lines)

# ============================================================
# 主函数
# ============================================================
def main():
    data = json.loads(Path("shows.json").read_text(encoding="utf-8"))
    shows = data['shows']
    today = get_today()

    total = len(shows)
    af_count = len([s for s in shows if s.get('is_all_female')])
    cities = set(s['city'] for s in shows if s.get('city'))

    report_date = format_report_date(today)
    report_date_badge = format_report_date_badge(today)
    data_updated = format_data_updated()

    july_cards = generate_month_cards(shows, today, 7)
    aug_cards = generate_month_cards(shows, today, 8)
    sep_cards = generate_month_cards(shows, today, 9)

    perf_dates_json = generate_perf_dates(shows)
    af_ids_json = generate_all_female_ids(shows)

    alert_urgent = generate_alert_urgent(shows, today)
    alert_new = generate_alert_new(shows, today)

    template = Path("template.html").read_text(encoding="utf-8")
    replacements = {
        "{{REPORT_DATE}}": report_date,
        "{{REPORT_DATE_BADGE}}": report_date_badge,
        "{{DATA_UPDATED}}": data_updated,
        "{{STAT_TOTAL}}": str(total),
        "{{STAT_ALL_FEMALE}}": str(af_count),
        "{{STAT_CITIES}}": str(len(cities)),
        "{{PERF_CARDS_JULY}}": july_cards,
        "{{PERF_CARDS_AUG}}": aug_cards,
        "{{PERF_CARDS_SEP}}": sep_cards,
        "{{PERF_DATES_JSON}}": perf_dates_json,
        "{{ALL_FEMALE_IDS_JSON}}": af_ids_json,
        "{{ALERT_URGENT}}": alert_urgent,
        "{{ALERT_NEW}}": alert_new,
    }
    html = template
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    remaining = re.findall(r'\{\{\w+\}\}', html)
    if remaining:
        print(f"⚠️ 警告：{len(remaining)} 个占位符未替换：{set(remaining)}")

    fingerprint_file = Path(".fingerprint_cache")
    current_fps = {s['id']: f"{s['date']}|{s['title']}|{s['venue']}" for s in shows}
    if fingerprint_file.exists():
        try:
            old_fps = json.loads(fingerprint_file.read_text(encoding="utf-8"))
            changed = [f"  ⚠️ {sid}: \"{old_fps[sid]}\" → \"{raw}\"" for sid, raw in current_fps.items() if sid in old_fps and old_fps[sid] != raw]
            if changed:
                print(f"\n🚨 警告：{len(changed)} 场演出的 fingerprint 输入值发生变化！已购状态可能丢失！")
                for c in changed: print(c)
        except: pass
    fingerprint_file.write_text(json.dumps(current_fps, ensure_ascii=False, indent=2), encoding="utf-8")

    Path("index.html").write_text(html, encoding="utf-8")
    print(f"✅ index.html 生成完成")
    print(f"   报告日期：{report_date}（{WEEKDAYS_CN[today.weekday()]}）")
    print(f"   演出场次：{total}（全女卡司 {af_count} 场）")
    print(f"   涉及城市：{len(cities)} 个")
    print(f"   数据时间：{data_updated}")

if __name__ == "__main__":
    main()
