# -*- coding: utf-8 -*-
"""組隊房間：5人房 + 排隊，狀態存 GitHub repo JSON"""
import base64
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
import streamlit as st

TZ = ZoneInfo("Asia/Taipei")
ROOM_SIZE = 5
MAX_AHEAD = timedelta(hours=2)          # 最多提前 2 小時預約
ADMIN_ID = "fantastic1936"

# (巴哈ID, 遊戲ID, priority)，命中任一即套用
PRIORITY_IDS = [
    ("小狼", "こはね", 1),
    ("夜久", "Ten Tender", 2),
]

st.set_page_config(page_title="組隊房間", page_icon="🎮", layout="wide")


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

def load_state():
    c = _gh()
    _sha, raw = _gh_get(c["token"], c["url"], c["branch"])
    if raw is None:
        return {"room": [], "queue": []}
    try:
        state = json.loads(raw)
    except Exception:
        st.error("room_state.json 內容損毀，請到 GitHub 手動檢查")
        st.stop()
    state.setdefault("room", [])
    state.setdefault("queue", [])
    return state

def save_state(state):
    c = _gh()
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

def _id_exists(state, baha, game):
    for x in (baha, game):
        if (x or "").strip() and (_find(state["room"], x) is not None
                                 or _find(state["queue"], x) is not None):
            return x
    return None

def refill(state, now):
    """空位 → 依排序遞補第一個時間到的排隊者"""
    room, queue, dirty = state["room"], state["queue"], False
    while len(room) < ROOM_SIZE and queue:
        idx = next((i for i, q in enumerate(queue) if _eligible(q, now)), None)
        if idx is None:
            break
        p = queue.pop(idx)
        p["sat_at"] = now.isoformat()
        p["until"] = (now + timedelta(minutes=max(10, min(p.get("duration") or 60, 60)))).isoformat()
        room.append(p)
        dirty = True
    return dirty

def reconcile(state, now):
    dirty = False
    room, queue = state["room"], state["queue"]
    for p in list(room):                      # 時間到：換人或延長
        if parse(p["until"]) <= now:
            if any(_eligible(q, now) for q in queue):
                room.remove(p)                # 滿時間必須換人
            else:
                p["until"] = (now + timedelta(hours=1)).isoformat()  # 沒人排 → 延長1hr
                p["ext"] = p.get("ext", 0) + 1
            dirty = True
    return refill(state, now) or dirty


# ---------- 頁面 ----------
now = now_tw()
state = load_state()
dirty = reconcile(state, now)

st.title("🎮 組隊房間")
st.caption("房間 5 人制｜入房滿 1 小時換人；沒人排隊自動延長（不限次）｜"
           "最多提前 2 小時預約｜priority：小狼/こはね > 夜久/Ten Tender > 其他人")

room, queue = state["room"], state["queue"]

st.subheader(f"🛋️ 目前房間成員（{len(room)}/{ROOM_SIZE}）")
rows = []
for i in range(ROOM_SIZE):
    if i < len(room):
        p = room[i]
        remain = int((parse(p["until"]) - now).total_seconds() // 60)
        rows.append({
            "座位": i + 1, "巴哈ID": p["baha_id"] or "—", "遊戲ID": p["game_id"] or "—",
            "P": f"p{p['prio']}", "入座": fmt(p["sat_at"]),
            "換人時間": fmt(p["until"]), "剩餘(分)": remain,
            "延長次數": p.get("ext", 0),
        })
    else:
        rows.append({"座位": i + 1, "巴哈ID": "（空位）", "遊戲ID": "—", "P": "—",
                     "入座": "—", "換人時間": "—", "剩餘(分)": "—", "延長次數": "—"})
st.dataframe(rows, use_container_width=True, hide_index=True)

st.subheader(f"⏳ 排隊（{len(queue)} 人）")
if queue:
    qrows = [{
        "順位": i + 1, "巴哈ID": p["baha_id"] or "—", "遊戲ID": p["game_id"] or "—",
        "P": f"p{p['prio']}", "隊伍分數": p.get("score") if p.get("score") is not None else "—",
        "火消耗": p.get("fire") if p.get("fire") is not None else "—",
        "希望開始": fmt(p.get("start_pref")),
        "持續(分)": p.get("duration", "—"), "註冊時間": fmt(p["reg_at"]),
    } for i, p in enumerate(sorted(queue, key=_qkey))]
    st.dataframe(qrows, use_container_width=True, hide_index=True)
else:
    st.info("目前沒有人排隊")

# ---------- 側邊欄：排隊表單 / 退出 / 管理 ----------
with st.sidebar:
    st.header("✍️ 加入排隊")
    with st.form("join_form", border=True):
        baha = st.text_input("巴哈ID（必填其一）")
        game = st.text_input("遊戲ID（必填其一）")
        st.caption("p1/p2（小狼、夜久）後面幾項可任意填，填 0 / 不選 = 不顯示")
        score = st.number_input("隊伍分數", min_value=0, value=0)
        fire = st.number_input("火消耗", min_value=0, value=0)
        when = st.selectbox("希望開始時間", ["現在馬上排", "指定時間（最多提前 2 小時）"])
        pref_t = st.time_input("指定時間", value=None, disabled=(when == "現在馬上排"))
        dur = st.number_input("持續時間（分鐘，上限 60）",
                              min_value=10, max_value=60, value=30, step=5)
        ok = st.form_submit_button("排隊 🎮", type="primary", use_container_width=True)

    if ok:
        baha, game = baha.strip(), game.strip()
        if not baha and not game:
            st.error("至少要填一個 ID")
        elif baha.casefold() == ADMIN_ID or game.casefold() == ADMIN_ID:
            st.session_state["admin"] = True
            st.toast("管理模式已開啟")
            st.rerun()
        else:
            dup = _id_exists(state, baha, game)
            if dup:
                st.error(f"「{dup}」已經在房間或排隊中，不要重複排")
            else:
                prio = resolve_prio(baha, game)
                start_pref = None
                if when != "現在馬上排":
                    if pref_t is None:
                        st.error("請選擇指定時間")
                        st.stop()
                    cand = now.replace(hour=pref_t.hour, minute=pref_t.minute,
                                       second=0, microsecond=0)
                    if cand < now:
                        cand += timedelta(days=1)
                    if cand > now + MAX_AHEAD:
                        st.error("最多只能提前 2 小時預約！")
                        st.stop()
                    start_pref = cand.isoformat()
                queue.append({
                    "baha_id": baha, "game_id": game, "prio": prio,
                    "score": score or None,       # 0 = 沒填 → 不顯示
                    "fire": fire or None,
                    "start_pref": start_pref,
                    "duration": dur,
                    "reg_at": now.isoformat(),
                })
                queue.sort(key=_qkey)
                dirty = True
                st.toast("已加入排隊！")

    st.markdown("---")
    st.header("🚪 退出")
    xid = st.text_input("輸入你的巴哈ID或遊戲ID", key="exit_id")
    if st.button("退出房間 / 排隊", use_container_width=True):
        if xid.strip().casefold() == ADMIN_ID:
            st.session_state["admin"] = True
            st.rerun()
        elif _find(room, xid) is None and _find(queue, xid) is None:
            st.error("找不到這個 ID")
        else:
            st.session_state["exit_pending"] = xid.strip()
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
                dirty |= refill(state, now)
            else:
                j = _find(queue, t)
                if j is not None:
                    queue.pop(j)
                    dirty = True
            del st.session_state["exit_pending"]
            st.toast("已退出")
            if save_state(state):        # 先存檔再重整，否則改動會丟掉
                st.rerun()
        if c2.button("取消"):
            del st.session_state["exit_pending"]
            st.rerun()

    # ---------- 後門管理面板 ----------
    if st.session_state.get("admin"):
        st.markdown("---")
        st.header("⚙️ 管理面板")
        if st.button("關閉管理模式"):
            del st.session_state["admin"]
            st.rerun()

        t = st.text_input("刪除指定玩家（任一 ID）", key="adm_target")
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
                for lst in (room, queue):
                    while _find(lst, ct) is not None:
                        lst.pop(_find(lst, ct))
                if _find(room, ct) is None:
                    dirty |= refill(state, now)
                dirty = True
                del st.session_state["adm_conf"]
                st.toast("已刪除")
                if save_state(state):    # 先存檔再重整，否則改動會丟掉
                    st.rerun()
            if c2.button("取消", key="adm_del_no"):
                del st.session_state["adm_conf"]
                st.rerun()

        for label, part in (("🧹 清空房間", "room"), ("🧹 清空排隊", "queue")):
            if st.button(label, key=f"clr_{part}"):
                st.session_state[f"clr_pending_{part}"] = True
                st.rerun()
            if st.session_state.get(f"clr_pending_{part}"):
                st.warning(f"確定要{label[1:]}？（不可復原）")
                c1, c2 = st.columns(2)
                if c1.button("確定清空", key=f"clr_{part}_yes", type="primary"):
                    state[part].clear()
                    if part == "room":
                        dirty |= refill(state, now)
                    dirty = True
                    del st.session_state[f"clr_pending_{part}"]
                    st.toast("已清空")
                    if save_state(state):    # 先存檔再重整，否則改動會丟掉
                        st.rerun()
                if c2.button("取消", key=f"clr_{part}_no"):
                    del st.session_state[f"clr_pending_{part}"]
                    st.rerun()

# ---------- 結算後存回 ----------
if dirty:
    if save_state(state):
        st.rerun()
