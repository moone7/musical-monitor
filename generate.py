#!/usr/bin/env python3
"""
generate.py — 读取嵌套 shows.json + template.html → 生成 index.html

音乐剧 · 全女卡司演出监控
数据模型（嵌套）：
  shows[]                      每部剧一个 tab
    └─ performances[]          该剧的多个场次（一个时间区间可有多场）
         ├─ date/time/venue     场次时间地点
         ├─ cast[]              该场次对应卡司（每场可不同）
         └─ is_all_female       该场次是否全女卡司
UI：
  - 每个剧名一个 tab；「全部场次」tab 展示所有剧的场次
  - 点击 tab → 展示该剧每个场次 + 对应卡司
  - 日历标记每个场次卡片
  - 全女卡司一等公民：卡片标签 / 统计 / 日历徽章 / 可筛选
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

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
# 数据展平：每场次带所属剧上下文
# ============================================================
def flatten_performances(data):
    perfs = []
    for show in data.get("shows", []):
        for p in show.get("performances", []):
            perf = dict(p)
            perf["show_id"] = show.get("id", "")
            perf["show_title"] = show.get("title", "")
            perf["show_subtitle"] = show.get("subtitle", "")
            perf["show_troupe"] = show.get("troupe", "")
            if "is_all_female" not in perf:
                perf["is_all_female"] = show.get("is_all_female", False)
            perfs.append(perf)
    perfs.sort(key=lambda s: (s.get("date", ""), s.get("time", "00:00")))
    return perfs

def cast_list(cast):
    if isinstance(cast, list):
        return [c for c in cast if c]
    if isinstance(cast, str) and cast.strip():
        return [cast.strip()]
    return []

# ============================================================
# 卡片状态
# ============================================================
def compute_card_class(date_iso, today):
    if date_iso < date_str(today):
        return "past"
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

def generate_card_html(perf, today):
    is_af = perf.get('is_all_female', False)
    card_class = compute_card_class(perf['date'], today)
    tags = compute_tags(perf['date'], today, is_af)

    classes = "perf-card"
    if is_af:
        classes += " all-female"
    if card_class:
        classes += f" {card_class}"

    city_html = ""
    if perf.get('city'):
        city_html = f'\n<span><span class="meta-icon">🏙️</span>{perf["city"]}</span>'

    casts = cast_list(perf.get('cast', []))
    if casts:
        chip_parts = []
        for c in casts:
            if '：' in c:
                role, name = c.split('：', 1)
                chip_parts.append(f'<span class="cast-chip"><b class="cast-role">{html_escape(role)}</b>{html_escape(name)}</span>')
            else:
                chip_parts.append(f'<span class="cast-chip">{html_escape(c)}</span>')
        cast_html = f'<span class="cast-chips">{"".join(chip_parts)}</span>'
    else:
        cast_html = '<span class="cast-chips"><span class="cast-chip cast-none">卡司待公布</span></span>'

    tags_html = "\n".join(f'<span class="tag {tc}">{tt}</span>' for tc, tt in tags)

    price = perf.get('price', '以场馆公布为准')
    if ' · ' in price:
        parts = price.split(' · ', 1)
        price_html = parts[0]
        if len(parts) > 1 and parts[1]:
            price_html = f'{parts[0]}<br/><small>{parts[1].strip("()")}</small>'
    else:
        price_html = price

    af_attr = ' data-all-female="1"' if is_af else ''

    return f"""<div class="{classes}"{af_attr} data-id="{perf['id']}" data-show="{perf['show_id']}" data-date="{perf['date']}" data-time="{perf.get('time','')}" data-title="{html_escape(perf['show_title'])}" data-venue="{html_escape(perf.get('venue',''))}">
<div class="perf-info">
<div class="perf-title">{html_escape(perf['show_title'])} <em>{html_escape(perf.get('show_subtitle', ''))}</em></div>
<div class="perf-meta">
<span><span class="meta-icon">📅</span>{format_show_date(perf['date'], perf.get('time',''))}</span>
<span><span class="meta-icon">📍</span>{html_escape(perf.get('venue',''))}</span>{city_html}
</div>
<div class="perf-cast">
<strong>演员表：</strong>{cast_html}<br/>
<strong>制作：</strong>{html_escape(perf.get('show_troupe', ''))}
</div>
</div>
<div class="perf-side">
{tags_html}
<button class="buy-btn" onclick="toggleBought(this)"><span class="btn-icon">🎟️</span><span class="btn-text">标记已购</span></button>
<div class="perf-price">{price_html}</div></div>
</div>"""


def generate_tabs(shows):
    parts = ['<button class="tab-btn active" data-tab="all">📋 全部场次</button>']
    for show in shows:
        title = clean_title(show.get('title', ''))
        parts.append(f'<button class="tab-btn" data-tab="{show["id"]}">{html_escape(title)}</button>')
    return "\n".join(parts)


def perf_with_show(p, show):
    pp = dict(p)
    pp['show_id'] = show.get('id', '')
    pp['show_title'] = show.get('title', '')
    pp['show_subtitle'] = show.get('subtitle', '')
    pp['show_troupe'] = show.get('troupe', '')
    if 'is_all_female' not in pp:
        pp['is_all_female'] = show.get('is_all_female', False)
    return pp

def generate_panels(data, today):
    panels = []
    for show in data.get("shows", []):
        perfs = sorted(show.get("performances", []), key=lambda s: (s.get("date", ""), s.get("time", "00:00")))
        if not perfs:
            continue
        is_af = show.get("is_all_female", False)
        af_badge = '<span class="sph-af">💜 全女卡司</span>' if is_af else '<span class="sph-af sph-mixed">⚧ 含男演员</span>'
        city = show.get("city") or (perfs[0].get("city", "") if perfs else "")
        note = show.get("note")
        note_html = f'<div class="sph-note">{html_escape(note)}</div>' if note else ''
        cards = "\n".join(generate_card_html(perf_with_show(p, show), today) for p in perfs)
        panel_cls = "show-panel" + (" all-female" if is_af else "")
        header = f"""<div class="show-panel-header">
  <div class="sph-left">
    <div class="sph-title">{html_escape(show.get('title', ''))} <em>{html_escape(show.get('subtitle', ''))}</em></div>
    <div class="sph-meta">🏛️ {html_escape(show.get('troupe', ''))} · {len(perfs)} 场 · {html_escape(city)} {af_badge}</div>
    {note_html}
  </div>
</div>"""
        panels.append(f'<div class="{panel_cls}" data-show="{show["id"]}">\n{header}\n<div class="perf-grid">\n{cards}\n</div>\n</div>')
    return "\n".join(panels)


def generate_perf_dates(perfs):
    dates = {}
    for p in perfs:
        dates.setdefault(p['date'], []).append(p['id'])
    lines = []
    for d in sorted(dates.keys()):
        ids = ", ".join('"%s"' % sid for sid in dates[d])
        lines.append('  "%s": [%s],' % (d, ids))
    return "{\n" + "\n".join(lines) + "\n}"


def generate_all_female_ids(perfs):
    ids = [p['id'] for p in perfs if p.get('is_all_female')]
    return "[" + ", ".join(f'"{i}"' for i in ids) + "]"

# ============================================================
# 提醒生成（基于场次）
# ============================================================
def clean_title(title):
    prefixes = ['大型', '小剧场', '原创', '中文', '法语原版', '英文原版', '音乐剧']
    cleaned = title
    for p in prefixes:
        if cleaned.startswith(p):
            cleaned = cleaned[len(p):]
            break
    return cleaned.strip('《》').strip()

def format_perf_list(perfs, max_n=None):
    parts = []
    for s in perfs:
        dt = datetime.strptime(s['date'], "%Y-%m-%d")
        parts.append(f"{dt.month}月{dt.day}日 {s.get('venue','')}《{clean_title(s['show_title'])}》")
    if max_n and len(parts) > max_n:
        parts = parts[:max_n] + ['等']
    return "、".join(parts)

def format_af_list(perfs):
    parts = []
    for s in perfs:
        dt = datetime.strptime(s['date'], "%Y-%m-%d")
        title_short = clean_title(s['show_title'])
        venue_short = s.get('venue', '').replace('上海', '').replace('大剧院', '').replace('·大剧场', '').replace('·中剧场', '')
        parts.append(f"{dt.month}月{dt.day}日{venue_short}《{title_short}》")
    return " → ".join(parts)

def generate_alert_urgent(perfs, today):
    today_str = date_str(today)
    tomorrow_str = date_str(today + timedelta(days=1))
    lines = []
    today_p = [s for s in perfs if s['date'] == today_str]
    if today_p:
        lines.append(f"· <strong>今日开演：</strong>{format_perf_list(today_p)}。<br/>")
    tomorrow_p = [s for s in perfs if s['date'] == tomorrow_str]
    if tomorrow_p:
        lines.append(f"· <strong>明日开演：</strong>{format_perf_list(tomorrow_p)}。<br/>")
    af_p = [s for s in perfs if s.get('is_all_female') and s['date'] >= today_str]
    if af_p:
        lines.append(f"· <strong>💜 全女卡司近期：</strong>{format_af_list(af_p)}。<br/>")
    week_ahead = date_str(today + timedelta(days=7))
    upcoming = [s for s in perfs if today_str < s['date'] <= week_ahead and not s.get('is_all_female')]
    if upcoming:
        lines.append(f"· <strong>一周内演出：</strong>{format_perf_list(upcoming[:4])}{'等' if len(upcoming) > 4 else ''}。<br/>")
    if not lines:
        lines.append("· 暂无近期高优提醒。<br/>")
    return "\n      ".join(lines)

def generate_alert_new(perfs, today):
    today_str = date_str(today)
    yesterday_str = date_str(today - timedelta(days=1))
    lines = []
    today_p = [s for s in perfs if s['date'] == today_str]
    if today_p:
        lines.append(f"· <strong>今日开演：</strong>{format_perf_list(today_p)}。<br/>")
    yesterday_p = [s for s in perfs if s['date'] == yesterday_str]
    if yesterday_p:
        lines.append(f"· <strong>昨日回顾：</strong>{format_perf_list(yesterday_p)} 已圆满演出。<br/>")
    af_up = [s for s in perfs if s.get('is_all_female') and s['date'] >= today_str]
    if af_up:
        lines.append(f"· <strong>💜 全女卡司行程：</strong>共 {len(af_up)} 场 — {format_af_list(af_up)}。<br/>")
    shanghai = [s for s in perfs if '上海' in (s.get('city', '') + s.get('venue', '')) and s['date'] >= today_str]
    if shanghai:
        lines.append(f"· <strong>上海近期：</strong>{format_perf_list(shanghai[:3])}{'等' if len(shanghai) > 3 else ''}。<br/>")
    if not lines:
        lines.append("· 今日暂无新动态。<br/>")
    return "\n      ".join(lines)

# ============================================================
# 主函数
# ============================================================
def main():
    data = json.loads(Path("shows.json").read_text(encoding="utf-8"))
    shows = data.get("shows", [])
    perfs = flatten_performances(data)
    today = get_today()

    total = len(perfs)
    af_count = len([p for p in perfs if p.get('is_all_female')])
    cities = set(p.get('city') for p in perfs if p.get('city'))

    report_date = format_report_date(today)
    report_date_badge = format_report_date_badge(today)
    data_updated = format_data_updated()

    tabs_html = generate_tabs(shows)
    panels_html = generate_panels(data, today)

    perf_dates_json = generate_perf_dates(perfs)
    af_ids_json = generate_all_female_ids(perfs)

    alert_urgent = generate_alert_urgent(perfs, today)
    alert_new = generate_alert_new(perfs, today)

    template = Path("template.html").read_text(encoding="utf-8")
    replacements = {
        "{{REPORT_DATE}}": report_date,
        "{{REPORT_DATE_BADGE}}": report_date_badge,
        "{{DATA_UPDATED}}": data_updated,
        "{{STAT_TOTAL}}": str(total),
        "{{STAT_ALL_FEMALE}}": str(af_count),
        "{{STAT_CITIES}}": str(len(cities)),
        "{{TABS_HTML}}": tabs_html,
        "{{PANELS_HTML}}": panels_html,
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
    current_fps = {p['id']: f"{p['date']}|{p['show_title']}|{p.get('venue','')}" for p in perfs}
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
    print(f"   剧目标题：{len(shows)} 部 · 演出场次：{total}（全女卡司 {af_count} 场）")
    print(f"   涉及城市：{len(cities)} 个")

if __name__ == "__main__":
    main()
