from __future__ import annotations


LANGUAGE_BY_BUTTON = {
    "🇹🇯 Тоҷикӣ": "tj",
    "🇷🇺 Русский": "ru",
    "🇬🇧 English": "en",
}

LANGUAGE_NAMES = {
    "tj": "Тоҷикӣ",
    "ru": "Русский",
    "en": "English",
}

MENU = {
    "tj": {
        "new_station": "📍 Стансияи нав",
        "search_station": "🔍 Ҷустуҷӯи стансия",
        "scan_qr": "📷 Скан кардани QR",
        "rustdesk": "🖥 RustDesk",
        "vpn": "🌐 VPN",
        "ping": "📡 Ping",
        "camera": "📷 Камера",
        "network_status": "📊 Ҳолати шабака",
        "alerts": "🚨 Огоҳӣ",
        "reports": "📝 Ҳисобот",
        "settings": "⚙️ Танзимот",
    },
    "ru": {
        "new_station": "📍 Новая станция",
        "search_station": "🔍 Поиск станции",
        "scan_qr": "📷 Сканировать QR",
        "rustdesk": "🖥 RustDesk",
        "vpn": "🌐 VPN",
        "ping": "📡 Ping",
        "camera": "📷 Камера",
        "network_status": "📊 Состояние сети",
        "alerts": "🚨 Оповещения",
        "reports": "📝 Отчеты",
        "settings": "⚙️ Настройки",
    },
    "en": {
        "new_station": "📍 New station",
        "search_station": "🔍 Search station",
        "scan_qr": "📷 Scan QR",
        "rustdesk": "🖥 RustDesk",
        "vpn": "🌐 VPN",
        "ping": "📡 Ping",
        "camera": "📷 Camera",
        "network_status": "📊 Network status",
        "alerts": "🚨 Alerts",
        "reports": "📝 Reports",
        "settings": "⚙️ Settings",
    },
}

TEXT = {
    "tj": {
        "welcome": "👋 Хуш омадед! Лутфан забони худро интихоб кунед.",
        "language_selected": "✅ Забони тоҷикӣ интихоб шуд.", "main_menu": "Менюи асосӣ:",
        "cancel": "❌ Бекор кардан", "save": "✅ Сабт кардан", "skip": "⏭ Гузариш",
        "send_location": "📍 Ирсоли ҷойгиршавӣ", "cancelled": "Амалиёт бекор шуд.",
        "pending_users": "Дархостҳои интизор", "my_access": "Дастрасии ман",
        "request_access": "Дархости дастрасӣ", "help_access": "Кӯмак",
        "enter_code": "Рақами расмии стансияро ворид кунед.\n\nМисол: 10042",
        "invalid_station_code": "Коди стансия нодуруст аст. Танҳо ҳарф, рақам, _ ва - истифода баред.",
        "enter_name": "Номи стансияро ворид кунед.", "enter_region": "Ноҳияи Душанбе ворид кунед.",
        "district_error": "Яке аз ноҳияҳоро ворид кунед: Исмоили Сомонӣ, Шоҳмансур, Сино ё Фирдавсӣ.",
        "enter_address": "Суроғаро ворид кунед.", "enter_vpn": "VPN IP ворид кунед ё Гузариш.",
        "enter_local": "Local IP ворид кунед ё Гузариш.", "enter_rustdesk": "RustDesk ID ворид кунед ё Гузариш.",
        "enter_location": "GPS ҷойгиршавиро фиристед ё Гузариш.",
        "invalid_required": "Ин майдон ҳатмист.", "invalid_ip": "IP нодуруст аст.",
        "invalid_location": "Ҷойгиршавиро бо тугма фиристед ё Гузаришро интихоб кунед.",
        "missing_backend": "Маълумоти ҳатмӣ намерасад.", "missing_fields": "Майдонҳои намерасида:",
        "station_exists_pending": "Стансияи {code} аллакай мавҷуд аст. Сабти интизор нав карда мешавад.",
        "station_exists_approved": "⚠️ Стансияи {code} дар истеҳсолот тасдиқ шудааст. Тасдиқи махсус лозим аст; ҳолати тасдиқ тағйир намеёбад.",
        "summary_title": "Маълумоти стансияро тасдиқ кунед:", "label_code": "Код", "label_name": "Ном",
        "label_district": "Ноҳия", "label_address": "Суроға", "label_vpn": "VPN IP",
        "label_local": "Local IP", "label_rustdesk": "RustDesk ID", "label_gps": "GPS",
        "label_record_status": "Навъи сабт", "label_approval": "Тасдиқи истеҳсолӣ",
        "record_existing": "Мавҷуд", "record_new": "Нав", "approval_pending": "Интизор",
        "approval_approved": "Тасдиқшуда", "confirm_approved_update": "⚠️ НАВ КАРДАНИ СТАНСИЯИ ТАСДИҚШУДА",
        "saved_existing_pending": "✅ Стансия нав карда шуд. Он барои тасдиқи истеҳсолӣ интизор мемонад.",
        "saved_new_pending": "✅ Стансия сохта шуд. Он барои тасдиқи истеҳсолӣ интизор мемонад.",
        "saved_approved": "✅ Стансияи истеҳсолӣ нав карда шуд. Ҳолати тасдиқ тағйир наёфт.",
        "api_error": "❌ Хатои сервер:", "search_prompt": "Код, ном, IP ё суроғаро ворид кунед.",
        "search_empty": "Матни ҷустуҷӯ холӣ аст.", "search_no_results": "Стансия ёфт нашуд.",
        "search_results": "Натиҷаҳои ҷустуҷӯ:", "not_implemented": "Ин қисм ҳоло дастрас нест.",
        "access_title": "Дастрасии City Parking", "access_username": "Номи корбар", "access_role": "Нақш",
        "access_status": "Ҳолат", "access_activation": "Фаъолсозӣ", "activation_required": "Лозим аст",
        "activation_not_required": "Лозим нест", "username_login_hint": "Дар саҳифаи воридшавӣ маҳз ҳамин номи корбарро истифода баред.",
        "role_admin": "Администратор", "role_operator": "Оператор", "role_viewer": "Намоиш",
    },
    "ru": {
        "welcome": "👋 Добро пожаловать! Пожалуйста, выберите язык.",
        "language_selected": "✅ Русский язык выбран.", "main_menu": "Главное меню:",
        "cancel": "❌ Отмена", "save": "✅ Сохранить", "skip": "⏭ Пропустить",
        "send_location": "📍 Отправить геолокацию", "cancelled": "Операция отменена.",
        "pending_users": "Ожидающие пользователи", "my_access": "Мой доступ",
        "request_access": "Запросить доступ", "help_access": "Помощь",
        "enter_code": "Введите официальный код станции.\n\nПример: 10042",
        "invalid_station_code": "Некорректный код станции. Используйте буквы, цифры, _ или -.",
        "enter_name": "Введите название станции.", "enter_region": "Введите район Душанбе.",
        "district_error": "Введите один район: Исмоили Сомони, Шохмансур, Сино или Фирдавси.",
        "enter_address": "Введите адрес.", "enter_vpn": "Введите VPN IP или нажмите Пропустить.",
        "enter_local": "Введите Local IP или нажмите Пропустить.", "enter_rustdesk": "Введите RustDesk ID или нажмите Пропустить.",
        "enter_location": "Отправьте GPS-локацию или нажмите Пропустить.",
        "invalid_required": "Это обязательное поле.", "invalid_ip": "Некорректный IP-адрес.",
        "invalid_location": "Отправьте геолокацию кнопкой или нажмите Пропустить.",
        "missing_backend": "Не хватает обязательных данных.", "missing_fields": "Отсутствующие поля:",
        "station_exists_pending": "Станция {code} уже существует. Существующая ожидающая запись будет обновлена.",
        "station_exists_approved": "⚠️ Станция {code} уже допущена в production. Требуется отдельное подтверждение; статус допуска не изменится.",
        "summary_title": "Проверьте данные станции:", "label_code": "Код", "label_name": "Название",
        "label_district": "Район", "label_address": "Адрес", "label_vpn": "VPN IP",
        "label_local": "Local IP", "label_rustdesk": "RustDesk ID", "label_gps": "GPS",
        "label_record_status": "Запись", "label_approval": "Production-допуск",
        "record_existing": "Существующая", "record_new": "Новая", "approval_pending": "Ожидает",
        "approval_approved": "Одобрена", "confirm_approved_update": "⚠️ ОБНОВИТЬ ОДОБРЕННУЮ СТАНЦИЮ",
        "saved_existing_pending": "✅ Станция обновлена. Она остаётся на рассмотрении для production.",
        "saved_new_pending": "✅ Станция создана. Она остаётся на рассмотрении для production.",
        "saved_approved": "✅ Production-станция обновлена. Статус допуска не изменён.",
        "api_error": "❌ Ошибка сервера:", "search_prompt": "Введите код, название, IP или адрес.",
        "search_empty": "Пустой поисковый запрос.", "search_no_results": "Станции не найдены.",
        "search_results": "Результаты поиска:", "not_implemented": "Этот раздел пока недоступен.",
        "access_title": "Доступ City Parking", "access_username": "Имя пользователя", "access_role": "Роль",
        "access_status": "Статус", "access_activation": "Активация", "activation_required": "Требуется",
        "activation_not_required": "Не требуется", "username_login_hint": "На странице входа используйте именно это имя пользователя.",
        "role_admin": "Администратор", "role_operator": "Оператор", "role_viewer": "Просмотр",
    },
    "en": {
        "welcome": "👋 Welcome! Please choose your language.", "language_selected": "✅ English selected.",
        "main_menu": "Main menu:", "cancel": "❌ Cancel", "save": "✅ Save", "skip": "⏭ Skip",
        "send_location": "📍 Send location", "cancelled": "Operation cancelled.",
        "pending_users": "Pending users", "my_access": "My access", "request_access": "Request access", "help_access": "Help",
        "enter_code": "Enter the official station code.\n\nExample: 10042",
        "invalid_station_code": "Invalid station code. Use letters, numbers, _ or -.",
        "enter_name": "Enter the station name.", "enter_region": "Enter a Dushanbe district.",
        "district_error": "Enter one district: Ismoili Somoni, Shohmansur, Sino, or Firdavsi.",
        "enter_address": "Enter the address.", "enter_vpn": "Enter VPN IP or Skip.",
        "enter_local": "Enter Local IP or Skip.", "enter_rustdesk": "Enter RustDesk ID or Skip.",
        "enter_location": "Send GPS location or Skip.", "invalid_required": "This field is required.",
        "invalid_ip": "Invalid IP address.", "invalid_location": "Send location with the button or choose Skip.",
        "missing_backend": "Required station data is missing.", "missing_fields": "Missing fields:",
        "station_exists_pending": "Station {code} already exists. The existing pending record will be updated.",
        "station_exists_approved": "⚠️ Station {code} is production-approved. A separate confirmation is required; approval will not change.",
        "summary_title": "Confirm the station details:", "label_code": "Code", "label_name": "Name",
        "label_district": "District", "label_address": "Address", "label_vpn": "VPN IP",
        "label_local": "Local IP", "label_rustdesk": "RustDesk ID", "label_gps": "GPS",
        "label_record_status": "Record", "label_approval": "Production approval",
        "record_existing": "Existing", "record_new": "New", "approval_pending": "Pending",
        "approval_approved": "Approved", "confirm_approved_update": "⚠️ UPDATE APPROVED STATION",
        "saved_existing_pending": "✅ Station updated successfully. It remains pending production approval.",
        "saved_new_pending": "✅ Station created successfully. It remains pending production approval.",
        "saved_approved": "✅ Production station updated. Approval state was not changed.",
        "api_error": "❌ Server error:", "search_prompt": "Enter code, name, IP, or address.",
        "search_empty": "Search text is empty.", "search_no_results": "No stations found.",
        "search_results": "Search results:", "not_implemented": "This section is not available yet.",
        "access_title": "City Parking access", "access_username": "System username", "access_role": "Role",
        "access_status": "Status", "access_activation": "Activation", "activation_required": "Required",
        "activation_not_required": "Not required", "username_login_hint": "Use this exact username on the login page.",
        "role_admin": "Administrator", "role_operator": "Operator", "role_viewer": "Viewer",
    },
}

TEXT["ru"].update({
    "wizard_step": "Шаг {step} из 7", "enter_code": "Введите код станции. Например: 10002",
    "existing_edit_notice": "Станция {code} существует. Вы будете редактировать существующую запись.",
    "keep_current": "Сохранить текущие данные", "edit_station": "Редактировать данные станции",
    "no_changes": "Изменения не внесены.", "back": "⬅️ Назад", "select_city": "Выберите город",
    "city_dushanbe": "Душанбе", "select_district": "Выберите район",
    "area_prompt": "Введите зону или ориентир. Например: Таможня, Опера, Садбарг",
    "address_prompt": "Введите точный адрес: улица, дом или ближайший объект.",
    "keep_existing_field": "Оставить текущее значение", "keep_station_name": "Сохранить название станции",
    "change_station_name": "Изменить название станции", "use_suggested_name": "Использовать предложенное название",
    "name_prompt": "Введите короткое отображаемое название станции.",
    "suggested_name": "Предложенное название: {name}",
    "gps_prompt": "Отправьте геолокацию или пропустите этот шаг. Без GPS станция не появится на карте.",
    "skip_now": "Пропустить пока", "diff_title": "Проверьте изменения OLD → NEW:",
    "no_field_changes": "Изменяемых полей нет.", "save_changes": "Сохранить изменения",
    "create_station": "Создать станцию", "stale_action": "Эта кнопка устарела. Начните действие заново.",
    "saving": "Сохранение уже выполняется.",
    "saved_existing_pending": "Станция {code} обновлена. Она остаётся на рассмотрении для production.",
    "saved_new_pending": "Станция создана. Она остаётся на рассмотрении для production.",
    "label_city": "Город", "label_operational_area": "Зона / ориентир",
})
TEXT["tj"].update({
    "wizard_step": "Қадами {step} аз 7", "enter_code": "Коди стансияро ворид кунед. Мисол: 10002",
    "existing_edit_notice": "Стансияи {code} мавҷуд аст. Сабти мавҷуда таҳрир мешавад.",
    "keep_current": "Нигоҳ доштани маълумоти ҷорӣ", "edit_station": "Таҳрири маълумоти стансия",
    "no_changes": "Тағйирот ворид нашуд.", "back": "⬅️ Қафо", "select_city": "Шаҳрро интихоб кунед",
    "city_dushanbe": "Душанбе", "select_district": "Ноҳияро интихоб кунед",
    "area_prompt": "Минтақа ё ориентирро ворид кунед. Мисол: Таможня, Опера, Садбарг",
    "address_prompt": "Суроғаи дақиқро ворид кунед: кӯча, бино ё объекти наздик.",
    "keep_existing_field": "Нигоҳ доштани арзиши ҷорӣ", "keep_station_name": "Нигоҳ доштани номи стансия",
    "change_station_name": "Тағйири номи стансия", "use_suggested_name": "Истифодаи номи пешниҳодшуда",
    "name_prompt": "Номи кӯтоҳи намоишии стансияро ворид кунед.",
    "suggested_name": "Номи пешниҳодшуда: {name}",
    "gps_prompt": "Ҷойгиршавиро фиристед ё ҳоло гузаред. Бе GPS стансия дар харита намоиш дода намешавад.",
    "skip_now": "Ҳоло гузариш", "diff_title": "Тағйироти OLD → NEW-ро санҷед:",
    "no_field_changes": "Майдони тағйирёбанда нест.", "save_changes": "Сабти тағйирот",
    "create_station": "Сохтани стансия", "stale_action": "Ин тугма кӯҳна шудааст. Аз нав оғоз кунед.",
    "saving": "Сабт аллакай иҷро шуда истодааст.",
    "saved_existing_pending": "Стансияи {code} нав карда шуд. Он барои тасдиқи истеҳсолӣ интизор мемонад.",
    "saved_new_pending": "Стансия сохта шуд. Он барои тасдиқи истеҳсолӣ интизор мемонад.",
    "label_city": "Шаҳр", "label_operational_area": "Минтақа / ориентир",
})
TEXT["en"].update({
    "wizard_step": "Step {step} of 7", "enter_code": "Enter the station code. Example: 10002",
    "existing_edit_notice": "Station {code} exists. You will edit the existing record.",
    "keep_current": "Keep current data", "edit_station": "Edit station data", "no_changes": "No changes were made.",
    "back": "⬅️ Back", "select_city": "Select the city", "city_dushanbe": "Dushanbe",
    "select_district": "Select the district", "area_prompt": "Enter the operational area or landmark.",
    "address_prompt": "Enter the exact address: street, building, or nearby object.",
    "keep_existing_field": "Keep current value", "keep_station_name": "Keep station name",
    "change_station_name": "Change station name", "use_suggested_name": "Use suggested name",
    "name_prompt": "Enter a short station display name.", "suggested_name": "Suggested name: {name}",
    "gps_prompt": "Send location or skip for now. Without GPS the station will not appear on the map.",
    "skip_now": "Skip for now", "diff_title": "Review OLD → NEW changes:",
    "no_field_changes": "There are no field changes.", "save_changes": "Save changes",
    "create_station": "Create station", "stale_action": "This button is stale. Start the action again.",
    "saving": "A save is already in progress.",
    "saved_existing_pending": "Station {code} was updated. It remains pending production approval.",
    "saved_new_pending": "Station was created. It remains pending production approval.",
    "label_city": "City", "label_operational_area": "Operational area / landmark",
})


def lang_or_default(lang: str | None) -> str:
    return lang if lang in TEXT else "tj"


def t(lang: str | None, key: str) -> str:
    selected = lang_or_default(lang)
    return TEXT[selected].get(key, TEXT["tj"][key])


def menu_label(lang: str | None, key: str) -> str:
    selected = lang_or_default(lang)
    return MENU[selected][key]


def all_menu_labels(key: str) -> set[str]:
    return {labels[key] for labels in MENU.values()}


def all_texts(key: str) -> set[str]:
    return {labels[key] for labels in TEXT.values()}
