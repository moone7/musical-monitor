# 🎵 全女卡司音乐剧演出监控

每日自动监控**全女卡司音乐剧**及全网音乐剧演出，生成可视化日报页。
与 [越剧演出售票监控](https://moone7.github.io/yueju-monitor/) 为**独立仓库、互不干扰**的两个分类。

- 🌐 在线地址：https://yeatszheng0916-lang.github.io/musical-monitor/
- ⚙️ 自动流：GitHub Actions 每日 **北京时间 07:00** 自动抓取 → 生成 → 推送
- 🎨 主题：霓虹 / 聚光灯舞台风格（区别于越剧的金红戏曲风）

## 功能（与越剧监控一致，新增全女卡司特性）

- 📅 **日历视图**：全女卡司日带 💜 徽章，点击日期筛选当天演出
- 💜 **全女卡司筛选**：顶部「仅看全女卡司」一键过滤
- 🎟️ **我的演出提醒**：卡片「标记已购」本地保存，含导出/导入（跨设备）
- 📊 **统计**：近期场次 / 全女卡司场次 / 已购场次 / 涉及城市
- 🔥 **紧急提醒** + 🆕 **今日新动态**
- 📱 PWA：可「添加到主屏幕」离线查看

> ⚠️ 本仓库**不设置单演员特别关注区**（越剧版有「陆志艳特别关注」），聚焦全女卡司整体。

## 数据来源

- 大麦网 damai.cn
- 东方演出网 · 音乐剧专版 shanghaiyinleju.df962388.com
- saoju 音乐剧档期库 y.saoju.net
- 上海文化广场 / 上海大剧院等官方排期

数据抓取脚本 `scraper.py` 为**可插拔**结构：在线抓取用于补全字段，稳定兜底见 `KNOWN_SHOWS`。
音乐剧票务站多为 JS 动态渲染、反爬严格，**建议以手动维护 `KNOWN_SHOWS` 为主**。

## 如何更新演出数据

编辑 `scraper.py` 中的 `KNOWN_SHOWS` 列表，每条演出字段：

```python
{
  "id": "m01",
  "date": "2026-07-10",          # YYYY-MM-DD
  "time": "19:30",
  "title": "音乐剧《SIX》中文版",
  "subtitle": "六位皇后 · 全女卡司",
  "venue": "上海文化广场",
  "city": "上海",
  "cast": "六位皇后卡司（全女班）",
  "troupe": "英方授权 · 中文制作",
  "price": "¥180 — 1080",
  "is_all_female": True          # True=全女卡司，驱动 💜 标签/筛选/统计
}
```

推送后 GitHub Actions 会在下次运行（或手动 `workflow_dispatch`）重新生成页面；也可本地：

```bash
python scraper.py
python generate.py   # 生成 index.html
```

## 本地预览

```bash
python -m http.server 8080
# 打开 http://localhost:8080
```

## 文件结构

```
musical-monitor/
├── index.html              # 生成的日报页（自动流输出）
├── template.html           # 页面模板（霓虹/聚光灯主题）
├── generate.py             # 读取 shows.json + 模板 → index.html
├── scraper.py              # 多源抓取 + KNOWN_SHOWS 兜底
├── shows.json              # 运行时生成（gitignore）
├── sw.js / manifest.json   # PWA
├── icon-*.png / icon.svg   # 图标
└── .github/workflows/      # 每日自动更新
```
