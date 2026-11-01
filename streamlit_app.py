# -*- coding: utf-8 -*-
"""HoloDreams 組隊房間：多房間版，狀態存 GitHub repo JSON"""
import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import streamlit as st

TZ = ZoneInfo("Asia/Taipei")
ROOM_SIZE = 5                # 每間房固定 5 人
MAX_ROOMS = 20               # 最多 20 間
MAX_AHEAD = timedelta(hours=2)          # 最多提前 2 小時預約
ROOM_TTL = timedelta(hours=8)           # 8 小時無排隊且無任何變化 → 自動刪
ADMIN_ID = "fantastic1936"

# (巴哈ID, 遊戲ID, priority)，命中任一即套用
PRIORITY_IDS = [
    ("小狼", "こはね", 1),
    ("夜久", "Ten Tender", 2),
]

st.set_page_config(page_title="Hololive dreams", page_icon="🎮", layout="wide")

# 背景圖：遮罩跟著 light / dark 主題切換（數字越小圖越清楚）
BG_URL = "https://truth.bahamut.com.tw/s01/202607/forum/84454/f2c592e75c79b276e76d85beb4ea4927.JPG"
st.markdown(f"""
<style>
.stApp {{
    background: linear-gradient(rgba(255, 255, 255, 0.75), rgba(255, 255, 255, 0.75)),
                url("{BG_URL}") center center / cover fixed no-repeat !important;
}}
.stDeployButton, [data-testid="stDeployButton"], [data-testid="stStatusWidget"] {{
    display: none !important;        # 右上角 Deploy／狀態連結（會連到 GitHub）
}}
[data-testid="stToolbar"], #MainMenu, [data-testid="stMainMenu"] {{
    display: none !important;        # 整條右上工具列（含漢堡選單）全藏
}}
[data-testid="stSidebar"] {{
    background-color: rgba(255, 255, 255, 0.88) !important;
}}
@media (prefers-color-scheme: dark) {{
    .stApp {{
        background: linear-gradient(rgba(18, 18, 26, 0.78), rgba(18, 18, 26, 0.78)),
                    url("{BG_URL}") center center / cover fixed no-repeat !important;
    }}
    [data-testid="stSidebar"] {{
        background-color: rgba(14, 14, 20, 0.88) !important;
    }}
}}
</style>
""", unsafe_allow_html=True)


# ---------- 時間 ----------
def now_tw():
    return datetime.now(TZ)

def parse(t):
    return datetime.fromisoformat(t)

def fmt(t):
    return parse(t).strftime("%m-%d %H:%M") if t else "—"


# ---------- GitHub JSON 儲存 ----------
def _gh():
    if "github_token" not in st.secrets or "repo" not in st.secrets:
        st.error("還沒設定 Secrets：github_token / repo")
        st.stop()
    return {
        "token": st.secrets["github_token"],
        "url": "https://api.github.com/repos/{}/contents/{}".format(
            st.secrets["repo"], st.secrets.get("state_path", "room_state.json")),
        "branch": st.secrets.get("branch", "main"),
    }

@st.cache_data(ttl=5, show_spinner=False)
def _gh_get(token, url, branch):
    r = requests.get(url, params={"ref": branch},
                     headers={"Authorization": f"Bearer {token}",
                              "Accept": "application/vnd.github+json"},
                     timeout=15)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    data = r.json()
    return data["sha"], base64.b64decode(data["content"])

def _migrate_old(state):
    """舊的單一房間格式 → 包成 rooms['r_default']"""
    if "rooms" in state:
        return state
    ts = now_tw().isoformat()
    old_room = state.get("room", [])
    return {
        "rev": state.get("rev", 0),
        "rooms": {
            "r_default": {
                "name": "小狼gamers",          # 原本的單一房間 = 第一間
                "owner": (old_room[0].get("baha_id") or old_room[0].get("game_id") or "") if old_room else "",
                "room": old_room,
                "queue": state.get("queue", []),
                "messages": state.get("messages", []),
                "active": ts, "created": ts,
            }
        },
    }

def load_state():
    c = _gh()
    _sha, raw = _gh_get(c["token"], c["url"], c["branch"])
    if raw is None:
        fetched = {"rooms": {}, "rev": 0}
    else:
        try:
            fetched = json.loads(raw)
        except Exception:
            st.error("room_state.json 內容損毀，請到 GitHub 手動檢查")
            st.stop()
        fetched = _migrate_old(fetched)
    # GitHub GET 有約 60 秒快取，剛存完會讀回舊檔 → 版號較新就用自己剛存的
    saved = st.session_state.get("saved_state")
    if saved and saved.get("rev", 0) > fetched.get("rev", 0):
        return saved
    return fetched

def save_state(state):
    c = _gh()
    state["rev"] = state.get("rev", 0) + 1
    payload = base64.b64encode(json.dumps(state, ensure_ascii=False).encode()).decode()
    for _ in range(3):                       # 同時有人改 → 409 重試
        sha, _raw = _gh_get(c["token"], c["url"], c["branch"])
        body = {"message": "update room state", "branch": c["branch"], "content": payload}
        if sha:
            body["sha"] = sha
        r = requests.put(c["url"],
                         headers={"Authorization": f"Bearer {c['token']}",
                                  "Accept": "application/vnd.github+json"},
                         json=body, timeout=15)
        if r.status_code < 300:
            _gh_get.clear()
            st.session_state["saved_state"] = state   # 寫穿快取：自己馬上看到
            return True
        _gh_get.clear()
    st.error("GitHub 儲存失敗（可能同時有人操作），請再試一次")
    return False


# ---------- 規則 ----------
def resolve_prio(baha, game):
    b, g = baha.strip().casefold(), game.strip().casefold()
    for pb, pg, p in PRIORITY_IDS:
        if b == pb.casefold() or g == pg.casefold():
            return p
    return 3

def _sha(pw):
    return hashlib.sha256((pw or "").encode()).hexdigest()

def _pw_ok(p, pw, is_admin):
    if is_admin or p.get("pw_hash") is None:   # 舊資料沒密碼 → 放行
        return True
    return _sha(pw) == p["pw_hash"]

def _qkey(p):
    """priority 絕對 → 較早半小時批 → 分數高 → 火消耗高 → 先註冊"""
    reg = parse(p["reg_at"])
    batch = reg.replace(minute=0 if reg.minute < 30 else 30, second=0, microsecond=0)
    return (p["prio"], batch, -(p.get("score") or 0),
            -(p.get("fire") or 0), reg)

def _eligible(p, now):
    pref = p.get("start_pref")
    return pref is None or parse(pref) <= now

def _find(lst, key_id):
    k = (key_id or "").strip().casefold()
    if not k:
        return None
    for i, p in enumerate(lst):
        if (p["baha_id"] and p["baha_id"].casefold() == k) or \
           (p["game_id"] and p["game_id"].casefold() == k):
            return i
    return None

def _locate_all_rooms(state, baha, game):
    """回傳玩家目前在哪間房（房裡或排隊中）：(rid, room_obj)"""
    for rid2, r2 in state["rooms"].items():
        for x in (baha, game):
            if _find(r2["room"], x) is not None or _find(r2["queue"], x) is not None:
                return rid2, r2
    return None, None

def _touch(r, now):
    r["active"] = now.isoformat()             # 房間活動時間（8 小時沒動+沒人排隊會刪）

def _transfer_owner(r):
    """房主不在房裡/排隊時，房主身分換給房內最早成員（只換一次，換了就鎖定）"""
    if not r.get("owner"):
        return False
    for lst in (r["room"], r["queue"]):
        if _find(lst, r["owner"]) is not None:
            return False
    p0 = r["room"][0] if r["room"] else None
    r["owner"] = (p0["baha_id"] or p0["game_id"] or "") if p0 else ""
    return True

def refill(r, now):
    """空位 → 依排序遞補第一個時間到的排隊者"""
    room, queue, dirty = r["room"], r["queue"], False
    while len(room) < ROOM_SIZE and queue:
        idx = next((i for i, q in enumerate(queue) if _eligible(q, now)), None)
        if idx is None:
            break
        p = queue.pop(idx)
        p["sat_at"] = now.isoformat()
        if p.get("prio", 3) <= 2:                 # p1/p2 入房即鎖定，不換人
            p["until"] = None
        else:
            d = p.get("duration") or 60          # 沒填 = 60
            if d > 60:
                d = 60
            p["until"] = (now + timedelta(minutes=max(10, d))).isoformat()
        room.append(p)
        dirty = True
    return dirty

def reconcile_room(r, now):
    dirty = False
    room, queue = r["room"], r["queue"]
    for p in room:                                  # 舊資料：p1/p2 補轉鎖定
        if p.get("prio", 3) <= 2 and p.get("until") is not None:
            p["until"] = None
            dirty = True
    for p in list(room):                            # 時間到：換人或延長
        until = p.get("until")
        if until is None:                           # 鎖定成員不換人
            continue
        if parse(until) <= now:
            if any(_eligible(q, now) for q in queue):
                room.remove(p)                      # 滿時間必須換人
            else:
                p["until"] = (now + timedelta(hours=1)).isoformat()  # 沒人排 → 延長1hr
                p["ext"] = p.get("ext", 0) + 1
            dirty = True
    dirty |= refill(r, now)
    if _transfer_owner(r):
        dirty = True
    if dirty:
        _touch(r, now)
    return dirty

def reconcile_all(state, now):
    dirty = False
    for rid in list(state["rooms"]):                # 8 小時沒人排隊也沒變化 → 自動刪房
        r = state["rooms"][rid]
        if reconcile_room(r, now):
            dirty = True
        act = r.get("active") or r.get("created")
        if not r["queue"] and act and now - parse(act) > ROOM_TTL:
            del state["rooms"][rid]
            dirty = True
    return dirty


# ---------- 頁面主流程 ----------
now = now_tw()
state = load_state()
dirty = reconcile_all(state, now)

ANNOUNCE = ("入房滿 1 小時換人；沒人排隊自動延長（不限次）｜最多提前 2 小時預約｜"
            "📌 修改持續時間只能縮短、冷卻 20 分｜📌 剩餘 10 分內且無人排隊可手動延長｜"
            "📌 一次只能排一間房")

rid = st.query_params.get("room")
if rid and rid not in state["rooms"]:               # 房間不存在（可能已被自動刪）
    del st.query_params["room"]
    rid = None

# ================================================================
# 房間列表頁
# ================================================================
if rid is None:
    st.title("🎮 Hololive dreams 組隊房間")
    st.caption(f"房間 {len(state['rooms'])}/{MAX_ROOMS} 間｜" + ANNOUNCE)

    st.subheader("🏠 房間列表")
    if not state["rooms"]:
        st.info("還沒有房間，開一間吧！")
    for rid2, r in state["rooms"].items():
        c1, c2 = st.columns([0.85, 0.15])
        c1.markdown(
            f"**{r['name']}**　開房：{r.get('owner') or '—'}　"
            f"👥 {len(r['room'])}/{ROOM_SIZE}　⏳ 排隊 {len(r['queue'])}　"
            f"💬 {len(r.get('messages', []))}"
        )
        if c2.button("進入", key=f"go_{rid2}", use_container_width=True):
            st.query_params["room"] = rid2
            st.rerun()

    st.subheader("＋ 開新房間（固定 5 人制）")
    with st.form("new_room", border=True):
        new_name = st.text_input("房間名稱")
        new_owner = st.text_input("開房者（你的巴哈或遊戲ID，僅顯示用）")
        if st.form_submit_button("開房 🏠", type="primary", use_container_width=True):
            if not new_name.strip() or not new_owner.strip():
                st.error("房名和開房者 ID 都要填")
            elif len(state["rooms"]) >= MAX_ROOMS:
                st.error(f"房間已達上限 {MAX_ROOMS} 間（沒人排隊的房 8 小時會自動刪）")
            else:
                nid = "r_" + secrets.token_hex(3)
                ts = now.isoformat()
                state["rooms"][nid] = {
                    "name": new_name.strip(), "owner": new_owner.strip(),
                    "room": [], "queue": [], "messages": [],
                    "active": ts, "created": ts,
                }
                if save_state(state):
                    st.query_params["room"] = nid
                    st.rerun()

    with st.sidebar:
        st.caption("先進入一間房間，或自己開一間。")

# ================================================================
# 房間頁（所有功能都綁在這間）
# ================================================================
else:
    r = state["rooms"][rid]
    room, queue = r["room"], r["queue"]
    msgs = r.setdefault("messages", [])

    if st.button("⬅ 回房間列表", type="secondary"):
        st.query_params.clear()
        st.rerun()
    st.title(f"🎮 {r['name']}")
    st.caption(f"開房：{r.get('owner') or '—'}｜房間 {len(room)}/{ROOM_SIZE}｜" + ANNOUNCE)

    st.subheader(f"🛋️ 目前房間成員（{len(room)}/{ROOM_SIZE}）")
    rows = []
    for i in range(ROOM_SIZE):
        if i < len(room):
            p = room[i]
            locked = p.get("until") is None
            rows.append({
                "座位": i + 1, "巴哈ID": p["baha_id"] or "—", "遊戲ID": p["game_id"] or "—",
                "入座": fmt(p["sat_at"]),
                "換人時間": "🔒 鎖定" if locked else fmt(p["until"]),
                "剩餘(分)": "—" if locked else int((parse(p["until"]) - now).total_seconds() // 60),
                "延長次數": "—" if locked else p.get("ext", 0),
            })
        else:
            rows.append({"座位": i + 1, "巴哈ID": "（空位）", "遊戲ID": "—",
                         "入座": "—", "換人時間": "—", "剩餘(分)": "—", "延長次數": "—"})
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.subheader(f"⏳ 排隊（{len(queue)} 人）")
    if queue:
        qrows = [{
            "順位": i + 1, "巴哈ID": p["baha_id"] or "—", "遊戲ID": p["game_id"] or "—",
            "隊伍分數": p.get("score") if p.get("score") is not None else "—",
            "火消耗": p.get("fire") if p.get("fire") is not None else "—",
            "希望開始": fmt(p.get("start_pref")),
            "持續(分)": p.get("duration") if p.get("duration") is not None else "—", "註冊時間": fmt(p["reg_at"]),
        } for i, p in enumerate(sorted(queue, key=_qkey))]
        st.dataframe(qrows, use_container_width=True, hide_index=True)
    else:
        st.info("目前沒有人排隊")

    # ---------- 留言板 ----------
    my_id = (st.session_state.get("sb_baha") or st.session_state.get("sb_game") or "").strip()

    st.subheader(f"💬 留言板（{len(msgs)} 則）") if msgs else st.subheader("💬 留言板")
    if not msgs:
        st.caption("還沒有留言")

    for m in reversed(msgs):
        tag = f"　↩ 回覆 #{m['reply_to']}" if m.get("reply_to") else ""
        c1, c2 = st.columns([0.92, 0.08])
        c1.markdown(f"**#{m['no']}　{m['name']}**{tag}　—　{fmt(m['ts'])}  \n{m['text']}")
        if c2.button("↩", key=f"reply_{m['no']}", help=f"回覆 #{m['no']}"):
            st.session_state["reply_to"] = m["no"]     # 點選回覆，像 YouTube
            st.rerun()

    reply_to = st.session_state.get("reply_to", 0)
    if reply_to and any(x["no"] == reply_to for x in msgs):
        rc1, rc2 = st.columns([0.6, 0.4])
        rc1.caption(f"↩ 正在回覆 #{reply_to}")
        if rc2.button("❌ 取消回覆", key="cancel_reply"):
            st.session_state["reply_to"] = 0
            st.rerun()
    elif reply_to:
        st.session_state["reply_to"] = 0

    label = f"留言內容（以「{my_id}」名義，上限 500 字）" if my_id else "留言內容（上限 500 字）"
    with st.form("msg_form", border=True):
        m_text = st.text_area(label, max_chars=500)
        if st.form_submit_button("留言 💬", type="primary", use_container_width=True):
            if not my_id:
                st.error("請先在左側填 巴哈ID 或 遊戲ID")
            elif not m_text.strip():
                st.error("內容要填")
            else:
                msgs.append({
                    "no": msgs[-1]["no"] + 1 if msgs else 1,
                    "name": my_id,                     # 名義直接用左側 ID
                    "reply_to": reply_to or None,
                    "text": m_text.strip(),
                    "ts": now.isoformat(),
                })
                del msgs[:len(msgs) - 100]          # 最多保留 100 則
                st.session_state["reply_to"] = 0
                dirty = True
                _touch(r, now)
                st.toast("已留言！")

    # ---------- 側邊欄：排隊表單 / 退出 / 修改 / 管理 ----------
    with st.sidebar:
        baha = st.text_input("巴哈ID", key="sb_baha")
        game = st.text_input("遊戲ID", key="sb_game")
        st.caption("排隊與留言板共用這兩個 ID")

        st.header("✍️ 加入排隊")
        when = st.selectbox("希望開始時間", ["現在馬上排", "指定時間（最多提前 2 小時）"])
        with st.form("join_form", border=True):
            pw = st.text_input("4位密碼（退出時必須相同）", max_chars=4, type="password")
            st.caption("一般玩家所有欄位都要填（沒填會跳警告）；特別名單只需 ID＋密碼")
            score = st.number_input("隊伍分數", min_value=0, value=0)
            fire = st.number_input("火消耗", min_value=0, value=0)
            pref_t = st.time_input("指定時間", value=None, disabled=(when == "現在馬上排"))
            dur = st.number_input("持續時間（分鐘，可不填；一般玩家上限 60）",
                                  min_value=10, value=None, step=5, placeholder="60")
            ok = st.form_submit_button("排隊 🎮", type="primary", use_container_width=True)

        if ok:
            baha, game = baha.strip(), game.strip()
            if not baha and not game:
                st.error("至少要填一個 ID")
            elif baha.casefold() == ADMIN_ID or game.casefold() == ADMIN_ID:
                st.session_state["admin"] = True
                st.toast("管理模式已開啟")
                st.rerun()
            elif len(pw) != 4:
                st.error("密碼請設剛好 4 位")
            else:
                loc_rid, other = _locate_all_rooms(state, baha, game)
                if other is not None and loc_rid == rid:
                    st.error("你已經在這間房的房間或排隊中，不要重複排")
                elif other is not None:
                    st.error(f"你已經在「{other['name']}」了，一次只能排一間（先退出再來）")
                else:
                    prio = resolve_prio(baha, game)
                    missing = []
                    if prio >= 3:                        # 一般玩家：所有欄位必填
                        if not baha:
                            missing.append("巴哈ID")
                        if not game:
                            missing.append("遊戲ID")
                        if not score:
                            missing.append("隊伍分數")
                        if not fire:
                            missing.append("火消耗")
                        if when != "現在馬上排" and pref_t is None:
                            missing.append("指定時間")
                        if dur is None:
                            missing.append("持續時間")
                    if missing:
                        st.error("欄位沒填完：" + "、".join(missing))
                    else:
                        start_pref = None
                        if when != "現在馬上排" and pref_t is not None:
                            cand = now.replace(hour=pref_t.hour, minute=pref_t.minute,
                                               second=0, microsecond=0)
                            if cand < now:
                                cand += timedelta(days=1)
                            if prio >= 3 and cand > now + MAX_AHEAD:
                                st.error("最多只能提前 2 小時預約！")
                                st.stop()
                            start_pref = cand.isoformat()
                        duration = dur
                        if duration is not None and prio >= 3 and duration > 60:
                            st.error("一般玩家持續時間上限 60 分鐘！")
                            st.stop()
                        queue.append({
                            "baha_id": baha, "game_id": game, "prio": prio,
                            "score": score or None,       # 0 = 沒填 → 不顯示
                            "fire": fire or None,
                            "pw_hash": _sha(pw),
                            "start_pref": start_pref,
                            "duration": duration,
                            "reg_at": now.isoformat(),
                        })
                        queue.sort(key=_qkey)
                        dirty = True
                        _touch(r, now)
                        st.toast("已加入排隊！")

        st.markdown("---")
        st.header("🚪 退出")
        xid = st.text_input("輸入你的巴哈ID或遊戲ID", key="exit_id")
        xpw = st.text_input("你的4位密碼", max_chars=4, type="password", key="exit_pw")
        if st.button("退出房間 / 排隊", use_container_width=True):
            is_admin = st.session_state.get("admin", False)
            if xid.strip().casefold() == ADMIN_ID:
                st.session_state["admin"] = True
                st.rerun()
            elif _find(room, xid) is None and _find(queue, xid) is None:
                st.error("你不在這間房（房內和排隊都找不到這個 ID）")
            else:
                i = _find(room, xid)
                target = room[i] if i is not None else queue[_find(queue, xid)]
                if _pw_ok(target, xpw, is_admin):
                    st.session_state["exit_pending"] = xid.strip()
                    st.rerun()
                else:
                    st.error("密碼不符合，無法退出")

        # ---------- 修改 / 延長 ----------
        st.markdown("---")
        st.header("✏️ 修改 / 延長")
        mid = st.text_input("輸入你的巴哈ID或遊戲ID", key="mod_id")
        mpw = st.text_input("你的4位密碼", max_chars=4, type="password", key="mod_pw")

        mi = _find(room, mid)
        m_src, m_target = ("room", room[mi]) if mi is not None else (None, None)
        if m_target is None:
            mj = _find(queue, mid)
            if mj is not None:
                m_src, m_target = "queue", queue[mj]

        if mid.strip():
            if m_target is None:
                st.caption("你在這間房找不到（可能排在別間？）")
            elif m_src == "room" and m_target.get("until") is None:
                st.caption("🔒 鎖定成員，沒有持續時間")
            elif m_src == "room":
                rem = int((parse(m_target["until"]) - now).total_seconds() // 60)
                st.caption(f"已在房間，剩餘 {rem} 分鐘｜排隊 {len(queue)} 人")
            else:
                st.caption(f"已在排隊，持續 {m_target.get('duration') or 60} 分鐘")

        ndur = st.number_input("縮短後的持續時間（分鐘）", min_value=10, value=None, key="mod_dur")
        if st.button("修改（只能縮短，冷卻 20 分）", key="mod_go", use_container_width=True):
            is_admin = st.session_state.get("admin", False)
            if m_target is None:
                st.error("找不到這個 ID")
            elif not _pw_ok(m_target, mpw, is_admin):
                st.error("密碼不符合")
            else:
                le = m_target.get("last_edit")
                if le and now - parse(le) < timedelta(minutes=20):
                    wait = 20 - int((now - parse(le)).total_seconds() // 60)
                    st.error(f"修改冷卻中，請 {wait} 分鐘後再試")
                elif ndur is None:
                    st.error("請填要縮短到的分鐘數")
                elif m_src == "room":
                    if m_target.get("until") is None:
                        st.error("🔒 鎖定成員沒有持續時間")
                    elif now + timedelta(minutes=ndur) >= parse(m_target["until"]):
                        st.error("只能縮短：要比目前剩餘時間更短")
                    else:
                        m_target["until"] = (now + timedelta(minutes=ndur)).isoformat()
                        m_target["last_edit"] = now.isoformat()
                        dirty = True
                        _touch(r, now)
                        st.toast("已縮短剩餘時間")
                        if save_state(state):
                            st.rerun()
                else:
                    if ndur >= (m_target.get("duration") or 60):
                        st.error("只能縮短：要比目前的持續時間更短")
                    else:
                        m_target["duration"] = ndur
                        m_target["last_edit"] = now.isoformat()
                        dirty = True
                        _touch(r, now)
                        st.toast("已縮短持續時間")
                        if save_state(state):
                            st.rerun()

        if st.button("延長 1 小時（剩餘 10 分內且無人排隊）", key="ext_go", use_container_width=True):
            is_admin = st.session_state.get("admin", False)
            if m_target is None:
                st.error("找不到這個 ID")
            elif not _pw_ok(m_target, mpw, is_admin):
                st.error("密碼不符合")
            elif m_src != "room" or m_target.get("until") is None:
                st.error("只有在房間、會換人的成員能延長")
            else:
                rem = (parse(m_target["until"]) - now).total_seconds() / 60
                if rem > 10:
                    st.error(f"要剩餘 10 分鐘內才能延長（現在剩 {int(rem)} 分）")
                elif len(queue) > 0:
                    st.error("現在有人排隊，不能延長")
                else:
                    m_target["until"] = (now + timedelta(hours=1)).isoformat()
                    m_target["ext"] = m_target.get("ext", 0) + 1
                    dirty = True
                    _touch(r, now)
                    st.toast("已延長 1 小時")
                    if save_state(state):
                        st.rerun()

        if "exit_pending" in st.session_state:
            t = st.session_state["exit_pending"]
            in_room = _find(room, t) is not None
            st.warning(f"確定要把「{t}」移出{'房間（立刻遞補下一位）' if in_room else '排隊'}嗎？")
            c1, c2 = st.columns(2)
            if c1.button("確定退出", type="primary"):
                i = _find(room, t)
                if i is not None:
                    room.pop(i)
                    dirty = True
                    dirty |= refill(r, now)
                else:
                    j = _find(queue, t)
                    if j is not None:
                        queue.pop(j)
                        dirty = True
                if _transfer_owner(r):
                    dirty = True
                del st.session_state["exit_pending"]
                st.toast("已退出")
                _touch(r, now)
                if save_state(state):        # 先存檔再重整，否則改動會丟掉
                    st.rerun()
            if c2.button("取消"):
                del st.session_state["exit_pending"]
                st.rerun()

        # ---------- 房主改名 ----------
        st.markdown("---")
        st.header("🏷 改房名（限房主）")
        rn_name = st.text_input("新的房間名稱", key="rn_name")
        rn_id = st.text_input("房主ID", key="rn_id")
        rn_pw = st.text_input("房主的4位密碼", max_chars=4, type="password", key="rn_pw")
        if st.button("修改房名", key="rn_go", use_container_width=True):
            is_admin = st.session_state.get("admin", False)
            owner_rec = None
            for lst in (room, queue):
                k = _find(lst, rn_id)
                if k is not None:
                    owner_rec = lst[k]
                    break
            is_owner = rn_id.strip().casefold() == (r.get("owner") or "").casefold()
            if not rn_name.strip():
                st.error("新房名要填")
            elif not (is_owner or is_admin):
                st.error("你不是這間房的房主")
            elif rn_name.strip() == r["name"]:
                st.error("跟原本的房名一樣，不用改")
            elif owner_rec is None:
                st.error("找不到你的排隊紀錄（房主要在房內或排隊中，用排隊時的密碼驗證）")
            elif not _pw_ok(owner_rec, rn_pw, is_admin):
                st.error("密碼不符合（要用排隊時設定的 4 位密碼）")
            else:
                r["name"] = rn_name.strip()
                dirty = True
                _touch(r, now)
                st.toast("房名已修改")
                if save_state(state):
                    st.rerun()

        # ---------- 後門管理面板 ----------
        if st.session_state.get("admin"):
            st.markdown("---")
            st.header("⚙️ 管理面板")
            if st.button("關閉管理模式"):
                del st.session_state["admin"]
                st.rerun()

            t = st.text_input("刪除指定玩家（任一 ID，全房間搜尋）", key="adm_target")
            if st.button("刪除該玩家", key="adm_del"):
                if not t.strip():
                    st.error("請輸入 ID")
                elif st.session_state.get("adm_conf") != t:
                    st.session_state["adm_conf"] = t
                st.rerun()
            if st.session_state.get("adm_conf"):
                ct = st.session_state["adm_conf"]
                st.warning(f"確定刪除「{ct}」？")
                c1, c2 = st.columns(2)
                if c1.button("確定刪除", key="adm_del_yes", type="primary"):
                    for rid2, r2 in state["rooms"].items():
                        for lst in (r2["room"], r2["queue"]):
                            while _find(lst, ct) is not None:
                                lst.pop(_find(lst, ct))
                        if _find(r2["room"], ct) is None:
                            dirty |= refill(r2, now)
                        if _transfer_owner(r2):
                            dirty = True
                    del st.session_state["adm_conf"]
                    st.toast("已刪除")
                    if save_state(state):
                        st.rerun()
                if c2.button("取消", key="adm_del_no"):
                    del st.session_state["adm_conf"]
                    st.rerun()

            for label, key in (("🧹 清空此房成員", "room"), ("🧹 清空此房排隊", "queue"),
                               ("🧹 清空此房留言", "messages")):
                if st.button(label, key=f"clr_{key}"):
                    st.session_state[f"clr_pending_{key}"] = True
                    st.rerun()
                if st.session_state.get(f"clr_pending_{key}"):
                    st.warning(f"確定要{label[1:]}？（不可復原）")
                    c1, c2 = st.columns(2)
                    if c1.button("確定清空", key=f"clr_{key}_yes", type="primary"):
                        r[key].clear()
                        if key == "room":
                            dirty |= refill(r, now)
                            _transfer_owner(r)
                        dirty = True
                        _touch(r, now)
                        del st.session_state[f"clr_pending_{key}"]
                        st.toast("已清空")
                        if save_state(state):
                            st.rerun()
                    if c2.button("取消", key=f"clr_{key}_no"):
                        del st.session_state[f"clr_pending_{key}"]
                        st.rerun()

            if st.button("🗑 刪除這個房間"):
                st.session_state["del_room_pending"] = True
                st.rerun()
            if st.session_state.get("del_room_pending"):
                st.warning("確定刪除整個房間？（成員、排隊、留言全部消失，不可復原）")
                c1, c2 = st.columns(2)
                if c1.button("確定刪除房間", key="del_room_yes", type="primary"):
                    del state["rooms"][rid]
                    del st.session_state["del_room_pending"]
                    if save_state(state):
                        st.query_params.clear()
                        st.rerun()
                if c2.button("取消", key="del_room_no"):
                    del st.session_state["del_room_pending"]
                    st.rerun()

# ---------- 結算後存回 ----------
if dirty:
    if save_state(state):
        st.rerun()
