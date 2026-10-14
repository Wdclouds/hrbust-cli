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

    def get_daily_briefing(self) -> Dict[str, Any]:
        """返回按分类整理的每日简报字典"""
        return {
            "notices": self.get_articles(self.COL_NOTICE, page=1)[:5],
            "news": self.get_articles(self.COL_NEWS, page=1)[:5],
        }

    def get_article_detail(self, article_id: str, column_id: int = 354) -> Dict[str, Any]:
        """
        拉取公告/新闻正文详情与附件列表
        免登录，自动清洗排版与附件 GBK 乱码修正
        """
        url = f"{self.BASE_URL}/homepage/infoSingleArticle.do"
        params = {"articleId": article_id, "columnId": column_id}
        res = self.session.get(url, params=params, timeout=8)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.content.decode("utf-8", errors="ignore"), "html.parser")

        # 1. 提取标题
        title_tag = soup.find("h2") or soup.find("h1") or soup.find(class_="article-title") or soup.find("td", class_="title")
        title = title_tag.get_text(strip=True) if title_tag else f"校内通告 #{article_id}"

        # 2. 提取发布日期与部门
        page_text = soup.get_text()
        m_date = re.search(r"(\d{4}-\d{2}-\d{2})", page_text)
        date_str = m_date.group(1) if m_date else ""

        dept_str = "教务处"
        m_dept = re.search(r"来源[：:]\s*([^\s\|]+)", page_text) or re.search(r"发布人[：:]\s*([^\s\|]+)", page_text)
        if m_dept:
            dept_str = m_dept.group(1).strip()

        # 3. 提取正文内容并清洗
        paragraphs = []
        # 优先查找主体容器
        content_box = soup.find(id="article-content") or soup.find(class_="article-content") or soup.find("div", class_="content")
        search_root = content_box or soup

        for elem in search_root.find_all(["p", "div"]):
            # 过滤包含脚本和附件区域的块
            txt = elem.get_text(strip=True)
            if not txt or txt == title or "downloadTheolFile" in str(elem):
                continue
            # 避免子块重复提取父级文本
            if elem.find(["p", "div"]):
                continue
            if txt not in paragraphs:
                paragraphs.append(txt)

        if not paragraphs:
            # 兜底直接提取纯文本行
            lines = [l.strip() for l in search_root.get_text(separator="\n").splitlines() if l.strip()]
            for l in lines:
                if len(l) > 10 and l != title and l not in paragraphs:
                    paragraphs.append(l)

        body_text = "\n\n".join(paragraphs)

        # 4. 提取附件列表
        attachments = []
        for a in soup.find_all("a"):
            href = str(a.get("href") or "")
            txt = a.get_text(strip=True)
            if not href:
                continue
            if "downloadTheolFile.do" in href or any(ext in href.lower() for ext in (".doc", ".docx", ".pdf", ".xls", ".xlsx", ".zip", ".rar")):
                full_href = href if href.startswith("http") else f"{self.BASE_URL}{href}" if href.startswith("/") else f"{self.BASE_URL}/homepage/{href}"
                
                # 优先保留链接文本作为可读附件名称 (如 "附件1：校赛报名表.docx")
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

        return {
            "id": str(article_id),
            "column_id": column_id,
            "title": title,
            "date": date_str,
            "department": dept_str,
            "content": body_text,
            "attachments": attachments,
            "raw_url": f"{self.BASE_URL}/homepage/infoSingleArticle.do?articleId={article_id}&columnId={column_id}"
        }
