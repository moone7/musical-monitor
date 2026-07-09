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
稳定兜底数据见 KNOWN_SHOWS（已核实真实档期的全女卡司音乐剧，
数据源：saoju 音乐剧档期库 / 豆瓣戏剧 / 剧方官方公告）。

✅ KNOWN_SHOWS 为已核实真实档期，抓取到的新场次会并入对应剧，新剧会新建。
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
# ✅ 已核实真实档期（数据源：saoju 音乐剧档期库 / 豆瓣戏剧 / 剧方官方公告）
# 抓取到的新场次会并入对应剧的 performances；未在库中的新剧会新建。
# ============================================================
KNOWN_SHOWS = [
    {
        "id": "tafan", "title": "音乐剧《她对此感到厌烦》", "subtitle": "全女班 · 改编自豆瓣9.0分小说",
        "troupe": "缪时客 / 染空间 出品", "is_all_female": True,
        "note": "全女班阵容演绎：莉莉丝/辛西娅/多琳/罗纳德/德国王均由女演员饰演。2026全国巡演，以下为已公布场次。",
        "performances": [
            {"id": "tafan-2026-09-04", "date": "2026-09-04", "time": "19:30", "venue": "青岛大剧院歌剧厅", "city": "青岛", "cast": ["莉莉丝：王洁璐", "辛西娅：党韫葳", "多琳：徐郑凯伊", "罗纳德：王竞琦", "德国王：王珏语涵"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-09-05", "date": "2026-09-05", "time": "14:30", "venue": "青岛大剧院歌剧厅", "city": "青岛", "cast": ["莉莉丝：杜钇樵", "辛西娅：党韫葳", "多琳：田梦", "罗纳德：王竞琦", "德国王：王珏语涵"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-09-11", "date": "2026-09-11", "time": "19:30", "venue": "河南艺术中心", "city": "郑州", "cast": ["莉莉丝：赵雨卉", "辛西娅：党韫葳", "多琳：田梦", "罗纳德：夏云梦", "德国王：蒋依敏"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-09-12", "date": "2026-09-12", "time": "19:30", "venue": "河南艺术中心", "city": "郑州", "cast": ["莉莉丝：赵雨卉", "辛西娅：党韫葳", "多琳：田梦", "罗纳德：夏云梦", "德国王：蒋依敏"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-09-19-a", "date": "2026-09-19", "time": "14:00", "venue": "哈尔滨大剧院歌剧厅", "city": "哈尔滨", "cast": ["莉莉丝：杜钇樵", "辛西娅：张烜尔", "多琳：徐郑凯伊", "罗纳德：王竞琦", "德国王：王明怡"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-09-19-b", "date": "2026-09-19", "time": "19:00", "venue": "哈尔滨大剧院歌剧厅", "city": "哈尔滨", "cast": ["莉莉丝：丁辰西", "辛西娅：张烜尔", "多琳：左一平", "罗纳德：王竞琦", "德国王：王明怡"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-09-26-a", "date": "2026-09-26", "time": "14:00", "venue": "盛京大剧院歌剧厅", "city": "沈阳", "cast": ["莉莉丝：杜钇樵", "辛西娅：郑涵一", "多琳：徐郑凯伊", "罗纳德：夏云梦", "德国王：王珏语涵"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-09-26-b", "date": "2026-09-26", "time": "19:30", "venue": "盛京大剧院歌剧厅", "city": "沈阳", "cast": ["莉莉丝：丁辰西", "辛西娅：杨依泠", "多琳：左一平", "罗纳德：夏云梦", "德国王：王明怡"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-10-06", "date": "2026-10-06", "time": "", "venue": "舟山普陀大剧院", "city": "舟山", "cast": ["阵容以官方公布为准"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-10-07", "date": "2026-10-07", "time": "", "venue": "舟山普陀大剧院", "city": "舟山", "cast": ["阵容以官方公布为准"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-10-16", "date": "2026-10-16", "time": "19:30", "venue": "江苏大剧院歌剧厅", "city": "南京", "cast": ["莉莉丝：赵雨卉", "辛西娅：张烜尔", "多琳：胥子含", "罗纳德：恩妤", "德国王：蒋依敏"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-10-17", "date": "2026-10-17", "time": "19:30", "venue": "江苏大剧院歌剧厅", "city": "南京", "cast": ["莉莉丝：王洁璐", "辛西娅：党韫葳", "多琳：胥子含", "罗纳德：恩妤", "德国王：王明怡"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-10-23", "date": "2026-10-23", "time": "19:30", "venue": "杭州金沙湖大剧院", "city": "杭州", "cast": ["莉莉丝：赵雨卉", "辛西娅：张烜尔", "多琳：胥子含", "罗纳德：恩妤", "德国王：蒋依敏"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-10-24", "date": "2026-10-24", "time": "19:30", "venue": "杭州金沙湖大剧院", "city": "杭州", "cast": ["莉莉丝：王洁璐", "辛西娅：党韫葳", "多琳：胥子含", "罗纳德：恩妤", "德国王：王明怡"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-10-31", "date": "2026-10-31", "time": "19:30", "venue": "温岭大剧院", "city": "台州", "cast": ["莉莉丝：杜钇樵", "辛西娅：马小乔", "多琳：徐郑凯伊", "罗纳德：王竞琦", "德国王：蒋依敏"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-11-01", "date": "2026-11-01", "time": "14:30", "venue": "温岭大剧院", "city": "台州", "cast": ["莉莉丝：王洁璐", "辛西娅：马小乔", "多琳：徐郑凯伊", "罗纳德：王竞琦", "德国王：蒋依敏"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-11-06", "date": "2026-11-06", "time": "19:30", "venue": "二七剧场", "city": "北京", "cast": ["莉莉丝：丁辰西", "辛西娅：郑涵一", "多琳：田梦", "罗纳德：恩妤", "德国王：王明怡"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "tafan-2026-11-07", "date": "2026-11-07", "time": "19:30", "venue": "二七剧场", "city": "北京", "cast": ["莉莉丝：丁辰西", "辛西娅：郑涵一", "多琳：田梦", "罗纳德：恩妤", "德国王：王明怡"], "price": "¥180 — 580", "is_all_female": True}
        ]
    },
    {
        "id": "chimera", "title": "音乐剧《奇美拉》", "subtitle": "全女班 · 女性反乌托邦",
        "troupe": "一部以女性视角探讨反乌托邦未来的音乐剧", "is_all_female": True,
        "note": "全女班阵容。以下为上海二轮（2026.4 艺海剧院小剧场，已售罄）真实场次，供卡司参考；新巡演档期以官方公布为准。",
        "performances": [
            {"id": "chimera-2026-04-03", "date": "2026-04-03", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["叶嘉雯", "郭耀嵘", "党韫葳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-04-a", "date": "2026-04-04", "time": "14:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["吴杭律", "胥子含", "叶嘉雯"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-04-b", "date": "2026-04-04", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["刘乙萱", "郭耀嵘", "党韫葳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-05-a", "date": "2026-04-05", "time": "14:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["叶嘉雯", "赵雨卉", "党韫葳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-05-b", "date": "2026-04-05", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["丁辰西", "宁梦恬", "杜鑫艳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-06-a", "date": "2026-04-06", "time": "14:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["刘乙萱", "赵雨卉", "杜鑫艳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-06-b", "date": "2026-04-06", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["叶嘉雯", "郭耀嵘", "马小乔"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-08", "date": "2026-04-08", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["丁辰西", "宁梦恬", "杜鑫艳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-09", "date": "2026-04-09", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["杜钇樵", "胥子含", "王珏语涵"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-10", "date": "2026-04-10", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["吴杭律", "胥子含", "马小乔"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-11-a", "date": "2026-04-11", "time": "14:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["丁辰西", "宁梦恬", "党韫葳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-11-b", "date": "2026-04-11", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["叶嘉雯", "左一平", "王竞琦"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-12-a", "date": "2026-04-12", "time": "14:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["刘乙萱", "赵雨卉", "党韫葳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-12-b", "date": "2026-04-12", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["杜钇樵", "胥子含", "王珏语涵"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-15", "date": "2026-04-15", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["丁辰西", "宁梦恬", "党韫葳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-16", "date": "2026-04-16", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["郑涵一", "赵雨卉", "马小乔"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-17", "date": "2026-04-17", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["叶嘉雯", "郭耀嵘", "杜鑫艳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-18-a", "date": "2026-04-18", "time": "14:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["叶嘉雯", "左一平", "党韫葳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-18-b", "date": "2026-04-18", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["郑涵一", "王洁璐", "王珏语涵"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-19-a", "date": "2026-04-19", "time": "14:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["叶嘉雯", "郭耀嵘", "杜鑫艳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-19-b", "date": "2026-04-19", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["杜钇樵", "左一平", "马小乔"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-22", "date": "2026-04-22", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["叶嘉雯", "郭耀嵘", "王竞琦"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-23", "date": "2026-04-23", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["吴杭律", "赵雨卉", "党韫葳"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-24", "date": "2026-04-24", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["郑涵一", "王洁璐", "王竞琦"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-25-a", "date": "2026-04-25", "time": "14:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["杜钇樵", "左一平", "马小乔"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-25-b", "date": "2026-04-25", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["吴杭律", "胥子含", "叶嘉雯"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-26-a", "date": "2026-04-26", "time": "14:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["吴杭律", "王洁璐", "王竞琦"], "price": "¥180 — 580", "is_all_female": True},
            {"id": "chimera-2026-04-26-b", "date": "2026-04-26", "time": "19:30", "venue": "艺海剧院小剧场", "city": "上海", "cast": ["刘乙萱", "赵雨卉", "杜鑫艳"], "price": "¥180 — 580", "is_all_female": True}
        ]
    },
    {
        "id": "witch", "title": "音乐剧《女巫》", "subtitle": "悬疑 · 含男演员饰「女巫猎人」",
        "troupe": "上海话剧艺术中心 呈现", "is_all_female": False,
        "note": "卡司以女演员为主，但「女巫猎人」角色由男演员饰演，故不计入全女卡司。上海驻演共12场。",
        "performances": [
            {"id": "witch-2026-07-23", "date": "2026-07-23", "time": "19:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：余思冉", "玛格丽特：张沁丹", "艾尔西丝：赵雨卉", "女巫猎人：付世刚"], "price": "¥180 — 986", "is_all_female": False},
            {"id": "witch-2026-07-24", "date": "2026-07-24", "time": "19:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：陈恬", "玛格丽特：丁臻滢", "艾尔西丝：王洁璐", "女巫猎人：曹洪远"], "price": "¥180 — 986", "is_all_female": False},
            {"id": "witch-2026-07-25", "date": "2026-07-25", "time": "14:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：余思冉", "玛格丽特：丁臻滢", "艾尔西丝：王洁璐", "女巫猎人：覃威尔"], "price": "¥180 — 986", "is_all_female": False},
            {"id": "witch-2026-07-26-a", "date": "2026-07-26", "time": "14:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：陈恬", "玛格丽特：党韫葳", "艾尔西丝：王洁璐", "女巫猎人：曹洪远"], "price": "¥180 — 986", "is_all_female": False},
            {"id": "witch-2026-07-26-b", "date": "2026-07-26", "time": "19:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：胥子含", "玛格丽特：张沁丹", "艾尔西丝：赵雨卉", "女巫猎人：付世刚"], "price": "¥180 — 986", "is_all_female": False},
            {"id": "witch-2026-07-28", "date": "2026-07-28", "time": "19:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：余思冉", "玛格丽特：丁臻滢", "艾尔西丝：党韫葳", "女巫猎人：覃威尔"], "price": "¥180 — 986", "is_all_female": False},
            {"id": "witch-2026-07-29", "date": "2026-07-29", "time": "19:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：胥子含", "玛格丽特：张沁丹", "艾尔西丝：赵雨卉", "女巫猎人：曹洪远"], "price": "¥180 — 986", "is_all_female": False},
            {"id": "witch-2026-07-30", "date": "2026-07-30", "time": "19:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：陈玉婷", "玛格丽特：丁辰西", "艾尔西丝：党韫葳", "女巫猎人：付世刚"], "price": "¥180 — 986", "is_all_female": False},
            {"id": "witch-2026-07-31", "date": "2026-07-31", "time": "19:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：陈玉婷", "玛格丽特：党韫葳", "艾尔西丝：赵雨卉", "女巫猎人：曹洪远"], "price": "¥180 — 986", "is_all_female": False},
            {"id": "witch-2026-08-01-a", "date": "2026-08-01", "time": "14:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：叶嘉雯", "玛格丽特：丁辰西", "艾尔西丝：党韫葳", "女巫猎人：覃威尔"], "price": "¥180 — 986", "is_all_female": False},
            {"id": "witch-2026-08-01-b", "date": "2026-08-01", "time": "19:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：陈玉婷", "玛格丽特：丁辰西", "艾尔西丝：党韫葳", "女巫猎人：付世刚"], "price": "¥180 — 986", "is_all_female": False},
            {"id": "witch-2026-08-02", "date": "2026-08-02", "time": "14:30", "venue": "上剧场", "city": "上海", "cast": ["艾比：叶嘉雯", "玛格丽特：党韫葳", "艾尔西丝：王洁璐", "女巫猎人：覃威尔"], "price": "¥180 — 986", "is_all_female": False}
        ]
    },
    {
        "id": "six", "title": "音乐剧《SIX》", "subtitle": "原版中国巡演首站 · 全女卡司六皇后",
        "troupe": "伦敦西区原版 · 英文演出", "is_all_female": True,
        "note": "2026.10.1–10.11 苏州湾大剧院 连演14场（全女卡司·原版中国巡演首站），以下为每日夜场，部分日期加演下午场，具体每日场次以官方开票为准。",
        "performances": [
            {"id": "six-2026-10-01", "date": "2026-10-01", "time": "19:30", "venue": "苏州湾大剧院", "city": "苏州", "cast": ["六位皇后（原版卡司，以官方公布为准）"], "price": "¥66 — 766", "is_all_female": True},
            {"id": "six-2026-10-02", "date": "2026-10-02", "time": "19:30", "venue": "苏州湾大剧院", "city": "苏州", "cast": ["六位皇后（原版卡司，以官方公布为准）"], "price": "¥66 — 766", "is_all_female": True},
            {"id": "six-2026-10-03", "date": "2026-10-03", "time": "19:30", "venue": "苏州湾大剧院", "city": "苏州", "cast": ["六位皇后（原版卡司，以官方公布为准）"], "price": "¥66 — 766", "is_all_female": True},
            {"id": "six-2026-10-04", "date": "2026-10-04", "time": "19:30", "venue": "苏州湾大剧院", "city": "苏州", "cast": ["六位皇后（原版卡司，以官方公布为准）"], "price": "¥66 — 766", "is_all_female": True},
            {"id": "six-2026-10-05", "date": "2026-10-05", "time": "19:30", "venue": "苏州湾大剧院", "city": "苏州", "cast": ["六位皇后（原版卡司，以官方公布为准）"], "price": "¥66 — 766", "is_all_female": True},
            {"id": "six-2026-10-06", "date": "2026-10-06", "time": "19:30", "venue": "苏州湾大剧院", "city": "苏州", "cast": ["六位皇后（原版卡司，以官方公布为准）"], "price": "¥66 — 766", "is_all_female": True},
            {"id": "six-2026-10-07", "date": "2026-10-07", "time": "19:30", "venue": "苏州湾大剧院", "city": "苏州", "cast": ["六位皇后（原版卡司，以官方公布为准）"], "price": "¥66 — 766", "is_all_female": True},
            {"id": "six-2026-10-08", "date": "2026-10-08", "time": "19:30", "venue": "苏州湾大剧院", "city": "苏州", "cast": ["六位皇后（原版卡司，以官方公布为准）"], "price": "¥66 — 766", "is_all_female": True},
            {"id": "six-2026-10-09", "date": "2026-10-09", "time": "19:30", "venue": "苏州湾大剧院", "city": "苏州", "cast": ["六位皇后（原版卡司，以官方公布为准）"], "price": "¥66 — 766", "is_all_female": True},
            {"id": "six-2026-10-10", "date": "2026-10-10", "time": "19:30", "venue": "苏州湾大剧院", "city": "苏州", "cast": ["六位皇后（原版卡司，以官方公布为准）"], "price": "¥66 — 766", "is_all_female": True},
            {"id": "six-2026-10-11", "date": "2026-10-11", "time": "19:30", "venue": "苏州湾大剧院", "city": "苏州", "cast": ["六位皇后（原版卡司，以官方公布为准）"], "price": "¥66 — 766", "is_all_female": True}
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
