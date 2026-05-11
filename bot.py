import os
import asyncio
import tempfile
import subprocess
import logging
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

import yt_dlp
import whisper
from deep_translator import GoogleTranslator

# ─────────────────────────────────────────
#  إعدادات
# ─────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TARGET_LANG = os.environ.get("TARGET_LANG", "ar")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "tiny")
TEMP_DIR = Path(tempfile.gettempdir()) / "tg_video_translator"
TEMP_DIR.mkdir(exist_ok=True)
CHUNK_MINUTES = 10  # كل جزء 10 دقائق

DEVELOPER = "𝑨𝒃𝒐-𝑲𝒂𝒛𝒆𝒎"
INSTAGRAM_URL = "https://www.instagram.com/of65i/"
TIKTOK_URL = "https://www.tiktok.com/@13it_"
TELEGRAM_USER = "of65i"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

log.info(f"⏳ تحميل نموذج Whisper ({WHISPER_MODEL})…")
WHISPER = whisper.load_model(WHISPER_MODEL)
log.info("✅ نموذج Whisper جاهز")


# ─────────────────────────────────────────
#  أوامر البوت
# ─────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        f"👋 *أهلاً وسهلاً بك!*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🎬 *بوت ترجمة الفيديوهات*\n\n"
        f"وظيفتي بسيطة:\n"
        f"أرسل لي رابط أي فيديو ← وأعيده لك *مترجماً مع ترجمة محروقة داخل الفيديو* 🔥\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ *المواقع المدعومة:*\n\n"
        f"▪️ يوتيوب 🎥 (فيديوهات + Shorts)\n"
        f"▪️ تيك توك 🎵\n"
        f"▪️ انستغرام 📸 (Reels + Posts)\n"
        f"▪️ فيسبوك 👥\n"
        f"▪️ تويتر/X 🐦\n"
        f"▪️ ديلي موشن 🎞️\n"
        f"▪️ ريديت 🤖\n"
        f"▪️ وأكثر من 1000 موقع آخر!\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 *الأوامر:*\n"
        f"/start – الصفحة الرئيسية\n"
        f"/lang – تغيير لغة الترجمة\n"
        f"/help – المساعدة والتواصل\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 *المطوّر:* {DEVELOPER}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📖 *كيفية الاستخدام:*\n\n"
        f"1️⃣ انسخ رابط الفيديو من أي موقع\n"
        f"2️⃣ أرسله مباشرة هنا في المحادثة\n"
        f"3️⃣ انتظر ⏳ (الفيديوهات الطويلة تأخذ وقتاً أطول)\n"
        f"4️⃣ يصلك الفيديو كاملاً مع الترجمة المحروقة ✅\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ *ملاحظات:*\n"
        f"• لا يوجد حد للطول أو الحجم\n"
        f"• الفيديوهات الطويلة تُعالج على أجزاء وتُجمع تلقائياً\n"
        f"• الفيديوهات الكبيرة تُرسل كملف\n"
        f"• الترجمة الافتراضية: العربية\n"
        f"• استخدم /lang لتغيير اللغة\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 *المطوّر:* {𝑨𝒃𝒐-𝑲𝒂𝒛𝒆𝒎}\n\n"
        f"📱 *تواصل مع المطوّر:*\n"
        f"▪️ انستغرام: {https://www.instagram.com/of65i/}\n"
        f"▪️ تيك توك: {https://www.tiktok.com/@13it_}\n"
        f"▪️ تيليغرام: @{of65i}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def lang_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    langs = [
        ("🇸🇦 العربية", "ar"),
        ("🇬🇧 الإنجليزية", "en"),
        ("🇫🇷 الفرنسية", "fr"),
        ("🇩🇪 الألمانية", "de"),
        ("🇹🇷 التركية", "tr"),
        ("🇮🇳 الهندية", "hi"),
        ("🇪🇸 الإسبانية", "es"),
        ("🇷🇺 الروسية", "ru"),
    ]
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"lang:{code}")]
        for name, code in langs
    ]
    await update.message.reply_text(
        "🌍 *اختر لغة الترجمة:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def lang_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data.split(":")[1]
    ctx.user_data["lang"] = code
    lang_names = {
        "ar": "العربية 🇸🇦", "en": "الإنجليزية 🇬🇧", "fr": "الفرنسية 🇫🇷",
        "de": "الألمانية 🇩🇪", "tr": "التركية 🇹🇷", "hi": "الهندية 🇮🇳",
        "es": "الإسبانية 🇪🇸", "ru": "الروسية 🇷🇺",
    }
    await query.edit_message_text(
        f"✅ تم تعيين لغة الترجمة إلى: *{lang_names.get(code, code)}*",
        parse_mode=ParseMode.MARKDOWN
    )


# ─────────────────────────────────────────
#  معالج الروابط
# ─────────────────────────────────────────
async def handle_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    user_id = update.effective_user.id
    target_lang = ctx.user_data.get("lang", TARGET_LANG)

    status_msg = await update.message.reply_text("⏬ جارٍ تنزيل الفيديو…")

    work_dir = TEMP_DIR / str(user_id)
    work_dir.mkdir(exist_ok=True)

    try:
        # 1. تنزيل الفيديو
        video_path = await asyncio.get_event_loop().run_in_executor(
            None, lambda: download_video(url, work_dir)
        )
        if not video_path:
            await status_msg.edit_text("❌ تعذّر تنزيل الفيديو. تأكد من الرابط.")
            return

        # 2. معرفة مدة الفيديو
        duration = get_duration(video_path)
        log.info(f"مدة الفيديو: {duration:.1f} ثانية")

        chunk_sec = CHUNK_MINUTES * 60
        total_chunks = max(1, -(-int(duration) // chunk_sec))  # تقريب للأعلى

        if total_chunks == 1:
            await status_msg.edit_text("🧠 جارٍ معالجة الفيديو…")
        else:
            await status_msg.edit_text(
                f"📦 الفيديو طويل! سيُقسّم إلى {total_chunks} أجزاء وتُجمع تلقائياً ✅"
            )
            await asyncio.sleep(2)

        # 3. تقسيم الفيديو إلى أجزاء
        chunks = split_video(video_path, work_dir, chunk_sec)

        processed_chunks = []
        for i, chunk_path in enumerate(chunks, 1):
            if total_chunks > 1:
                await status_msg.edit_text(
                    f"⚙️ جارٍ معالجة الجزء {i} من {total_chunks}…\n"
                    f"{'▓' * i}{'░' * (total_chunks - i)} {int(i/total_chunks*100)}%"
                )

            # استخراج الصوت
            audio_path = work_dir / f"audio_{i}.wav"
            await asyncio.get_event_loop().run_in_executor(
                None, lambda c=chunk_path, a=audio_path: extract_audio(c, a)
            )

            # نسخ الكلام
            segments = await asyncio.get_event_loop().run_in_executor(
                None, lambda a=audio_path: transcribe(a)
            )

            # حذف ملف الصوت فوراً لتوفير المساحة
            audio_path.unlink(missing_ok=True)

            if not segments:
                # لا يوجد كلام في هذا الجزء، أضفه بدون ترجمة
                processed_chunks.append(chunk_path)
                continue

            # الترجمة
            translated = await asyncio.get_event_loop().run_in_executor(
                None, lambda s=segments: translate_segments(s, target_lang)
            )

            # كتابة SRT
            srt_path = work_dir / f"subs_{i}.srt"
            write_srt(translated, srt_path)

            # حرق الترجمة
            output_chunk = work_dir / f"output_{i}.mp4"
            await asyncio.get_event_loop().run_in_executor(
                None, lambda c=chunk_path, s=srt_path, o=output_chunk: burn_subtitles(c, s, o)
            )

            # تنظيف
            srt_path.unlink(missing_ok=True)
            chunk_path.unlink(missing_ok=True)
            processed_chunks.append(output_chunk)

        # 4. دمج الأجزاء
        if len(processed_chunks) > 1:
            await status_msg.edit_text("🔗 جارٍ دمج الأجزاء في فيديو واحد…")
            final_path = work_dir / "final.mp4"
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: merge_chunks(processed_chunks, final_path)
            )
            for c in processed_chunks:
                c.unlink(missing_ok=True)
        else:
            final_path = processed_chunks[0]

        # 5. إرسال الفيديو
        output_size_mb = final_path.stat().st_size / (1024 * 1024)
        await status_msg.edit_text(f"📤 جارٍ رفع الفيديو ({output_size_mb:.1f}MB)…")

        caption = f"✅ *الفيديو مع الترجمة*\n👨‍💻 بواسطة {DEVELOPER}"

        with open(final_path, "rb") as f:
            if output_size_mb <= 50:
                await update.message.reply_video(
                    video=f,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    supports_streaming=True,
                )
            else:
                await update.message.reply_document(
                    document=f,
                    filename="translated_video.mp4",
                    caption=caption + "\n\n📁 _تم إرساله كملف بسبب الحجم الكبير_",
                    parse_mode=ParseMode.MARKDOWN,
                )

        await status_msg.delete()

    except Exception as e:
        log.error(f"خطأ: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ حدث خطأ: {str(e)[:200]}")

    finally:
        # تنظيف كل الملفات المؤقتة
        for f in work_dir.glob("*"):
            try:
                f.unlink()
            except Exception:
                pass


# ─────────────────────────────────────────
#  وظائف المساعدة
# ─────────────────────────────────────────
def download_video(url: str, work_dir: Path):
    out_template = str(work_dir / "video.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 60,
        "retries": 3,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android_vr", "android", "web"],
            }
        },
        "http_headers": {
            "User-Agent": "com.google.android.youtube/17.36.4 (Linux; U; Android 12) gzip",
        },
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            return None
        filename = ydl.prepare_filename(info)
        path = Path(filename)
        if not path.exists():
            mp4 = path.with_suffix(".mp4")
            if mp4.exists():
                return mp4
            for f in work_dir.glob("video.*"):
                return f
        return path


def get_duration(video: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def split_video(video: Path, work_dir: Path, chunk_sec: int) -> list:
    duration = get_duration(video)
    if duration <= chunk_sec:
        return [video]

    chunks = []
    start = 0
    i = 1
    while start < duration:
        chunk_path = work_dir / f"chunk_{i}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video),
             "-ss", str(start), "-t", str(chunk_sec),
             "-c", "copy", str(chunk_path)],
            check=True, capture_output=True,
        )
        chunks.append(chunk_path)
        start += chunk_sec
        i += 1

    return chunks


def extract_audio(video: Path, out: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video),
         "-vn", "-ar", "16000", "-ac", "1", str(out)],
        check=True, capture_output=True,
    )


def transcribe(audio: Path) -> list:
    result = WHISPER.transcribe(str(audio), task="transcribe", fp16=False)
    return result.get("segments", [])


def translate_segments(segments: list, target: str) -> list:
    translator = GoogleTranslator(source="auto", target=target)
    out = []
    batch_size = 10
    for i in range(0, len(segments), batch_size):
        batch = segments[i:i+batch_size]
        texts = [seg.get("text", "").strip() for seg in batch if seg.get("text", "").strip()]
        if not texts:
            continue
        try:
            joined = "\n".join(texts)
            translated = translator.translate(joined)
            translated_list = translated.split("\n") if translated else texts
        except Exception:
            translated_list = texts

        j = 0
        for seg in batch:
            text = seg.get("text", "").strip()
            if not text:
                continue
            tr = translated_list[j] if j < len(translated_list) else text
            out.append({"start": seg["start"], "end": seg["end"], "text": tr})
            j += 1
    return out


def write_srt(segments: list, path: Path):
    def fmt(t: float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t % 1) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    with open(path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{fmt(seg['start'])} --> {fmt(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")


def burn_subtitles(video: Path, srt: Path, output: Path):
    subtitle_filter = (
        f"subtitles='{srt}':"
        "force_style='FontName=Noto Sans,FontSize=18,PrimaryColour=&Hffffff,"
        "OutlineColour=&H000000,BackColour=&H80000000,"
        "Bold=1,Outline=2,Shadow=1,Alignment=2,MarginV=15'"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", subtitle_filter,
            "-c:v", "libx264", "-crf", "28",
            "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "96k",
            str(output),
        ],
        check=True, capture_output=True,
    )


def merge_chunks(chunks: list, output: Path):
    # إنشاء ملف قائمة الأجزاء
    list_file = output.parent / "chunks_list.txt"
    with open(list_file, "w") as f:
        for chunk in chunks:
            f.write(f"file '{chunk}'\n")

    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(list_file),
         "-c", "copy", str(output)],
        check=True, capture_output=True,
    )
    list_file.unlink(missing_ok=True)


# ─────────────────────────────────────────
#  تشغيل البوت
# ─────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("lang", lang_cmd))
    app.add_handler(CallbackQueryHandler(lang_callback, pattern="^lang:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    log.info("🤖 البوت يعمل…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
