"""Russian strings."""

T = {
    "start_welcome": (
        "🕶 <b>Anonex</b>\n\n"
        "Анонимный P2P-маркетплейс.\n"
        "Твой ID: <code>{ghost_id}</code>{rating_line}\n\n"
        "Никакой регистрации. Никаких имён.\n"
        "Только ты, продавец и крипта.\n\n"
        "Меню ниже 👇"
    ),
    "start_rating": "\nТвой рейтинг: ⭐ {avg:.1f} ({count} отзывов)",
    "help_text": (
        "📖 <b>Как работает Anonex</b>\n\n"
        "1. <b>🛒 Маркет</b> → выбери товар → оплати в USDT через CryptoBot\n"
        "2. <b>Эскроу</b> → деньги заморожены до подтверждения\n"
        "3. Продавец передаёт товар прямо в боте\n"
        "4. Подтверждаешь получение → деньги идут продавцу\n"
        "5. Молчишь 48ч → авто-подтверждение\n"
        "6. Проблема → открой спор, разберём вручную\n"
        "7. После сделки оставь ⭐ отзыв продавцу\n\n"
        "💰 Комиссия: 10% | 👥 Рефералы: 50% от комиссии навсегда\n"
        "⏳ Вывод: через 7 дней после подтверждения\n"
        "🕒 Срок объявлений: 30 дней"
    ),
    "referral_info": (
        "👥 <b>Реферальная программа Anonex</b>\n\n"
        "50% от комиссии платформы с каждой сделки приглашённого — навсегда.\n\n"
        "Твоя ссылка:\n<code>{link}</code>\n\n"
        "Приглашено: <b>{count}</b>"
    ),
    "lang_changed": "✅ Язык изменён на русский.",

    "btn_market": "🛒 Маркет",
    "btn_sell": "➕ Продать",
    "btn_purchases": "📦 Мои покупки",
    "btn_listings": "📋 Мои товары",
    "btn_wallet": "💼 Кошелёк",
    "btn_referral": "👥 Реферальная",
    "btn_language": "🌐 Язык",

    "sell_start": (
        "📝 <b>Новое объявление</b>\n\n"
        "<i>Активно 30 дней.</i>\n\n"
        "Введи название (3–100 символов):"
    ),
    "sell_title_short": "Слишком короткое. Минимум 3 символа.",
    "sell_title_long": "Слишком длинное. Максимум 100 символов.",
    "sell_title_text": "Введи текстовое название.",
    "sell_desc_prompt": "Описание (10–1000 символов):",
    "sell_desc_short": "Слишком короткое. Минимум 10 символов.",
    "sell_desc_long": "Слишком длинное. Максимум 1000 символов.",
    "sell_desc_text": "Введи текстовое описание.",
    "sell_price_prompt": "💵 Цена в USDT (мин. 0.50):",
    "sell_price_min": "Минимальная цена 0.50 USDT.",
    "sell_price_max": "Максимальная цена 100 000 USDT.",
    "sell_price_invalid": "Некорректная цена. Например: 5.00",
    "sell_price_text": "Введи число.",
    "sell_cat_prompt": "Выбери категорию:",
    "sell_cat_buttons": "Используй кнопки выше 👆",
    "sell_subcat_prompt": "{emoji} <b>{name}</b>\nВыбери подкатегорию:",
    "sell_file_prompt": (
        "Категория: {label}\n\n"
        "📎 Прикрепи файл (необязательно).\n"
        "Или напиши <b>нет</b> чтобы пропустить."
    ),
    "sell_file_hint": "Файл или <b>нет</b>.",
    "sell_session_broken": "Сессия повреждена. Начни заново.",
    "sell_published": (
        "✅ Опубликовано! Активно 30 дней.\n\n"
        "<b>{title}</b> — <b>{price} USDT</b>\n"
        "📂 {label}\n"
        "ID: <code>{id}</code>"
    ),
    "sell_suggest_cat": "💡 Напиши название категории, которую хочешь добавить:",
    "sell_suggest_sent": "✅ Заявка отправлена. Админ рассмотрит её.",
    "sell_suggest_invalid": "2–100 символов.",

    "market_choose_cat": "🛒 <b>Маркет Anonex</b>\nВыбери категорию:",
    "market_empty_cat": "В этой категории пока нет объявлений.",
    "market_empty": "Маркет пустой. Будь первым продавцом! ➕",
    "market_no_more": "Больше нет.",
    "market_header": "🛒 <b>Маркет Anonex</b>",
    "market_no_reviews": "⭐ нет отзывов",
    "market_suggest_btn": "💡 Предложить категорию",

    "reviews_none": "⭐ <b>{ghost}</b>\n\nОтзывов пока нет.",
    "reviews_header": "⭐ <b>{ghost}</b>\nСредняя: <b>{avg:.1f}</b> / 5  ({count})\n",
    "rate_prompt": (
        "⭐ <b>Оцени сделку #{order_id}</b>\n\n"
        "Поставь продавцу оценку — это поможет другим покупателям."
    ),
    "rate_text_prompt": (
        "Оценка: {stars}\n\n"
        "Хочешь добавить текст? (до 500 символов)\n"
        "Или напиши /skip чтобы оставить только звёзды."
    ),
    "rate_saved": "✅ Отзыв сохранён.\n\n{stars}",
    "rate_skipped": "Понял, отзыв пропущен.",
    "rate_already": "Ты уже оставил отзыв на эту сделку.",
    "rate_invalid": "Некорректная оценка.",
    "rate_no_access": "Нет доступа.",
    "rate_wrong_status": "Можно оценить только завершённую сделку.",
    "rate_failed": "Не удалось сохранить отзыв.",
    "rate_seller_notif": "⭐ Новый отзыв по сделке #{order_id}: {stars}",

    "order_unavailable": "Объявление недоступно.",
    "order_self": "Нельзя купить у самого себя.",
    "order_duplicate": "У тебя уже есть активный заказ на этот товар.",
    "order_invoice_error": "Ошибка создания инвойса. Попробуй позже.",
    "order_created": (
        "🛒 <b>Заказ #{id}</b>\n\n"
        "Товар: <b>{title}</b>\n"
        "Сумма: <b>{amount} USDT</b>\n"
        "Комиссия: {fee} USDT (10%)\n\n"
        "Оплати через CryptoBot, затем нажми «Проверить оплату»."
    ),
    "order_already_processed": "Уже обработан.",
    "order_not_paid": "Оплата ещё не поступила.",
    "order_check_error": "Не удалось проверить. Попробуй позже.",
    "order_paid_ok": (
        "✅ <b>Оплата подтверждена!</b>\n"
        "Заказ #{id} в эскроу. Жди товар от продавца."
    ),
    "order_seller_notif": (
        "💰 <b>Новая сделка #{id}</b>\n"
        "Сумма: {amount} USDT → тебе {net} USDT\n"
        "Передай товар покупателю:"
    ),
    "order_cancel_ok": "❌ Заказ #{id} отменён.",
    "order_cancel_fail": "Отменить можно только неоплаченный заказ.",
    "order_no_access": "Нет доступа.",
    "order_not_found": "Заказ не найден.",
    "purchases_empty": "У тебя ещё нет покупок.",
    "deliver_prompt": (
        "📤 <b>Заказ #{id}</b>\n"
        "Отправь товар / ссылку / код доступа. Дойдёт анонимно."
    ),
    "deliver_status_changed": "Статус заказа #{id} изменился. Передача невозможна.",
    "deliver_already_changed": "Статус уже изменился.",
    "deliver_ok": "✅ Передано. Ждём подтверждения покупателя (авто через 48ч).",
    "deliver_buyer_notif": (
        "📦 <b>Продавец передал товар по заказу #{id}.</b>\n"
        "Подтверди получение или открой спор."
    ),
    "deliver_buyer_text": "📦 <b>Товар по заказу #{id}:</b>\n\n{note}",
    "confirm_ok": "✅ Заказ #{id} завершён. Спасибо!",
    "confirm_status": "Статус уже: {label}",
    "release_seller_notif": "🎉 <b>Сделка #{id} завершена!</b>\n+{net} USDT (вывод через 7 дней)",
    "release_referral_notif": "💸 Реферальное: <b>+{amount} USDT</b> (сделка #{id})",
    "dispute_prompt": "⚠️ <b>Спор по заказу #{id}</b>\nОпиши проблему:",
    "dispute_wrong_status": "Спор можно открыть только по активному заказу.",
    "dispute_opened": "⚠️ Спор открыт. Деньги заморожены до решения.",
    "dispute_failed": "Не удалось открыть спор (статус изменился).",
    "dispute_admin_notif": (
        "⚠️ <b>Спор — Заказ #{id}</b>\n"
        "Покупатель: <code>{ghost}</code>\n"
        "Причина: {reason}"
    ),
    "dispute_text_only": "Опиши проблему текстом.",

    "wallet_info": (
        "💼 <b>Кошелёк</b>\n\n"
        "Доступно: <b>{balance} USDT</b>\n"
        "Заморожено: <b>{pending} USDT</b> ⏳\n"
        "Заработано всего: {earned} USDT\n\n"
        "<i>Заморозка снимается через 7 дней после подтверждения сделки.</i>"
    ),
    "withdraw_min": "Мин. 1.00 USDT. У тебя: {balance}",
    "withdraw_prompt": "📤 Доступно: <b>{balance} USDT</b>\nВведи сумму (мин. 1.00):",
    "withdraw_min_amount": "Минимум 1.00 USDT.",
    "withdraw_insufficient": "Недостаточно. Доступно: {balance} USDT",
    "withdraw_invalid": "Некорректная сумма.",
    "withdraw_addr_prompt": (
        "Адрес для вывода:\n\n"
        "• TRC20 USDT: <code>T...</code> (34 символа)\n"
        "• Telegram ID: 5–12 цифр"
    ),
    "withdraw_addr_invalid": (
        "❌ Некорректный адрес.\n\n"
        "TRC20 (начинается с T, 34 символа)\n"
        "или Telegram ID (5–12 цифр)."
    ),
    "withdraw_session_expired": "Сессия устарела. Начни заново.",
    "withdraw_balance_changed": "Баланс изменился. Начни заново.",
    "withdraw_created": (
        "✅ Заявка на вывод <b>{amount} USDT</b> создана.\n"
        "Адрес: <code>{addr}</code>\n\n"
        "Обработка до 24 часов."
    ),
    "withdraw_admin_notif": (
        "💸 <b>Вывод #{id}</b>\n"
        "<code>{ghost}</code> | {amount} USDT\n"
        "Адрес: <code>{wallet}</code>"
    ),
    "tx_empty": "Транзакций пока нет.",
    "tx_header": "📊 <b>Транзакции</b>\n",
    "tx_types": {
        "escrow_in": "🔒 Эскроу",
        "escrow_release": "📤 Выход",
        "fee": "💸 Комиссия",
        "referral": "👥 Реферал",
        "refund": "↩️ Возврат",
        "withdrawal": "📤 Вывод",
    },

    "admin_panel": (
        "🔧 <b>Админ-панель</b>\n\n"
        "👤 Юзеров: {users} | 📋 Листингов: {listings}\n"
        "📦 Заказов: {orders} | 💰 Оборот: {volume} USDT\n"
        "💸 Комиссии: {fees} USDT\n"
        "⚠️ Споров: {disputes} | 📤 Выводов: {withdrawals}"
    ),
    "admin_no_access": "Нет доступа.",
    "admin_no_disputes": "Споров нет 🎉",
    "admin_no_withdrawals": "Выводов нет.",
    "admin_no_transactions": "Транзакций нет.",
    "admin_no_listings": "Активных объявлений нет.",
    "admin_no_suggestions": "Заявок нет.",
    "admin_dispute_resolved_buyer": "✅ Спор #{id} — возврат покупателю.",
    "admin_dispute_resolved_seller": "✅ Спор #{id} — выплата продавцу (hold 7д).",
    "admin_dispute_already": "Уже решён.",
    "admin_withdrawal_approved": "✅ Вывод #{id} — переведено.",
    "admin_withdrawal_rejected": "❌ Вывод #{id} отклонён, средства возвращены.",
    "admin_withdrawal_already": "Уже обработано.",
    "admin_ban_ok": "✅ Забанен: {ghost}",
    "admin_ban_fail": "❌ Не найден: {ghost}",
    "admin_unban_ok": "✅ Разбанен: {ghost}",
    "admin_unban_fail": "❌ Не найден: {ghost}",
    "admin_listing_deleted": "✅ Удалено.",
    "admin_listing_delete_fail": "Не удалось.",
    "admin_cat_created": "✅ Создана: {emoji} {name} (ID {id})",
    "admin_cat_renamed": "✅ Переименовано.",
    "admin_cat_rename_fail": "❌ Не удалось.",
    "admin_cat_disabled": "✅ Деактивирована",
    "admin_cat_new_root_prompt": "Название новой корневой категории:",
    "admin_cat_new_emoji_prompt": "Эмодзи (1 символ, например 🎮):",
    "admin_cat_new_sub_prompt": "Название подкатегории (эмодзи в начале опционально, напр. «🎯 Valorant»):",
    "admin_cat_rename_prompt": "Новое название (эмодзи в начале опционально):",
    "admin_sug_where": "Куда добавить «{name}»?",
    "admin_sug_name_prompt": (
        "Заявка: «{name}»\n\n"
        "Введи финальное название (эмодзи в начале опционально)\n"
        "или просто <b>=</b> чтобы принять как есть:"
    ),
    "admin_sug_approved": "✅ Категория создана: {emoji} {name} (ID {id})",
    "admin_sug_rejected": "Отклонено.",
    "admin_sug_already": "Уже обработана.",
    "admin_sug_user_approved": "✅ Твоя заявка «{name}» одобрена!\nДобавлена категория {emoji} {cat_name}.",
    "admin_sug_user_rejected": "❌ Твоя заявка «{name}» отклонена.",
    "admin_buyer_notif": "↩️ Спор #{id} решён в твою пользу. +{amount} USDT",
    "admin_seller_notif_buyer_won": "⚠️ Спор #{id} — возврат покупателю.",
    "admin_seller_notif_seller_won": "✅ Спор #{id} решён в твою пользу. Средства на hold (7д).",
    "admin_buyer_notif_seller_won": "⚠️ Спор #{id} — решён в пользу продавца.",
    "admin_withdrawal_user_ok": "✅ Вывод #{id}: {amount} USDT отправлен.",
    "admin_withdrawal_user_fail": "❌ Вывод #{id} не удался. {amount} USDT возвращены.",
    "admin_withdrawal_user_rejected": "❌ Вывод #{id} отклонён. {amount} USDT возвращены.",
    "admin_listing_seller_notif": "🛑 Объявление «{title}» снято администратором.",

    "sched_auto_confirmed": "⏰ Заказ #{id} авто-подтверждён (прошло 48ч).",
    "sched_unlocked": "🔓 <b>Средства разблокированы!</b>\nЗаказ #{id}: +{amount} USDT доступны для вывода.",
}
