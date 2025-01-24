import os
import random

from telegram import Update
from telegram.ext import Application, CommandHandler, PollAnswerHandler, ContextTypes

# Đường dẫn thư mục chứa các file từ vựng
NOTE_FOLDER = "note"

def get_txt_files(folder):
    """Lấy danh sách các file .txt trong thư mục."""
    return [f for f in os.listdir(folder) if f.endswith(".txt")]

def read_words_from_file(filepath):
    """Đọc từ vựng từ file và trả về danh sách các cặp (từ, nghĩa)."""
    with open(filepath, "r", encoding="utf-8") as file:
        lines = file.readlines()
        return [line.strip().split(": ") for line in lines if ": " in line]

def get_latest_file(folder):
    """Lấy file .txt mới nhất trong thư mục."""
    files = get_txt_files(folder)
    if not files:
        return None
    latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(folder, f)))
    return os.path.join(folder, latest_file)

def generate_question(word, all_words):
    """Tạo câu hỏi với 4 đáp án từ danh sách từ vựng."""
    vocab, correct_meaning = word
    other_meanings = [w[1] for w in all_words if w[1] != correct_meaning]
    options = random.sample(other_meanings, 3) + [correct_meaning]
    random.shuffle(options)
    return vocab, correct_meaning, options

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị thông báo chào mừng và hướng dẫn sử dụng bot."""
    print("[DEBUG] User started the bot.")
    await update.message.reply_text(
        "Chào mừng bạn đến với bot học từ vựng!\n"
        "Chọn một tùy chọn:\n"
        "/random <số câu> - Học từ ngẫu nhiên\n"
        "/latest <số câu> - Học từ gần đây"
    )

async def learn_random_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bắt đầu học từ vựng ngẫu nhiên."""
    print("[DEBUG] learn_random_words command invoked.")
    try:
        total_questions = int(context.args[0]) if context.args else 10
    except ValueError:
        print("[ERROR] Invalid number of questions.")
        await update.message.reply_text("Vui lòng nhập một số hợp lệ cho số câu hỏi.")
        return

    files = get_txt_files(NOTE_FOLDER)
    print(f"[DEBUG] Found files: {files}")
    if not files:
        await update.message.reply_text("Không có file từ vựng nào trong thư mục 'note'.")
        return

    all_words = []
    for file in files:
        all_words.extend(read_words_from_file(os.path.join(NOTE_FOLDER, file)))

    print(f"[DEBUG] Total words loaded: {len(all_words)}")
    if not all_words:
        await update.message.reply_text("Không có từ vựng nào trong các file.")
        return

    context.user_data["mode"] = "random"
    context.user_data["words"] = random.sample(all_words, min(total_questions, len(all_words)))
    context.user_data["current_question"] = 0
    context.user_data["correct_count"] = 0
    context.user_data["total_questions"] = total_questions

    await ask_question(update, context)

async def learn_latest_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bắt đầu học từ vựng từ file mới nhất."""
    print("[DEBUG] learn_latest_words command invoked.")
    try:
        total_questions = int(context.args[0]) if context.args else 10
    except ValueError:
        print("[ERROR] Invalid number of questions.")
        await update.message.reply_text("Vui lòng nhập một số hợp lệ cho số câu hỏi.")
        return

    latest_file = get_latest_file(NOTE_FOLDER)
    print(f"[DEBUG] Latest file: {latest_file}")
    if not latest_file:
        await update.message.reply_text("Không tìm thấy file từ vựng gần đây.")
        return

    words = read_words_from_file(latest_file)
    print(f"[DEBUG] Total words in latest file: {len(words)}")
    if not words:
        await update.message.reply_text("Không có từ vựng nào trong file gần đây.")
        return

    context.user_data["mode"] = "latest"
    context.user_data["words"] = random.sample(words, min(total_questions, len(words)))
    context.user_data["current_question"] = 0
    context.user_data["correct_count"] = 0
    context.user_data["total_questions"] = total_questions

    await ask_question(update, context)

async def ask_question(update, context):
    """Gửi câu hỏi dưới dạng poll."""
    current_question = context.user_data["current_question"]
    correct_count = context.user_data.get("correct_count", 0)
    vocab_meanings = context.user_data["words"]
    total_questions = context.user_data["total_questions"]

    print(f"[DEBUG] Asking question {current_question + 1}/{total_questions}")
    if current_question >= total_questions:
        await send_final_score(update, context, correct_count, total_questions)
        return

    vocab, correct_answer = vocab_meanings[current_question]
    all_meanings = [meaning for _, meaning in vocab_meanings]

    options = [correct_answer]
    other_meanings = [meaning for meaning in all_meanings if meaning != correct_answer]
    options += random.sample(other_meanings, 3)
    random.shuffle(options)

    correct_option_id = options.index(correct_answer)
    context.user_data["correct_option_id"] = correct_option_id

    chat_id = update.message.chat.id if update.message else update.poll_answer.user.id

    question_text = f"Câu {current_question + 1}/{total_questions}: {vocab}\nChọn đáp án đúng:"
    print(f"[DEBUG] Sending poll: {question_text}")
    await context.bot.send_poll(
        chat_id=chat_id,
        question=question_text,
        options=options,
        type="quiz",
        correct_option_id=correct_option_id,
        is_anonymous=False,
    )

    context.user_data["current_question"] += 1

async def handle_poll_answer(update, context):
    """Xử lý câu trả lời của người dùng từ poll."""
    correct_count = context.user_data.get("correct_count", 0)
    correct_option_id = context.user_data.get("correct_option_id")
    answer = update.poll_answer

    print(f"[DEBUG] User answered: {answer.option_ids}, Correct ID: {correct_option_id}")
    if answer.option_ids and answer.option_ids[0] == correct_option_id:
        correct_count += 1
        context.user_data["correct_count"] = correct_count

    print(f"[DEBUG] Current correct count: {correct_count}")
    await ask_question(update, context)

async def send_final_score(update, context, correct_count, total_questions):
    """Gửi điểm cuối cùng sau khi hoàn thành tất cả các câu hỏi."""
    chat_id = update.message.chat.id if update.message else update.poll_answer.user.id

    print(f"[DEBUG] Final score: {correct_count}/{total_questions}")
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ Bạn đã trả lời đúng {correct_count}/{total_questions} câu!"
    )

def main():
    BOT_TOKEN = "tu xin bot token tren https://telegram.me/BotFather"

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("random", learn_random_words))
    app.add_handler(CommandHandler("latest", learn_latest_words))
    app.add_handler(PollAnswerHandler(handle_poll_answer))

    print("Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
