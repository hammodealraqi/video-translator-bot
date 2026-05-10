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
TARGET_LANG = os.environ.get("TARGET_LANG", "ar")          # لغة الترجمة الافتراضية
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")    # tiny/base/small/medium
MAX_VIDEO_SIZE_MB = int(os.environ.get("MAX_VIDEO_SIZE_MB", "50"))
TEMP_DIR = Path(tempfile.gettempdir()) / "tg_video_translator"
TEMP_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# تحميل نموذج Whisper مرة واحدة عند بدء التشغيل
log.info(f"⏳ تحميل نموذج Whisper ({WHISPER_MODEL})…")
WHISPER = whisper.load_model(WHISPER_MODEL)
log.info("✅ نموذج Whisper جاهز")


# ─────────────────────────────────────────
#  أوامر البوت
# ─────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 *بوت ترجمة الفيديوهات*\n\n"
        "أرسل لي رابط أي فيديو من:\n"
        "• يوتيوب (فيديو كامل أو Shorts)\n"
        "• انستغرام (Reels / Posts)\n"
        "• فيسبوك\n"
        "• تيك توك\n"
        "• تويتر/X\n"
        "• وأي موقع آخر مدعوم!\n\n"
        "وسأعيد إليك الفيديو *مع ترجمة محروقة* 🔥\n\n"
        "الأوامر:\n"
        "/start – هذه الرسالة\n"
        "/lang – تغيير لغة الترجمة\n"
        "/help – المساعدة"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *كيفية الاستخدام:*\n\n"
        "1️⃣ انسخ رابط الفيديو\n"
        "2️⃣ أرسله مباشرة في المحادثة\n"
        "3️⃣ انتظر قليلاً ⏳\n"
        "4️⃣ ستصلك الفيديو مع الترجمة المحروقة ✅\n\n"
        "⚠️ *ملاحظات:*\n"
        f"• الحد الأقصى لحجم الفيديو: {MAX_VIDEO_SIZE_MB}MB\n"
        "• الحد الأقصى للمدة: 10 دقائق\n"
        "• الترجمة الافتراضية: العربية\n\n"
        "💡 استخدم /lang لتغيير لغة الترجمة"
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
        "🌍 اختر لغة الترجمة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def lang_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data.split(":")[1]
    ctx.user_data["lang"] = code
    lang_names = {
        "ar": "العربية", "en": "الإنجليزية", "fr": "الفرنسية",
        "de": "الألمانية", "tr": "التركية", "hi": "الهندية",
        "es": "الإسبانية", "ru": "الروسية",
    }
    await query.edit_message_text(f"✅ تم تعيين لغة الترجمة إلى: *{lang_names.get(code, code)}*", parse_mode=ParseMode.MARKDOWN)


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

    video_path = None
    audio_path = None
    output_path = None
    srt_path = None

    try:
        # ── 1. تنزيل الفيديو ──────────────────────────────────
        video_path = await asyncio.get_event_loop().run_in_executor(
            None, lambda: download_video(url, work_dir)
        )
        if not video_path:
            await status_msg.edit_text("❌ تعذّر تنزيل الفيديو. تأكد من الرابط.")
            return

        size_mb = video_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_VIDEO_SIZE_MB:
            await status_msg.edit_text(
                f"❌ حجم الفيديو ({size_mb:.1f}MB) يتجاوز الحد المسموح ({MAX_VIDEO_SIZE_MB}MB)."
            )
            return

        # ── 2. استخراج الصوت ─────────────────────────────────
        await status_msg.edit_text("🎙️ جارٍ استخراج الصوت…")
        audio_path = work_dir / "audio.mp3"
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: extract_audio(video_path, audio_path)
        )

        # ── 3. النسخ بـ Whisper ──────────────────────────────
        await status_msg.edit_text("🧠 جارٍ نسخ الكلام بالذكاء الاصطناعي…")
        segments = await asyncio.get_event_loop().run_in_executor(
            None, lambda: transcribe(audio_path)
        )
        if not segments:
            await status_msg.edit_text("⚠️ لم يُعثر على كلام في الفيديو.")
            return

        # ── 4. الترجمة ───────────────────────────────────────
        await status_msg.edit_text(f"🌍 جارٍ الترجمة إلى {target_lang}…")
        translated = await asyncio.get_event_loop().run_in_executor(
            None, lambda: translate_segments(segments, target_lang)
        )

        # ── 5. إنشاء ملف SRT ─────────────────────────────────
        srt_path = work_dir / "subs.srt"
        write_srt(translated, srt_path)

        # ── 6. حرق الترجمة على الفيديو ───────────────────────
        await status_msg.edit_text("🔥 جارٍ حرق الترجمة على الفيديو…")
        output_path = work_dir / "output.mp4"
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: burn_subtitles(video_path, srt_path, output_path)
        )

        # ── 7. إرسال الفيديو ─────────────────────────────────
        await status_msg.edit_text("📤 جارٍ رفع الفيديو…")
        with open(output_path, "rb") as f:
            await update.message.reply_video(
                video=f,
                caption="✅ *الفيديو مع الترجمة*\nبواسطة @YourBotUsername",
                parse_mode=ParseMode.MARKDOWN,
                supports_streaming=True,
            )
        await status_msg.delete()

    except Exception as e:
        log.error(f"خطأ: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ حدث خطأ: {str(e)[:200]}")

    finally:
        # تنظيف الملفات المؤقتة
        for p in [video_path, audio_path, output_path, srt_path]:
            if p and p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass


# ─────────────────────────────────────────
#  وظائف المساعدة
# ─────────────────────────────────────────
def download_video(url: str, work_dir: Path) -> Path | None:
    """تنزيل الفيديو بأفضل جودة ≤ 720p"""
    out_template = str(work_dir / "video.%(ext)s")
    ydl_opts = {
        "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]/best",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "retries": 3,
        # تجاوز بعض القيود
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            return None
        filename = ydl.prepare_filename(info)
        # yt-dlp قد يغيّر الامتداد
        path = Path(filename)
        if not path.exists():
            mp4 = path.with_suffix(".mp4")
            if mp4.exists():
                return mp4
            # بحث في المجلد
            for f in work_dir.glob("video.*"):
                return f
        return path


def extract_audio(video: Path, out: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vn", "-ar", "16000",
         "-ac", "1", "-b:a", "64k", str(out)],
        check=True, capture_output=True,
    )


def transcribe(audio: Path) -> list[dict]:
    result = WHISPER.transcribe(str(audio), task="transcribe")
    return result.get("segments", [])


def translate_segments(segments: list[dict], target: str) -> list[dict]:
    translator = GoogleTranslator(source="auto", target=target)
    out = []
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        try:
            translated = translator.translate(text)
        except Exception:
            translated = text
        out.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": translated,
        })
    return out


def write_srt(segments: list[dict], path: Path):
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
    """حرق الترجمة بخط واضح مع خلفية شبه شفافة"""
    # نمط الخط للعربية والنصوص RTL
    subtitle_filter = (
        f"subtitles='{srt}':"
        "force_style='FontName=Arial,FontSize=20,PrimaryColour=&Hffffff,"
        "OutlineColour=&H000000,BackColour=&H80000000,"
        "Bold=1,Outline=2,Shadow=1,Alignment=2,MarginV=20'"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", subtitle_filter,
            "-c:v", "libx264", "-crf", "23", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            str(output),
        ],
        check=True, capture_output=True,
    )


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
