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

EDIT_PATTERN = re.compile(r'^#(\d+)\s+(.+)$')


def is_single_emoji(text: str) -> bool:
    if not text:
        return False
    text = text.strip()
    if not text:
        return False
    return bool(EMOJI_PATTERN.match(text))


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def group_message_handler(message: types.Message):
    if message.from_user.is_bot:
        return
    chat_id = message.chat.id
    user = message.from_user

    db_user = db.get_or_create_user(
        telegram_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username
    )
    anon_name = db_user[2]
    content = message.text or message.caption or ""

    # Edit-by-reference: "#123 new text" edits post 123
    edit_match = EDIT_PATTERN.match(content)
    if edit_match:
        target_post_id = int(edit_match.group(1))
        new_text = edit_match.group(2)
        post = db.select_post(id=target_post_id)
        if post:
            up = db.select_user_post(post=target_post_id)
            if up and up[1] == db_user[0]:
                escaped = new_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                lines = [f"<b>{anon_name} (edited)</b>", escaped]
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id, message_id=post[3],
                        text="\n".join(lines), parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.info(f"Edit failed: {e}")
        await message.delete()
        return

    # Single emoji = reaction
    if is_single_emoji(content):
        if message.reply_to_message:
            target_post = db.select_post(
                to_id=chat_id, message_id=message.reply_to_message.message_id
            )
        else:
            target_post = db.select_last_post(to_id=chat_id)
        if not target_post:
            return
        target_post_id = target_post[0]
        now_ts = int(datetime.now().timestamp())
        db.add_reaction(
            user=db_user[0], post=target_post_id,
            reaction=content.strip(), created_at=now_ts
        )
        await message.delete()
        return

    # Build bot's message
    lines = [f"<b>{anon_name}</b>"]

    if message.reply_to_message:
        reply_post = db.select_post(
            to_id=chat_id, message_id=message.reply_to_message.message_id
        )
        if reply_post:
            reply_up = db.select_user_post(post=reply_post[0])
            if reply_up:
                reply_user = db.select_user(id=reply_up[1])
                if reply_user:
                    lines.append(f"└─ #{reply_post[0]} <b>{reply_user[2]}</b>")

    if content:
        escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(escaped)

    if message.photo:
        sent = await bot.send_photo(
            chat_id=chat_id, photo=message.photo[-1].file_id,
            caption="\n".join(lines), parse_mode=ParseMode.HTML
        )
    elif message.video:
        sent = await bot.send_video(
            chat_id=chat_id, video=message.video.file_id,
            caption="\n".join(lines), parse_mode=ParseMode.HTML
        )
    elif message.animation:
        sent = await bot.send_animation(
            chat_id=chat_id, animation=message.animation.file_id,
            caption="\n".join(lines), parse_mode=ParseMode.HTML
        )
    else:
        sent = await bot.send_message(
            chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML
        )

    db.add_post(
        to_id=chat_id, message_id=message.message_id,
        to_message_id=sent.message_id, channel_id=chat_id,
        created_at=datetime.now()
    )
    last_post = db.select_post(to_id=chat_id, message_id=message.message_id)
    if last_post:
        db.add_user_post(user=db_user[0], post=last_post[0])

    await message.delete()


@router.edited_message(F.chat.type.in_({"group", "supergroup"}))
async def group_edit_handler(message: types.Message):
    if message.from_user.is_bot:
        return
    chat_id = message.chat.id
    post = db.select_post(to_id=chat_id, message_id=message.message_id)
    if not post:
        return

    user = message.from_user
    db_user = db.get_or_create_user(
        telegram_id=user.id, first_name=user.first_name,
        last_name=user.last_name, username=user.username
    )
    content = message.text or message.caption or ""
    lines = [f"<b>{db_user[2]} (edited)</b>"]
    if content:
        escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(escaped)

    try:
        if message.photo or message.video or message.animation:
            await bot.edit_message_caption(
                chat_id=chat_id, message_id=post[3],
                caption="\n".join(lines), parse_mode=ParseMode.HTML
            )
        else:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=post[3],
                text="\n".join(lines), parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.info(f"Edit failed: {e}")


@router.message_reaction()
async def group_reaction_handler(reaction: types.MessageReactionUpdated):
    if reaction.chat.type not in ("group", "supergroup"):
        return
    user = reaction.user
    db_user = db.select_user(telegram_id=user.id)
    if not db_user:
        return
    new_emojis = [r.emoji for r in reaction.new_reaction if r.emoji]
    if not new_emojis:
        return
    post = db.select_post(to_id=reaction.chat.id, message_id=reaction.message_id)
    if not post:
        return
    now_ts = int(datetime.now().timestamp())
    for emoji in new_emojis:
        db.add_reaction(user=db_user[0], post=post[0], reaction=emoji, created_at=now_ts)