"""
HRBUST Toolkit 公告、新闻与每日简报服务
免登录拉取、强制时间倒序检索、附件乱码修正与本地 SQLite (campus.db) 持久化
支持断网离线缓存降级、未读标记追踪与增量推送
"""

import re
from typing import List, Dict, Any, Optional
from ..core.network import CampusSession
from ..core.db import (
    upsert_notices,
    get_cached_notices,
    get_unread_notices as db_get_unread_notices,
    mark_notice_read as db_mark_notice_read,
    mark_all_notices_read as db_mark_all_notices_read,
    update_notice_content,
    get_cached_notice_detail,
)

class NewsService:
    BASE_URL = "http://jwzx.hrbust.edu.cn"
    COL_NOTICE = 354   # 教务公告
    COL_NEWS = 355     # 教学新闻

    def __init__(self, session: CampusSession = None):
        self.session = session or CampusSession()

    def get_articles(self, column_id: int, page: int = 1) -> List[Dict[str, Any]]:
        """
        拉取指定栏目的文章列表（强制 publicationDate 倒序）
        自动同步持久化至本地 SQLite 数据库；断网时自动降级读取本地缓存
        """
        cat = "教务公告" if column_id == self.COL_NOTICE else "教学新闻"
        url = f"{self.BASE_URL}/homepage/infoArticleList.do"
        params = {
            "columnId": column_id,
            "pagingPage": page,
            "sortColumn": "publicationDate",
            "sortDirection": -1
        }

        try:
            res = self.session.get(url, params=params, timeout=6)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.content.decode("utf-8", errors="ignore"), "html.parser")

            articles = []
            for a in soup.find_all("a", href=re.compile(r"articleId=")):
                title = a.get_text(strip=True)
                href = str(a.get("href") or "")
                m_aid = re.search(r"articleId=(\d+)", href)
                aid = m_aid.group(1) if m_aid else ""

                parent = a.parent
                parent_text = parent.get_text(separator=" ", strip=True) if parent else ""
                m_date = re.search(r"(\d{4}-\d{2}-\d{2})", parent_text)
                date_str = m_date.group(1) if m_date else ""

                if aid and title:
                    articles.append({
                        "id": aid,
                        "title": title,
                        "date": date_str,
                        "category": cat,
                        "url": f"{self.BASE_URL}/homepage/infoSingleArticle.do?articleId={aid}&columnId={column_id}"
                    })

            if articles:
                # 增量存入本地 SQLite
                upsert_notices(articles, category=cat)

            # 读取 DB 中的已读状态补齐
            cached_map = {item["id"]: item for item in get_cached_notices(limit=100, category=cat)}
            for a in articles:
                if a["id"] in cached_map:
                    a["is_read"] = cached_map[a["id"]].get("is_read", False)
                else:
                    a["is_read"] = False

            return articles

        except Exception:
            # 断网或教务在线异常：平滑降级至本地数据库离线缓存
            cached = get_cached_notices(limit=20, category=cat)
            for c in cached:
                c["is_cached"] = True
            return cached

    def search_articles(self, keyword: str, page: int = 1) -> List[Dict[str, Any]]:
        """全站文章倒序检索"""
        url = f"{self.BASE_URL}/homepage/findArticleList.do"
        params = {
            "keyword": keyword,
            "pagingPage": page,
            "sortColumn": "publicationDate",
            "sortDirection": -1
        }
        res = self.session.get(url, params=params, timeout=8)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.content.decode("utf-8", errors="ignore"), "html.parser")

        articles = []
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if "infoContent.do" in href:
                title = a.get_text(strip=True)
                m = re.search(r"articleId=(\d+)", href)
                articles.append({
                    "id": m.group(1) if m else "",
                    "title": title,
                    "url": f"{self.BASE_URL}/homepage/{href}" if not href.startswith("http") else href
                })
        return articles

    def get_daily_brief(self) -> List[Dict[str, Any]]:
        """
        获取每日简报 (公告 + 新闻)
        专为微信机器人 (AstrBot) 或 Agent 定时推送设计，自动持久化至本地库
        """
        notices = self.get_articles(self.COL_NOTICE, page=1)[:5]
        news = self.get_articles(self.COL_NEWS, page=1)[:5]
        brief = []
        for item in notices:
            item["type"] = "教务公告"
            brief.append(item)
        for item in news:
            item["type"] = "教学新闻"
            brief.append(item)
        return brief

    def get_unread_articles(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        查询所有尚未阅读的增量公告 (只推送已读时间戳之后的公告)
        专为解决重复推送、信息打扰而设计
        """
        # 预先拉取一次最新列表并更新 DB
        try:
            if not category or category == "教务公告":
                self.get_articles(self.COL_NOTICE, page=1)
            if not category or category == "教学新闻":
                self.get_articles(self.COL_NEWS, page=1)
        except Exception:
            pass

        return db_get_unread_notices(category=category)

    def mark_as_read(self, article_id: int) -> bool:
        """标记文章为已读"""
        return db_mark_notice_read(article_id)

    def mark_all_as_read(self, category: Optional[str] = None) -> int:
        """一键标记所有公告为已读"""
        return db_mark_all_notices_read(category=category)

    def get_article_detail(self, article_id: str, column_id: int = 354) -> Dict[str, Any]:
        """
        拉取公告/新闻正文详情与附件列表
        免登录，自动清洗排版与附件 GBK 乱码修正
        自动落盘缓存至本地数据库，并自动标记该文章为已读
        """
        aid_int = None
        try:
            aid_int = int(article_id)
        except Exception:
            pass

        # 1. 优先尝试从本地缓存读取正文
        if aid_int:
            cached_detail = get_cached_notice_detail(aid_int)
            if cached_detail and cached_detail.get("content"):
                db_mark_notice_read(aid_int)
                cached_detail["is_from_cache"] = True
                return cached_detail

        # 2. 从官方接口拉取
        url = f"{self.BASE_URL}/homepage/infoSingleArticle.do"
        params = {"articleId": article_id, "columnId": column_id}
        res = self.session.get(url, params=params, timeout=8)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.content.decode("utf-8", errors="ignore"), "html.parser")

        title_tag = soup.find("h2") or soup.find("h1") or soup.find(class_="article-title") or soup.find("td", class_="title")
        title = title_tag.get_text(strip=True) if title_tag else f"校内通告 #{article_id}"

        page_text = soup.get_text()
        m_date = re.search(r"(\d{4}-\d{2}-\d{2})", page_text)
        date_str = m_date.group(1) if m_date else ""

        dept_str = "教务处"
        m_dept = re.search(r"来源[：:]\s*([^\s\|]+)", page_text) or re.search(r"发布人[：:]\s*([^\s\|]+)", page_text)
        if m_dept:
            dept_str = m_dept.group(1).strip()

        paragraphs = []
        content_box = soup.find(id="article-content") or soup.find(class_="article-content") or soup.find("div", class_="content")
        search_root = content_box or soup

        for elem in search_root.find_all(["p", "div"]):
            txt = elem.get_text(strip=True)
            if not txt or txt == title or "downloadTheolFile" in str(elem):
                continue
            if elem.find(["p", "div"]):
                continue
            if txt not in paragraphs:
                paragraphs.append(txt)

        if not paragraphs:
            lines = [l.strip() for l in search_root.get_text(separator="\n").splitlines() if l.strip()]
            for l in lines:
                if len(l) > 10 and l != title and l not in paragraphs:
                    paragraphs.append(l)

        body_text = "\n\n".join(paragraphs)

        attachments = []
        for a in soup.find_all("a"):
            href = str(a.get("href") or "")
            txt = a.get_text(strip=True)
            if not href:
                continue
            if "downloadTheolFile.do" in href or any(ext in href.lower() for ext in (".doc", ".docx", ".pdf", ".xls", ".xlsx", ".zip", ".rar")):
                full_href = href if href.startswith("http") else f"{self.BASE_URL}{href}" if href.startswith("/") else f"{self.BASE_URL}/homepage/{href}"
                fn = txt.strip()
                if not fn or fn.lower().startswith("download") or fn.startswith("http"):
                    m_fn = re.search(r"fileName=([^&]+)", href)
                    if m_fn:
                        try:
                            raw_fn = m_fn.group(1)
                            fn = raw_fn.encode("latin1").decode("gbk", errors="ignore")
                        except Exception:
                            fn = m_fn.group(1)
                    else:
                        fn = "校内附件"

                attachments.append({
                    "name": fn,
                    "url": full_href,
                    "raw_href": href
                })

        # 3. 异步缓存正文并标记已读
        if aid_int:
            update_notice_content(aid_int, body_text, attachments)
            db_mark_notice_read(aid_int)

        return {
            "id": str(article_id),
            "column_id": column_id,
            "title": title,
            "date": date_str,
            "department": dept_str,
            "content": body_text,
            "attachments": attachments,
            "raw_url": f"{self.BASE_URL}/homepage/infoSingleArticle.do?articleId={article_id}&columnId={column_id}",
            "is_read": True
        }
