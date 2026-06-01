#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临沂市卫生健康委员会网站自建 RSS

功能：
1. 抓取指定栏目页
2. 解析文章标题、链接、日期
3. 生成 rss.xml
4. 可配合 GitHub Actions 定时运行

运行：
    pip install -r requirements.txt
    python linyi_wsjsw_rss.py
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag


BASE_URL = "https://wsjsw.linyi.gov.cn/"
SITE_NAME = "临沂市卫生健康委员会"

# 输出文件
OUTPUT_FILE = "rss.xml"

# RSS 中最多保留多少条
MAX_ITEMS = 80

# 中国时区
CN_TZ = timezone(timedelta(hours=8))

# 默认抓取的栏目。后续你想加栏目，只要在这里继续加即可。
CHANNELS = {
    "首页": "https://wsjsw.linyi.gov.cn/",
    "要闻新闻": "https://wsjsw.linyi.gov.cn/ywxw.htm",
    "公示公告": "https://wsjsw.linyi.gov.cn/ywxw/gsgg.htm",
    "政策法规": "https://wsjsw.linyi.gov.cn/wjgz/zcfg/1.htm",
    "办事指南": "https://wsjsw.linyi.gov.cn/bsfw/bszn.htm",
    "资料下载": "https://wsjsw.linyi.gov.cn/bsfw/zlxz.htm",
}


@dataclass(frozen=True)
class FeedItem:
    title: str
    link: str
    channel: str
    pub_date: datetime
    description: str = ""


def fetch_html(url: str) -> str:
    """抓取网页 HTML。"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    # 政府网站常见编码不统一，优先用 apparent_encoding 纠正中文乱码
    if not resp.encoding or resp.encoding.lower() in {"iso-8859-1", "ascii"}:
        resp.encoding = resp.apparent_encoding
    else:
        # 即使服务端给了编码，也用 apparent_encoding 做一次兜底
        apparent = resp.apparent_encoding
        if apparent and apparent.lower() in {"utf-8", "gb2312", "gbk", "gb18030"}:
            resp.encoding = apparent

    return resp.text


def normalize_date(date_text: str) -> datetime | None:
    """从一段文本中识别日期。"""
    if not date_text:
        return None

    patterns = [
        r"(?P<y>20\d{2})[-./年](?P<m>\d{1,2})[-./月](?P<d>\d{1,2})日?",
        r"(?P<m>\d{1,2})[-./月](?P<d>\d{1,2})日?",
    ]

    now = datetime.now(CN_TZ)

    for pattern in patterns:
        m = re.search(pattern, date_text)
        if not m:
            continue

        try:
            year = int(m.groupdict().get("y") or now.year)
            month = int(m.group("m"))
            day = int(m.group("d"))
            dt = datetime(year, month, day, 9, 0, tzinfo=CN_TZ)

            # 首页常出现 MM-DD。若识别出来的日期比今天未来太多，可能是上一年。
            if "y" not in m.groupdict() or not m.groupdict().get("y"):
                if dt > now + timedelta(days=7):
                    dt = dt.replace(year=year - 1)

            return dt
        except ValueError:
            continue

    return None


def is_probably_article_link(link: str, title: str) -> bool:
    """过滤导航、空链接、外部广告等，尽量保留文章链接。"""
    if not link or not title:
        return False

    title = title.strip()
    link = link.strip()

    if len(title) < 6:
        return False

    low = link.lower()

    if low.startswith(("javascript:", "#", "mailto:", "tel:")):
        return False

    parsed = urlparse(link)
    if parsed.netloc and "wsjsw.linyi.gov.cn" not in parsed.netloc:
        # 这个站有些文章跳转微信、人民网、新华社等外链。
        # 如果你想把外链也纳入 RSS，把这里改成 return True。
        return False

    # 排除典型栏目页、目录页
    if low.endswith((".htm", ".html")):
        # 文章页一般有 /info/ 或较深路径；栏目页常是 ywxw.htm、bsfw/bszn.htm
        if "/info/" in low:
            return True
        if re.search(r"/\d{4,}/", low):
            return True

    # 某些政府站文章链接可能不是 /info/，保留含日期/数字路径的
    if re.search(r"/\d+\.htm[l]?$", low):
        return True

    return False


def nearby_text_for_date(a: Tag) -> str:
    """围绕 a 标签向上找一小段文本，用来提取日期。"""
    parts: list[str] = []

    current = a
    for _ in range(4):
        if not isinstance(current, Tag):
            break
        text = current.get_text(" ", strip=True)
        if text:
            parts.append(text)
        if current.parent is None:
            break
        current = current.parent

    return " ".join(parts)


def parse_list_page(url: str, channel: str) -> list[FeedItem]:
    """解析栏目页中的文章列表。"""
    html_text = fetch_html(url)
    soup = BeautifulSoup(html_text, "html.parser")

    items: list[FeedItem] = []
    seen: set[str] = set()

    for a in soup.find_all("a"):
        if not isinstance(a, Tag):
            continue

        raw_title = a.get("title") or a.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", html.unescape(raw_title or "")).strip()
        href = a.get("href")

        if not href:
            continue

        link = urljoin(url, href)

        if not is_probably_article_link(link, title):
            continue

        if link in seen:
            continue
        seen.add(link)

        date_text = nearby_text_for_date(a)
        pub_date = normalize_date(date_text) or datetime.now(CN_TZ)

        items.append(
            FeedItem(
                title=title,
                link=link,
                channel=channel,
                pub_date=pub_date,
                description=f"{channel}｜{title}",
            )
        )

    return items


def escape_xml(text: str) -> str:
    return html.escape(text or "", quote=True)


def build_rss(items: Iterable[FeedItem]) -> str:
    """手写 RSS，减少额外依赖。"""
    unique: dict[str, FeedItem] = {}
    for item in items:
        if item.link not in unique:
            unique[item.link] = item

    sorted_items = sorted(unique.values(), key=lambda x: x.pub_date, reverse=True)[:MAX_ITEMS]
    now = datetime.now(CN_TZ)

    rss_items = []
    for item in sorted_items:
        rss_items.append(
            f"""    <item>
      <title>{escape_xml(f"【{item.channel}】{item.title}")}</title>
      <link>{escape_xml(item.link)}</link>
      <guid isPermaLink="true">{escape_xml(item.link)}</guid>
      <description>{escape_xml(item.description)}</description>
      <pubDate>{format_datetime(item.pub_date)}</pubDate>
    </item>"""
        )

    rss_body = "\n".join(rss_items)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{escape_xml(SITE_NAME)}更新</title>
    <link>{escape_xml(BASE_URL)}</link>
    <description>{escape_xml(SITE_NAME)}栏目更新自建 RSS</description>
    <language>zh-cn</language>
    <lastBuildDate>{format_datetime(now)}</lastBuildDate>
{rss_body}
  </channel>
</rss>
"""


def main() -> None:
    all_items: list[FeedItem] = []

    for channel, url in CHANNELS.items():
        try:
            print(f"抓取：{channel} - {url}")
            items = parse_list_page(url, channel)
            print(f"  解析到 {len(items)} 条")
            all_items.extend(items)
        except Exception as exc:
            print(f"  失败：{channel} - {exc}")

    rss = build_rss(all_items)
    Path(OUTPUT_FILE).write_text(rss, encoding="utf-8")
    print(f"完成：生成 {OUTPUT_FILE}，共 {len(set(i.link for i in all_items))} 条去重候选")


if __name__ == "__main__":
    main()
