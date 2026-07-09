#!/usr/bin/env python3
"""
scraper.py — 音乐剧 · 全女卡司演出监控 数据抓取

数据模型（嵌套）：
  shows[]                      每部剧
    └─ performances[]          该剧多个场次
         ├─ date/time/venue
         ├─ cast[]             该场次对应卡司
         └─ is_all_female

数据源（可插拔，单个失败不阻塞）：
1. 大麦网 (damai.cn) 音乐剧搜索
2. 东方演出网 · 音乐剧专版 (shanghaiyinleju.df962388.com)
3. saoju 音乐剧档期库 (y.saoju.net)

说明：音乐剧票务站多为 JS 动态渲染、反爬严格，运行时抓取常用于「补全字段」。
稳定兜底数据见 KNOWN_SHOWS（已确认/代表性的全女卡司音乐剧），
请按实际巡演档期在大麦网 / 各剧院官方渠道核实后修改。

⚠️ KNOWN_SHOWS 为「示例/待校验」种子数据，日期与场馆为代表性占位，
正式使用前请替换为真实演出信息。
"""
import json
import re
import time
import copy
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_NET = True
except Exception:
    HAS_NET = False

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}
TIMEOUT = 15
RETRIES = 1
SLEEP_BETWEEN = 1.5

# ============================================================
# 已知演出数据库（种子 / 兜底）—— 嵌套结构
# ⚠️ 示例数据，请按真实档期替换
# ============================================================
KNOWN_SHOWS = [
    {
        "id": "six", "title": "音乐剧《SIX》中文版", "subtitle": "六位皇后 · 全女卡司",
        "troupe": "英方授权 · 中文制作", "is_all_female": True,
        "note": "同一制作在全国多城巡演，卡司随场次轮换",
        "performances": [
            {"id": "six-2026-07-10", "date": "2026-07-10", "time": "19:30", "venue": "上海文化广场", "city": "上海", "cast": ["六位皇后 · A组卡司（全女班）", "轮换卡司"], "price": "¥180 — 1080", "is_all_female": True},
            {"id": "six-2026-07-10-m", "date": "2026-07-10", "time": "14:00", "venue": "上海文化广场", "city": "上海", "cast": ["六位皇后 · B组卡司（全女班）", "轮换卡司"], "price": "¥180 — 1080", "is_all_female": True},
            {"id": "six-2026-09-19", "date": "2026-09-19", "time": "19:30", "venue": "北京·世纪剧院", "city": "北京", "cast": ["六位皇后卡司（全女班）"], "price": "¥180 — 1080", "is_all_female": True},
            {"id": "six-2026-09-26", "date": "2026-09-26", "time": "19:30", "venue": "广州大剧院", "city": "广州", "cast": ["六位皇后卡司（全女班）"], "price": "¥180 — 1080", "is_all_female": True}
        ]
    },
    {
        "id": "nv", "title": "音乐剧《女巫》", "subtitle": "全女卡司悬疑音乐剧",
        "troupe": "独立制作", "is_all_female": True,
        "performances": [
            {"id": "nv-2026-07-18", "date": "2026-07-18", "time": "19:30", "venue": "茉莉花剧场", "city": "上海", "cast": ["全女卡司主演", "特邀女中音"], "price": "¥280 — 680", "is_all_female": True},
            {"id": "nv-2026-07-19", "date": "2026-07-19", "time": "14:00", "venue": "茉莉花剧场", "city": "上海", "cast": ["全女卡司主演", "青年卡司"], "price": "¥280 — 680", "is_all_female": True}
        ]
    },
    {
        "id": "zx", "title": "音乐剧《造星计划》", "subtitle": "全女卡司 · 青春成长",
        "troupe": "上剧场出品", "is_all_female": True,
        "performances": [
            {"id": "zx-2026-07-25", "date": "2026-07-25", "time": "14:00", "venue": "上剧场", "city": "上海", "cast": ["全女卡司主演"], "price": "¥199 — 599", "is_all_female": True}
        ]
    },
    {
        "id": "wanou", "title": "音乐剧《玩偶》", "subtitle": "全女卡司 · 环境式",
        "troupe": "环境式音乐剧", "is_all_female": True,
        "performances": [
            {"id": "wanou-2026-08-01", "date": "2026-08-01", "time": "19:30", "venue": "虹桥艺术中心", "city": "上海", "cast": ["全女卡司主演"], "price": "¥380 — 880", "is_all_female": True}
        ]
    },
    {
        "id": "poqiang", "title": "音乐剧《破墙》", "subtitle": "全女卡司 · 先锋",
        "troupe": "YOUNG剧场委约", "is_all_female": True,
        "performances": [
            {"id": "poqiang-2026-08-08", "date": "2026-08-08", "time": "19:30", "venue": "YOUNG剧场", "city": "上海", "cast": ["全女卡司主演"], "price": "¥180 — 580", "is_all_female": True}
        ]
    },
    {
        "id": "demian", "title": "音乐剧《德米安》", "subtitle": "全女卡司 · 心理",
        "troupe": "中文改编", "is_all_female": True,
        "performances": [
            {"id": "demian-2026-08-15", "date": "2026-08-15", "time": "19:30", "venue": "兰心大戏院", "city": "上海", "cast": ["全女卡司主演"], "price": "¥280 — 680", "is_all_female": True}
        ]
    },
    {
        "id": "lianbi", "title": "音乐剧《连璧》", "subtitle": "全女卡司 · 双女主",
        "troupe": "音乐剧制作", "is_all_female": True,
        "performances": [
            {"id": "lianbi-2026-08-22", "date": "2026-08-22", "time": "19:30", "venue": "上海文化广场", "city": "上海", "cast": ["双女主 · 全女卡司"], "price": "¥180 — 880", "is_all_female": True}
        ]
    },
    {
        "id": "lizi", "title": "音乐剧《丽兹》", "subtitle": "全女卡司 · 黑色幽默",
        "troupe": "独立制作", "is_all_female": True,
        "performances": [
            {"id": "lizi-2026-08-29", "date": "2026-08-29", "time": "19:30", "venue": "茉莉花剧场", "city": "上海", "cast": ["全女卡司主演"], "price": "¥280 — 680", "is_all_female": True}
        ]
    },
    {
        "id": "xuexing", "title": "音乐剧《嗜血博士》", "subtitle": "全女卡司 · 哥特",
        "troupe": "上剧场出品", "is_all_female": True,
        "performances": [
            {"id": "xuexing-2026-09-05", "date": "2026-09-05", "time": "19:30", "venue": "上剧场", "city": "上海", "cast": ["全女卡司主演"], "price": "¥199 — 599", "is_all_female": True}
        ]
    },
    {
        "id": "sanfu", "title": "音乐剧《三妇志异》", "subtitle": "全女卡司 · 三部曲",
        "troupe": "音乐剧制作", "is_all_female": True,
        "performances": [
            {"id": "sanfu-2026-09-12", "date": "2026-09-12", "time": "19:30", "venue": "虹桥艺术中心", "city": "上海", "cast": ["全女卡司主演"], "price": "¥380 — 880", "is_all_female": True}
        ]
    },
    {
        "id": "r1", "title": "音乐剧《剧院魅影》", "subtitle": "经典复排",
        "troupe": "上海大剧院呈现", "is_all_female": False,
        "performances": [
            {"id": "r1-2026-07-15", "date": "2026-07-15", "time": "19:30", "venue": "上海大剧院", "city": "上海", "cast": ["轮换卡司"], "price": "¥280 — 1280", "is_all_female": False}
        ]
    },
    {
        "id": "r2", "title": "音乐剧《妈妈咪呀！》", "subtitle": "经典 IP 巡演",
        "troupe": "中文制作", "is_all_female": False,
        "performances": [
            {"id": "r2-2026-08-12", "date": "2026-08-12", "time": "19:30", "venue": "上海文化广场", "city": "上海", "cast": ["轮换卡司"], "price": "¥180 — 1080", "is_all_female": False}
        ]
    },
    {
        "id": "r3", "title": "音乐剧《摇滚红与黑》", "subtitle": "法语原版巡演",
        "troupe": "法语原版授权", "is_all_female": False,
        "performances": [
            {"id": "r3-2026-09-09", "date": "2026-09-09", "time": "19:30", "venue": "兰心大戏院", "city": "上海", "cast": ["法方卡司"], "price": "¥280 — 880", "is_all_female": False}
        ]
    },
]


# ============================================================
# HTTP 工具
# ============================================================
def fetch_url(url, encoding='utf-8'):
    if not HAS_NET:
        return None
    for attempt in range(RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if encoding:
                resp.encoding = encoding
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            if attempt < RETRIES:
                time.sleep(SLEEP_BETWEEN)
                continue
            print(f"  ⚠️ 抓取失败 [{url}]: {e}")
            return None
    return None


# ============================================================
# 数据源 1: 东方演出网 · 音乐剧专版
# ============================================================
def scrape_df962388():
    print("🎶 抓取东方演出网(音乐剧)...")
    shows = []
    try:
        html = fetch_url("https://shanghaiyinleju.df962388.com/")
        if not html:
            return shows
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('a[href*="/yanchu/"]')
        for item in items:
            try:
                title_text = item.get_text(strip=True)
                href = item.get('href', '')
                if not title_text or '/yanchu/' not in href:
                    continue
                parent = item.find_parent()
                if not parent:
                    continue
                parent_text = parent.get_text()
                date_match = re.search(r'(2026\.\d{2}\.\d{2})', parent_text)
                if not date_match:
                    continue
                date_raw = date_match.group(1).replace('.', '-')
                if date_raw < datetime.now().strftime("%Y-%m-%d"):
                    continue
                venue = ""
                vm = re.search(r'地点[：:]\s*([^\n]+)', parent_text)
                if vm:
                    venue = vm.group(1).strip()
                price = ""
                pm = re.search(r'门票价格[：:]\s*([^\n]+)', parent_text)
                if pm:
                    price = pm.group(1).strip()
                shows.append({
                    "title": title_text, "date": date_raw, "venue": venue, "price": price,
                    "is_all_female": False, "source": "df962388",
                })
            except Exception:
                continue
        print(f"  ✓ 东方演出网(音乐剧): {len(shows)} 条")
    except Exception as e:
        print(f"  ⚠️ 东方演出网(音乐剧)抓取失败: {e}")
    return shows


# ============================================================
# 数据源 2: saoju 音乐剧档期库
# ============================================================
def scrape_saoju():
    print("📊 抓取 saoju 音乐剧档期库...")
    shows = []
    try:
        html = fetch_url("https://y.saoju.net/yyj/year/2026/")
        if not html:
            return shows
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        for m in re.finditer(r'(2026[年\-./]\d{1,2}[月\-./]\d{1,2}日?)\s*.*?音乐剧[《「]?([^》」]+)', text):
            try:
                raw = re.sub(r'[年/]', '-', m.group(1)).replace('月', '-').replace('日', '').replace('..', '-')
                dt = datetime.strptime(raw, "%Y-%m-%d") if raw.count('-') == 2 else None
                if not dt:
                    continue
                date_iso = dt.strftime("%Y-%m-%d")
                if date_iso < datetime.now().strftime("%Y-%m-%d"):
                    continue
                shows.append({
                    "title": f"音乐剧《{m.group(2).strip()}》", "date": date_iso,
                    "is_all_female": False, "source": "saoju",
                })
            except Exception:
                continue
        print(f"  ✓ saoju: {len(shows)} 条")
    except Exception as e:
        print(f"  ⚠️ saoju 抓取失败: {e}")
    return shows


# ============================================================
# 数据源 3: 大麦网音乐剧搜索（占位，需按实际情况细化选择器）
# ============================================================
def scrape_damai():
    print("🎟️ 抓取大麦网(音乐剧)...")
    shows = []
    try:
        html = fetch_url("https://www.damai.cn/search_list.html?keyword=%E5%85%A8%E5%A5%B3%E5%8D%A1%E5%8F%B8%E9%9F%B3%E4%B9%90%E5%89%A7")
        if not html:
            return shows
        soup = BeautifulSoup(html, 'html.parser')
        print(f"  ✓ 大麦网: {len(shows)} 条（动态页面，建议以手动维护 KNOWN_SHOWS 为主）")
    except Exception as e:
        print(f"  ⚠️ 大麦网抓取失败（动态页面，可忽略）: {e}")
    return shows


# ============================================================
# 合并与去重（扁平抓取 → 嵌套剧）
# ============================================================
def normalize_title(title):
    prefixes = ['大型', '小剧场', '原创', '中文', '法语原版', '英文原版', '音乐剧']
    cleaned = title
    for p in prefixes:
        if cleaned.startswith(p):
            cleaned = cleaned[len(p):]
            break
    m = re.search(r'《([^》]+)》', cleaned)
    if m:
        return m.group(1)
    return cleaned.strip('《》')


def merge_shows(scraped_shows, known_shows):
    merged = []
    index = {}
    for show in known_shows:
        s = copy.deepcopy(show)
        s.setdefault('performances', [])
        s['_keys'] = set((p.get('date'), p.get('time', ''), p.get('venue', '')) for p in s['performances'])
        index[normalize_title(show['title'])] = s
        merged.append(s)

    new_count = 0
    for sc in scraped_shows:
        title = sc.get('title', '')
        date = sc.get('date', '')
        venue = sc.get('venue', '')
        nt = normalize_title(title) if title else ''
        key = (date, sc.get('time', ''), venue)
        if nt and nt in index:
            s = index[nt]
            if key not in s['_keys']:
                s['_keys'].add(key)
                s['performances'].append({
                    'id': f"{s['id']}-{date}" + (f"-{len(s['performances'])+1}" if len([p for p in s['performances'] if p.get('date')==date]) else ""),
                    'date': date, 'time': sc.get('time', ''), 'venue': venue,
                    'city': sc.get('city', ''),
                    'cast': [sc['cast']] if sc.get('cast') else [],
                    'price': sc.get('price', '以场馆公布为准'),
                    'is_all_female': sc.get('is_all_female', s.get('is_all_female', False)),
                })
                if not s.get('troupe') and sc.get('troupe'):
                    s['troupe'] = sc['troupe']
        elif date and title and len(title) > 2:
            new_count += 1
            sid = f"new-{new_count:03d}"
            merged.append({
                'id': sid, 'title': title, 'subtitle': '', 'troupe': sc.get('troupe', ''),
                'is_all_female': sc.get('is_all_female', False),
                'performances': [{
                    'id': f"{sid}-{date}", 'date': date, 'time': sc.get('time', ''),
                    'venue': venue, 'city': sc.get('city', ''),
                    'cast': [sc['cast']] if sc.get('cast') else [],
                    'price': sc.get('price', '以场馆公布为准'),
                    'is_all_female': sc.get('is_all_female', False),
                }],
            })
            index[nt] = merged[-1]

    for s in merged:
        s.pop('_keys', None)
    return merged


# ============================================================
# 主函数
# ============================================================
def main():
    print("=" * 60)
    print("🎵 音乐剧 · 全女卡司演出监控 — 数据抓取")
    print(f"📅 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    if not HAS_NET:
        print("⚠️ 本地缺少 requests/bs4，跳过在线抓取，仅使用种子数据。")

    all_scraped = []
    all_scraped += scrape_df962388()
    time.sleep(SLEEP_BETWEEN)
    all_scraped += scrape_saoju()
    time.sleep(SLEEP_BETWEEN)
    all_scraped += scrape_damai()

    print(f"\n📊 抓取汇总: {len(all_scraped)} 条原始数据")
    shows = merge_shows(all_scraped, KNOWN_SHOWS)

    total_perfs = sum(len(s.get('performances', [])) for s in shows)
    af_perfs = sum(1 for s in shows for p in s.get('performances', []) if p.get('is_all_female'))
    cities = set(p.get('city', '') for s in shows for p in s.get('performances', []) if p.get('city'))

    output = {
        "metadata": {
            "report_date": "auto", "data_updated": "auto",
            "total_shows": len(shows), "total_performances": total_perfs,
            "all_female_shows": len([s for s in shows if s.get('is_all_female')]),
            "all_female_performances": af_perfs,
            "cities": len(cities), "scraped_at": datetime.now().isoformat(),
            "sources": ["df962388", "saoju", "damai", "known_seed"],
        },
        "shows": shows,
    }
    Path("shows.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ shows.json 生成完成")
    print(f"   剧目标题: {len(shows)} 部 · 演出场次: {total_perfs}（全女卡司 {af_perfs} 场）")
    print(f"   涉及城市: {len(cities)} 个")
    if not all_scraped:
        print("\n⚠️ 在线抓取无数据，使用种子数据兜底（请按真实档期核实 KNOWN_SHOWS）")

if __name__ == "__main__":
    main()
