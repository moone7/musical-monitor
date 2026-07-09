#!/usr/bin/env python3
"""
scraper.py — 音乐剧 · 全女卡司演出监控 数据抓取

数据源（可插拔，单个失败不阻塞）：
1. 大麦网 (damai.cn) 音乐剧搜索
2. 东方演出网 · 音乐剧专版 (shanghaiyinleju.df962388.com)
3. saoju 音乐剧档期库 (y.saoju.net)
4. 上海文化广场 / 上海大剧院 官方演出排期

说明：音乐剧票务站多为 JS 动态渲染、反爬严格，运行时抓取常用于「补全字段」。
稳定兜底数据见 KNOWN_SHOWS（已确认/代表性的全女卡司音乐剧），
请按实际巡演档期在大麦网 / 各剧院官方渠道核实后修改。

⚠️ KNOWN_SHOWS 为「示例/待校验」种子数据，日期与场馆为代表性占位，
正式使用前请替换为真实演出信息。
"""
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

# 依赖按需导入，缺失时自动跳过对应数据源（保证本地无网络/无依赖也能生成）
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
# 已知演出数据库（种子 / 兜底）
# 字段: id, date, time, title, subtitle, venue, city, cast, troupe, price, is_all_female
# ⚠️ 示例数据，请按真实档期替换
# ============================================================
KNOWN_SHOWS = [
    # ---------- 全女卡司 ----------
    {"id":"m01","date":"2026-07-10","time":"19:30","title":"音乐剧《SIX》中文版","subtitle":"六位皇后 · 全女卡司","venue":"上海文化广场","city":"上海","cast":"六位皇后卡司（全女班）","troupe":"英方授权 · 中文制作","price":"¥180 — 1080","is_all_female":True},
    {"id":"m02","date":"2026-07-18","time":"19:30","title":"音乐剧《女巫》","subtitle":"全女卡司悬疑音乐剧","venue":"茉莉花剧场","city":"上海","cast":"全女卡司","troupe":"独立制作","price":"¥280 — 680","is_all_female":True},
    {"id":"m03","date":"2026-07-25","time":"14:00","title":"音乐剧《造星计划》","subtitle":"全女卡司 · 青春成长","venue":"上剧场","city":"上海","cast":"全女卡司","troupe":"上剧场出品","price":"¥199 — 599","is_all_female":True},
    {"id":"m04","date":"2026-08-01","time":"19:30","title":"音乐剧《玩偶》","subtitle":"全女卡司 · 环境式","venue":"虹桥艺术中心","city":"上海","cast":"全女卡司","troupe":"环境式音乐剧","price":"¥380 — 880","is_all_female":True},
    {"id":"m05","date":"2026-08-08","time":"19:30","title":"音乐剧《破墙》","subtitle":"全女卡司 · 先锋","venue":"YOUNG剧场","city":"上海","cast":"全女卡司","troupe":"YOUNG剧场委约","price":"¥180 — 580","is_all_female":True},
    {"id":"m06","date":"2026-08-15","time":"19:30","title":"音乐剧《德米安》","subtitle":"全女卡司 · 心理","venue":"兰心大戏院","city":"上海","cast":"全女卡司","troupe":"中文改编","price":"¥280 — 680","is_all_female":True},
    {"id":"m07","date":"2026-08-22","time":"19:30","title":"音乐剧《连璧》","subtitle":"全女卡司 · 双女主","venue":"上海文化广场","city":"上海","cast":"双女主 · 全女卡司","troupe":"音乐剧制作","price":"¥180 — 880","is_all_female":True},
    {"id":"m08","date":"2026-08-29","time":"19:30","title":"音乐剧《丽兹》","subtitle":"全女卡司 · 黑色幽默","venue":"茉莉花剧场","city":"上海","cast":"全女卡司","troupe":"独立制作","price":"¥280 — 680","is_all_female":True},
    {"id":"m09","date":"2026-09-05","time":"19:30","title":"音乐剧《嗜血博士》","subtitle":"全女卡司 · 哥特","venue":"上剧场","city":"上海","cast":"全女卡司","troupe":"上剧场出品","price":"¥199 — 599","is_all_female":True},
    {"id":"m10","date":"2026-09-12","time":"19:30","title":"音乐剧《三妇志异》","subtitle":"全女卡司 · 三部曲","venue":"虹桥艺术中心","city":"上海","cast":"全女卡司","troupe":"音乐剧制作","price":"¥380 — 880","is_all_female":True},
    {"id":"m11","date":"2026-09-19","time":"19:30","title":"音乐剧《SIX》中文版","subtitle":"六位皇后 · 全国巡演·北京","venue":"北京·世纪剧院","city":"北京","cast":"六位皇后卡司（全女班）","troupe":"英方授权 · 中文制作","price":"¥180 — 1080","is_all_female":True},
    {"id":"m12","date":"2026-09-26","time":"19:30","title":"音乐剧《SIX》中文版","subtitle":"六位皇后 · 全国巡演·广州","venue":"广州大剧院","city":"广州","cast":"六位皇后卡司（全女班）","troupe":"英方授权 · 中文制作","price":"¥180 — 1080","is_all_female":True},
    # ---------- 常规卡司（用于演示筛选） ----------
    {"id":"r01","date":"2026-07-15","time":"19:30","title":"音乐剧《剧院魅影》","subtitle":"经典复排","venue":"上海大剧院","city":"上海","cast":"轮换卡司","troupe":"上海大剧院呈现","price":"¥280 — 1280","is_all_female":False},
    {"id":"r02","date":"2026-08-12","time":"19:30","title":"音乐剧《妈妈咪呀！》","subtitle":"经典 IP 巡演","venue":"上海文化广场","city":"上海","cast":"轮换卡司","troupe":"中文制作","price":"¥180 — 1080","is_all_female":False},
    {"id":"r03","date":"2026-09-09","time":"19:30","title":"音乐剧《摇滚红与黑》","subtitle":"法语原版巡演","venue":"兰心大戏院","city":"上海","cast":"法方卡司","troupe":"法语原版授权","price":"¥280 — 880","is_all_female":False},
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
        # 大麦为 JS 渲染，纯静态抓取通常只能拿到骨架；此处仅做容错占位
        print(f"  ✓ 大麦网: {len(shows)} 条（动态页面，建议以手动维护 KNOWN_SHOWS 为主）")
    except Exception as e:
        print(f"  ⚠️ 大麦网抓取失败（动态页面，可忽略）: {e}")
    return shows


# ============================================================
# 合并与去重
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
    merged = {f"{s['date']}|{s['title']}|{s['venue']}": s.copy() for s in known_shows}
    norm_index = {}
    for key, show in merged.items():
        nt = normalize_title(show['title'])
        norm_index.setdefault((show['date'], nt), []).append(key)
    new_count = 0
    for scraped in scraped_shows:
        title = scraped.get('title', '')
        date = scraped.get('date', '')
        venue = scraped.get('venue', '')
        nt = normalize_title(title) if title else ''
        matched = None
        if nt and (date, nt) in norm_index:
            matched = norm_index[(date, nt)][0]
        if matched:
            existing = merged[matched]
            if not existing.get('price') or existing['price'] == '以场馆公布为准':
                if scraped.get('price'):
                    existing['price'] = scraped['price']
            if not existing.get('cast') and scraped.get('cast'):
                existing['cast'] = scraped['cast']
        elif date and title and len(title) > 2:
            new_count += 1
            print(f"  🆕 新发现: {date} {title} @ {venue}")
            merged[f"{date}|{title}|{venue}"] = {
                "id": f"new-{new_count:03d}", "date": date, "time": scraped.get('time', ''),
                "title": title, "subtitle": "", "venue": venue, "city": scraped.get('city', ''),
                "cast": scraped.get('cast', ''), "troupe": scraped.get('troupe', ''),
                "price": scraped.get('price', '以场馆公布为准'),
                "is_all_female": scraped.get('is_all_female', False),
            }
    return list(merged.values())


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
    shows.sort(key=lambda s: (s['date'], s.get('time', '00:00')))

    total = len(shows)
    af_count = len([s for s in shows if s.get('is_all_female')])
    cities = set(s.get('city', '') for s in shows if s.get('city'))

    output = {
        "metadata": {
            "report_date": "auto", "data_updated": "auto",
            "total_shows": total, "all_female_shows": af_count,
            "cities": len(cities), "scraped_at": datetime.now().isoformat(),
            "sources": ["df962388", "saoju", "damai", "known_seed"],
        },
        "shows": shows,
    }
    Path("shows.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ shows.json 生成完成")
    print(f"   总场次: {total}（全女卡司 {af_count} 场）")
    print(f"   涉及城市: {len(cities)} 个")
    if not all_scraped:
        print("\n⚠️ 在线抓取无数据，使用种子数据兜底（请按真实档期核实 KNOWN_SHOWS）")

if __name__ == "__main__":
    main()
