import os
import asyncio
import subprocess
from datetime import datetime, timedelta
from pytz import timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dateutil.parser import parse
import json

def get_channel_url(channel_name):
    try:
        with open("chann.json", "r") as f:
            data = json.load(f)
        return data.get(channel_name.lower())
    except Exception as e:
        print(f"Error loading channel JSON: {e}")
        return None

BOT_TOKEN = os.environ.get("8171747104:AAEexB4MhCSpPQ4Xad70LSzpqw_NX0arVBc")
ALLOWED_GROUP_ID = -1002558109345
IST = timezone("Asia/Kolkata")

async def record_stream(url, duration, filename):
    try:
        process = await asyncio.create_subprocess_exec(
            '/usr/bin/ffmpeg', '-y', '-i', url, '-t', str(duration), '-c', 'copy', filename,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if stdout:
            print(f"FFMPEG Output: {stdout.decode()}")
        if stderr:
            print(f"FFMPEG Error: {stderr.decode()}")
    except Exception as e:
        print(f"[FFMPEG ERROR] {e}")

def parse_time_str_to_aware_datetime(time_str):
    try:
        naive_time = parse(time_str)
        aware_time = IST.localize(naive_time)
        return aware_time
    except Exception as e:
        raise ValueError(f"❌ Invalid time format: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "*🌟 Welcome to the Video Recording Bot!*\n\n"
        "This bot allows you to record video streams for scheduled or instant times.\n\n"
        "📝 *Commands:*\n"
        "- `/start` - Welcome message\n"
        "- `/record URL start_time end_time` - Schedule a recording\n"
        "- `/rsec URL start_offset duration` - Record for seconds\n"
        "- `/mrr Channel start_time end_time`\n"
        "- `/mrr_sec Channel start_offset duration`\n\n"
        "📆 *Example:* `/record http://example.com 10:00 10:05`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_recording(update: Update, context: ContextTypes.DEFAULT_TYPE, url, start_time, end_time):
    now = datetime.now(IST)
    start_time_str = start_time.strftime('%I:%M:%S %p')
    end_time_str = end_time.strftime('%I:%M:%S %p')
    wait_time = (start_time - now).total_seconds()
    duration = int((end_time - start_time).total_seconds())

    if wait_time > 0:
        await asyncio.sleep(wait_time)

    filename = f"rec_{update.effective_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ts"

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"⚙️ *Recording started... Sit back & relax!*",
        parse_mode="Markdown"
    )

    await record_stream(url, duration, filename)

    try:
        max_size = 50 * 1024 * 1024
        if os.path.getsize(filename) > max_size:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="✂️ *Video too long, splitting...*", parse_mode="Markdown")
            part_num = 1
            split_cmd = [
                "/usr/bin/ffmpeg", "-i", filename, "-c", "copy", "-f", "segment",
                "-segment_time", "300", f"part_%03d.ts"
            ]
            subprocess.run(split_cmd)
            for file in sorted(f for f in os.listdir('.') if f.startswith("part_")):
                with open(file, 'rb') as f:
                    await context.bot.send_video(chat_id=update.effective_chat.id, video=f, caption=f"🎬 *Part {part_num}*", parse_mode="Markdown")
                os.remove(file)
                part_num += 1
            os.remove(filename)
        else:
            with open(filename, 'rb') as f:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=f,
                    caption=f"✅ *Recording Complete!*\nDeveloper: *Lover*\nStart: `{start_time_str}`\nEnd: `{end_time_str}`",
                    parse_mode="Markdown"
                )
            os.remove(filename)

    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error sending video: {e}")

async def set_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id != ALLOWED_GROUP_ID:
        await update.message.reply_text("🚫 *Not allowed here.*", parse_mode="Markdown")
        return

    try:
        url = context.args[0]
        start_time_str = context.args[1]
        end_time_str = context.args[2]

        start_time = parse_time_str_to_aware_datetime(start_time_str)
        end_time = parse_time_str_to_aware_datetime(end_time_str)
        now = datetime.now(IST)

        if end_time <= start_time:
            await update.message.reply_text("❌ *End time must be after start time.*", parse_mode="Markdown")
            return
        if start_time <= now:
            await update.message.reply_text(f"⏰ *Scheduled time is in the past.* Now: `{now.strftime('%I:%M %p')}`", parse_mode="Markdown")
            return

        await update.message.reply_text(
            f"✅ *Schedule Set!*\n\n🕐 From: `{start_time_str}`\n🕑 To: `{end_time_str}`",
            parse_mode="Markdown"
        )

        asyncio.create_task(handle_recording(update, context, url, start_time, end_time))

    except Exception as e:
        await update.message.reply_text(f"❌ *Error:* {e}", parse_mode="Markdown")

async def record_seconds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id != ALLOWED_GROUP_ID:
        await update.message.reply_text("🚫 *Not allowed here.*", parse_mode="Markdown")
        return

    try:
        url = context.args[0]
        start_offset = int(context.args[1])
        duration = int(context.args[2])

        now = datetime.now(IST)
        start_time = now + timedelta(seconds=start_offset)
        end_time = start_time + timedelta(seconds=duration)

        await update.message.reply_text(
            f"⚡ *Recording will start in* `{start_offset}s` *for* `{duration}s`...",
            parse_mode="Markdown"
        )

        asyncio.create_task(handle_recording(update, context, url, start_time, end_time))

    except Exception as e:
        await update.message.reply_text(f"❌ *Error:* {e}", parse_mode="Markdown")

async def mrr_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id != ALLOWED_GROUP_ID:
        await update.message.reply_text("🚫 *Not allowed here.*", parse_mode="Markdown")
        return

    try:
        channel = context.args[0]
        start_time_str = context.args[1]
        end_time_str = context.args[2]

        url = get_channel_url(channel)
        if not url:
            await update.message.reply_text(f"❌ *Invalid channel name:* `{channel}`", parse_mode="Markdown")
            return

        start_time = parse_time_str_to_aware_datetime(start_time_str)
        end_time = parse_time_str_to_aware_datetime(end_time_str)
        now = datetime.now(IST)

        if end_time <= start_time:
            await update.message.reply_text("❌ *End time must be after start time.*", parse_mode="Markdown")
            return
        if start_time <= now:
            await update.message.reply_text(f"⏰ *Scheduled time is in the past.*", parse_mode="Markdown")
            return

        await update.message.reply_text(
            f"✅ *Scheduled for channel:* `{channel}`\n🕐 From: `{start_time_str}`\n🕑 To: `{end_time_str}`",
            parse_mode="Markdown"
        )

        asyncio.create_task(handle_recording(update, context, url, start_time, end_time))

    except Exception as e:
        await update.message.reply_text(f"❌ *Error:* {e}", parse_mode="Markdown")

async def mrr_sec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.id != ALLOWED_GROUP_ID:
        await update.message.reply_text("🚫 *Not allowed here.*", parse_mode="Markdown")
        return

    try:
        channel = " ".join(context.args[:-2])
        start_offset = int(context.args[-2])
        duration = int(context.args[-1])

        url = get_channel_url(channel)
        if not url:
            await update.message.reply_text(f"❌ Invalid channel: `{channel}`", parse_mode="Markdown")
            return

        now = datetime.now(IST)
        start_time = now + timedelta(seconds=start_offset)
        end_time = start_time + timedelta(seconds=duration)

        await update.message.reply_text(
            f"⚡ *Recording channel:* `{channel}`\nStarts in `{start_offset}s` for `{duration}s`...",
            parse_mode="Markdown"
        )

        asyncio.create_task(handle_recording(update, context, url, start_time, end_time))

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("record", set_schedule))
    app.add_handler(CommandHandler("rsec", record_seconds))
    app.add_handler(CommandHandler("mrr", mrr_set))
    app.add_handler(CommandHandler("mrr_sec", mrr_sec))
    app.run_polling()

if __name__ == "__main__":
    main()