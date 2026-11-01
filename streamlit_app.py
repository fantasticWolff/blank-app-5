# -*- coding: utf-8 -*-
"""HoloDreams 組隊房間：多房間 + 暫時登入制 + 四語切換，狀態存 GitHub repo JSON"""
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

# ---------------- 多語系 ----------------
LANG_NAMES = {"zh": "中文", "ja": "日本語", "en": "English", "id": "Bahasa Indonesia"}

T = {
"zh": {
    "title_suffix": "組隊房間",
    "login_sub": "🚄 暫時登入",
    "login_cap": "填一次就好，這個瀏覽器關掉或登出就要重填。密碼＝你排隊時設定的 4 位數。",
    "login_btn": "登入 🚄",
    "err_need_id": "至少要填一個 ID",
    "err_pw_len": "密碼要剛好 4 位",
    "err_pw_mismatch": "密碼跟上次排隊設定的不符，請再確認",
    "welcome_prefix": "歡迎 ",
    "admin_on": "管理模式已開啟",
    "sb_logged": "🚄 已登入：{x}",
    "logout": "登出",
    "sb_admin_only": "管理模式（未登入玩家身分）",
    "lang_label": "🌐 語言",
    "announce": "入房滿 1 小時換人；沒人排隊自動延長（不限次）｜最多提前 2 小時預約｜"
                "📌 修改持續時間只能縮短、冷卻 20 分｜📌 剩餘 10 分內且無人排隊可手動延長｜"
                "📌 一次只能排一間房｜車掌＝開房者：固定第 1 位、可改房名與移除車廂成員",
    "rooms_caption": "房間 {n}/{cap} 間｜",
    "new_room_h": "🚃 車掌：開新房間（固定 5 人制）",
    "new_room_cap": "開房後你就是車掌：自動坐第 1 位、鎖定不換人",
    "f_room_name": "房間名稱",
    "open_room_btn": "開房（我是車掌 🚃）",
    "err_room_name": "房名要填",
    "err_room_cap": "房間已達上限 20 間（沒人排隊的房 8 小時會自動刪）",
    "err_in_room_already": "你已經在其他房間或排隊中，先退出才能開新房",
    "join_sec": "🎫 乘客：進入現有房間",
    "no_rooms": "還沒有房間，當車掌開一間吧！",
    "enter": "進入",
    "del_room_btn": "🗑 刪房",
    "confirm_del_room": "確定刪除房間「{name}」？（成員、排隊、留言全刪，不可復原）",
    "sure_del": "確定刪除",
    "cancel": "取消",
    "room_deleted": "房間已刪除",
    "room_card": "**{name}**　車掌：{owner}　👥 {n}/{cap}　⏳ 排隊 {q}　💬 {m}",
    "back_list": "⬅ 回房間列表",
    "room_cap": "車掌：{owner}｜房間 {n}/{cap}｜",
    "members_h": "🛋️ 目前車廂成員（{n}/{cap}）",
    "col_seat": "座位", "col_baha": "社群ID", "col_game": "遊戲ID",
    "f_pw": "4位密碼",
    "col_in": "入座", "col_swap": "換人時間", "col_left": "剩餘(分)",
    "col_ext": "延長次數", "col_pos": "順位", "col_fire": "火消耗",
    "col_start": "希望開始", "col_dur": "持續(分)",
    "empty_seat": "（空位）",
    "locked": "🔒 鎖定",
    "del_btn": "🗑 刪除",
    "seat_line": "座位 {n}：{x}（{y}）",
    "queued_line": "排隊：{x}（{y}）",
    "del_member_toast": "已刪除乘客",
    "queue_h": "⏳ 排隊（{n} 人）",
    "no_queue": "目前沒有人排隊",
    "board_h": "💬 留言板（{n} 則）", "board_h_empty": "💬 留言板",
    "no_msgs": "還沒有留言",
    "clear_msgs": "🧹 刪除全部留言",
    "confirm_clear_msgs": "確定刪除此房全部留言？（不可復原）",
    "msgs_cleared": "已刪除全部留言",
    "reply_tag": "　↩ 回覆 #",
    "replying": "↩ 正在回覆 #{n}",
    "cancel_reply": "❌ 取消回覆",
    "msg_label": "留言內容（以「{x}」名義，上限 500 字）",
    "msg_label_anon": "留言內容（上限 500 字）",
    "post_btn": "留言 💬",
    "err_text_required": "內容要填",
    "posted": "已留言！",
    "msg_deleted": "已刪除留言",
    "join_h": "✍️ 加入排隊",
    "join_as": "以「{x}」的身分排隊",
    "start_when": "希望開始時間",
    "now": "現在馬上排",
    "pick_time": "指定時間（最多提前 2 小時）",
    "f_time": "指定時間",
    "f_score": "隊伍分數", "f_fire": "火消耗",
    "f_dur": "持續時間（分鐘，可不填；一般玩家上限 60）",
    "join_form_cap": "特別名單（p1/p2）欄位可全留空；一般玩家所有欄位都要填",
    "queue_btn": "排隊 🎮",
    "err_dup_this": "你已經在這間房的房間或排隊中，不要重複排",
    "err_dup_other": "你已經在「{x}」了，一次只能排一間（先退出再來）",
    "err_missing": "欄位沒填完：{x}",
    "err_too_far": "最多只能提前 2 小時預約！",
    "err_dur_cap": "一般玩家持續時間上限 60 分鐘！",
    "joined": "已加入排隊！",
    "err_login_first": "請先登入",
    "err_login_queue": "請先登入再排隊",
    "exit_h": "🚪 退出",
    "exit_btn": "退出房間 / 排隊",
    "err_not_here": "你在這間房（房內和排隊）找不到這個 ID",
    "confirm_exit": "確定要把「{x}」移出{where}嗎？",
    "from_room": "房間（立刻遞補下一位）", "from_queue": "排隊",
    "exited": "已退出",
    "err_pw_fail": "密碼驗證失敗，無法退出",
    "mod_h": "✏️ 修改 / 延長",
    "mod_need_login": "登入後才能修改／延長",
    "mod_no_rec": "你在這間房還沒有紀錄（可能排在別間？）",
    "mod_locked": "🔒 鎖定成員，沒有持續時間",
    "mod_in_room": "已在車廂，剩餘 {n} 分鐘｜排隊 {q} 人",
    "mod_in_queue": "已在排隊，持續 {n} 分鐘",
    "f_new_dur": "縮短後的持續時間（分鐘）",
    "mod_btn": "修改（只能縮短，冷卻 20 分）",
    "ext_btn": "延長 1 小時（剩餘 10 分內且無人排隊）",
    "err_cd": "修改冷卻中，請 {n} 分鐘後再試",
    "err_fill_dur": "請填要縮短到的分鐘數",
    "err_shorter_only": "只能縮短：要比目前剩餘時間更短",
    "err_shorter_q": "只能縮短：要比目前的持續時間更短",
    "shortened": "已縮短剩餘時間", "shortened_q": "已縮短持續時間",
    "err_ext_where": "只有在車廂、會換人的成員能延長",
    "err_ext_time": "要剩餘 10 分鐘內才能延長（現在剩 {n} 分）",
    "err_ext_queue": "現在有人排隊，不能延長",
    "extended": "已延長 1 小時",
    "rename_btn": "✏️ 改房名",
    "rename_h": "🏷 修改房名（你是車掌）",
    "err_same_name": "跟原本的房名一樣，不用改",
    "renamed": "房名已修改",
    "save_btn": "儲存",
    "admin_h": "⚙️ 管理面板",
    "admin_exit": "🚪 退出管理模式（回登入頁）",
    "admin_hint": "沿用名字旁的 🗑 按鈕刪除：車廂成員／排隊者／留言；列表頁可刪整間房",
    "clear_members": "🧹 清空此房成員", "clear_queue": "🧹 清空此房排隊",
    "clear_messages": "🧹 清空此房留言",
    "confirm_clear": "確定要{x}？（不可復原）",
    "cleared": "已清空",
    "del_this_room": "🗑 刪除這個房間",
    "confirm_del_room2": "確定刪除整個房間？（成員、排隊、留言全部消失，不可復原）",
    "status_offline": "⚠️ 讀取房間資料失敗：{x}",
    "json_broken": "room_state.json 內容損毀，請到 GitHub 手動檢查",
    "no_secrets": "還沒設定 Secrets：github_token / repo",
    "save_fail": "GitHub 儲存失敗（可能同時有人操作），請再試一次",
    "save_fail2": "⚠️ 儲存失敗：{x}",
},
"ja": {
    "title_suffix": "チーム募集ルーム",
    "login_sub": "🚄 一時ログイン",
    "login_cap": "一度入力すればOK。ブラウザを閉じるかログアウトすると再入力が必要です。パスワード＝待機時に設定した4桁の数字。",
    "login_btn": "ログイン 🚄",
    "err_need_id": "IDを1つ以上入力してください",
    "err_pw_len": "パスワードは4桁にしてください",
    "err_pw_mismatch": "前回設定したパスワードと一致しません",
    "welcome_prefix": "ようこそ ",
    "admin_on": "管理モードを有効にしました",
    "sb_logged": "🚄 ログイン中：{x}",
    "logout": "ログアウト",
    "sb_admin_only": "管理モード（未ログイン）",
    "lang_label": "🌐 言語",
    "announce": "乗車は1時間で交代。待機者がいなければ自動延長（無制限）｜予約は2時間前まで｜"
                "📌 持続時間の変更は短縮のみ・CD20分｜📌 残り10分以内＆待機なしで手動延長可｜"
                "📌 同時に待機できるのは1ルームのみ｜車掌＝開設者：1番席固定、改名・乗客削除が可能",
    "rooms_caption": "ルーム {n}/{cap} 件｜",
    "new_room_h": "🚃 車掌：新規ルーム作成（5人固定）",
    "new_room_cap": "作成後あなたは車掌：自動的に1番席に着席、交代なし",
    "f_room_name": "ルーム名",
    "open_room_btn": "作成（私は車掌 🚃）",
    "err_room_name": "ルーム名を入力してください",
    "err_room_cap": "ルームは上限20件（待機者のいないルームは8時間で自動削除）",
    "err_in_room_already": "他のルームに参加・待機中です。先に退出してください",
    "join_sec": "🎫 乗客：既存ルームに入る",
    "no_rooms": "まだルームがありません。車掌として開きましょう！",
    "enter": "入る",
    "del_room_btn": "🗑 削除",
    "confirm_del_room": "ルーム「{name}」を削除？（メンバー・待機・コメントも全て消え、元に戻せません）",
    "sure_del": "削除する",
    "cancel": "キャンセル",
    "room_deleted": "ルームを削除しました",
    "room_card": "**{name}**　車掌：{owner}　👥 {n}/{cap}　⏳ 待機 {q}　💬 {m}",
    "back_list": "⬅ ルーム一覧へ",
    "room_cap": "車掌：{owner}｜ルーム {n}/{cap}｜",
    "members_h": "🛋️ 現在の乗客（{n}/{cap}）",
    "col_seat": "座席", "col_baha": "コミュニティID", "col_game": "ゲームID",
    "f_pw": "4桁パスワード",
    "col_in": "着席", "col_swap": "交代時間", "col_left": "残り(分)",
    "col_ext": "延長回数", "col_pos": "順番", "col_fire": "消費火",
    "col_start": "希望開始", "col_dur": "持続(分)",
    "empty_seat": "（空席）",
    "locked": "🔒 固定",
    "del_btn": "🗑 削除",
    "seat_line": "座席 {n}：{x}（{y}）",
    "queued_line": "待機：{x}（{y}）",
    "del_member_toast": "乗客を削除しました",
    "queue_h": "⏳ 待機（{n}人）",
    "no_queue": "待機者はいません",
    "board_h": "💬 掲示板（{n}件）", "board_h_empty": "💬 掲示板",
    "no_msgs": "まだコメントはありません",
    "clear_msgs": "🧹 全コメント削除",
    "confirm_clear_msgs": "このルームの全コメントを削除？（元に戻せません）",
    "msgs_cleared": "全コメントを削除しました",
    "reply_tag": "　↩ 返信 #",
    "replying": "↩ #{n} に返信中",
    "cancel_reply": "❌ 返信を取消",
    "msg_label": "コメント内容（「{x}」として、500字まで）",
    "msg_label_anon": "コメント内容（500字まで）",
    "post_btn": "コメントする 💬",
    "err_text_required": "内容を入力してください",
    "posted": "コメントしました！",
    "msg_deleted": "コメントを削除しました",
    "join_h": "✍️ 待機に並ぶ",
    "join_as": "「{x}」として待機に並む",
    "start_when": "希望開始時刻",
    "now": "今すぐ",
    "pick_time": "指定時刻（2時間前まで）",
    "f_time": "指定時刻",
    "f_score": "チームスコア", "f_fire": "消費火",
    "f_dur": "持続時間（分、未入力可・一般は60まで）",
    "join_form_cap": "特別リスト（p1/p2）は全て空欄でOK。一般は全項目必須",
    "queue_btn": "並ぶ 🎮",
    "err_dup_this": "このルームに既に参加・待機中です",
    "err_dup_other": "「{x}」に既にいます。1度に1ルームのみ（先に退出してください）",
    "err_missing": "未入力の項目：{x}",
    "err_too_far": "予約は2時間前までです！",
    "err_dur_cap": "一般は持続時間60分までです！",
    "joined": "待機に並びました！",
    "err_login_first": "先にログインしてください",
    "err_login_queue": "ログイン後に待機できます",
    "exit_h": "🚪 退出",
    "exit_btn": "参加・待機を退出",
    "err_not_here": "このルーム（乗車・待機）にあなたのIDがありません",
    "confirm_exit": "「{x}」を{where}から外しますか？",
    "from_room": "ルーム（次の人が補充されます）", "from_queue": "待機",
    "exited": "退出しました",
    "err_pw_fail": "パスワード認証に失敗しました",
    "mod_h": "✏️ 変更・延長",
    "mod_need_login": "ログイン後に変更・延長できます",
    "mod_no_rec": "このルームに記録がありません（他ルーム待機中？）",
    "mod_locked": "🔒 固定メンバー、持続時間なし",
    "mod_in_room": "乗車中、残り{n}分｜待機{q}人",
    "mod_in_queue": "待機中、持続{n}分",
    "f_new_dur": "短縮後の持続時間（分）",
    "mod_btn": "変更（短縮のみ、CD20分）",
    "ext_btn": "1時間延長（残り10分以内＆待機なし）",
    "err_cd": "変更のクールダウン中、あと{n}分",
    "err_fill_dur": "短縮後の分数を入力してください",
    "err_shorter_only": "短縮のみ：現在の残りより短く",
    "err_shorter_q": "短縮のみ：現在の持続より短く",
    "shortened": "残り時間を短縮しました", "shortened_q": "持続時間を短縮しました",
    "err_ext_where": "乗車中・交代制のメンバーのみ延長できます",
    "err_ext_time": "残り10分以内なら延長できます（現在{n}分）",
    "err_ext_queue": "待機者がいるため延長できません",
    "extended": "1時間延長しました",
    "rename_btn": "✏️ 名前変更",
    "rename_h": "🏷 ルーム名変更（車掌）",
    "err_same_name": "現在と同じ名前です",
    "renamed": "ルーム名を変更しました",
    "save_btn": "保存",
    "admin_h": "⚙️ 管理パネル",
    "admin_exit": "🚪 管理モードを終了（ログインへ）",
    "admin_hint": "名前横の🗑で削除：乗客・待機・コメント。一覧画面でルーム削除可",
    "clear_members": "🧹 乗客全消", "clear_queue": "🧹 待機全消",
    "clear_messages": "🧹 コメント全消",
    "confirm_clear": "{x}します？（元に戻せません）",
    "cleared": "消去しました",
    "del_this_room": "🗑 このルームを削除",
    "confirm_del_room2": "ルーム全体を削除？（全データが消え、元に戻せません）",
    "status_offline": "⚠️ ルームデータの読み取りに失敗：{x}",
    "json_broken": "room_state.json が壊れています。GitHub で確認してください",
    "no_secrets": "Secrets 未設定：github_token / repo",
    "save_fail": "GitHub 保存に失敗（同時操作の可能性）。もう一度お試しください",
    "save_fail2": "⚠️ 保存に失敗：{x}",
},
"en": {
    "title_suffix": "Team Room",
    "login_sub": "🚄 Temporary Login",
    "login_cap": "Enter once per session. Closing the browser or logging out clears it. Password = the 4 digits you set when queuing.",
    "login_btn": "Log in 🚄",
    "err_need_id": "Enter at least one ID",
    "err_pw_len": "Password must be exactly 4 digits",
    "err_pw_mismatch": "Password doesn't match the one you set when queuing",
    "welcome_prefix": "Welcome ",
    "admin_on": "Admin mode enabled",
    "sb_logged": "🚄 Logged in: {x}",
    "logout": "Log out",
    "sb_admin_only": "Admin mode (not logged in)",
    "lang_label": "🌐 Language",
    "announce": "Seats rotate every hour; auto-extends while nobody is queuing (unlimited) | Book up to 2 hours ahead | "
                "📌 Duration edits can only shorten (20-min cooldown) | 📌 Manual +1h extend when ≤10 min left and nobody queuing | "
                "📌 One room at a time | Conductor = creator: fixed seat #1, can rename & remove cabin members",
    "rooms_caption": "Rooms {n}/{cap} | ",
    "new_room_h": "🚃 Conductor: open a new room (5 seats fixed)",
    "new_room_cap": "After creating, you're the conductor: auto seat #1, no rotation",
    "f_room_name": "Room name",
    "open_room_btn": "Create (I'm the conductor 🚃)",
    "err_room_name": "Room name required",
    "err_room_cap": "Room limit reached (20; rooms with no queue auto-delete after 8h)",
    "err_in_room_already": "You're already in another room or queue — leave first to open a new one",
    "join_sec": "🎫 Passenger: join an existing room",
    "no_rooms": "No rooms yet — open one as the conductor!",
    "enter": "Enter",
    "del_room_btn": "🗑 Delete",
    "confirm_del_room": "Delete room \"{name}\"? (members, queue, messages all removed — irreversible)",
    "sure_del": "Delete",
    "cancel": "Cancel",
    "room_deleted": "Room deleted",
    "room_card": "**{name}**　Conductor: {owner}　👥 {n}/{cap}　⏳ queue {q}　💬 {m}",
    "back_list": "⬅ Back to rooms",
    "room_cap": "Conductor: {owner} | Room {n}/{cap} | ",
    "members_h": "🛋️ Current cabin members ({n}/{cap})",
    "col_seat": "Seat", "col_baha": "Community ID", "col_game": "Game ID",
    "f_pw": "4-digit password",
    "col_in": "Seated", "col_swap": "Swap at", "col_left": "Left (min)",
    "col_ext": "Extensions", "col_pos": "Pos", "col_fire": "Fire cost",
    "col_start": "Desired start", "col_dur": "Duration (min)",
    "empty_seat": "(empty)",
    "locked": "🔒 Locked",
    "del_btn": "🗑 Delete",
    "seat_line": "Seat {n}: {x} ({y})",
    "queued_line": "Queued: {x} ({y})",
    "del_member_toast": "Member removed",
    "queue_h": "⏳ Queue ({n})",
    "no_queue": "The queue is empty",
    "board_h": "💬 Message board ({n})", "board_h_empty": "💬 Message board",
    "no_msgs": "No messages yet",
    "clear_msgs": "🧹 Delete all messages",
    "confirm_clear_msgs": "Delete all messages in this room? (irreversible)",
    "msgs_cleared": "All messages deleted",
    "reply_tag": " ↩ reply #",
    "replying": "↩ Replying to #{n}",
    "cancel_reply": "❌ Cancel reply",
    "msg_label": "Message (as \"{x}\", max 500 chars)",
    "msg_label_anon": "Message (max 500 chars)",
    "post_btn": "Post 💬",
    "err_text_required": "Content required",
    "posted": "Posted!",
    "msg_deleted": "Message deleted",
    "join_h": "✍️ Join the queue",
    "join_as": "Queueing as \"{x}\"",
    "start_when": "Desired start time",
    "now": "Right now",
    "pick_time": "Pick a time (up to 2 hours ahead)",
    "f_time": "Pick time",
    "f_score": "Team score", "f_fire": "Fire cost",
    "f_dur": "Duration (minutes, optional; max 60 for regular players)",
    "join_form_cap": "Special-list players (p1/p2) may leave fields empty; regular players must fill all",
    "queue_btn": "Queue 🎮",
    "err_dup_this": "You're already in this room or its queue",
    "err_dup_other": "You're already in \"{x}\" — one room at a time (leave first)",
    "err_missing": "Missing fields: {x}",
    "err_too_far": "You can book at most 2 hours ahead!",
    "err_dur_cap": "Regular players: max 60 minutes!",
    "joined": "Queued!",
    "err_login_first": "Please log in first",
    "err_login_queue": "Log in to queue",
    "exit_h": "🚪 Leave",
    "exit_btn": "Leave room / queue",
    "err_not_here": "Your ID isn't in this room (cabin or queue)",
    "confirm_exit": "Remove \"{x}\" from the {where}?",
    "from_room": "cabin (next person fills in immediately)", "from_queue": "queue",
    "exited": "Left",
    "err_pw_fail": "Password verification failed",
    "mod_h": "✏️ Modify / Extend",
    "mod_need_login": "Log in to modify/extend",
    "mod_no_rec": "You have no record in this room (queued elsewhere?)",
    "mod_locked": "🔒 Locked member — no duration",
    "mod_in_room": "In cabin, {n} min left | {q} queued",
    "mod_in_queue": "Queued, duration {n} min",
    "f_new_dur": "New (shorter) duration (min)",
    "mod_btn": "Modify (shorten only, 20-min cooldown)",
    "ext_btn": "Extend 1 hour (≤10 min left & nobody queuing)",
    "err_cd": "Modification on cooldown, retry in {n} min",
    "err_fill_dur": "Enter the new duration",
    "err_shorter_only": "Shorten only: must be less than remaining time",
    "err_shorter_q": "Shorten only: less than the current duration",
    "shortened": "Remaining time shortened", "shortened_q": "Duration shortened",
    "err_ext_where": "Only cabin members with rotation can extend",
    "err_ext_time": "Extend when 10 min or less remain (now {n} min)",
    "err_ext_queue": "Someone is queuing — can't extend",
    "extended": "Extended by 1 hour",
    "rename_btn": "✏️ Rename",
    "rename_h": "🏷 Rename room (conductor)",
    "err_same_name": "Same as the current name",
    "renamed": "Room renamed",
    "save_btn": "Save",
    "admin_h": "⚙️ Admin panel",
    "admin_exit": "🚪 Exit admin mode (back to login)",
    "admin_hint": "Use the 🗑 buttons next to names to delete members/queued/messages; delete whole rooms on the rooms page",
    "clear_members": "🧹 Clear cabin members", "clear_queue": "🧹 Clear queue",
    "clear_messages": "🧹 Clear messages",
    "confirm_clear": "Confirm: {x}? (irreversible)",
    "cleared": "Cleared",
    "del_this_room": "🗑 Delete this room",
    "confirm_del_room2": "Delete the whole room? (members, queue, messages all removed — irreversible)",
    "status_offline": "⚠️ Failed to load room data: {x}",
    "json_broken": "room_state.json is corrupted — check it on GitHub",
    "no_secrets": "Secrets not set: github_token / repo",
    "save_fail": "GitHub save failed (possible concurrent edit) — try again",
    "save_fail2": "⚠️ Save failed: {x}",
},
"id": {
    "title_suffix": "Ruang Tim",
    "login_sub": "🚄 Login Sementara",
    "login_cap": "Cukup isi sekali. Menutup browser atau logout menghapusnya. Kata sandi = 4 digit yang kamu set saat mengantri.",
    "login_btn": "Masuk 🚄",
    "err_need_id": "Isi minimal satu ID",
    "err_pw_len": "Kata sandi harus tepat 4 digit",
    "err_pw_mismatch": "Kata sandi tidak cocok dengan yang sebelumnya",
    "welcome_prefix": "Selamat datang ",
    "admin_on": "Mode admin aktif",
    "sb_logged": "🚄 Masuk sebagai: {x}",
    "logout": "Keluar",
    "sb_admin_only": "Mode admin (belum login)",
    "lang_label": "🌐 Bahasa",
    "announce": "Kursi berganti tiap 1 jam; otomatis diperpanjang saat tidak ada antrean (tanpa batas) | Pesan maks 2 jam ke depan | "
                "📌 Perubahan durasi hanya boleh memperpendek (jeda 20 menit) | 📌 Perpanjang manual +1 jam saat sisa ≤10 menit & tidak ada antrean | "
                "📌 Satu ruangan saja dalam satu waktu | Kondektur = pembuat: kursi #1 tetap, bisa ganti nama & hapus penumpang",
    "rooms_caption": "Ruang {n}/{cap} | ",
    "new_room_h": "🚃 Kondektur: buka ruang baru (tetap 5 orang)",
    "new_room_cap": "Setelah membuat, kamu jadi kondektur: otomatis kursi #1, tanpa rotasi",
    "f_room_name": "Nama ruang",
    "open_room_btn": "Buat (Saya kondektur 🚃)",
    "err_room_name": "Nama ruang wajib diisi",
    "err_room_cap": "Ruang sudah maksimal 20 (ruang tanpa antrean otomatis terhapus setelah 8 jam)",
    "err_in_room_already": "Kamu sudah di ruang/antrean lain — keluar dulu untuk membuat baru",
    "join_sec": "🎫 Penumpang: masuk ruang yang ada",
    "no_rooms": "Belum ada ruang — buat sebagai kondektur!",
    "enter": "Masuk",
    "del_room_btn": "🗑 Hapus",
    "confirm_del_room": "Hapus ruang \"{name}\"? (anggota, antrean, pesan semuanya terhapus — permanen)",
    "sure_del": "Hapus",
    "cancel": "Batal",
    "room_deleted": "Ruang dihapus",
    "room_card": "**{name}**　Kondektur: {owner}　👥 {n}/{cap}　⏳ antre {q}　💬 {m}",
    "back_list": "⬅ Kembali ke daftar ruang",
    "room_cap": "Kondektur: {owner} | Ruang {n}/{cap} | ",
    "members_h": "🛋️ Penumpang saat ini ({n}/{cap})",
    "col_seat": "Kursi", "col_baha": "ID Komunitas", "col_game": "ID game",
    "f_pw": "Kata sandi 4 digit",
    "col_in": "Duduk sejak", "col_swap": "Ganti pada", "col_left": "Sisa (mnt)",
    "col_ext": "Perpanjangan", "col_pos": "Urutan", "col_fire": "Konsumsi api",
    "col_start": "Mulai diinginkan", "col_dur": "Durasi (mnt)",
    "empty_seat": "(kosong)",
    "locked": "🔒 Terkunci",
    "del_btn": "🗑 Hapus",
    "seat_line": "Kursi {n}: {x} ({y})",
    "queued_line": "Antre: {x} ({y})",
    "del_member_toast": "Penumpang dihapus",
    "queue_h": "⏳ Antrean ({n})",
    "no_queue": "Antrean kosong",
    "board_h": "💬 Papan pesan ({n})", "board_h_empty": "💬 Papan pesan",
    "no_msgs": "Belum ada pesan",
    "clear_msgs": "🧹 Hapus semua pesan",
    "confirm_clear_msgs": "Hapus semua pesan di ruangan ini? (permanen)",
    "msgs_cleared": "Semua pesan dihapus",
    "reply_tag": " ↩ balas #",
    "replying": "↩ Membalas #{n}",
    "cancel_reply": "❌ Batal balas",
    "msg_label": "Isi pesan (atas nama \"{x}\", maks 500)",
    "msg_label_anon": "Isi pesan (maks 500)",
    "post_btn": "Kirim 💬",
    "err_text_required": "Isi dulu pesannya",
    "posted": "Terkirim!",
    "msg_deleted": "Pesan dihapus",
    "join_h": "✍️ Ikut antre",
    "join_as": "Ikut antre sebagai \"{x}\"",
    "start_when": "Waktu mulai diinginkan",
    "now": "Sekarang",
    "pick_time": "Pilih waktu (maks 2 jam ke depan)",
    "f_time": "Pilih waktu",
    "f_score": "Skor tim", "f_fire": "Konsumsi api",
    "f_dur": "Durasi (menit, opsional; maks 60 untuk reguler)",
    "join_form_cap": "Daftar khusus (p1/p2) boleh kosong; pemain reguler wajib isi semua",
    "queue_btn": "Antre 🎮",
    "err_dup_this": "Kamu sudah di ruangan/antrean ini",
    "err_dup_other": "Kamu sudah di \"{x}\" — hanya satu ruangan (keluar dulu)",
    "err_missing": "Belum diisi: {x}",
    "err_too_far": "Pemesanan maksimal 2 jam ke depan!",
    "err_dur_cap": "Pemain reguler maksimal 60 menit!",
    "joined": "Masuk antrean!",
    "err_login_first": "Silakan login dulu",
    "err_login_queue": "Login dulu untuk antre",
    "exit_h": "🚪 Keluar",
    "exit_btn": "Keluar dari ruangan / antrean",
    "err_not_here": "ID kamu tidak ada di ruangan ini (kursi atau antrean)",
    "confirm_exit": "Keluarkan \"{x}\" dari {where}?",
    "from_room": "kursi (orang berikutnya langsung mengisi)", "from_queue": "antrean",
    "exited": "Keluar",
    "err_pw_fail": "Verifikasi kata sandi gagal",
    "mod_h": "✏️ Ubah / Perpanjang",
    "mod_need_login": "Login untuk ubah/perpanjang",
    "mod_no_rec": "Kamu belum ada data di ruangan ini (di ruang lain?)",
    "mod_locked": "🔒 Terkunci — tanpa durasi",
    "mod_in_room": "Di kursi, sisa {n} mnt | antre {q}",
    "mod_in_queue": "Antre, durasi {n} mnt",
    "f_new_dur": "Durasi baru (lebih pendek, menit)",
    "mod_btn": "Ubah (hanya memperpendek; jeda 20 menit)",
    "ext_btn": "Perpanjang 1 jam (sisa ≤10 mnt & tanpa antrean)",
    "err_cd": "Jeda perubahan, coba lagi dalam {n} mnt",
    "err_fill_dur": "Isi durasi barunya",
    "err_shorter_only": "Hanya memperpendek: harus kurang dari sisa waktu",
    "err_shorter_q": "Hanya memperpendek: kurang dari durasi saat ini",
    "shortened": "Sisa waktu dipersingkat", "shortened_q": "Durasi dipersingkat",
    "err_ext_where": "Hanya yang duduk & bergilir bisa perpanjang",
    "err_ext_time": "Perpanjang saat sisa ≤10 mnt (sekarang {n} mnt)",
    "err_ext_queue": "Ada yang antre — tidak bisa perpanjang",
    "extended": "Diperpanjang 1 jam",
    "rename_btn": "✏️ Ganti nama",
    "rename_h": "🏷 Ganti nama ruang (kondektur)",
    "err_same_name": "Nama sama dengan yang sekarang",
    "renamed": "Nama ruang diganti",
    "save_btn": "Simpan",
    "admin_h": "⚙️ Panel admin",
    "admin_exit": "🚪 Keluar mode admin (ke halaman login)",
    "admin_hint": "Gunakan tombol 🗑 di samping nama untuk hapus anggota/antrean/pesan; hapus ruangan di halaman daftar",
    "clear_members": "🧹 Kosongkan kursi", "clear_queue": "🧹 Kosongkan antrean",
    "clear_messages": "🧹 Kosongkan pesan",
    "confirm_clear": "Yakin {x}? (permanen)",
    "cleared": "Dikosongkan",
    "del_this_room": "🗑 Hapus ruangan ini",
    "confirm_del_room2": "Hapus seluruh ruangan? (semua data hilang — permanen)",
    "status_offline": "⚠️ Gagal memuat data ruang: {x}",
    "json_broken": "room_state.json rusak — periksa di GitHub",
    "no_secrets": "Secrets belum diatur: github_token / repo",
    "save_fail": "Gagal simpan ke GitHub (mungkin ada operasi bersamaan) — coba lagi",
    "save_fail2": "⚠️ Gagal simpan: {x}",
},
}

def _t(key, **kw):
    lang = st.session_state.get("lang", "zh")
    s = T.get(lang, {}).get(key) or T["zh"].get(key, key)
    if kw:
        s = s.format(**kw)
    return s

def _lang_widget(where, key):
    opts = list(LANG_NAMES)
    cur = st.session_state.get("lang", "zh")
    sel = where.selectbox(_t("lang_label"), opts, index=opts.index(cur),
                          format_func=lambda x: LANG_NAMES[x], key=key)
    if sel != st.session_state.get("lang", "zh"):
        st.session_state["lang"] = sel
        st.rerun()

def _safe_secret(key, default=None):
    """秘密值放 Secrets，public repo 也看不到（沒設定 = 功能關閉）"""
    try:
        return st.secrets[key]
    except Exception:
        return default

ADMIN_ID = _safe_secret("admin_id", "") or ""
try:
    _pid = st.secrets["priority_ids"]
    if isinstance(_pid, str):                     # 字串格式："巴哈|遊戲|1, 巴哈|遊戲|2"
        PRIORITY_IDS = [(a.strip(), g.strip(), int(p.strip()))
                        for item in _pid.split(",") if item.strip()
                        for a, g, p in [item.split("|")]]
    else:                                          # 陣列格式（本地 secrets.toml 可用）
        PRIORITY_IDS = [(str(a), str(g), int(p)) for a, g, p in _pid]
except Exception:
    PRIORITY_IDS = []        # 沒設定或格式錯 → 沒有特別名單，大家一律一般玩家

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
    display: none !important;
}}
[data-testid="stToolbar"], #MainMenu, [data-testid="stMainMenu"] {{
    display: none !important;
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
        st.error(_t("no_secrets"))
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
    if r.status_code in (401, 403):
        raise PermissionError(
            f"GitHub API {r.status_code}: token has no access (check fine-grained token "
            "Repository access = Only select repositories + this repo)")
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
                "name": "小狼gamers",
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
    try:
        _sha, raw = _gh_get(c["token"], c["url"], c["branch"])
    except Exception as e:
        st.error(_t("status_offline", x=e))
        st.stop()
    if raw is None:
        fetched = {"rooms": {}, "rev": 0}
    else:
        try:
            fetched = json.loads(raw)
        except Exception:
            st.error(_t("json_broken"))
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
    try:
        for _ in range(3):                   # 同時有人改 → 409 重試
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
    except Exception as e:
        st.error(_t("save_fail2", x=e))
        return False
    st.error(_t("save_fail"))
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

def _record_anywhere(state, baha, game):
    """在任何房間找到玩家的紀錄（房內或排隊中）"""
    for r in state["rooms"].values():
        for lst in (r["room"], r["queue"]):
            for x in (baha, game):
                i = _find(lst, x)
                if i is not None:
                    return lst[i]
    return None

def _touch(r, now):
    r["active"] = now.isoformat()

def _transfer_owner(r):
    """車掌不在房裡/排隊時，車掌身分換給房內最早成員（只換一次，換了就鎖定）"""
    if not r.get("owner"):
        return False
    for lst in (r["room"], r["queue"]):
        if _find(lst, r["owner"]) is not None:
            return False
    p0 = r["room"][0] if r["room"] else None
    r["owner"] = (p0["baha_id"] or p0["game_id"] or "") if p0 else ""
    return True

def _ensure_conductor(r, now):
    """車掌固定在第一個成員欄位、鎖定不換人"""
    owner = r.get("owner")
    if not owner:
        return False
    changed = False
    jq = _find(r["queue"], owner)
    if jq is not None and len(r["room"]) < ROOM_SIZE:   # 車掌還在排隊 → 直接入座
        p = r["queue"].pop(jq)
        p["sat_at"] = now.isoformat()
        p["until"] = None
        r["room"].insert(0, p)
        changed = True
    jr = _find(r["room"], owner)
    if jr is not None:
        p = r["room"].pop(jr)
        if p.get("until") is not None:
            p["until"] = None
            changed = True
        if jr != 0:                                      # 有移位要存檔
            changed = True
        r["room"].insert(0, p)                           # 永遠第 1 位
    return changed

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
                p["until"] = (now + timedelta(hours=1)).isoformat()
                p["ext"] = p.get("ext", 0) + 1
            dirty = True
    dirty |= refill(r, now)
    if _transfer_owner(r):
        dirty = True
    if _ensure_conductor(r, now):
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


# ---------- 登入 ----------
def _me():
    me = st.session_state.get("me")
    if not me:
        return None
    me.setdefault("baha", "")
    me.setdefault("game", "")
    me.setdefault("pw", "")
    return me

def _my_baha():
    me = _me()
    return (me["baha"] or me["game"] or "") if me else ""

def _login_gate(state):
    """未登入時顯示登入頁（管理模式可繞過）"""
    me = _me()
    if me or st.session_state.get("admin"):
        return
    _lang_widget(st, "lang_login")
    st.title("🎮 Hololive dreams " + _t("title_suffix"))
    st.caption(_t("announce"))
    st.subheader(_t("login_sub"))
    st.caption(_t("login_cap"))
    with st.form("login_form", border=True):
        lb = st.text_input(_t("col_baha"), key="lb")
        lg = st.text_input(_t("col_game"), key="lg")
        lpw = st.text_input(_t("f_pw"), max_chars=4, type="password", key="lpw")
        ok = st.form_submit_button(_t("login_btn"), type="primary", use_container_width=True)
    if ok:
        lb, lg = lb.strip(), lg.strip()
        if not lb and not lg:
            st.error(_t("err_need_id"))
        elif ADMIN_ID and (lb.casefold() == ADMIN_ID or lg.casefold() == ADMIN_ID):
            st.session_state["admin"] = True
            st.toast(_t("admin_on"))
            st.rerun()
        elif len(lpw) != 4:
            st.error(_t("err_pw_len"))
        else:
            rec = _record_anywhere(state, lb, lg)
            if rec is not None and rec.get("pw_hash") and rec["pw_hash"] != _sha(lpw):
                st.error(_t("err_pw_mismatch"))
            else:
                st.session_state["me"] = {"baha": lb, "game": lg, "pw": lpw}
                st.toast(_t("welcome_prefix") + (lb or lg) + "！")
                st.rerun()
    st.stop()

def _sidebar_account():
    me = _me()
    with st.sidebar:
        _lang_widget(st, "lang_sidebar")
        if me:
            st.success(_t("sb_logged", x=me["baha"] or me["game"]))
            if st.button(_t("logout"), use_container_width=True):
                del st.session_state["me"]
                st.rerun()
        else:
            st.warning(_t("sb_admin_only"))


# ---------- 頁面主流程 ----------
now = now_tw()
state = load_state()
dirty = reconcile_all(state, now)

_login_gate(state)
_sidebar_account()
me = _me()
is_admin = st.session_state.get("admin", False)

rid = st.query_params.get("room")
if rid and rid not in state["rooms"]:               # 房間不存在（可能已被自動刪）
    del st.query_params["room"]
    rid = None

# ================================================================
# 房間列表頁：選車掌（開新房）或乘客（進現有房）
# ================================================================
if rid is None:
    st.title("🎮 Hololive dreams " + _t("title_suffix"))
    st.caption(_t("rooms_caption", n=len(state["rooms"]), cap=MAX_ROOMS) + _t("announce"))

    st.subheader(_t("new_room_h"))
    st.caption(_t("new_room_cap"))
    with st.form("new_room", border=True):
        new_name = st.text_input(_t("f_room_name"))
        if st.form_submit_button(_t("open_room_btn"), type="primary", use_container_width=True):
            if not me:
                st.error(_t("err_login_first"))
            elif not new_name.strip():
                st.error(_t("err_room_name"))
            elif len(state["rooms"]) >= MAX_ROOMS:
                st.error(_t("err_room_cap"))
            elif _record_anywhere(state, me["baha"], me["game"]) is not None:
                st.error(_t("err_in_room_already"))
            else:
                nid = "r_" + secrets.token_hex(3)
                ts = now.isoformat()
                me_rec = {                              # 車掌自動入座第 1 位、鎖定
                    "baha_id": me["baha"], "game_id": me["game"],
                    "prio": resolve_prio(me["baha"], me["game"]),
                    "score": None, "fire": None,
                    "pw_hash": _sha(me["pw"]),
                    "start_pref": None, "duration": 60,
                    "reg_at": ts, "sat_at": ts, "until": None,
                }
                state["rooms"][nid] = {
                    "name": new_name.strip(),
                    "owner": me["baha"] or me["game"],
                    "room": [me_rec], "queue": [], "messages": [],
                    "active": ts, "created": ts,
                }
                if save_state(state):
                    st.query_params["room"] = nid
                    st.rerun()

    st.subheader(_t("join_sec"))
    if not state["rooms"]:
        st.info(_t("no_rooms"))
    for rid2, r in state["rooms"].items():
        card = _t("room_card", name=r["name"], owner=r.get("owner") or "—",
                  n=len(r["room"]), cap=ROOM_SIZE, q=len(r["queue"]),
                  m=len(r.get("messages", [])))
        if is_admin:
            c1, c2, c3 = st.columns([0.72, 0.16, 0.12])
            c1.markdown(card)
            if c2.button(_t("enter"), key=f"go_{rid2}", use_container_width=True):
                st.query_params["room"] = rid2
                st.rerun()
            if c3.button(_t("del_room_btn"), key=f"admdelroom_{rid2}", use_container_width=True):
                st.session_state[f"delrm_{rid2}"] = True
                st.rerun()
            if st.session_state.get(f"delrm_{rid2}"):
                st.warning(_t("confirm_del_room", name=r["name"]))
                bc1, bc2 = st.columns(2)
                if bc1.button(_t("sure_del"), key=f"delrm_yes_{rid2}", type="primary"):
                    del state["rooms"][rid2]
                    st.session_state.pop(f"delrm_{rid2}", None)
                    dirty = True
                    st.toast(_t("room_deleted"))
                    if save_state(state):
                        st.rerun()
                if bc2.button(_t("cancel"), key=f"delrm_no_{rid2}"):
                    st.session_state.pop(f"delrm_{rid2}", None)
                    st.rerun()
        else:
            c1, c2 = st.columns([0.85, 0.15])
            c1.markdown(card)
            if c2.button(_t("enter"), key=f"go_{rid2}", use_container_width=True):
                st.query_params["room"] = rid2
                st.rerun()

# ================================================================
# 房間頁（所有功能都綁在這間 + 登入身分）
# ================================================================
else:
    r = state["rooms"][rid]
    room, queue = r["room"], r["queue"]
    msgs = r.setdefault("messages", [])
    owner_now = (r.get("owner") or "").casefold()
    am_owner = bool(me and owner_now and
                    ((me["baha"] or "").strip().casefold() == owner_now or
                     (me["game"] or "").strip().casefold() == owner_now))

    if st.button(_t("back_list"), type="secondary"):
        st.query_params.clear()
        st.rerun()

    # 標題列：房名＋車掌專用的改名按鈕
    tc1, tc2 = st.columns([0.88, 0.12])
    tc1.title(f"🎮 {r['name']}")
    if am_owner and tc2.button(_t("rename_btn"), key="rename_open_btn", use_container_width=True):
        st.session_state["rename_open"] = not st.session_state.get("rename_open", False)
        st.rerun()
    if am_owner and st.session_state.get("rename_open"):
        st.caption(_t("rename_h"))
        rn_name = st.text_input(_t("f_room_name"), key="rn_name")
        rc1, rc2 = st.columns(2)
        if rc1.button(_t("save_btn"), key="rn_go", type="primary"):
            owner_rec = None
            for lst in (room, queue):
                k = _find(lst, r.get("owner"))
                if k is not None:
                    owner_rec = lst[k]
                    break
            if not rn_name.strip():
                st.error(_t("err_room_name"))
            elif rn_name.strip() == r["name"]:
                st.error(_t("err_same_name"))
            elif me and owner_rec is not None and not _pw_ok(owner_rec, me["pw"], is_admin):
                st.error(_t("err_pw_fail"))
            else:
                r["name"] = rn_name.strip()
                dirty = True
                _touch(r, now)
                st.session_state.pop("rename_open", None)
                st.toast(_t("renamed"))
                if save_state(state):
                    st.rerun()
        if rc2.button(_t("cancel"), key="rn_cancel"):
            st.session_state.pop("rename_open", None)
            st.rerun()

    st.caption(_t("room_cap", owner=r.get("owner") or "—", n=len(room), cap=ROOM_SIZE)
               + _t("announce"))

    st.subheader(_t("members_h", n=len(room), cap=ROOM_SIZE))
    rows = []
    for i in range(ROOM_SIZE):
        if i < len(room):
            p = room[i]
            locked = p.get("until") is None
            rows.append({
                _t("col_seat"): i + 1, _t("col_baha"): p["baha_id"] or "—",
                _t("col_game"): p["game_id"] or "—",
                _t("col_in"): fmt(p["sat_at"]),
                _t("col_swap"): _t("locked") if locked else fmt(p["until"]),
                _t("col_left"): "—" if locked else int((parse(p["until"]) - now).total_seconds() // 60),
                _t("col_ext"): "—" if locked else p.get("ext", 0),
            })
        else:
            rows.append({_t("col_seat"): i + 1, _t("col_baha"): _t("empty_seat"),
                         _t("col_game"): "—", _t("col_in"): "—", _t("col_swap"): "—",
                         _t("col_left"): "—", _t("col_ext"): "—"})
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if is_admin or am_owner:              # 管理模式／車掌：車廂成員名字旁直接刪
        for i, p in enumerate(list(room)):
            c1, c2 = st.columns([0.88, 0.12])
            c1.markdown(_t("seat_line", n=i + 1, x=p["baha_id"] or "—", y=p["game_id"] or "—"))
            if c2.button(_t("del_btn"), key=f"admrm_{i}", use_container_width=True):
                room.remove(p)
                dirty |= refill(r, now)
                _transfer_owner(r)
                _ensure_conductor(r, now)
                dirty = True
                _touch(r, now)
                st.toast(_t("del_member_toast"))
                if save_state(state):
                    st.rerun()

    st.subheader(_t("queue_h", n=len(queue)))
    if queue:
        qrows = [{
            _t("col_pos"): i + 1, _t("col_baha"): p["baha_id"] or "—",
            _t("col_game"): p["game_id"] or "—",
            _t("col_fire"): p.get("fire") if p.get("fire") is not None else "—",
            _t("col_start"): fmt(p.get("start_pref")),
            _t("col_dur"): p.get("duration") if p.get("duration") is not None else "—",
        } for i, p in enumerate(sorted(queue, key=_qkey))]
        st.dataframe(qrows, use_container_width=True, hide_index=True)
        if is_admin:                      # 管理模式：排隊者名字旁直接刪
            for pq in sorted(queue, key=_qkey):
                c1, c2 = st.columns([0.88, 0.12])
                c1.markdown(_t("queued_line", x=pq["baha_id"] or "—", y=pq["game_id"] or "—"))
                if c2.button(_t("del_btn"), key=f"admq_{pq['reg_at']}", use_container_width=True):
                    queue.remove(pq)
                    dirty = True
                    _touch(r, now)
                    st.toast(_t("del_member_toast"))
                    if save_state(state):
                        st.rerun()
    else:
        st.info(_t("no_queue"))

    # ---------- 留言板 ----------
    my_id = _my_baha()
    if msgs:
        st.subheader(_t("board_h", n=len(msgs)))
    else:
        st.subheader(_t("board_h_empty"))
        st.caption(_t("no_msgs"))

    if is_admin:                                   # 管理模式：刪除全部留言
        if st.button(_t("clear_msgs"), key="clr_msgs_board", use_container_width=True):
            st.session_state["clr_msgs_board"] = True
            st.rerun()
        if st.session_state.get("clr_msgs_board"):
            st.warning(_t("confirm_clear_msgs"))
            cc1, cc2 = st.columns(2)
            if cc1.button(_t("sure_del"), key="clr_msgs_board_yes", type="primary"):
                msgs.clear()
                st.session_state.pop("clr_msgs_board", None)
                dirty = True
                _touch(r, now)
                st.toast(_t("msgs_cleared"))
                if save_state(state):
                    st.rerun()
            if cc2.button(_t("cancel"), key="clr_msgs_board_no"):
                st.session_state.pop("clr_msgs_board", None)
                st.rerun()

    for m in reversed(msgs):
        tag = _t("reply_tag") + str(m["reply_to"]) if m.get("reply_to") else ""
        if is_admin:
            c1, c2, c3 = st.columns([0.84, 0.08, 0.08])
        else:
            c1, c2 = st.columns([0.92, 0.08])
            c3 = None
        c1.markdown(f"**#{m['no']}　{m['name']}**{tag}　—　{fmt(m['ts'])}  \n{m['text']}")
        if c2.button("↩", key=f"reply_{m['no']}", help=f"reply #{m['no']}"):
            st.session_state["reply_to"] = m["no"]
            st.rerun()
        if is_admin and c3.button("🗑", key=f"delmsg_{m['no']}", help=_t("msg_deleted")):
            msgs[:] = [x for x in msgs if x["no"] != m["no"]]
            dirty = True
            _touch(r, now)
            st.toast(_t("msg_deleted"))
            if save_state(state):
                st.rerun()

    reply_to = st.session_state.get("reply_to", 0)
    if reply_to and any(x["no"] == reply_to for x in msgs):
        rc1, rc2 = st.columns([0.6, 0.4])
        rc1.caption(_t("replying", n=reply_to))
        if rc2.button(_t("cancel_reply"), key="cancel_reply"):
            st.session_state["reply_to"] = 0
            st.rerun()
    elif reply_to:
        st.session_state["reply_to"] = 0

    label = _t("msg_label", x=my_id) if my_id else _t("msg_label_anon")
    with st.form("msg_form", border=True):
        m_text = st.text_area(label, max_chars=500)
        if st.form_submit_button(_t("post_btn"), type="primary", use_container_width=True):
            if not my_id:
                st.error(_t("err_login_first"))
            elif not m_text.strip():
                st.error(_t("err_text_required"))
            else:
                msgs.append({
                    "no": msgs[-1]["no"] + 1 if msgs else 1,
                    "name": my_id,
                    "reply_to": reply_to or None,
                    "text": m_text.strip(),
                    "ts": now.isoformat(),
                })
                del msgs[:len(msgs) - 100]          # 最多保留 100 則
                st.session_state["reply_to"] = 0
                dirty = True
                _touch(r, now)
                st.toast(_t("posted"))

    # ---------- 側邊欄：排隊 / 退出 / 修改 / 管理 ----------
    with st.sidebar:
        st.header(_t("join_h"))
        st.caption(_t("join_as", x=my_id))
        when = st.selectbox(_t("start_when"), [_t("now"), _t("pick_time")])
        with st.form("join_form", border=True):
            st.caption(_t("join_form_cap"))
            score = st.number_input(_t("f_score"), min_value=0, value=0)
            fire = st.number_input(_t("f_fire"), min_value=0, value=0)
            pref_t = st.time_input(_t("f_time"), value=None, disabled=(when == _t("now")))
            dur = st.number_input(_t("f_dur"), min_value=10, value=None, step=5, placeholder="60")
            ok = st.form_submit_button(_t("queue_btn"), type="primary", use_container_width=True)

        if ok and not me:
            st.error(_t("err_login_queue"))
        if ok and me:
            loc_rid, other = None, None
            for rid2, r2 in state["rooms"].items():
                if (_find(r2["room"], me["baha"]) is not None or _find(r2["room"], me["game"]) is not None or
                        _find(r2["queue"], me["baha"]) is not None or _find(r2["queue"], me["game"]) is not None):
                    loc_rid, other = rid2, r2
                    break
            if other is not None and loc_rid == rid:
                st.error(_t("err_dup_this"))
            elif other is not None:
                st.error(_t("err_dup_other", x=other["name"]))
            else:
                prio = resolve_prio(me["baha"], me["game"])
                missing = []
                if prio >= 3:                        # 一般玩家：所有欄位必填
                    if not score:
                        missing.append(_t("f_score"))
                    if not fire:
                        missing.append(_t("f_fire"))
                    if when != _t("now") and pref_t is None:
                        missing.append(_t("f_time"))
                    if dur is None:
                        missing.append(_t("col_dur"))
                if missing:
                    st.error(_t("err_missing", x="、".join(missing)))
                else:
                    start_pref = None
                    if when != _t("now") and pref_t is not None:
                        cand = now.replace(hour=pref_t.hour, minute=pref_t.minute,
                                           second=0, microsecond=0)
                        if cand < now:
                            cand += timedelta(days=1)
                        if prio >= 3 and cand > now + MAX_AHEAD:
                            st.error(_t("err_too_far"))
                            st.stop()
                        start_pref = cand.isoformat()
                    duration = dur
                    if duration is not None and prio >= 3 and duration > 60:
                        st.error(_t("err_dur_cap"))
                        st.stop()
                    queue.append({
                        "baha_id": me["baha"], "game_id": me["game"], "prio": prio,
                        "score": score or None,
                        "fire": fire or None,
                        "pw_hash": _sha(me["pw"]),
                        "start_pref": start_pref,
                        "duration": duration,
                        "reg_at": now.isoformat(),
                    })
                    queue.sort(key=_qkey)
                    dirty = True
                    _touch(r, now)
                    st.toast(_t("joined"))

        st.markdown("---")
        st.header(_t("exit_h"))
        if st.button(_t("exit_btn"), use_container_width=True):
            if not me:
                st.error(_t("err_login_first"))
            else:
                i = _find(room, me["baha"]) if me["baha"] else None
                if i is None and me["game"]:
                    i = _find(room, me["game"])
                j = _find(queue, me["baha"]) if me["baha"] else None
                if j is None and me["game"]:
                    j = _find(queue, me["game"])
                if i is None and j is None:
                    st.error(_t("err_not_here"))
                else:
                    st.session_state["exit_pending"] = True
                    st.rerun()

        if me and st.session_state.get("exit_pending"):
            target = None
            for lst in (room, queue):
                for x in (me["baha"], me["game"]):
                    k = _find(lst, x)
                    if k is not None and not target:
                        target = lst[k]
            in_room = _find(room, me["baha"] or me["game"]) is not None
            st.warning(_t("confirm_exit", x=my_id,
                          where=_t("from_room") if in_room else _t("from_queue")))
            c1, c2 = st.columns(2)
            if c1.button(_t("sure_del"), type="primary", key="exit_yes"):
                if target is not None and not _pw_ok(target, me["pw"], is_admin):
                    st.error(_t("err_pw_fail"))
                else:
                    i = _find(room, my_id)
                    if i is not None:
                        room.pop(i)
                        dirty = True
                        dirty |= refill(r, now)
                    else:
                        j = _find(queue, my_id)
                        if j is not None:
                            queue.pop(j)
                            dirty = True
                    if _transfer_owner(r):
                        dirty = True
                    del st.session_state["exit_pending"]
                    st.toast(_t("exited"))
                    _touch(r, now)
                    if save_state(state):        # 先存檔再重整，否則改動會丟掉
                        st.rerun()
            if c2.button(_t("cancel"), key="exit_no"):
                del st.session_state["exit_pending"]
                st.rerun()

        # ---------- 修改 / 延長（限自己的紀錄，登入即識別） ----------
        st.markdown("---")
        st.header(_t("mod_h"))
        m_target, m_src = None, None
        if me:
            for lst, src in ((room, "room"), (queue, "queue")):
                for x in (me["baha"], me["game"]):
                    k = _find(lst, x)
                    if k is not None and m_target is None:
                        m_target, m_src = lst[k], src
        if not me:
            st.caption(_t("mod_need_login"))
        elif m_target is None:
            st.caption(_t("mod_no_rec"))
        elif m_src == "room" and m_target.get("until") is None:
            st.caption(_t("mod_locked"))
        elif m_src == "room":
            rem = int((parse(m_target["until"]) - now).total_seconds() // 60)
            st.caption(_t("mod_in_room", n=rem, q=len(queue)))
        else:
            st.caption(_t("mod_in_queue", n=m_target.get("duration") or 60))

        ndur = st.number_input(_t("f_new_dur"), min_value=10, value=None, key="mod_dur")
        if st.button(_t("mod_btn"), key="mod_go", use_container_width=True):
            if me and m_target is not None and not _pw_ok(m_target, me["pw"], is_admin):
                st.error(_t("err_pw_fail"))
            elif not me:
                st.error(_t("mod_need_login"))
            elif m_target is None:
                st.error(_t("mod_no_rec"))
            else:
                le = m_target.get("last_edit")
                if le and now - parse(le) < timedelta(minutes=20):
                    wait = 20 - int((now - parse(le)).total_seconds() // 60)
                    st.error(_t("err_cd", n=wait))
                elif ndur is None:
                    st.error(_t("err_fill_dur"))
                elif m_src == "room":
                    if m_target.get("until") is None:
                        st.error(_t("mod_locked"))
                    elif now + timedelta(minutes=ndur) >= parse(m_target["until"]):
                        st.error(_t("err_shorter_only"))
                    else:
                        m_target["until"] = (now + timedelta(minutes=ndur)).isoformat()
                        m_target["last_edit"] = now.isoformat()
                        dirty = True
                        _touch(r, now)
                        st.toast(_t("shortened"))
                        if save_state(state):
                            st.rerun()
                else:
                    if ndur >= (m_target.get("duration") or 60):
                        st.error(_t("err_shorter_q"))
                    else:
                        m_target["duration"] = ndur
                        m_target["last_edit"] = now.isoformat()
                        dirty = True
                        _touch(r, now)
                        st.toast(_t("shortened_q"))
                        if save_state(state):
                            st.rerun()

        if st.button(_t("ext_btn"), key="ext_go", use_container_width=True):
            if me and m_target is not None and not _pw_ok(m_target, me["pw"], is_admin):
                st.error(_t("err_pw_fail"))
            elif not me:
                st.error(_t("mod_need_login"))
            elif m_target is None:
                st.error(_t("mod_no_rec"))
            elif m_src != "room" or m_target.get("until") is None:
                st.error(_t("err_ext_where"))
            else:
                rem = (parse(m_target["until"]) - now).total_seconds() / 60
                if rem > 10:
                    st.error(_t("err_ext_time", n=int(rem)))
                elif len(queue) > 0:
                    st.error(_t("err_ext_queue"))
                else:
                    m_target["until"] = (now + timedelta(hours=1)).isoformat()
                    m_target["ext"] = m_target.get("ext", 0) + 1
                    dirty = True
                    _touch(r, now)
                    st.toast(_t("extended"))
                    if save_state(state):
                        st.rerun()

        # ---------- 後門管理面板 ----------
        if st.session_state.get("admin"):
            st.markdown("---")
            st.header(_t("admin_h"))
            if st.button(_t("admin_exit")):
                st.session_state.pop("admin", None)
                st.session_state.pop("me", None)
                st.rerun()

            st.caption(_t("admin_hint"))

            for label, key in ((_t("clear_members"), "room"), (_t("clear_queue"), "queue"),
                               (_t("clear_messages"), "messages")):
                if st.button(label, key=f"clr_{key}"):
                    st.session_state[f"clr_pending_{key}"] = True
                    st.rerun()
                if st.session_state.get(f"clr_pending_{key}"):
                    st.warning(_t("confirm_clear", x=label[1:]))
                    c1, c2 = st.columns(2)
                    if c1.button(_t("sure_del"), key=f"clr_{key}_yes", type="primary"):
                        r[key].clear()
                        if key == "room":
                            dirty |= refill(r, now)
                            _transfer_owner(r)
                            _ensure_conductor(r, now)
                        dirty = True
                        _touch(r, now)
                        del st.session_state[f"clr_pending_{key}"]
                        st.toast(_t("cleared"))
                        if save_state(state):
                            st.rerun()
                    if c2.button(_t("cancel"), key=f"clr_{key}_no"):
                        del st.session_state[f"clr_pending_{key}"]
                        st.rerun()

            if st.button(_t("del_this_room")):
                st.session_state["del_room_pending"] = True
                st.rerun()
            if st.session_state.get("del_room_pending"):
                st.warning(_t("confirm_del_room2"))
                c1, c2 = st.columns(2)
                if c1.button(_t("sure_del"), key="del_room_yes", type="primary"):
                    del state["rooms"][rid]
                    del st.session_state["del_room_pending"]
                    if save_state(state):
                        st.query_params.clear()
                        st.rerun()
                if c2.button(_t("cancel"), key="del_room_no"):
                    del st.session_state["del_room_pending"]
                    st.rerun()

# ---------- 結算後存回 ----------
if dirty:
    if save_state(state):
        st.rerun()
