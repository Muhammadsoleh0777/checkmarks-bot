import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import BotCommand, MenuButtonCommands, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = "8791984826:AAHH-JFIs1shl9xUyBAGFLMmp3S5kVsE45s"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилища данных в памяти
users_db = {}
schedule_db = {}  # {telegram_id: {"Понедельник": ["Алгебра", ...], ...}}
grades_db = {}    # {telegram_id: {"Алгебра": [5, 4], ...}}

# Фиксированный список дней недели
DAYS_OF_WEEK = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]

# Состояния для пошагового ввода
class Form(StatesGroup):
    waiting_for_name = State()
    waiting_for_grade_num = State()
    
    # Состояния для расписания
    schedule_day = State()
    schedule_lessons = State()

    # Состояния для оценок
    adding_subject = State()

# Главная клавиатура (меню бота)
def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="👤 Мои данные")
    builder.button(text="📅 Расписание")
    builder.button(text="📊 Мои оценки")
    builder.button(text="➕ Добавить расписание")
    builder.button(text="➕ Добавить оценку")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

# Клавиатура с кнопкой «Назад» для шагов, где есть предыдущий шаг
def back_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Назад")]],
        resize_keyboard=True
    )

# Клавиатура с кнопкой «Отмена / В меню» для одношаговых действий
def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Отмена / В меню")]],
        resize_keyboard=True
    )

# Инлайн-клавиатура для выбора дней недели (для расписания)
def days_inline_keyboard():
    builder = InlineKeyboardBuilder()
    for day in DAYS_OF_WEEK:
        builder.button(text=day, callback_data=f"day_{day}")
    builder.adjust(2)
    return builder.as_markup()

# Инлайн-клавиатура для конкретного дня расписания
def schedule_actions_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ К дням недели", callback_data="back_to_days")
    builder.adjust(1)
    return builder.as_markup()

# Инлайн-клавиатура для выбора предметов (для оценок)
def subjects_inline_keyboard(user_grades):
    builder = InlineKeyboardBuilder()
    for subject in user_grades.keys():
        builder.button(text=subject, callback_data=f"subj_{subject}")
    builder.adjust(2)
    return builder.as_markup()

# Инлайн-клавиатура для конкретного предмета
def subject_actions_keyboard(subject):
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Удалить последнюю оценку", callback_data=f"del_{subject}")
    builder.button(text="⬅️ К списку предметов", callback_data="back_to_subjects")
    builder.adjust(1)
    return builder.as_markup()

# Команда /start
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id not in users_db:
        await message.answer("Привет! Давай познакомимся. Как тебя зовут?", reply_markup=cancel_keyboard())
        await state.set_state(Form.waiting_for_name)
    else:
        name = users_db[user_id]["name"]
        class_num = users_db[user_id]["class"]
        await message.answer(
            f"С возвращением, {name} ({class_num})! Выбери нужное действие в меню:",
            reply_markup=main_keyboard()
        )

# --- МОИ ДАННЫЕ ---

@dp.message(F.text == "👤 Мои данные")
async def show_my_data(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем, есть ли пользователь в базе и заполнены ли его данные
    if user_id not in users_db or not users_db[user_id]:
        await message.answer(
            "⚠️ У тебя еще не сохранены данные!\n"
            "Давай познакомимся, введи команду /start",
            reply_markup=main_keyboard()
        )
        return

    # Если данные есть — показываем их
    user_data = users_db[user_id]
    await message.answer(
        f"👤 <b>Твои данные:</b>\n"
        f"• Имя: {user_data.get('name', 'Не указано')}\n"
        f"• Класс: {user_data.get('class', 'Не указан')}",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )

# --- РЕГИСТРАЦИЯ ---

@dp.message(Form.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Отмена / В меню":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_keyboard())
        return

    await state.update_data(name=message.text)
    await message.answer("В каком ты классе? (например: 11 «А»)", reply_markup=back_keyboard())
    await state.set_state(Form.waiting_for_grade_num)

@dp.message(Form.waiting_for_grade_num)
async def process_grade_num(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        # Возвращаемся к вводу имени
        await message.answer("Как тебя зовут?", reply_markup=cancel_keyboard())
        await state.set_state(Form.waiting_for_name)
        return

    user_id = message.from_user.id
    data = await state.get_data()
    name = data["name"]
    class_num = message.text

    users_db[user_id] = {"name": name, "class": class_num}
    await state.clear()

    await message.answer(
        f"Отлично, данные сохранены!\nИмя: {name}\nКласс: {class_num}",
        reply_markup=main_keyboard()
    )

# --- РАСПИСАНИЕ ---

@dp.message(F.text == "➕ Добавить расписание")
async def add_schedule_start(message: types.Message, state: FSMContext):
    await message.answer(
        "Напиши день недели, для которого хочешь добавить (или исправить) расписание (например: Понедельник):",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(Form.schedule_day)

@dp.message(Form.schedule_day)
async def process_schedule_day(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Отмена / В меню":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_keyboard())
        return

    day_input = message.text.capitalize()
    if day_input not in DAYS_OF_WEEK:
        await message.answer("⚠️ Такого дня недели нет. Пожалуйста, напиши корректный день (например: Понедельник):")
        return
        
    await state.update_data(day=day_input)
    await message.answer(
        f"Напиши предметы на <b>{day_input}</b> через запятую (старое расписание на этот день обновится):\n"
        "(например: Алгебра, Геометрия, Русский яз, Литература)",
        parse_mode="HTML",
        reply_markup=back_keyboard()
    )
    await state.set_state(Form.schedule_lessons)

@dp.message(Form.schedule_lessons)
async def process_schedule_lessons(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await message.answer("Напиши день недели, для которого хочешь добавить расписание:", reply_markup=cancel_keyboard())
        await state.set_state(Form.schedule_day)
        return

    user_id = message.from_user.id
    data = await state.get_data()
    day = data["day"]
    
    lessons = [l.strip() for l in message.text.split(",")]

    if user_id not in schedule_db:
        schedule_db[user_id] = {}

    schedule_db[user_id][day] = lessons
    await state.clear()

    await message.answer(f"✅ Расписание на <b>{day}</b> успешно сохранено/обновлено!", reply_markup=main_keyboard(), parse_mode="HTML")

@dp.message(F.text == "📅 Расписание")
async def show_schedule_days(message: types.Message):
    await message.answer("📅 Выбери день недели, чтобы посмотреть расписание:", reply_markup=days_inline_keyboard())

@dp.callback_query(F.data.startswith("day_"))
async def process_day_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    day = callback.data.split("_", 1)[1]
    
    lessons = schedule_db.get(user_id, {}).get(day, [])
    
    if not lessons:
        await callback.answer(f"На день «{day}» расписание еще не добавлено.", show_alert=True)
        return

    text = f"📅 <b>Расписание на {day}:</b>\n\n"
    for i, lesson in enumerate(lessons, 1):
        text += f"{i}. {lesson}\n"

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=schedule_actions_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "back_to_days")
async def process_back_to_days(callback: types.CallbackQuery):
    await callback.message.edit_text("📅 Выбери день недели, чтобы посмотреть расписание:", reply_markup=days_inline_keyboard())
    await callback.answer()

# --- ОЦЕНКИ ---

@dp.message(F.text == "➕ Добавить оценку")
async def add_grade_start(message: types.Message, state: FSMContext):
    await message.answer(
        "Введи название предмета и оценку через пробел (например: Алгебра 5).\n"
        "<i>Если по этому предмету уже есть оценки, новая просто добавится к ним.</i>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(Form.adding_subject)

@dp.message(Form.adding_subject)
async def save_grade(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Отмена / В меню":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_keyboard())
        return

    user_id = message.from_user.id
    parts = message.text.rsplit(" ", 1)
    
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("⚠️ Неверный формат. Напиши предмет и оценку цифрой, например: Алгебра 5")
        return

    subject, score = parts[0].strip().capitalize(), int(parts[1])
    
    if user_id not in grades_db:
        grades_db[user_id] = {}
    if subject not in grades_db[user_id]:
        grades_db[user_id][subject] = []

    grades_db[user_id][subject].append(score)
    await state.clear()
    await message.answer(f"✅ Оценка {score} по предмету «{subject}» успешно добавлена!", reply_markup=main_keyboard())

@dp.message(F.text == "📊 Мои оценки")
async def show_grades_menu(message: types.Message):
    user_id = message.from_user.id
    user_grades = grades_db.get(user_id, {})
    
    if not user_grades:
        await message.answer("📊 У тебя пока нет добавленных оценок. Нажми «➕ Добавить оценку».")
        return

    await message.answer("📊 Выбери предмет, по которому хочешь посмотреть оценки:", reply_markup=subjects_inline_keyboard(user_grades))

@dp.callback_query(F.data.startswith("subj_"))
async def process_subject_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    subject = callback.data.split("_", 1)[1]
    
    scores = grades_db.get(user_id, {}).get(subject, [])
    
    if not scores:
        await callback.answer("Оценки по этому предмету не найдены.", show_alert=True)
        return

    avg = sum(scores) / len(scores)
    text = f"📚 <b>Предмет: {subject}</b>\n\n"
    text += f"• Оценки: {', '.join(map(str, scores))}\n"
    text += f"• Всего оценок: {len(scores)}\n"
    text += f"• Средний балл: {avg:.2f}"

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=subject_actions_keyboard(subject))
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def process_delete_last_grade(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    subject = callback.data.split("_", 1)[1]
    
    if user_id in grades_db and subject in grades_db[user_id] and grades_db[user_id][subject]:
        removed = grades_db[user_id][subject].pop()
        
        if not grades_db[user_id][subject]:
            del grades_db[user_id][subject]
            await callback.message.edit_text(f"🗑 Последняя оценка ({removed}) по предмету «{subject}» удалена. Больше оценок по этому предмету нет.")
            await callback.answer("Оценка удалена!")
            return

        scores = grades_db[user_id][subject]
        avg = sum(scores) / len(scores)
        text = f"🗑 <i>Удалена последняя оценка ({removed})!</i>\n\n"
        text += f"📚 <b>Предмет: {subject}</b>\n\n"
        text += f"• Оценки: {', '.join(map(str, scores))}\n"
        text += f"• Всего оценок: {len(scores)}\n"
        text += f"• Средний балл: {avg:.2f}"

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=subject_actions_keyboard(subject))
        await callback.answer("Последняя оценка удалена!")
    else:
        await callback.answer("У вас нет оценок для удаления по этому предмету.", show_alert=True)

@dp.callback_query(F.data == "back_to_subjects")
async def process_back_to_subjects(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_grades = grades_db.get(user_id, {})
    
    if not user_grades:
        await callback.message.edit_text("📊 У тебя пока нет добавленных оценок.")
        return

    await callback.message.edit_text("📊 Выбери предмет, по которому хочешь посмотреть оценки:", reply_markup=subjects_inline_keyboard(user_grades))
    await callback.answer()

async def main():
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота / Главное меню")
    ])
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    print("Ура! Школьный бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
