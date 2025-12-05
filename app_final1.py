# -*- coding: utf-8 -*-
"""
Streamlit Web App: 電影推薦系統
"""

import streamlit as st
import pandas as pd
from dataclasses import dataclass, field
import os
from typing import List, Optional
import requests

# ======================================================================
# TMDB CONFIG
# ======================================================================
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "fb4409aa098199be14089c8489fd414d")
USE_API = bool(TMDB_API_KEY)

TMDB_LANGUAGE = "zh-TW"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_DISCOVER_URL = "https://api.themoviedb.org/3/discover/movie"
TMDB_PERSON_SEARCH_URL = "https://api.themoviedb.org/3/search/person"
TMDB_PERSON_CREDITS_URL = "https://api.themoviedb.org/3/person/{id}/movie_credits"
TMDB_MOVIE_VIDEOS = "https://api.themoviedb.org/3/movie/{id}/videos"

# ======================================================================
# CONSTANTS
# ======================================================================
REGION_MAP = {
    "歐洲": {"英國": "GB", "法國": "FR", "德國": "DE", "義大利": "IT", "西班牙": "ES", "俄羅斯": "RU", "波蘭": "PL"},
    "美洲": {"美國": "US", "加拿大": "CA", "墨西哥": "MX", "巴西": "BR", "阿根廷": "AR"},
    "亞洲": {"中國": "CN", "日本": "JP", "韓國": "KR", "台灣": "TW", "香港": "HK", "印度": "IN", "泰國": "TH", "新加坡": "SG"},
    "非洲": {"南非": "ZA", "埃及": "EG", "奈及利亞": "NG"},
    "大洋洲": {"澳洲": "AU", "紐西蘭": "NZ"},
}

GENRE_MAP = {
    "動作": "28", "冒險": "12", "動畫": "16", "喜劇": "35", "犯罪": "80", "紀錄片": "99", "劇情": "18",
    "家庭": "10751", "奇幻": "14", "歷史": "36", "恐怖": "27", "音樂": "10402", "愛情": "10749",
    "科幻": "878", "驚悚": "53", "戰爭": "10752", "西部": "37", "經典電影": "80,18,36"
}

MOOD_KEYWORDS = {
    "開心": ["開心", "快樂", "高興", "興奮", "愉快", "開朗", "歡樂", "喜悅"],
    "難過": ["難過", "悲傷", "沮喪", "失落", "憂鬱", "傷心", "低落", "消沉"],
    "壓力大": ["壓力", "焦慮", "緊張", "煩躁", "疲憊", "累", "忙", "煩"],
    "無聊": ["無聊", "沒事做", "空虛", "無趣", "閒", "發呆"],
    "想哭": ["想哭", "感傷", "感動", "淚", "哭"],
    "想刺激": ["刺激", "興奮", "冒險", "挑戰", "熱血", "爽", "過癮"]
}

MOOD_TO_GENRE = {
    "開心": ["喜劇", "動畫", "音樂"],
    "難過": ["喜劇", "動畫", "家庭"],
    "壓力大": ["喜劇", "動畫", "愛情"],
    "無聊": ["動作", "冒險", "科幻"],
    "想哭": ["愛情", "劇情", "家庭"],
    "想刺激": ["動作", "驚悚", "恐怖", "科幻"]
}

# ======================================================================
# DATA MODELS
# ======================================================================
@dataclass
class Movie:
    id: int
    title: str
    release_date: str = ""
    vote_average: float = 0.0
    overview: str = ""
    genres: List[str] = field(default_factory=list)
    trailer_url: Optional[str] = None

# ======================================================================
# TMDB WRAPPER
# ======================================================================
def tmdb_get_trailer(movie_id: int) -> Optional[str]:
    if not USE_API:
        return None
 
    url = TMDB_MOVIE_VIDEOS.format(id=movie_id)
    params = {"api_key": TMDB_API_KEY}
    res = requests.get(url, params=params)
    res.raise_for_status()
    data = res.json()
 
    videos = data.get("results", [])
    if not videos:
        return None
 
    # 只拿 YouTube 的
    yt = [v for v in videos if v.get("site") == "YouTube"]
 
    # 1) 先挑正式 Trailer
    trailers = [v for v in yt if v.get("type") == "Trailer"]
 
    # 1-1) 若有中文 trailer，優先
    zh_trailers = [
        v for v in trailers 
        if v.get("iso_639_1") in ("zh", "zh-TW", "zh-CN")
    ]
    if zh_trailers:
        return f"https://www.youtube.com/watch?v={zh_trailers[0]['key']}"
 
    # 1-2) 沒中文，挑第一個正式預告片
    if trailers:
        return f"https://www.youtube.com/watch?v={trailers[0]['key']}"
 
    # 2) 沒有 Trailer → 挑 Teaser（避開 Shorts）
    teasers = [v for v in yt if v.get("type") == "Teaser"]
    if teasers:
        return f"https://www.youtube.com/watch?v={teasers[0]['key']}"
 
    # 3) 最後才挑 fallback（避免 shorts）
    fallback = [v for v in yt if v.get("type") not in ("Clip", "Featurette")]
    if fallback:
        return f"https://www.youtube.com/watch?v={fallback[0]['key']}"
 
    return None

def _fetch(item: dict) -> Movie:
    # 1. 嘗試抓中文翻譯名稱
    title_zh = item.get("title_zh") or item.get("name_zh")

    # 2. 如果 original_title 本身是中文，也用它
    original_title = item.get("original_title")
    is_chinese = original_title and any("\u4e00" <= c <= "\u9fff" for c in original_title)

    # 3. fallback：title（通常是英文）
    title = (
        title_zh
        or (original_title if is_chinese else None)
        or item.get("title")
        or item.get("name")
        or "未命名電影"
    )

    m = Movie(
        id=item.get("id"),
        title=title,
        release_date=item.get("release_date", ""),
        vote_average=item.get("vote_average", 0),
        overview=item.get("overview", "")
    )
    m.trailer_url = tmdb_get_trailer(m.id)
    return m

def tmdb_search(query: str, max_results: int = 10) -> List[Movie]:
    if not USE_API:
        return []
    params = {"api_key": TMDB_API_KEY, "query": query, "language": TMDB_LANGUAGE}
    res = requests.get(TMDB_SEARCH_URL, params=params)
    res.raise_for_status()
    data = res.json()
    return [_fetch(x) for x in data.get("results", [])[:max_results]]

def tmdb_search_by_region(region_codes: List[str], max_results=10) -> List[Movie]:
    if not USE_API:
        return []
    params = {
        "api_key": TMDB_API_KEY,
        "with_origin_country": "|".join(region_codes),
        "language": TMDB_LANGUAGE
    }
    res = requests.get(TMDB_DISCOVER_URL, params=params)
    res.raise_for_status()
    data = res.json()
    return [_fetch(x) for x in data.get("results", [])[:max_results]]

def tmdb_search_multi(title=None, genres=None, region_codes=None, max_results=10) -> List[Movie]:
    if not USE_API:
        return []
    params = {"api_key": TMDB_API_KEY, "language": TMDB_LANGUAGE}
    url = TMDB_DISCOVER_URL

    if genres:
        genre_ids = [GENRE_MAP.get(g) for g in genres if GENRE_MAP.get(g)]
        params["with_genres"] = ",".join(genre_ids)

    if region_codes:
        params["with_origin_country"] = "|".join(region_codes)

    if title:
        url = TMDB_SEARCH_URL
        params = {"api_key": TMDB_API_KEY, "query": title, "language": TMDB_LANGUAGE}

    res = requests.get(url, params=params)
    res.raise_for_status()
    data = res.json()
    return [_fetch(x) for x in data.get("results", [])[:max_results]]

def tmdb_search_by_actor(actor_name: str, max_results=10) -> List[Movie]:
    if not USE_API:
        return []
    res = requests.get(TMDB_PERSON_SEARCH_URL, params={"api_key": TMDB_API_KEY, "query": actor_name})
    res.raise_for_status()
    person_list = res.json().get("results", [])
    if not person_list:
        return []
    person_id = person_list[0]["id"]

    credit_res = requests.get(
        TMDB_PERSON_CREDITS_URL.format(id=person_id),
        params={"api_key": TMDB_API_KEY}
    )
    credit_res.raise_for_status()
    cast = credit_res.json().get("cast", [])
    cast.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    return [_fetch(x) for x in cast[:max_results]]

# ======================================================================
# LINKED LISTS
# ======================================================================
class SNode:
    def __init__(self, movie: Movie):
        self.movie = movie
        self.next = None

class SingleLinkedList:
    def __init__(self):
        self.head = None

    def insert_end(self, movie: Movie):
        node = SNode(movie)
        if not self.head:
            self.head = node
            return
        cur = self.head
        while cur.next:
            cur = cur.next
        cur.next = node

    def traverse(self):
        cur = self.head
        out = []
        while cur:
            out.append(cur.movie)
            cur = cur.next
        return out

    def get_by_index(self, idx):
        cur = self.head
        i = 0
        while cur:
            if i == idx:
                return cur.movie
            cur = cur.next
            i += 1
        return None

class DNode:
    def __init__(self, movie: Movie, user_rating=None):
        self.movie = movie
        self.user_rating = user_rating
        self.prev = None
        self.next = None

class DoublyLinkedList:
    def __init__(self):
        self.head=None
        self.tail=None

    def add(self, movie: Movie, user_rating=None):
        # 防重複
        cur=self.head
        while cur:
            if cur.movie.id == movie.id:
                return False
            cur = cur.next

        node = DNode(movie, user_rating)
        if not self.head:
            self.head=self.tail=node
        else:
            self.tail.next=node
            node.prev=self.tail
            self.tail=node
        return True

    def remove_by_title(self, title):
        title = title.strip().lower()
        cur=self.head
        while cur:
            if cur.movie.title.strip().lower()==title:
                if cur.prev:
                    cur.prev.next=cur.next
                else:
                    self.head=cur.next
                if cur.next:
                    cur.next.prev=cur.prev
                else:
                    self.tail=cur.prev
                return True
            cur=cur.next
        return False

    def traverse_forward(self):
        cur=self.head
        arr=[]
        while cur:
            arr.append(cur)
            cur=cur.next
        return arr

# ======================================================================
# MOCK DATA
# ======================================================================
def get_mock_movies():
    return [
        Movie(1,"全面啟動","2010-07-16",8.8),
        Movie(2,"刺激1995","1994-09-23",9.3),
        Movie(3,"寄生上流","2019-05-30",8.6),
        Movie(4,"神隱少女","2001-07-20",8.5),
        Movie(5,"星際效應","2014-11-07",8.6),
    ]

# ======================================================================
# HELPERS
# ======================================================================
def create_movie_df(movie_list):
    if not movie_list:
        return pd.DataFrame()
    data=[]
    for i,m in enumerate(movie_list):
        trailer_link = f'<a href="{m.trailer_url}" target="_blank">預告片</a>' if m.trailer_url else "N/A"
        data.append({
            "編號": i,
            "片名": m.title,
            "上映日期": m.release_date,
            "TMDB 評分": m.vote_average,
            "劇情摘要": (m.overview[:120] + "...") if m.overview else "（無資料）",
            "預告片": trailer_link
        })
    return pd.DataFrame(data)

def create_favorites_df():
    items = st.session_state["favorites"].traverse_forward()
    if not items:
        return pd.DataFrame()
    out=[]
    for i,node in enumerate(items):
        out.append({
            "收藏編號": i,
            "片名": node.movie.title,
            "TMDB ID": node.movie.id,
            "我的評分": node.user_rating if node.user_rating else "未評分",
            "TMDB 評分": node.movie.vote_average,
        })
    return pd.DataFrame(out)

def analyze_mood(text):
    score={}
    for mood,keys in MOOD_KEYWORDS.items():
        hits=sum([1 for k in keys if k in text])
        if hits>0:
            score[mood]=hits
    if not score:
        return None
    return max(score,key=score.get)

def add_to_favorites_handler(idx):
    movie = st.session_state["search_results"].get_by_index(idx)
    if not movie:
        st.error("編號不存在")
        return
    ok = st.session_state["favorites"].add(movie)
    if ok:
        st.success(f"已加入收藏：{movie.title}")
    else:
        st.warning("已在收藏中")

# ======================================================================
# STREAMLIT UI
# ======================================================================
st.set_page_config(page_title="🎬 智能電影推薦平台", layout="wide")
st.title("🎬 智能電影推薦平台")
st.markdown("---")

if not USE_API:
    st.warning("⚠️ 未設定 TMDB API Key，使用模擬資料中")

if "favorites" not in st.session_state:
    st.session_state["favorites"]=DoublyLinkedList()
if "search_results" not in st.session_state:
    st.session_state["search_results"]=SingleLinkedList()

menu = st.sidebar.radio("功能選單",[
    "1) 🔍 電影搜尋",
    "2) ⭐ 顯示收藏",
    "3) 🗑️ 移除收藏",
    "4) 🧠 心情推薦",
    "5) 🚪 離開"
])

# ======================================================================
# 1) SEARCH
# ======================================================================
if menu.startswith("1"):
    st.header("電影搜尋")

    tabs = st.tabs(["片名","類型","演員","地區","複合"])
    
    # 片名
    with tabs[0]:
        title = st.text_input("輸入電影片名關鍵字：")
        if st.button("搜尋 A"):
            st.session_state["search_results"]=SingleLinkedList()
            if USE_API:
                movies = tmdb_search(title)
            else:
                movies=get_mock_movies()
            for m in movies:
                st.session_state["search_results"].insert_end(m)

    # 類型
    with tabs[1]:
        g = st.selectbox("選擇電影類型：", list(GENRE_MAP.keys()))
        if st.button("搜尋 B"):
            st.session_state["search_results"]=SingleLinkedList()
            if USE_API:
                movies = tmdb_search(g)
            else:
                movies = get_mock_movies()
            for m in movies:
                st.session_state["search_results"].insert_end(m)

    # 演員
    with tabs[2]:
        actor = st.text_input("輸入演員名稱：")
        if st.button("搜尋 C"):
            st.session_state["search_results"]=SingleLinkedList()
            if USE_API:
                movies = tmdb_search_by_actor(actor)
            else:
                movies=[]
            for m in movies:
                st.session_state["search_results"].insert_end(m)

    # 地區
    with tabs[3]:
        all_cs = [c for group in REGION_MAP.values() for c in group]
        cs = st.multiselect("選擇國家：", all_cs)
        if st.button("搜尋 D"):
            st.session_state["search_results"]=SingleLinkedList()
            if USE_API and cs:
                codes=[]
                for c in cs:
                    for g in REGION_MAP.values():
                        if c in g:
                            codes.append(g[c])
                movies = tmdb_search_by_region(codes)
            else:
                movies=get_mock_movies()
            for m in movies:
                st.session_state["search_results"].insert_end(m)

    # 複合
    with tabs[4]:
        t = st.text_input("片名（可空）")
        g = st.multiselect("類型（可空）", list(GENRE_MAP.keys()))
        r = st.multiselect("地區（可空）", [c for group in REGION_MAP.values() for c in group])

        if st.button("搜尋 E"):
            st.session_state["search_results"]=SingleLinkedList()
            if USE_API:
                region_codes=[]
                for x in r:
                    for g in REGION_MAP.values():
                        if x in g:
                            region_codes.append(g[x])

                movies = tmdb_search_multi(
                    title=t or None,
                    genres=g or None,
                    region_codes=region_codes or None,
                )
            else:
                movies=get_mock_movies()

            for m in movies:
                st.session_state["search_results"].insert_end(m)

    # 結果呈現
    st.markdown("---")
    movies = st.session_state["search_results"].traverse()
    df = create_movie_df(movies)

    if not df.empty:
        st.subheader("搜尋結果")
        st.markdown(df.to_html(escape=False), unsafe_allow_html=True)

        col_add,_=st.columns([1,5])
        max_idx = len(movies)-1

        idx = col_add.number_input("輸入編號加入收藏：", min_value=0, max_value=max_idx, step=1, format="%d")

        if st.button("加入收藏"):
            add_to_favorites_handler(idx)


# ======================================================================
# 2) FAVORITES
# ======================================================================
elif menu.startswith("2"):
    st.header("收藏清單")
    df = create_favorites_df()
    if df.empty:
        st.info("沒有收藏")
    else:
        st.markdown(df.to_html(escape=False), unsafe_allow_html=True)


# ======================================================================
# 3) REMOVE FAVORITE
# ======================================================================
elif menu.startswith("3"):
    st.header("移除收藏")

    df = create_favorites_df()
    st.markdown(df.to_html(escape=False), unsafe_allow_html=True)

    title = st.text_input("輸入要移除的電影名稱：")
    if st.button("刪除"):
        if st.session_state["favorites"].remove_by_title(title):
            st.success("已刪除")
        else:
            st.error("找不到該電影")


# ======================================================================
# 4) MOOD RECOMMENDATION
# ======================================================================
# ======================================================================
# 4) MOOD RECOMMENDATION
# ======================================================================
elif menu.startswith("4"):
    st.header("心情推薦")

    text = st.text_area("描述你的心情：")

    # 1. 按下「推薦」時，更新 session_state["search_results"]
    if st.button("推薦"):
        mood = analyze_mood(text or "")
        if not mood:
            st.info("無法判斷心情，自動推薦喜劇")
            mood = "開心"

        genres = MOOD_TO_GENRE[mood]
        st.success(f"偵測到心情：{mood} → 推薦類型：{genres}")

        # 建立結果清單
        results = SingleLinkedList()

        if USE_API:
            movies = []
            for g in genres[:2]:
                movies += tmdb_search(g, max_results=5)
            seen = set()
            for m in movies:
                if m.id not in seen:
                    results.insert_end(m)
                    seen.add(m.id)
        else:
            for m in get_mock_movies():
                results.insert_end(m)

        # 把結果存到 session_state，之後「加入收藏」會用
        st.session_state["search_results"] = results

    # 2. 無論有沒有剛按「推薦」，都試著讀 session_state 裡的結果來顯示
    movies = st.session_state["search_results"].traverse()
    df = create_movie_df(movies)

    if df.empty:
        st.info("目前沒有推薦結果，請先按上面的『推薦』按鈕。")
    else:
        st.markdown(df.to_html(escape=False), unsafe_allow_html=True)

        col_add, _ = st.columns([1, 5])
        max_idx = len(movies) - 1

        idx = col_add.number_input(
            "輸入編號加入收藏：",
            min_value=0,
            max_value=max_idx,
            step=1,
            format="%d",
            key="mood_add_input"
        )

        if st.button("加入收藏（心情推薦）", key="mood_add_btn"):
            add_to_favorites_handler(idx)


# ======================================================================
# 5) EXIT
# ======================================================================
else:
    st.header("感謝使用")
    st.stop()