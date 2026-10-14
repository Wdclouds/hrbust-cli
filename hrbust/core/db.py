"""
HRBUST Toolkit 本地数据持久化引擎 (Campus Database)
基于 SQLite (WAL 模式) 实现教学公告、校内新闻、大课表与用户已读时间戳的本地持久化
支持断网离线秒开、历史文章归档、增量未读追踪与已读标记
"""

import os
import json
import time
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

from .auth import CONFIG_DIR

DB_FILE = CONFIG_DIR / "campus.db"

def get_db_connection() -> sqlite3.Connection:
    """获取 SQLite 数据库连接并确保表结构就绪 (启用 WAL 模式)"""
    if not CONFIG_DIR.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(CONFIG_DIR, 0o700)
        except Exception:
            pass

    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _init_tables(conn)
    return conn

def _init_tables(conn: sqlite3.Connection) -> None:
    """初始化通知公告、课表快照与元数据表"""
    with conn:
        # 1. 文章与公告表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                date TEXT,
                url TEXT,
                content TEXT,
                attachments TEXT,
                first_seen_at REAL,
                is_read INTEGER DEFAULT 0,
                read_at REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notices_date ON notices (date DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notices_unread ON notices (is_read, first_seen_at DESC)")

        # 2. 课表与课时快照表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT NOT NULL,
                course_name TEXT NOT NULL,
                teacher TEXT,
                room TEXT,
                day_of_week TEXT,
                session TEXT,
                weeks TEXT,
                raw_text TEXT,
                updated_at REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_schedules_term ON schedules (term)")

        # 3. 系统元数据表 (已读时间戳、最近检查时间等)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at REAL
            )
        """)

# ==================== 公告与新闻持久化操作 ====================

def upsert_notices(articles: List[Dict[str, Any]], category: str = "公告") -> Dict[str, int]:
    """
    增量插入或更新文章列表。
    保留已存在的已读标记与初次捕获时间；新文章标记为未读 (is_read=0)。
    :return: {"new_count": 新增未读篇数, "total": 总数}
    """
    if not articles:
        return {"new_count": 0, "total": 0}

    now = time.time()
    new_count = 0
    conn = get_db_connection()
    try:
        with conn:
            for item in articles:
                aid_raw = item.get("id") or item.get("article_id")
                if not aid_raw:
                    continue
                try:
                    aid = int(aid_raw)
                except (ValueError, TypeError):
                    continue

                title = str(item.get("title", "")).strip()
                date_str = str(item.get("date", "")).strip()
                url = str(item.get("url", "")).strip()
                content = item.get("content")
                attachments = json.dumps(item.get("attachments", []), ensure_ascii=False) if item.get("attachments") else None

                # 检查是否存在
                cur = conn.execute("SELECT id, is_read FROM notices WHERE id = ?", (aid,))
                row = cur.fetchone()
                if row is None:
                    # 全新文章
                    conn.execute("""
                        INSERT INTO notices (id, category, title, date, url, content, attachments, first_seen_at, is_read, read_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
                    """, (aid, category, title, date_str, url, content, attachments, now))
                    new_count += 1
                else:
                    # 已存在：更新正文/标题等，但保留原始 is_read 状态
                    if content or attachments:
                        conn.execute("""
                            UPDATE notices SET title = ?, date = ?, url = ?, content = COALESCE(?, content),
                                               attachments = COALESCE(?, attachments)
                            WHERE id = ?
                        """, (title, date_str, url, content, attachments, aid))
        return {"new_count": new_count, "total": len(articles)}
    finally:
        conn.close()

def get_cached_notices(limit: int = 50, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """从本地数据库读取已缓存的文章列表 (按日期与 ID 倒序)"""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM notices"
        params: List[Any] = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY date DESC, id DESC LIMIT ?"
        params.append(limit)

        cur = conn.execute(query, params)
        rows = cur.fetchall()
        result = []
        for r in rows:
            att = []
            if r["attachments"]:
                try:
                    att = json.loads(r["attachments"])
                except Exception:
                    pass
            result.append({
                "id": str(r["id"]),
                "category": r["category"],
                "title": r["title"],
                "date": r["date"],
                "url": r["url"],
                "content": r["content"],
                "attachments": att,
                "first_seen_at": r["first_seen_at"],
                "is_read": bool(r["is_read"]),
                "read_at": r["read_at"]
            })
        return result
    finally:
        conn.close()

def get_unread_notices(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """查询所有未读公告（自上次标记已读以来的增量公告）"""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM notices WHERE is_read = 0"
        params: List[Any] = []
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY date DESC, id DESC"

        cur = conn.execute(query, params)
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": str(r["id"]),
                "category": r["category"],
                "title": r["title"],
                "date": r["date"],
                "url": r["url"],
                "first_seen_at": r["first_seen_at"],
                "is_read": False
            })
        return result
    finally:
        conn.close()

def mark_notice_read(article_id: int) -> bool:
    """标记单篇公告为已读"""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE notices SET is_read = 1, read_at = ? WHERE id = ?",
                (time.time(), article_id)
            )
        return True
    finally:
        conn.close()

def mark_all_notices_read(category: Optional[str] = None) -> int:
    """一键标记所有公告（或指定分类）为已读"""
    conn = get_db_connection()
    try:
        now = time.time()
        with conn:
            if category:
                cur = conn.execute("UPDATE notices SET is_read = 1, read_at = ? WHERE category = ? AND is_read = 0", (now, category))
            else:
                cur = conn.execute("UPDATE notices SET is_read = 1, read_at = ? WHERE is_read = 0", (now,))
            return cur.rowcount
    finally:
        conn.close()

def update_notice_content(article_id: int, content: str, attachments: Optional[List[Dict[str, str]]] = None) -> None:
    """缓存公告正文与附件信息"""
    conn = get_db_connection()
    try:
        att_json = json.dumps(attachments or [], ensure_ascii=False) if attachments is not None else None
        with conn:
            conn.execute("""
                UPDATE notices SET content = ?, attachments = COALESCE(?, attachments)
                WHERE id = ?
            """, (content, att_json, article_id))
    finally:
        conn.close()

def get_cached_notice_detail(article_id: int) -> Optional[Dict[str, Any]]:
    """查询单篇文章的已缓存正文与附件详情"""
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT * FROM notices WHERE id = ?", (article_id,))
        row = cur.fetchone()
        if not row or not row["content"]:
            return None
        att = []
        if row["attachments"]:
            try:
                att = json.loads(row["attachments"])
            except Exception:
                pass
        return {
            "id": str(row["id"]),
            "title": row["title"],
            "date": row["date"],
            "content": row["content"],
            "attachments": att,
            "is_read": bool(row["is_read"])
        }
    finally:
        conn.close()

# ==================== 课表与课时快照持久化 ====================

def save_schedule_snapshot(courses: List[Dict[str, Any]], term: str = "current") -> None:
    """持久化保存学期课表快照 (覆盖对应学期)"""
    if not courses:
        return
    now = time.time()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM schedules WHERE term = ?", (term,))
            for c in courses:
                conn.execute("""
                    INSERT INTO schedules (term, course_name, teacher, room, day_of_week, session, weeks, raw_text, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    term,
                    c.get("name") or c.get("title", ""),
                    c.get("teacher", ""),
                    c.get("room") or c.get("classroom", ""),
                    c.get("day_of_week", ""),
                    c.get("session", ""),
                    c.get("weeks", ""),
                    c.get("raw", ""),
                    now
                ))
            set_meta(f"schedule_{term}_updated_at", now, conn=conn)
    finally:
        conn.close()

def get_cached_schedule(term: str = "current") -> Dict[str, Any]:
    """读取本地缓存的课表快照 (离线可用)"""
    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT * FROM schedules WHERE term = ? ORDER BY id ASC", (term,))
        rows = cur.fetchall()
        courses = []
        for r in rows:
            courses.append({
                "title": r["course_name"],
                "name": r["course_name"],
                "teacher": r["teacher"],
                "classroom": r["room"],
                "room": r["room"],
                "day_of_week": r["day_of_week"],
                "session": r["session"],
                "weeks": r["weeks"],
                "raw": r["raw_text"]
            })
        up_at = get_meta(f"schedule_{term}_updated_at", conn=conn)
        return {
            "has_cache": len(courses) > 0,
            "courses": courses,
            "updated_at": float(up_at) if up_at else None
        }
    finally:
        conn.close()

# ==================== 元数据与时间戳管理 ====================

def set_meta(key: str, value: Any, conn: Optional[sqlite3.Connection] = None) -> None:
    """保存配置键值"""
    val_str = str(value)
    now = time.time()
    own_conn = False
    if conn is None:
        conn = get_db_connection()
        own_conn = True
    try:
        with conn:
            conn.execute("""
                INSERT INTO meta (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """, (key, val_str, now))
    finally:
        if own_conn:
            conn.close()

def get_meta(key: str, default: Any = None, conn: Optional[sqlite3.Connection] = None) -> Any:
    """读取配置键值"""
    own_conn = False
    if conn is None:
        conn = get_db_connection()
        own_conn = True
    try:
        cur = conn.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default
    finally:
        if own_conn:
            conn.close()
