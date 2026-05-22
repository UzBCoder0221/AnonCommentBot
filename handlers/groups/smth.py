from aiogram import Router, types, F
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.session.middlewares.request_logging import logger
from loader import db, bot
from datetime import datetime
import re

router = Router()

EMOJI_PATTERN = re.compile(
    r'^[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF'
    r'\U0001F1E0-\U0001F1FF\U0001F600-\U0001F64F'
    r'\U0001F680-\U0001F6FF\u200D\uFE0F\u20E3'
    r'\U0001F1F2-\U0001F1F4\U0001F1E6-\U0001F1FF]+$'
)

EDIT_PATTERN = re.compile(r'^#USER_(\d+)$')


def is_single_emoji(text: str) -> bool:
    if not text:
        return False
    text = text.strip()
    if not text:
        return False
    return bool(EMOJI_PATTERN.match(text))


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _get_reply_post(chat_id: int, reply_msg_id: int):
    """Try to find the post by to_message_id (bot copy) first, then by original message_id."""
    post = db.select_post(to_message_id=reply_msg_id)
    if not post:
        post = db.select_post(to_id=chat_id, message_id=reply_msg_id)
    return post


def _get_reply_user(reply_post):
    """Get anon_name of user who wrote the reply target."""
    if not reply_post:
        return None
    reply_up = db.select_user_post(post=reply_post[0])
    if reply_up:
        reply_user = db.select_user(id=reply_up[1])
        if reply_user:
            return reply_user[2]
    return None


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def group_message_handler(message: types.Message):
    if message.from_user.is_bot:
        return
    chat_id = message.chat.id
    user = message.from_user
    msg_id = message.message_id
    is_reply = message.reply_to_message is not None
    reply_id = message.reply_to_message.message_id if is_reply else None
    content = message.text or message.caption or ""


    sender = db.get_or_create_user(
        telegram_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username
    )
    sender_anon_name = sender[2]

    # --- Single emoji = REACTION --- #
    if is_single_emoji(content) and is_reply:
        reply_post = _get_reply_post(chat_id, reply_id)
        if reply_post:
            uid = sender[0]
            if db.select_reaction(user=uid, post=reply_post[0]):
                await message.delete()
                return
            db.add_reaction(uid, reply_post[0], content)
            reactions = db.select_reactions(post=reply_post[0])
            org = message.reply_to_message.html_text or message.reply_to_message.caption or ""
            tmp = org.split('\n')
            if tmp[-1].startswith('<blockquote>'):
                org = ''.join(tmp[:-1])
            org += "\n\n<blockquote>REACTIONS: "
            for i in reactions:
                org+=f"{i[1]}x{i[0]}  "
            org += "</blockquote>"

            try:
                if message.reply_to_message.caption:
                    await bot.edit_message_caption(chat_id=chat_id, message_id=reply_post[3], caption=org)
                else:
                    await bot.edit_message_text(text=org, chat_id=chat_id, message_id=reply_post[3])
                await message.delete()
            except Exception as e:
                logger.error(e)
            return

        ####    FALLBACK LOGIC HERE    ####


    # --- Edit-by-reference: edit "*new text" ---
    if content[0] == "*" and is_reply:
        tmp = message.reply_to_message.html_text.split('\n\n')
        new_text = tmp[0] + content[1:] + tmp[2] if len(tmp) == 3 else ''
        post = db.select_post(to_message_id=reply_id)
        user = db.select_user(telegram_id=user.id)
        user_post = db.select_user_post(post=post[0], user=user[0])
        if user_post:
            try:
                if message.reply_to_message.caption:
                    await bot.edit_message_caption(chat_id=chat_id, message_id=post[3], caption=new_text)
                else:
                    await bot.edit_message_text(text=new_text, chat_id=chat_id, message_id=post[3])
                await message.delete()
            except Exception as e:
                logger.error(e)
        return


    # --- Normal message ---
    lines = [f"<blockquote>#{sender_anon_name}</blockquote>"]

    reply_post = None
    if message.reply_to_message:
        reply_post = _get_reply_post(chat_id, reply_id)
        reply_user = _get_reply_user(reply_post)
        if reply_user:
            lines.append(f"<blockquote>#REPLY_TO #{reply_user}</blockquote>")
            lines.append(f"<blockquote>#REPLY_TO_MESSAGE #MESSAGE_{reply_post[0]}</blockquote>")
    # lines.append(f"<blockquote>#MESSAGE_{last_post[0]}</blockquote>")
    # todo: fix last post (unbounded)

    if content:
        escaped = _esc(content)
        lines.append(f'\n{escaped}')

    msg = "\n".join(lines)
    # Send message to group
    if message.photo:
        sent = await bot.send_photo(
            chat_id=chat_id, photo=message.photo[-1].file_id,
            caption=msg, parse_mode=ParseMode.HTML
        )
    elif message.video:
        sent = await bot.send_video(
            chat_id=chat_id, video=message.video.file_id,
            caption=msg, parse_mode=ParseMode.HTML
        )
    elif message.animation:
        sent = await bot.send_animation(
            chat_id=chat_id, animation=message.animation.file_id,
            caption=msg, parse_mode=ParseMode.HTML
        )
    else:
        sent = await bot.send_message(
            chat_id=chat_id, text=msg, parse_mode=ParseMode.HTML
        )

    # Save to DB
    db.add_post(
        to_id=chat_id, message_id=msg_id,
        to_message_id=sent.message_id, channel_id=chat_id,
        created_at=datetime.now()
    )
    last_post = db.select_post(to_id=chat_id, message_id=msg_id)
    if last_post:
        db.add_user_post(user=sender[0], post=last_post[0])

    await message.delete()
