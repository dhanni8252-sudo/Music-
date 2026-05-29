"""
Premium Telegram Music Bot — Pro Level v7 (JioSaavn API Edition)
Voice Chat Streaming via JioSaavn
"""
import os
import re
import asyncio
import json
import time
import io
import urllib.request
import urllib.parse
import requests
from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, CallbackQuery,
)
from pyrogram.errors import (
    SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired,
    FloodWait, PhoneNumberInvalid,
)
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, StreamEnded, Update

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
API_ID         = int(os.environ.get("TELEGRAM_API_ID", "39712134"))
API_HASH       = os.environ.get("TELEGRAM_API_HASH", "b1647a213b0e804cf8e19587ae055bd7")
BOT_TOKEN      = os.environ.get("TELEGRAM_BOT_TOKEN", "8964791887:AAHgDfwcPTdBzgf-Cuy9d1_V99wS-_dltac")
ADMIN_ID       = int(os.environ.get("ADMIN_ID", "8136495141"))
STRING_SESSION = os.environ.get("STRING_SESSION", "").strip()

BOT_DIR      = os.path.dirname(os.path.abspath(__file__))
GROUPS_FILE  = os.path.join(BOT_DIR, "groups.json")
SESSION_FILE = os.path.join(BOT_DIR, ".session_output")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PERSISTENCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def load_session() -> str:
    if STRING_SESSION and len(STRING_SESSION) > 50:
        return STRING_SESSION
    if os.path.exists(SESSION_FILE):
        s = open(SESSION_FILE).read().strip()
        if len(s) > 50:
            return s
    return ""

def save_session(s: str):
    with open(SESSION_FILE, "w") as f:
        f.write(s)

def delete_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

def load_groups() -> dict:
    if os.path.exists(GROUPS_FILE):
        try:
            return json.load(open(GROUPS_FILE))
        except Exception:
            pass
    return {}

def save_groups(data: dict):
    with open(GROUPS_FILE, "w") as f:
        json.dump(data, f, indent=2)

groups: dict = load_groups()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CLIENTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
bot  = Client("bot_client", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user: Client | None    = None
call: PyTgCalls | None = None

_saved_session = load_session()
if _saved_session:
    user = Client("user_client", api_id=API_ID, api_hash=API_HASH,
                  session_string=_saved_session, in_memory=True)
    call = PyTgCalls(user)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STATE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
admin_state:  dict[int, str]    = {}
admin_data:   dict[int, dict]   = {}
otp_clients:  dict[int, Client] = {}
queues:       dict[int, list]   = {}
now_playing:  dict[int, dict]   = {}
search_cache: dict[int, list]   = {}
start_times:  dict[int, float]  = {}   # track when song started

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  JIOSAAVN API LOGIC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SAAVN_API = "https://saavn.dev/api/search/songs?query="

def get_audio(query: str) -> dict:
    safe_query = urllib.parse.quote(query.strip())
    api_url = f"{SAAVN_API}{safe_query}"
    
    try:
        resp = requests.get(api_url).json()
        if resp.get('success') and resp['data']['results']:
            song = resp['data']['results'][0]
            
            audio_links = song.get('downloadUrl', [])
            audio_url = audio_links[-1]['url'] if audio_links else ""
            
            images = song.get('image', [])
            thumb_url = images[-1]['url'] if images else ""
            
            return {
                "title": song.get('name', 'Unknown'),
                "url": audio_url,
                "duration": int(song.get('duration', 0)),
                "thumbnail": thumb_url,
                "uploader": song.get('primaryArtists', 'Unknown'),
                "yt_url": song.get('url', '') 
            }
    except Exception as e:
        print(f"JioSaavn Error: {e}")
    
    raise Exception("Gaana nahi mila! Koi aur naam try karo.")

def search_yt(query: str, n: int = 5) -> list[dict]:
    safe_query = urllib.parse.quote(query.strip())
    api_url = f"{SAAVN_API}{safe_query}"
    out = []
    
    try:
        resp = requests.get(api_url).json()
        if resp.get('success') and resp['data']['results']:
            results = resp['data']['results'][:n]
            for song in results:
                audio_links = song.get('downloadUrl', [])
                audio_url = audio_links[-1]['url'] if audio_links else ""
                
                out.append({
                    "title": song.get('name', '?'),
                    "url": audio_url,
                    "duration": int(song.get('duration', 0)),
                    "uploader": song.get('primaryArtists', ''),
                    "yt_url": song.get('url', ''),
                })
    except Exception as e:
        print(f"JioSaavn Search Error: {e}")
        
    return out

def fmt_dur(sec) -> str:
    m, s = divmod(int(sec or 0), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def progress_bar(elapsed: int, total: int, length: int = 10) -> str:
    if not total:
        return "▬" * length
    filled = int(length * min(elapsed, total) / total)
    return "▰" * filled + "▱" * (length - filled)

def vc_ready() -> bool:
    return call is not None

def fetch_thumb(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read()
    except Exception:
        return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PREMIUM NOW PLAYING TEXT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def np_caption(track: dict, chat_id: int) -> str:
    title   = track.get("title", "Unknown")
    dur     = track.get("duration", 0)
    req     = track.get("requested_by", "")
    yt_url  = track.get("yt_url", "")
    elapsed = int(time.time() - start_times.get(chat_id, time.time()))
    bar     = progress_bar(elapsed, dur)
    dur_str = fmt_dur(dur)
    ela_str = fmt_dur(elapsed)

    lines = [
        f"🎵 **{title}**\n",
        f"⏱  `{ela_str}` {bar} `{dur_str}`",
    ]
    if req:
        lines.append(f"👤 Requested by **{req}**")
    if yt_url:
        lines.append(f"🔗 [Listen on JioSaavn]({yt_url})")
    return "\n".join(lines)

def np_text_only(track: dict) -> str:
    title  = track.get("title", "Unknown")
    dur    = fmt_dur(track.get("duration", 0))
    req    = track.get("requested_by", "")
    yt_url = track.get("yt_url", "")
    lines  = [f"🎵 **{title}**", f"⚙️ Duration: `{dur}`"]
    if req:
        lines.append(f"👤 Requested by **{req}**")
    if yt_url:
        lines.append(f"🔗 [JioSaavn]({yt_url})")
    return "\n".join(lines)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  KEYBOARDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADMIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("📱 Session"),   KeyboardButton("🗑 Delete Session")],
        [KeyboardButton("📢 Broadcast"), KeyboardButton("📊 Stats")],
        [KeyboardButton("🏓 Ping"),      KeyboardButton("❓ Help")],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

def player_kb(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Pause",   callback_data=f"vc_pause_{chat_id}"),
            InlineKeyboardButton("▶️ Resume",  callback_data=f"vc_resume_{chat_id}"),
            InlineKeyboardButton("⏭ Skip",    callback_data=f"vc_skip_{chat_id}"),
            InlineKeyboardButton("⏹ Stop",    callback_data=f"vc_stop_{chat_id}"),
        ],
        [
            InlineKeyboardButton("📋 Queue",   callback_data=f"vc_queue_{chat_id}"),
            InlineKeyboardButton("🔀 Shuffle", callback_data=f"vc_shuffle_{chat_id}"),
            InlineKeyboardButton("🎵 Now Playing", callback_data=f"vc_np_{chat_id}"),
        ],
    ])

def add_kb(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{username}?startgroup=true"),
        InlineKeyboardButton("💬 Support",      url=f"https://t.me/{username}"),
    ]])

def confirm_delete_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes, Delete", callback_data="del_session_yes"),
        InlineKeyboardButton("❌ Cancel",       callback_data="del_session_no"),
    ]])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STREAM HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def setup_call_handlers():
    @call.on_update(filters=lambda _, u: isinstance(u, StreamEnded))
    async def _on_end(_, update: Update):
        await play_next(update.chat_id)

async def play_next(chat_id: int):
    if not queues.get(chat_id):
        now_playing.pop(chat_id, None)
        start_times.pop(chat_id, None)
        return
    track = queues[chat_id].pop(0)
    now_playing[chat_id] = track
    start_times[chat_id] = time.time()
    try:
        await call.play(chat_id, MediaStream(track["url"]))
    except Exception as e:
        print(f"[play_next] {e}")
        now_playing.pop(chat_id, None)

async def _activate_session(session_str: str, uid: int, msg: Message):
    global user, call
    admin_state.pop(uid, None)
    admin_data.pop(uid, None)
    for c in [call, user]:
        if c:
            try: await c.stop()
            except Exception: pass
    user = call = None
    save_session(session_str)
    user = Client("user_client", api_id=API_ID, api_hash=API_HASH,
                  session_string=session_str, in_memory=True)
    call = PyTgCalls(user)
    setup_call_handlers()
    await user.start()
    await call.start()
    me = await user.get_me()
    await msg.edit(
        "✅ **Session Activated!**\n\n"
        f"👤 **Assistant:** {me.first_name} `(@{me.username or 'N/A'})`\n"
        f"📱 **Phone:** `{me.phone_number}`\n\n"
        "🎵 Voice Chat is now **READY!**\n"
        "_Go to your group and use_ `/play <song>`"
    )

async def ensure_assistant_in_group(chat_id: int, chat_username: str = "") -> bool:
    if not user:
        return False
    try:
        await user.get_chat_member(chat_id, (await user.get_me()).id)
        return True 
    except Exception:
        pass
    if chat_username:
        try:
            await user.join_chat(chat_username)
            return True
        except Exception:
            pass
    try:
        link = await bot.export_chat_invite_link(chat_id)
        await user.join_chat(link)
        return True
    except Exception:
        pass
    return False

async def send_now_playing(target, track: dict, chat_id: int, edit: bool = False):
    caption  = np_caption(track, chat_id)
    kb       = player_kb(chat_id)
    thumb_url = track.get("thumbnail", "")
    thumb_data = None
    if thumb_url:
        thumb_data = await asyncio.to_thread(fetch_thumb, thumb_url)

    if thumb_data:
        photo = io.BytesIO(thumb_data)
        photo.name = "thumb.jpg"
        if edit:
            try:
                await target.delete()
            except Exception:
                pass
            if hasattr(target, "chat"):
                await target.chat.send_photo(photo, caption=caption, reply_markup=kb)
            else:
                await target.reply_photo(photo, caption=caption, reply_markup=kb)
        else:
            await target.reply_photo(photo, caption=caption, reply_markup=kb)
    else:
        text = np_text_only(track)
        if edit and hasattr(target, "edit"):
            await target.edit(text, reply_markup=kb, disable_web_page_preview=True)
        else:
            await target.reply(text, reply_markup=kb, disable_web_page_preview=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AUTO-TRACK GROUPS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.on_message(filters.group, group=-1)
async def track_group(_, m: Message):
    cid = str(m.chat.id)
    if cid not in groups:
        groups[cid] = {"title": m.chat.title or "Unknown", "username": m.chat.username or ""}
        save_groups(groups)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /start — PRIVATE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.on_message(filters.command("start") & filters.private)
async def cmd_start_dm(client, m: Message):
    me  = await client.get_me()
    uid = m.from_user.id
    if uid == ADMIN_ID:
        vc = "✅ Active" if vc_ready() else "⚠️ Not Set"
        session_info = "⚠️ No session"
        if vc_ready() and user:
            try:
                vc_me = await user.get_me()
                session_info = (
                    f"✅ **{vc_me.first_name}**\n"
                    f"   📱 `{vc_me.phone_number}`\n"
                    f"   👤 @{vc_me.username or 'N/A'}\n"
                    f"   🆔 `{vc_me.id}`"
                )
            except Exception:
                session_info = "✅ Active (info unavailable)"
        await m.reply(
            "👑 **ADMIN PANEL**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 Bot: @{me.username}\n"
            f"👥 Groups: `{len(groups)}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📱 **Active Session:**\n"
            f"{session_info}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Use keyboard below 👇",
            reply_markup=ADMIN_KB,
        )
    else:
        await m.reply(
            "🎵 **Premium Music Bot**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Stream music in your group Voice Chat!\n\n"
            "**Commands:**\n"
            "▶️ `/play <song name>`\n"
            "🔍 `/search <song name>`\n"
            "⏸ `/pause`  ▶️ `/resume`  ⏭ `/skip`\n"
            "⏹ `/stop`  📋 `/queue`  🎵 `/np`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 Add me to your group:",
            reply_markup=add_kb(me.username),
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /start — GROUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.on_message(filters.command("start") & filters.group)
async def cmd_start_group(client, m: Message):
    me  = await client.get_me()
    cid = str(m.chat.id)
    groups[cid] = {"title": m.chat.title or "Unknown", "username": m.chat.username or ""}
    save_groups(groups)
    vc = "✅ Ready" if vc_ready() else "⚠️ Session required"
    await m.reply(
        f"🎵 **Premium Music Bot is here!**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Voice Chat: {vc}\n\n"
        "▶️ `/play <song>`  🔍 `/search <song>`\n"
        "⏸ `/pause`  ▶️ `/resume`  ⏭ `/skip`  ⏹ `/stop`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Make me **Admin** to enable Voice Chat!",
        reply_markup=add_kb(me.username),
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BOT ADDED TO GROUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.on_message(filters.new_chat_members)
async def on_new_member(client, m: Message):
    me = await client.get_me()
    for new_user in m.new_chat_members:
        if new_user.id == me.id:
            cid = str(m.chat.id)
            groups[cid] = {"title": m.chat.title or "Unknown", "username": m.chat.username or ""}
            save_groups(groups)
            await m.reply(
                "👋 **Thanks for adding me!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🎵 I stream music in Voice Chats!\n\n"
                "**To get started:**\n"
                "1️⃣ Make me **Admin** (Manage Voice Chats)\n"
                "2️⃣ Start a **Voice Chat** in the group\n"
                "3️⃣ Use `/play <song name>`\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🎧 Let the music play!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "📋 How to Make Admin",
                        callback_data=f"how_admin_{m.chat.id}"
                    )
                ]])
            )
            return

@bot.on_callback_query(filters.regex(r"^how_admin_(-?\d+)$"))
async def cb_how_admin(_, cq: CallbackQuery):
    await cq.answer(
        "Group Settings → Administrators → Add Admin → Select bot → Enable 'Manage Voice Chats' ✅",
        show_alert=True,
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ADMIN DM HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.on_message(filters.private & filters.user(ADMIN_ID))
async def admin_handler(client, m: Message):
    global user, call
    uid   = m.from_user.id
    text  = (m.text or "").strip()
    state = admin_state.get(uid)

    if text.lower() in ("/cancel", "cancel"):
        admin_state.pop(uid, None)
        admin_data.pop(uid, None)
        if uid in otp_clients:
            try: await otp_clients[uid].disconnect()
            except Exception: pass
            otp_clients.pop(uid, None)
        await m.reply("❌ Cancelled.", reply_markup=ADMIN_KB)
        return

    if text == "📱 Session":
        admin_state.pop(uid, None)
        admin_data.pop(uid, None)
        if vc_ready():
            try:
                me   = await user.get_me()
                info = f"{me.first_name} `(@{me.username or 'N/A'})` | `{me.phone_number}`"
            except Exception:
                info = "Unknown"
            await m.reply(
                "📱 **Session Status**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Status: ✅ Active\n"
                f"Assistant: {info}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Send phone number to create new session\n"
                "or /cancel to skip.",
                reply_markup=ADMIN_KB,
            )
        else:
            await m.reply(
                "📱 **Create Session**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Send your Telegram phone number:\n"
                "_Format: +918xxxxxxxxx_\n\n"
                "OTP will be sent to your Telegram.\n"
                "Type /cancel to cancel.",
                reply_markup=ADMIN_KB,
            )
        admin_state[uid] = "session_phone"
        return

    if text == "🗑 Delete Session":
        admin_state.pop(uid, None)
        if not vc_ready() and not os.path.exists(SESSION_FILE):
            await m.reply("⚠️ No active session.", reply_markup=ADMIN_KB)
            return
        await m.reply(
            "🗑 **Delete Session?**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "This will stop the assistant and\n"
            "disable Voice Chat streaming.\n\n"
            "Are you sure?",
            reply_markup=confirm_delete_kb(),
        )
        return

    if text == "📢 Broadcast":
        admin_state.pop(uid, None)
        admin_data.pop(uid, None)
        if not groups:
            await m.reply("⚠️ Bot is not in any group yet.", reply_markup=ADMIN_KB)
            return
        await m.reply(
            "📢 **Broadcast**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Bot is in **{len(groups)} groups**.\n\n"
            "Send your message:\n"
            "_Text, photo, video — all supported_\n\n"
            "Type /cancel to cancel.",
            reply_markup=ADMIN_KB,
        )
        admin_state[uid] = "broadcast"
        return

    if text == "📊 Stats":
        admin_state.pop(uid, None)
        active  = len(now_playing)
        total_q = sum(len(v) for v in queues.values())
        vc = "✅ Active" if vc_ready() else "⚠️ Not Set"
        lines = [
            "📊 **Bot Statistics**",
            "━━━━━━━━━━━━━━━━━━━━━━━",
            f"👥 Total Groups: `{len(groups)}`",
            f"🎵 Active Streams: `{active}`",
            f"📋 Queued Songs: `{total_q}`",
            f"🎛 VC Status: {vc}",
        ]
        if groups:
            lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("**Groups:**")
            for i, (_, info) in enumerate(list(groups.items())[:15], 1):
                lines.append(f"`{i:02d}.` {info['title']}")
            if len(groups) > 15:
                lines.append(f"_...and {len(groups)-15} more_")
        await m.reply("\n".join(lines), reply_markup=ADMIN_KB)
        return

    if text == "🏓 Ping":
        admin_state.pop(uid, None)
        vc = "✅ Ready" if vc_ready() else "⚠️ Not Set"
        await m.reply(
            "🏓 **Pong!**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 Bot: Online ✅\n"
            f"🎵 VC: {vc}",
            reply_markup=ADMIN_KB,
        )
        return

    if text == "❓ Help":
        admin_state.pop(uid, None)
        await m.reply(
            "❓ **Admin Help**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📱 **Session** — Create/view session\n"
            "🗑 **Delete Session** — Remove session\n"
            "📢 **Broadcast** — Send to all groups\n"
            "📊 **Stats** — Bot statistics\n"
            "🏓 **Ping** — Check status\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "**Group Commands:**\n"
            "`/play <song>` — Play music\n"
            "`/search <song>` — Search top 5\n"
            "`/pause` `/resume` `/skip` `/stop`\n"
            "`/queue` `/np` `/ping`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "**Session Flow:**\n"
            "📱 Session → Phone → OTP → ✅ Done!",
            reply_markup=ADMIN_KB,
        )
        return

    if state == "session_phone":
        phone = text
        if not phone.startswith("+") or not phone[1:].isdigit():
            await m.reply(
                "❌ Invalid format!\n\nExample: `+918876543210`\n\nTry again:",
                reply_markup=ADMIN_KB,
            )
            return
        msg = await m.reply(f"📲 Sending OTP to `{phone}` ...")
        tc = Client(f"otp_{uid}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
        try:
            await tc.connect()
            sent = await tc.send_code(phone)
            otp_clients[uid] = tc
            admin_data[uid]   = {"phone": phone, "hash": sent.phone_code_hash}
            admin_state[uid]  = "session_otp"
            await msg.edit(
                "📲 **OTP Sent!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ OTP sent to `{phone}`\n\n"
                "Enter the OTP you received:\n"
                "_Format: 12345 or 1 2 3 4 5_\n\n"
                "⏳ Expires in 2 minutes.\n"
                "Type /cancel to cancel."
            )
        except PhoneNumberInvalid:
            await tc.disconnect()
            await msg.edit("❌ Invalid phone number! Try again.")
            admin_state[uid] = "session_phone"
        except FloodWait as e:
            await tc.disconnect()
            await msg.edit(f"⏳ Flood wait! Try again in `{e.value}` seconds.")
            admin_state.pop(uid, None)
        except Exception as e:
            await tc.disconnect()
            await msg.edit(f"❌ Error: `{e}`\n\nClick 📱 Session to retry.")
            admin_state.pop(uid, None)
        return

    if state == "session_otp":
        otp  = text.replace(" ", "").strip()
        data = admin_data.get(uid, {})
        tc   = otp_clients.get(uid)
        if not tc or not data:
            await m.reply("⚠️ Session expired. Click 📱 Session again.", reply_markup=ADMIN_KB)
            admin_state.pop(uid, None)
            return
        msg = await m.reply("🔐 Verifying OTP...")
        try:
            await tc.sign_in(
                phone_number=data["phone"],
                phone_code_hash=data["hash"],
                phone_code=otp,
            )
            sess = await tc.export_session_string()
            await tc.disconnect()
            otp_clients.pop(uid, None)
            await _activate_session(sess, uid, msg)
        except SessionPasswordNeeded:
            admin_state[uid] = "session_2fa"
            await msg.edit(
                "🔒 **2FA Required**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Send your Telegram 2FA password:\n\n"
                "Type /cancel to cancel."
            )
        except PhoneCodeInvalid:
            await msg.edit("❌ Wrong OTP! Enter the correct OTP:")
        except PhoneCodeExpired:
            await tc.disconnect()
            otp_clients.pop(uid, None)
            admin_state.pop(uid, None)
            await msg.edit("⏰ OTP Expired!\n\nClick 📱 Session → enter phone again.")
        except Exception as e:
            await msg.edit(f"❌ Error: `{e}`")
        return

    if state == "session_2fa":
        pwd  = text.strip()
        data = admin_data.get(uid, {})
        tc   = otp_clients.get(uid)
        if not tc or not data:
            await m.reply("⚠️ Session expired. Click 📱 Session again.", reply_markup=ADMIN_KB)
            admin_state.pop(uid, None)
            return
        msg = await m.reply("🔐 Verifying 2FA password...")
        try:
            await tc.check_password(pwd)
            sess = await tc.export_session_string()
            await tc.disconnect()
            otp_clients.pop(uid, None)
            admin_data.pop(uid, None)
            await _activate_session(sess, uid, msg)
        except Exception as e:
            await msg.edit(f"❌ Wrong password: `{e}`\n\nTry again:")
        return

    if state == "broadcast":
        if not text.startswith("/"):
            admin_data[uid]  = {"bc_text": text}
            admin_state[uid] = "broadcast_confirm"
            await m.reply(
                f"📢 **Preview:**\n\n{text}\n\n"
                f"Send to **{len(groups)} groups**?\n\n"
                "Reply **YES** to confirm, or /cancel.",
                reply_markup=ADMIN_KB,
            )
        return

    if state == "broadcast_confirm":
        if text.upper() == "YES":
            bc_text = admin_data.get(uid, {}).get("bc_text", "")
            admin_state.pop(uid, None)
            admin_data.pop(uid, None)
            prog = await m.reply(f"📡 Sending to {len(groups)} groups...")
            sent, failed = 0, 0
            for cid_str in list(groups.keys()):
                try:
                    await bot.send_message(int(cid_str), bc_text)
                    sent += 1
                except Exception:
                    failed += 1
                await asyncio.sleep(0.5)
            await prog.edit(
                f"📢 **Broadcast Done!**\n\n"
                f"✅ Sent: `{sent}` groups\n"
                f"❌ Failed: `{failed}` groups",
                reply_markup=ADMIN_KB,
            )
        else:
            admin_state[uid] = "broadcast"
            await m.reply("Type your broadcast message or /cancel.", reply_markup=ADMIN_KB)
        return

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CALLBACK: Delete Session
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.on_callback_query(filters.regex(r"^del_session_(yes|no)$") & filters.user(ADMIN_ID))
async def cb_delete_session(_, cq: CallbackQuery):
    global user, call
    if cq.matches[0].group(1) == "no":
        await cq.answer("Cancelled.", show_alert=True)
        await cq.message.delete()
        return
    if call:
        try: await call.stop()
        except Exception: pass
        call = None
    if user:
        try: await user.stop()
        except Exception: pass
        user = None
    delete_session()
    await cq.answer("Session deleted!", show_alert=True)
    await cq.message.edit(
        "🗑 **Session Deleted**\n\n"
        "Voice Chat is now disabled.\n"
        "Click 📱 Session to create a new one."
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /play
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.on_message(filters.command("play") & filters.group)
async def cmd_play(_, m: Message):
    cid_str = str(m.chat.id)
    if cid_str not in groups:
        groups[cid_str] = {"title": m.chat.title or "", "username": m.chat.username or ""}
        save_groups(groups)

    if not vc_ready():
        await m.reply(
            "❌ **Voice Chat not ready!**\n\n"
            "Admin needs to set up session first.\n"
            "_DM the bot → /start → 📱 Session_"
        )
        return

    query = " ".join(m.command[1:]).strip()
    if not query:
        await m.reply(
            "🎵 **How to play music:**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "**Song name se:**\n"
            "`/play Sidhu Moosewala 295`\n"
            "`/play Arijit Singh Tum Hi Ho`\n\n"
            "**Search karke select karo:**\n"
            "`/search Punjabi songs 2024`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━"
        )
        return

    msg = await m.reply("🔍 **Searching on JioSaavn...**")
    chat_id = m.chat.id
    chat_username = m.chat.username or ""

    if vc_ready():
        joined = await ensure_assistant_in_group(chat_id, chat_username)
        if not joined:
            await msg.edit(
                "⚠️ **Assistant ko group mein add karo!**\n\n"
                "Assistant account group ka member nahi hai.\n"
                "Manually add karo, phir `/play` karo. 🎵"
            )
            return

    try:
        track = await asyncio.to_thread(get_audio, query)
    except Exception as e:
        await msg.edit(
            f"❌ **Failed to find song!**\n\n`{e}`\n\n"
            "_Try a different name_"
        )
        return

    track["requested_by"] = m.from_user.first_name if m.from_user else ""

    if chat_id in now_playing:
        try: await call.leave_call(chat_id)
        except Exception: pass
    queues.pop(chat_id, None)
    now_playing[chat_id] = track
    start_times[chat_id] = time.time()
    queues[chat_id] = []

    try:
        await call.play(chat_id, MediaStream(track["url"]))
        await msg.delete()
        await send_now_playing(m, track, chat_id)
    except Exception as e:
        now_playing.pop(chat_id, None)
        start_times.pop(chat_id, None)
        await msg.edit(
            "❌ **Playback Failed!**\n\n"
            f"`{e}`\n\n"
            "**Checklist:**\n"
            "• Bot Admin hai group mein ✅\n"
            "• Voice Chat start hai ✅\n"
            "• Assistant group member hai ✅"
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /search
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.on_message(filters.command("search") & filters.group)
async def cmd_search(_, m: Message):
    if not vc_ready():
        await m.reply("❌ **VC not ready.** Admin needs to set up session.")
        return
    query = " ".join(m.command[1:]).strip()
    if not query:
        await m.reply("⚠️ **Usage:** `/search <song name>`")
        return

    msg = await m.reply("🔍 **Searching top 5 results on JioSaavn...**")
    try:
        results = await asyncio.to_thread(search_yt, query, 5)
    except Exception as e:
        await msg.edit(f"❌ **Search failed:** `{e}`")
        return
    if not results:
        await msg.edit("❌ No results found. Try different keywords.")
        return

    search_cache[m.chat.id] = results
    emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣"]
    lines = ["🔍 **Search Results** — Tap to play:\n━━━━━━━━━━━━━━━━━━━━━━━"]
    buttons = []
    for i, r in enumerate(results):
        dur = fmt_dur(r["duration"])
        lines.append(f"{emojis[i]} **{r['title'][:42]}** `{dur}`")
        buttons.append([InlineKeyboardButton(
            f"{emojis[i]}  {r['title'][:48]}  [{dur}]",
            callback_data=f"sr_{m.chat.id}_{i}"
        )])
    await msg.edit("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))

@bot.on_callback_query(filters.regex(r"^sr_(-?\d+)_(\d+)$"))
async def cb_search_play(_, cq: CallbackQuery):
    if not vc_ready():
        await cq.answer("VC not ready!", show_alert=True)
        return
    chat_id = int(cq.matches[0].group(1))
    idx     = int(cq.matches[0].group(2))
    results = search_cache.get(chat_id, [])
    if idx >= len(results):
        await cq.answer("Results expired. Search again.", show_alert=True)
        return
    track = results[idx]
    track["requested_by"] = cq.from_user.first_name if cq.from_user else ""
    await cq.answer(f"▶️ {track['title'][:30]}")
    await cq.message.edit("🔄 **Loading...**")

    if chat_id in now_playing:
        try: await call.leave_call(chat_id)
        except Exception: pass
    queues.pop(chat_id, None)
    now_playing[chat_id] = track
    start_times[chat_id] = time.time()
    queues[chat_id] = []

    try:
        await call.play(chat_id, MediaStream(track["url"]))
        try:
            await cq.message.delete()
        except Exception:
            pass
        await send_now_playing(cq.message, track, chat_id)
    except Exception as e:
        now_playing.pop(chat_id, None)
        start_times.pop(chat_id, None)
        await cq.message.edit(
            f"❌ **Playback failed:** `{e}`\n\n"
            "Check: Bot is Admin + VC is started"
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PLAYER CALLBACKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.on_callback_query(filters.regex(r"^vc_(pause|resume|skip|stop|queue|shuffle|np)_(-?\d+)$"))
async def cb_player(_, cq: CallbackQuery):
    action  = cq.matches[0].group(1)
    chat_id = int(cq.matches[0].group(2))

    if not vc_ready():
        await cq.answer("VC not active!", show_alert=True)
        return

    if action == "pause":
        try:
            await call.pause(chat_id)
            await cq.answer("⏸ Paused!")
        except Exception as e:
            await cq.answer(str(e)[:100], show_alert=True)

    elif action == "resume":
        try:
            await call.resume(chat_id)
            await cq.answer("▶️ Resumed!")
        except Exception as e:
            await cq.answer(str(e)[:100], show_alert=True)

    elif action == "skip":
        try:
            await call.leave_call(chat_id)
            now_playing.pop(chat_id, None)
            start_times.pop(chat_id, None)
            if queues.get(chat_id):
                await cq.answer("⏭ Skipped!")
                await play_next(chat_id)
            else:
                await cq.answer("⏭ Queue empty.")
                try: await cq.message.edit_reply_markup(None)
                except Exception: pass
        except Exception as e:
            await cq.answer(str(e)[:100], show_alert=True)

    elif action == "stop":
        queues.pop(chat_id, None)
        now_playing.pop(chat_id, None)
        start_times.pop(chat_id, None)
        try: await call.leave_call(chat_id)
        except Exception: pass
        await cq.answer("⏹ Stopped!")
        try: await cq.message.edit_reply_markup(None)
        except Exception: pass
        await cq.message.reply("⏹ **Playback stopped.**")

    elif action == "shuffle":
        import random
        q = queues.get(chat_id, [])
        if not q:
            await cq.answer("Queue is empty!", show_alert=True)
            return
        random.shuffle(q)
        queues[chat_id] = q
        await cq.answer(f"🔀 Shuffled! ({len(q)} songs)")

    elif action == "queue":
        q   = queues.get(chat_id, [])
        cur = now_playing.get(chat_id)
        if not q and not cur:
            await cq.answer("Queue is empty!", show_alert=True)
            return
        lines = []
        if cur:
            lines.append(f"▶️ {cur['title'][:35]} [{fmt_dur(cur['duration'])}]")
        for i, t in enumerate(q[:5], 1):
            lines.append(f"{i}. {t['title'][:30]} [{fmt_dur(t['duration'])}]")
        if len(q) > 5:
            lines.append(f"...+{len(q)-5} more")
        await cq.answer("\n".join(lines), show_alert=True)

    elif action == "np":
        cur = now_playing.get(chat_id)
        if not cur:
            await cq.answer("Nothing is playing!", show_alert=True)
            return
        elapsed = int(time.time() - start_times.get(chat_id, time.time()))
        dur     = cur.get("duration", 0)
        bar     = progress_bar(elapsed, dur, 8)
        await cq.answer(
            f"🎵 {cur['title'][:40]}\n"
            f"⏱ {fmt_dur(elapsed)} {bar} {fmt_dur(dur)}",
            show_alert=True,
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GROUP COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@bot.on_message(filters.command("pause") & filters.group)
async def cmd_pause(_, m: Message):
    if not vc_ready() or m.chat.id not in now_playing:
        await m.reply("⚠️ Nothing is playing!")
        return
    try:
        await call.pause(m.chat.id)
        await m.reply("⏸ **Paused!**", reply_markup=player_kb(m.chat.id))
    except Exception as e:
        await m.reply(f"❌ `{e}`")

@bot.on_message(filters.command("resume") & filters.group)
async def cmd_resume(_, m: Message):
    if not vc_ready() or m.chat.id not in now_playing:
        await m.reply("⚠️ Nothing is playing!")
        return
    try:
        await call.resume(m.chat.id)
        await m.reply("▶️ **Resumed!**", reply_markup=player_kb(m.chat.id))
    except Exception as e:
        await m.reply(f"❌ `{e}`")

@bot.on_message(filters.command("skip") & filters.group)
async def cmd_skip(_, m: Message):
    chat_id = m.chat.id
    if not vc_ready() or chat_id not in now_playing:
        await m.reply("⚠️ Nothing is playing!")
        return
    try:
        await call.leave_call(chat_id)
        now_playing.pop(chat_id, None)
        start_times.pop(chat_id, None)
        if queues.get(chat_id):
            await m.reply("⏭ **Skipped!**")
            await play_next(chat_id)
        else:
            await m.reply("⏭ **Skipped! Queue is empty.**")
    except Exception as e:
        await m.reply(f"❌ `{e}`")

@bot.on_message(filters.command("stop") & filters.group)
async def cmd_stop(_, m: Message):
    chat_id = m.chat.id
    queues.pop(chat_id, None)
    now_playing.pop(chat_id, None)
    start_times.pop(chat_id, None)
    if vc_ready():
        try: await call.leave_call(chat_id)
        except Exception: pass
    await m.reply("⏹ **Stopped! Left Voice Chat.**")

@bot.on_message(filters.command(["queue", "q"]) & filters.group)
async def cmd_queue(_, m: Message):
    chat_id = m.chat.id
    cur = now_playing.get(chat_id)
    q   = queues.get(chat_id, [])
    if not cur and not q:
        await m.reply("📋 Queue is empty! Use `/play` to start.")
        return
    lines = ["📋 **Queue**\n━━━━━━━━━━━━━━━━━━━━━━━"]
    if cur:
        elapsed = int(time.time() - start_times.get(chat_id, time.time()))
        bar     = progress_bar(elapsed, cur.get("duration", 0), 8)
        lines.append(
            f"▶️ **Now Playing:**\n"
            f"🎵 {cur['title'][:45]}\n"
            f"⏱ `{fmt_dur(elapsed)}` {bar} `{fmt_dur(cur['duration'])}`"
        )
    if q:
        lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━\n📋 **Up Next ({len(q)} songs):**")
        for i, t in enumerate(q[:10], 1):
            lines.append(f"`{i:02d}.` {t['title'][:40]} `[{fmt_dur(t['duration'])}]`")
        if len(q) > 10:
            lines.append(f"_...and {len(q)-10} more_")
    await m.reply("\n".join(lines))

@bot.on_message(filters.command("np") & filters.group)
async def cmd_np(_, m: Message):
    cur = now_playing.get(m.chat.id)
    if not cur:
        await m.reply("⚠️ Nothing is playing!")
        return
    await send_now_playing(m, cur, m.chat.id)

@bot.on_message(filters.command("ping"))
async def cmd_ping(_, m: Message):
    vc = "✅ Ready" if vc_ready() else "⚠️ Not set"
    await m.reply(
        "🏓 **Pong!**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Bot: Online ✅\n"
        f"🎵 VC: {vc}"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def main():
    global user, call
    await bot.start()
    me = await bot.get_me()
    print(f"[✅] Bot: @{me.username}")
    print(f"[✅] Admin ID: {ADMIN_ID}")
    print(f"[✅] Groups tracked: {len(groups)}")

    session = load_session()
    if session:
        try:
            user = Client("user_client", api_id=API_ID, api_hash=API_HASH,
                          session_string=session, in_memory=True)
            call = PyTgCalls(user)
            setup_call_handlers()
            await user.start()
            await call.start()
            vc_me = await user.get_me()
            print(f"[✅] Assistant: @{vc_me.username or vc_me.first_name} | VC READY")
        except Exception as e:
            print(f"[⚠️] Session load failed: {e}")
            user = call = None
    else:
        print(f"[⚠️] No session. DM @{me.username} → 📱 Session → enter phone")

    print(f"[🔗] Add to group: https://t.me/{me.username}?startgroup=true")
    await idle()

    await bot.stop()
    if user:
        try: await user.stop()
        except Exception: pass

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
