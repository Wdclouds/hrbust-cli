"""
HRBUST Toolkit 公告、新闻与每日简报服务
免登录拉取、强制时间倒序检索与附件乱码修正
"""

import re
from typing import List, Dict, Any
from ..core.network import CampusSession

class NewsService:
    BASE_URL = "http://jwzx.hrbust.edu.cn"
    COL_NOTICE = 354   # 教务公告
    COL_NEWS = 355     # 教学新闻

    def __init__(self, session: CampusSession = None):
        self.session = session or CampusSession()

    def get_articles(self, column_id: int, page: int = 1) -> List[Dict[str, Any]]:
        """
        拉取指定栏目的文章列表（强制 publicationDate 倒序）
        """
        url = f"{self.BASE_URL}/homepage/infoArticleList.do"
        params = {
            "columnId": column_id,
            "pagingPage": page,
            "sortColumn": "publicationDate",
            "sortDirection": -1
        }
        res = self.session.get(url, params=params, timeout=6)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.content.decode("utf-8", errors="ignore"), "html.parser")

        articles = []
        for a in soup.find_all("a", href=re.compile(r"articleId=")):
            title = a.get_text(strip=True)
            href = a.get("href", "")
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
                    "url": f"{self.BASE_URL}/homepage/infoSingleArticle.do?articleId={aid}&columnId={column_id}"
                })
        return articles

    def search_articles(self, keyword: str, page: int = 1) -> List[Dict[str, Any]]:
        """
        全站文章倒序检索
        """
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
        获取每日增量简报 (公告 + 新闻)
        专为微信机器人 (AstrBot) 或 Agent 定时推送设计
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
