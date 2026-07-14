import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Language = "ru" | "tj" | "en";
export const SUPPORTED_LANGUAGES: Language[] = ["ru", "tj", "en"];
export const DEFAULT_LANGUAGE: Language = "ru";
export const LANGUAGE_STORAGE_KEY = "city-parking-language";

type Messages = Record<string, string>;

const RU: Messages = {
  "nav.dashboard": "Панель управления",
  "nav.stations": "Станции",
  "nav.cameras": "Камеры",
  "nav.map": "Карта",
  "nav.alerts": "Оповещения",
  "nav.reports": "Отчёты",
  "nav.rustdesk": "RustDesk",
  "nav.headscale": "Headscale",
  "nav.onboarding": "Ввод в эксплуатацию",
  "nav.telegram": "Доступ Telegram",
  "nav.n8n": "n8n",
  "nav.settings": "Настройки",
  "login.title": "Вход",
  "login.subtitle": "Доступ оператора к панели NOC.",
  "login.username": "Username / Имя пользователя",
  "login.usernameHelp": "Используйте точное имя пользователя, полученное от Telegram-бота.",
  "login.password": "Пароль",
  "login.submit": "Войти",
  "login.loading": "Вход…",
  "login.invalid": "Неверное имя пользователя или пароль.",
  "api.unauthorized": "Требуется вход в систему.",
  "api.forbidden": "Недостаточно прав для этого действия.",
  "api.notFound": "Запрошенные данные не найдены.",
  "api.conflict": "Данные изменились или конфликтуют. Обновите страницу и повторите попытку.",
  "api.unavailable": "Сервис временно недоступен. Повторите попытку позже.",
  "activate.title": "Активация учётной записи City Parking",
  "activate.code": "Код активации / сброса",
  "activate.password": "Новый пароль",
  "activate.confirm": "Подтвердите пароль",
  "activate.submit": "Активировать учётную запись",
  "activate.mismatch": "Пароли не совпадают.",
  "activate.failed": "Не удалось активировать учётную запись.",
  "activate.success": "Учётная запись активирована.",
  "activate.username": "Точное имя пользователя",
  "activate.role": "Роль",
  "activate.status": "Статус",
  "activate.copy": "Копировать имя пользователя",
  "activate.copied": "Имя пользователя скопировано",
  "activate.login": "Перейти ко входу",
  "common.logout": "Выйти",
  "common.active": "Активен",
  "common.inactive": "Неактивен",
  "common.retry": "Повторить",
  "loading.dashboard": "Загрузка панели управления…",
  "loading.stations": "Загрузка станций…",
  "loading.headscale": "Загрузка узлов Headscale…",
  "dashboard.attentionTitle": "Станции, требующие внимания",
  "dashboard.attentionSubtext":
    "Здесь показаны только станции со статусом снижена, офлайн или неизвестно.",
  "dashboard.viewAll": "Показать все",
  "dashboard.of": "из",
  "dashboard.stationsNoun": "станций",
  "health.latestLatency": "Текущая задержка",
  "health.degradedEnter": "Порог входа в сниженный статус",
  "health.degradedExit": "Порог выхода из сниженного статуса",
  "health.recoverySamples": "Пробы восстановления",
  "health.recoveryTimer": "Таймер стабильного восстановления",
  "health.canonicalReason": "Каноническая причина",
  "health.timeInState": "Время в текущем статусе",
  "approval.readOnly": "Предпросмотр только для чтения; изменения ещё не внесены.",
  "approval.requirements": "Обязательные условия допуска",
  "approval.verified_district": "Подтверждённый район Душанбе",
  "approval.linked_headscale_node": "Узел Headscale связан с этой станцией",
  "approval.approved_station_node": "Связанный узел допущен как устройство станции",
  "approval.one_to_one_link": "Связь станции и узла один-к-одному",
  "approval.monitoring_configured": "VPN мониторинга совпадает с узлом Headscale",
  "approval.ready": "Готово",
  "approval.blocked": "Не готово",
  "approval.copyPhrase": "Копировать фразу",
  "approval.copiedPhrase": "Фраза скопирована",
  "approval.disabled": "Действие заблокировано, пока все обязательные условия не выполнены.",
  "role.admin": "Администратор",
  "role.operator": "Оператор",
  "role.viewer": "Просмотр",
  "district.Ismoili Somoni": "Исмоили Сомони",
  "district.Shohmansur": "Шохмансур",
  "district.Sino": "Сино",
  "district.Firdavsi": "Фирдавси",
};

const TJ: Messages = {
  "nav.dashboard": "Лавҳаи идоракунӣ",
  "nav.stations": "Стансияҳо",
  "nav.cameras": "Камераҳо",
  "nav.map": "Харита",
  "nav.alerts": "Огоҳиҳо",
  "nav.reports": "Ҳисоботҳо",
  "nav.rustdesk": "RustDesk",
  "nav.headscale": "Headscale",
  "nav.onboarding": "Омодасозии истеҳсолӣ",
  "nav.telegram": "Дастрасии Telegram",
  "nav.n8n": "n8n",
  "nav.settings": "Танзимот",
  "login.title": "Воридшавӣ",
  "login.subtitle": "Дастрасии оператор ба лавҳаи NOC.",
  "login.username": "Номи корбар / Username",
  "login.usernameHelp": "Номи дақиқи аз Telegram-бот гирифташударо истифода баред.",
  "login.password": "Парол",
  "login.submit": "Ворид шудан",
  "login.loading": "Воридшавӣ…",
  "login.invalid": "Номи корбар ё парол нодуруст аст.",
  "api.unauthorized": "Воридшавӣ лозим аст.",
  "api.forbidden": "Барои ин амал иҷозат кофӣ нест.",
  "api.notFound": "Маълумоти дархостшуда ёфт нашуд.",
  "api.conflict": "Маълумот тағйир ёфт. Саҳифаро нав карда, такрор кунед.",
  "api.unavailable": "Хидмат муваққатан дастнорас аст.",
  "activate.title": "Фаъолсозии ҳисоби City Parking",
  "activate.code": "Коди фаъолсозӣ / барқарорсозӣ",
  "activate.password": "Пароли нав",
  "activate.confirm": "Паролро тасдиқ кунед",
  "activate.submit": "Фаъол кардани ҳисоб",
  "activate.mismatch": "Паролҳо мувофиқ нестанд.",
  "activate.failed": "Фаъолсозӣ иҷро нашуд.",
  "activate.success": "Ҳисоб фаъол шуд.",
  "activate.username": "Номи дақиқи корбар",
  "activate.role": "Нақш",
  "activate.status": "Ҳолат",
  "activate.copy": "Нусхабардории номи корбар",
  "activate.copied": "Номи корбар нусхабардорӣ шуд",
  "activate.login": "Ба воридшавӣ гузаред",
  "common.logout": "Баромадан",
  "common.active": "Фаъол",
  "common.inactive": "Ғайрифаъол",
  "common.retry": "Такрор кардан",
  "loading.dashboard": "Панели идоракунӣ бор шуда истодааст…",
  "loading.stations": "Стансияҳо бор шуда истодаанд…",
  "loading.headscale": "Узелҳои Headscale бор шуда истодаанд…",
  "dashboard.attentionTitle": "Стансияҳои мушкилдор",
  "dashboard.attentionSubtext":
    "Дар ин ҷо танҳо стансияҳои мушкилдор, хомӯш ё номаълум нишон дода мешаванд.",
  "dashboard.viewAll": "Намоиши ҳамаи",
  "dashboard.of": "аз",
  "dashboard.stationsNoun": "стансия",
  "health.latestLatency": "Таъхири ҷорӣ",
  "health.degradedEnter": "Ҳадди воридшавӣ ба ҳолати мушкилдор",
  "health.degradedExit": "Ҳадди баромадан аз ҳолати мушкилдор",
  "health.recoverySamples": "Намунаҳои барқароршавӣ",
  "health.recoveryTimer": "Вақтсанҷи барқароршавии устувор",
  "health.canonicalReason": "Сабаби канонӣ",
  "health.timeInState": "Вақт дар ҳолати ҷорӣ",
  "approval.readOnly": "Пешнамоиш танҳо барои хондан аст; ҳанӯз тағйирот ворид нашудааст.",
  "approval.requirements": "Шартҳои ҳатмии тасдиқ",
  "approval.verified_district": "Ноҳияи тасдиқшудаи Душанбе",
  "approval.linked_headscale_node": "Узели Headscale ба ин стансия пайваст аст",
  "approval.approved_station_node": "Узели пайваст ҳамчун дастгоҳи стансия тасдиқ шудааст",
  "approval.one_to_one_link": "Пайванди як-ба-яки стансия ва узел",
  "approval.monitoring_configured": "VPN-и мониторинг бо узели Headscale мувофиқ аст",
  "approval.ready": "Омода",
  "approval.blocked": "Омода нест",
  "approval.copyPhrase": "Нусхабардории ибора",
  "approval.copiedPhrase": "Ибора нусхабардорӣ шуд",
  "approval.disabled": "То иҷро шудани ҳамаи шартҳои ҳатмӣ амал баста аст.",
  "role.admin": "Администратор",
  "role.operator": "Оператор",
  "role.viewer": "Намоиш",
  "district.Ismoili Somoni": "Исмоили Сомонӣ",
  "district.Shohmansur": "Шоҳмансур",
  "district.Sino": "Сино",
  "district.Firdavsi": "Фирдавсӣ",
};

const EN: Messages = {
  "nav.dashboard": "Dashboard",
  "nav.stations": "Stations",
  "nav.cameras": "Cameras",
  "nav.map": "Map",
  "nav.alerts": "Alerts",
  "nav.reports": "Reports",
  "nav.rustdesk": "RustDesk",
  "nav.headscale": "Headscale",
  "nav.onboarding": "Onboarding",
  "nav.telegram": "Telegram Access",
  "nav.n8n": "n8n",
  "nav.settings": "Settings",
  "login.title": "Sign in",
  "login.subtitle": "Operator access to the NOC dashboard.",
  "login.username": "Username / Имя пользователя",
  "login.usernameHelp": "Use the exact username received from the Telegram bot.",
  "login.password": "Password",
  "login.submit": "Sign in",
  "login.loading": "Signing in…",
  "login.invalid": "Invalid username or password.",
  "api.unauthorized": "Authentication is required.",
  "api.forbidden": "You do not have permission for this action.",
  "api.notFound": "The requested data was not found.",
  "api.conflict": "The data changed or conflicts. Refresh and try again.",
  "api.unavailable": "The service is temporarily unavailable. Try again later.",
  "activate.title": "Activate City Parking account",
  "activate.code": "Activation / reset code",
  "activate.password": "New password",
  "activate.confirm": "Confirm password",
  "activate.submit": "Activate account",
  "activate.mismatch": "Passwords do not match.",
  "activate.failed": "Activation failed.",
  "activate.success": "Account activated.",
  "activate.username": "Exact username",
  "activate.role": "Role",
  "activate.status": "Status",
  "activate.copy": "Copy username",
  "activate.copied": "Username copied",
  "activate.login": "Go to login",
  "common.logout": "Logout",
  "common.active": "Active",
  "common.inactive": "Inactive",
  "common.retry": "Retry",
  "loading.dashboard": "Loading dashboard…",
  "loading.stations": "Loading stations…",
  "loading.headscale": "Loading Headscale nodes…",
  "dashboard.attentionTitle": "Stations requiring attention",
  "dashboard.attentionSubtext": "Only degraded, offline, or unknown stations are shown here.",
  "dashboard.viewAll": "View all",
  "dashboard.of": "of",
  "dashboard.stationsNoun": "stations",
  "health.latestLatency": "Current latest latency",
  "health.degradedEnter": "Degraded-enter threshold",
  "health.degradedExit": "Degraded-exit threshold",
  "health.recoverySamples": "Recovery samples",
  "health.recoveryTimer": "Stable-recovery timer",
  "health.canonicalReason": "Canonical reason",
  "health.timeInState": "Time in current state",
  "approval.readOnly": "Read-only preview; no change has been made.",
  "approval.requirements": "Required approval checks",
  "approval.verified_district": "Verified Dushanbe district",
  "approval.linked_headscale_node": "Headscale node linked to this station",
  "approval.approved_station_node": "Linked node approved as a station device",
  "approval.one_to_one_link": "Station and node have a one-to-one link",
  "approval.monitoring_configured": "Monitoring VPN matches the Headscale node",
  "approval.ready": "Ready",
  "approval.blocked": "Not ready",
  "approval.copyPhrase": "Copy phrase",
  "approval.copiedPhrase": "Phrase copied",
  "approval.disabled": "This action is blocked until every required check passes.",
  "role.admin": "Administrator",
  "role.operator": "Operator",
  "role.viewer": "Viewer",
  "district.Ismoili Somoni": "Ismoili Somoni",
  "district.Shohmansur": "Shohmansur",
  "district.Sino": "Sino",
  "district.Firdavsi": "Firdavsi",
};

const DICTIONARIES: Record<Language, Messages> = { ru: RU, tj: TJ, en: EN };

const LITERALS: Record<string, [string, string]> = {
  Dashboard: ["Панель управления", "Лавҳаи идоракунӣ"],
  "Operations Overview": ["Операционный обзор", "Шарҳи амалиёт"],
  "Uptime & Availability": ["Доступность и время работы", "Дастрасӣ ва вақти кор"],
  Stations: ["Станции", "Стансияҳо"],
  Cameras: ["Камеры", "Камераҳо"],
  Map: ["Карта", "Харита"],
  Alerts: ["Оповещения", "Огоҳиҳо"],
  Reports: ["Отчёты", "Ҳисоботҳо"],
  Onboarding: ["Ввод в эксплуатацию", "Омодасозии истеҳсолӣ"],
  "Production Onboarding": ["Ввод станций в эксплуатацию", "Омодасозии стансияҳо"],
  "Telegram Access": ["Доступ Telegram", "Дастрасии Telegram"],
  Settings: ["Настройки", "Танзимот"],
  "Station approval": ["Допуск станции", "Тасдиқи стансия"],
  "District assignment": ["Назначение района", "Таъини ноҳия"],
  "Duplicate VPN report": ["Отчёт о дубликатах VPN", "Ҳисоботи VPN-и такрорӣ"],
  "Duplicate alert dry-run": ["Проверка дубликатов оповещений", "Санҷиши огоҳиҳои такрорӣ"],
  "Station code": ["Код станции", "Коди стансия"],
  "Station name": ["Название станции", "Номи стансия"],
  District: ["Район", "Ноҳия"],
  Address: ["Адрес", "Суроға"],
  Status: ["Статус", "Ҳолат"],
  "Last seen": ["Последняя активность", "Охирин фаъолият"],
  Actions: ["Действия", "Амалҳо"],
  Action: ["Действие", "Амал"],
  User: ["Пользователь", "Корбар"],
  Role: ["Роль", "Нақш"],
  Requested: ["Запрошено", "Дархост"],
  Review: ["Рассмотрение", "Баррасӣ"],
  Select: ["Выбор", "Интихоб"],
  Current: ["Текущее", "Ҷорӣ"],
  Proposed: ["Предлагаемое", "Пешниҳод"],
  Change: ["Изменение", "Тағйир"],
  Type: ["Тип", "Навъ"],
  Severity: ["Критичность", "Дараҷаи хатар"],
  Message: ["Сообщение", "Паём"],
  Created: ["Создано", "Сохта шуд"],
  Acknowledged: ["Подтверждено", "Тасдиқ шуд"],
  Availability: ["Доступность", "Дастрасӣ"],
  Degraded: ["Снижена", "Пастшуда"],
  Unknown: ["Неизвестно", "Номаълум"],
  Outages: ["Сбои", "Қатъшавӣ"],
  Longest: ["Максимальный", "Дарозтарин"],
  Average: ["Средний", "Миёна"],
  Permission: ["Разрешение", "Иҷозат"],
  Node: ["Узел", "Узел"],
  "Hostname / name": ["Имя узла / название", "Номи узел"],
  "Device type": ["Тип устройства", "Навъи дастгоҳ"],
  "Linked station": ["Связанная станция", "Стансияи пайваст"],
  "Linked node": ["Связанный узел", "Узели пайваст"],
  "Headscale hostname": ["Имя узла Headscale", "Номи Headscale"],
  "Headscale approval": ["Допуск Headscale", "Тасдиқи Headscale"],
  "Existing user link": ["Связь с пользователем", "Пайваст ба корбар"],
  "System username": ["Системное имя пользователя", "Номи корбари система"],
  "Current role": ["Текущая роль", "Нақши ҷорӣ"],
  "Active status": ["Статус активности", "Ҳолати фаъолият"],
  "Monitoring readiness": ["Готовность мониторинга", "Омодагии мониторинг"],
  "Canonical alert": ["Основное оповещение", "Огоҳии асосӣ"],
  "Proposed resolution": ["Предлагаемое закрытие", "Ҳалли пешниҳодшуда"],
  "Open count": ["Открыто", "Кушода"],
  Oldest: ["Самое раннее", "Куҳнатарин"],
  Newest: ["Самое новое", "Навтарин"],
  "Safe actions": ["Безопасные действия", "Амалҳои бехатар"],
  "Station inventory": ["Инвентарь станций", "Феҳристи стансияҳо"],
  "Operational area": ["Зона / ориентир", "Минтақа / ориентир"],
  "Headscale node": ["Узел Headscale", "Узели Headscale"],
  "Approval state": ["Статус допуска", "Ҳолати тасдиқ"],
  "Record state": ["Состояние записи", "Ҳолати сабт"],
  "Repair data": ["Исправить данные", "Ислоҳи маълумот"],
  "Link Headscale": ["Связать Headscale", "Пайваст кардани Headscale"],
  "Prepare for production": ["Подготовить к production", "Омода барои истеҳсолот"],
  "Archive station": ["Архивировать станцию", "Бойгонии стансия"],
  "Restore archived station": ["Восстановить станцию", "Барқарор кардани стансия"],
  "Production approved": ["Допущена в production", "Барои истеҳсолот тасдиқшуда"],
  Archived: ["В архиве", "Бойгонӣ"],
  Active: ["Активна", "Фаъол"],
  Inactive: ["Неактивна", "Ғайрифаъол"],
  all: ["все", "ҳама"],
  pending: ["ожидающие", "интизор"],
  approved: ["допущенные", "тасдиқшуда"],
  archived: ["архивные", "бойгонӣ"],
  "missing headscale": ["без Headscale", "бе Headscale"],
  "suspected duplicate": ["возможные дубликаты", "такрори эҳтимолӣ"],
  "data quality": ["проблемы качества", "мушкилоти сифат"],
  "Suspected duplicate dry-run": [
    "Предпросмотр возможных дубликатов",
    "Пешнамоиши такрори эҳтимолӣ",
  ],
  "Edit classification / Link station": [
    "Изменить классификацию / связать станцию",
    "Тағйири тасниф / пайвасти стансия",
  ],
  "Apply classification": ["Применить классификацию", "Татбиқи тасниф"],
  "Current station VPN": ["Текущий VPN станции", "VPN-и ҷории стансия"],
  Connectivity: ["Подключение", "Пайвастшавӣ"],
  "Existing links": ["Текущие связи", "Пайвандҳои ҷорӣ"],
  "Select station": ["Выберите станцию", "Стансияро интихоб кунед"],
  "Select station node": ["Выберите узел станции", "Узели стансияро интихоб кунед"],
  "Apply repair": ["Применить исправление", "Татбиқи ислоҳ"],
  "Preview changes": ["Предпросмотр изменений", "Пешнамоиши тағйирот"],
  Repair: ["Исправить", "Ислоҳ"],
  Archive: ["Архивировать", "Бойгонӣ"],
  "Keep both": ["Оставить обе", "Ҳар дуро нигоҳ доштан"],
  "Link node (does not publish)": ["Связать узел (не публикует)", "Пайвасти узел (нашр намекунад)"],
  "Publish station to Dashboard": [
    "Опубликовать станцию на Dashboard",
    "Нашри стансия дар Dashboard",
  ],
  "Separate production approval": ["Отдельный production-допуск", "Тасдиқи алоҳидаи истеҳсолӣ"],
  Ready: ["Готово", "Омода"],
  Blocked: ["Заблокировано", "Баста"],
  "Confirm archive": ["Подтвердить архивирование", "Тасдиқи бойгонӣ"],
  "Confirm restore": ["Подтвердить восстановление", "Тасдиқи барқарорсозӣ"],
  unknown: ["неизвестно", "номаълум"],
  station: ["станция", "стансия"],
  operator_pc: ["ПК оператора", "Компютери оператор"],
  admin_pc: ["ПК администратора", "Компютери администратор"],
  phone: ["телефон", "телефон"],
  server: ["сервер", "сервер"],
  "Operator Activity": ["Активность операторов", "Фаъолияти операторҳо"],
  "Registration review": ["Проверка регистраций", "Баррасии сабти ном"],
  "Application presence": ["Присутствие в приложении", "Ҳузур дар барнома"],
  "Last activity": ["Последняя активность", "Фаъолияти охирин"],
  "Current workflow": ["Текущий процесс", "Раванди ҷорӣ"],
  "All roles": ["Все роли", "Ҳамаи нақшҳо"],
  "All presence": ["Любое присутствие", "Ҳамаи ҳолатҳои ҳузур"],
  "All sources": ["Все источники", "Ҳамаи манбаъҳо"],
  "All workflow states": ["Все состояния процессов", "Ҳамаи ҳолатҳои раванд"],
  "Search operator, Telegram ID, station or action": [
    "Поиск по оператору, Telegram ID, станции или действию",
    "Ҷустуҷӯи оператор, Telegram ID, стансия ё амал",
  ],
  "From (Dushanbe)": ["С (Душанбе)", "Аз (Душанбе)"],
  "To (Dushanbe)": ["По (Душанбе)", "То (Душанбе)"],
  "Recently active": ["Недавно активен", "Ба наздикӣ фаъол"],
  online: ["онлайн", "онлайн"],
  recently_active: ["недавно активен", "ба наздикӣ фаъол"],
  "recently active": ["недавно активен", "ба наздикӣ фаъол"],
  offline: ["офлайн", "офлайн"],
  in_progress: ["в процессе", "дар ҷараён"],
  "in progress": ["в процессе", "дар ҷараён"],
  completed: ["завершено", "анҷом ёфт"],
  cancelled: ["отменено", "бекор шуд"],
  failed: ["ошибка", "хато"],
  abandoned: ["не завершено", "нотамом"],
  web: ["веб", "веб"],
  telegram: ["Telegram", "Telegram"],
  api: ["API", "API"],
  "Step:": ["Шаг:", "Қадам:"],
  "Fields:": ["Поля:", "Майдонҳо:"],
  "City Skyline activity, not Telegram presence": [
    "Активность в City Skyline, не статус присутствия Telegram",
    "Фаъолият дар City Skyline, на ҳузури Telegram",
  ],
  "Full administration, approvals, access and security operations.": [
    "Полное администрирование, допуски, доступ и операции безопасности.",
    "Идоракунии пурра, тасдиқ, дастрасӣ ва амалиёти амниятӣ.",
  ],
  "Register/update station data and use monitoring; no approvals, links, archives, roles or resets.":
    [
      "Регистрация и обновление данных станций и мониторинг; без допусков, связей, архива, ролей и сбросов.",
      "Сабт ва навсозии стансия ва мониторинг; бе тасдиқ, пайваст, бойгонӣ, нақш ва барқарорсозӣ.",
    ],
  "Read-only dashboards, searches, summaries and reports.": [
    "Только чтение панелей, поиска, сводок и отчётов.",
    "Танҳо хондани лавҳаҳо, ҷустуҷӯ, хулоса ва ҳисобот.",
  ],
  Approval: ["Одобрение", "Тасдиқ"],
  "Approval status": ["Статус допуска", "Ҳолати тасдиқ"],
  "Production approval": ["Production-допуск", "Тасдиқи истеҳсолӣ"],
  "Monitoring status": ["Статус мониторинга", "Ҳолати мониторинг"],
  "Operating system": ["Операционная система", "Системаи амалиётӣ"],
  Online: ["Онлайн", "Онлайн"],
  Offline: ["Офлайн", "Офлайн"],
  Pending: ["Ожидает", "Интизор"],
  Approved: ["Одобрено", "Тасдиқшуда"],
  Rejected: ["Отклонено", "Радшуда"],
  All: ["Все", "Ҳама"],
  Linked: ["Связано", "Пайваст"],
  Unlinked: ["Не связано", "Пайваст нест"],
  Critical: ["Критическое", "Хатарнок"],
  Warning: ["Предупреждение", "Огоҳӣ"],
  Info: ["Информация", "Маълумот"],
  "All districts": ["Все районы", "Ҳамаи ноҳияҳо"],
  "All statuses": ["Все статусы", "Ҳамаи ҳолатҳо"],
  "All severities": ["Все уровни", "Ҳамаи дараҷаҳо"],
  "All approvals": ["Все допуски", "Ҳамаи тасдиқҳо"],
  "All links": ["Все связи", "Ҳамаи пайвастҳо"],
  "All device types": ["Все типы устройств", "Ҳамаи навъҳои дастгоҳ"],
  "All connectivity": ["Любое подключение", "Ҳамаи пайвастҳо"],
  Search: ["Поиск", "Ҷустуҷӯ"],
  Filters: ["Фильтры", "Филтрҳо"],
  "Clear filters": ["Сбросить фильтры", "Тоза кардани филтрҳо"],
  Cancel: ["Отмена", "Бекор кардан"],
  Confirm: ["Подтвердить", "Тасдиқ"],
  Save: ["Сохранить", "Сабт"],
  "Approve station": ["Допустить станцию", "Тасдиқи стансия"],
  "Remove from production": ["Убрать из production", "Аз истеҳсолот хориҷ кардан"],
  "Link to existing user": [
    "Связать с существующим пользователем",
    "Ба корбари мавҷуд пайваст кардан",
  ],
  "Send password reset": ["Отправить сброс пароля", "Ирсоли барқарорсозии парол"],
  "Send single-use reset link": ["Отправить одноразовую ссылку", "Ирсоли пайванди якдафъаина"],
  "Password reset preview": ["Предпросмотр сброса пароля", "Пешнамоиши барқарорсозии парол"],
  "Confirm Headscale approval": ["Подтверждение допуска Headscale", "Тасдиқи Headscale"],
  "Station approval preview": ["Предпросмотр допуска станции", "Пешнамоиши тасдиқи стансия"],
  "Production removal preview": ["Предпросмотр удаления из production", "Пешнамоиши хориҷкунӣ"],
  "District assignment preview": ["Предпросмотр назначения района", "Пешнамоиши таъини ноҳия"],
  "Apply assignments": ["Применить назначения", "Татбиқи таъинот"],
  "Apply confirmed action": ["Выполнить подтверждённое действие", "Иҷрои амали тасдиқшуда"],
  "No registration requests.": ["Нет запросов на регистрацию.", "Дархости сабти ном нест."],
  "No stations match this approval filter.": [
    "Нет станций с таким статусом допуска.",
    "Стансия бо ин филтр нест.",
  ],
  "No nodes match these filters.": ["Нет узлов с такими фильтрами.", "Узел бо ин филтр нест."],
  "No alerts found.": ["Оповещения не найдены.", "Огоҳӣ ёфт нашуд."],
  "No cameras configured.": ["Камеры не настроены.", "Камера танзим нашудааст."],
  "No active alerts.": ["Нет активных оповещений.", "Огоҳии фаъол нест."],
  "No active alerts match.": ["Нет подходящих активных оповещений.", "Огоҳии мувофиқ нест."],
  "No stations match these filters.": [
    "Нет станций с такими фильтрами.",
    "Стансия бо ин филтр нест.",
  ],
  "No monitored status history for this period.": [
    "Нет истории мониторинга за этот период.",
    "Таърихи мониторинг нест.",
  ],
  "Uptime Reports": ["Отчёты по доступности", "Ҳисоботи кори стансияҳо"],
  "Measured status history · unknown intervals remain unknown": [
    "Измеренная история состояний · неизвестные интервалы остаются неизвестными",
    "Таърихи ченшудаи ҳолат · фосилаҳои номаълум номаълум мемонанд",
  ],
  From: ["С", "Аз"],
  To: ["По", "То"],
  Station: ["Станция", "Стансия"],
  "Current status": ["Текущий статус", "Ҳолати ҷорӣ"],
  "All stations": ["Все станции", "Ҳамаи стансияҳо"],
  "Run report": ["Сформировать отчёт", "Сохтани ҳисобот"],
  "Download CSV": ["Скачать CSV", "Боргирии CSV"],
  "Download XLSX": ["Скачать XLSX", "Боргирии XLSX"],
  "Preparing CSV…": ["Подготовка CSV…", "Омодасозии CSV…"],
  "Preparing XLSX…": ["Подготовка XLSX…", "Омодасозии XLSX…"],
  "Measured uptime": ["Измеренный uptime", "Фоизи кори ченшуда"],
  "Data coverage": ["Покрытие данными", "Фарогирии маълумот"],
  "Code / station": ["Код / станция", "Код / стансия"],
  "Last change": ["Последнее изменение", "Тағйири охирин"],
  "No data": ["Нет измеренных данных", "Маълумоти ченшуда нест"],
  "Measured uptime = online ÷ (online + degraded + offline). Data coverage = measured time ÷ selected range. Unknown means no measured data and is never counted as offline.":
    [
      "Измеренный uptime = онлайн ÷ (онлайн + с проблемами + офлайн). Покрытие данными = измеренное время ÷ выбранный период. Неизвестно означает отсутствие измерений и никогда не считается офлайном.",
      "Фоизи кори ченшуда = онлайн ÷ (онлайн + мушкилдор + хомӯш). Фарогирии маълумот = вақти ченшуда ÷ давраи интихобшуда. Номаълум маънои набудани ченакро дорад ва ҳеҷ гоҳ хомӯш ҳисоб намешавад.",
    ],
  "Online for:": ["Онлайн в течение:", "Онлайн дар давоми:"],
  "Last seen:": ["Последняя связь:", "Алоқаи охирин:"],
  "Camera:": ["Камера:", "Камера:"],
  "Internet:": ["Интернет:", "Интернет:"],
  "Station connectivity:": ["Связь со станцией:", "Алоқа бо стансия:"],
  "Problem:": ["Проблема:", "Мушкил:"],
  "Problem duration:": ["Длительность проблемы:", "Давомнокии мушкил:"],
  "Offline since:": ["Офлайн с:", "Хомӯш аз:"],
  "Offline for:": ["Офлайн в течение:", "Хомӯш дар давоми:"],
  "Reason:": ["Причина:", "Сабаб:"],
  "Last reliable observation:": ["Последнее надёжное измерение:", "Ченаки боэътимоди охирин:"],
  "Connectivity and configured components are healthy": [
    "Связь и настроенные компоненты исправны",
    "Алоқа ва ҷузъҳои танзимшуда солиманд",
  ],
  "Headscale is offline": ["Headscale офлайн", "Headscale хомӯш аст"],
  "Headscale last seen is stale": [
    "Данные Headscale устарели",
    "Маълумоти Headscale кӯҳна шудааст",
  ],
  "Station connectivity check failed": [
    "Проверка связи со станцией неуспешна",
    "Санҷиши алоқа бо стансия ноком шуд",
  ],
  "Measured ping latency is high": [
    "Измеренная задержка ping высокая",
    "Таъхири ченшудаи ping баланд аст",
  ],
  "Monitoring-agent heartbeat is stale": [
    "Heartbeat агента мониторинга устарел",
    "Heartbeat-и агенти мониторинг кӯҳна шудааст",
  ],
  "Station online, camera offline": [
    "Станция онлайн, камера офлайн",
    "Стансия онлайн, камера хомӯш",
  ],
  "Camera RTSP check failed": ["Проверка RTSP камеры неуспешна", "Санҷиши RTSP-и камера ноком шуд"],
  "Monitoring is not configured": ["Мониторинг не настроен", "Мониторинг танзим нашудааст"],
  "Insufficient fresh measured data": [
    "Недостаточно свежих измеренных данных",
    "Маълумоти нави ченшуда кофӣ нест",
  ],
  "Exact cause is not determined": ["Причина точно не определена", "Сабаби дақиқ муайян нашуд"],
  "No linked RustDesk devices.": [
    "Нет связанных устройств RustDesk.",
    "Дастгоҳи RustDesk пайваст нест.",
  ],
  "No unplaced stations.": ["Нет станций без координат.", "Стансияи бе координата нест."],
  "No duplicated station VPN addresses.": [
    "Нет дублирующихся VPN-адресов станций.",
    "VPN-и такрорӣ нест.",
  ],
  "Search cameras…": ["Поиск камер…", "Ҷустуҷӯи камераҳо…"],
  "Search active alerts…": ["Поиск активных оповещений…", "Ҷустуҷӯи огоҳиҳо…"],
  "Search code, name, district, address, IP, hostname…": [
    "Поиск по коду, названию, району, адресу, IP, имени узла…",
    "Ҷустуҷӯ аз рӯи код, ном, ноҳия, суроға, IP…",
  ],
};

export function initialLanguage(storage?: Pick<Storage, "getItem">): Language {
  const stored = storage?.getItem(LANGUAGE_STORAGE_KEY);
  return SUPPORTED_LANGUAGES.includes(stored as Language) ? (stored as Language) : DEFAULT_LANGUAGE;
}

export function translate(language: Language, key: string): string {
  return DICTIONARIES[language][key] ?? EN[key] ?? key;
}

export function currentLanguage(): Language {
  return typeof window === "undefined" ? DEFAULT_LANGUAGE : initialLanguage(window.localStorage);
}

export function apiErrorMessage(language: Language, status: number, detail: string): string {
  if (status === 401) return translate(language, "api.unauthorized");
  if (status === 403) return translate(language, "api.forbidden");
  if (status >= 500) return translate(language, "api.unavailable");
  if (detail && !detail.startsWith("Request failed")) return detail;
  if (status === 404) return translate(language, "api.notFound");
  if (status === 409) return translate(language, "api.conflict");
  return detail;
}

export function roleLabel(language: Language, role: "admin" | "operator" | "viewer"): string {
  return translate(language, `role.${role}`);
}

export function districtLabel(language: Language, district: string | null): string {
  return district ? translate(language, `district.${district}`) : "—";
}

function literal(language: Language, source: string): string {
  if (language === "en") return source;
  const row = LITERALS[source];
  return row ? row[language === "ru" ? 0 : 1] : source;
}

type I18nContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: string) => string;
  role: (role: "admin" | "operator" | "viewer") => string;
  district: (district: string | null) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);
const originalText = new WeakMap<Text, string>();
const translatedText = new WeakMap<Text, string>();

function localizeDom(language: Language, root: ParentNode) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode() as Text | null;
  while (node) {
    const parent = node.parentElement;
    if (parent && !["SCRIPT", "STYLE"].includes(parent.tagName)) {
      const previousTranslation = translatedText.get(node);
      const source =
        previousTranslation !== undefined && node.data !== previousTranslation
          ? node.data
          : (originalText.get(node) ?? node.data);
      originalText.set(node, source);
      const trimmed = source.trim();
      if (trimmed) {
        const translated = literal(language, trimmed);
        const start = source.indexOf(trimmed);
        const next = source.slice(0, start) + translated + source.slice(start + trimmed.length);
        translatedText.set(node, next);
        if (node.data !== next) node.data = next;
      }
    }
    node = walker.nextNode() as Text | null;
  }
  root.querySelectorAll?.<HTMLElement>("[placeholder]").forEach((element) => {
    const source = element.dataset.i18nPlaceholder ?? element.getAttribute("placeholder") ?? "";
    element.dataset.i18nPlaceholder = source;
    element.setAttribute("placeholder", literal(language, source));
  });
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() =>
    typeof window === "undefined" ? DEFAULT_LANGUAGE : initialLanguage(window.localStorage),
  );
  const setLanguage = (next: Language) => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, next);
    setLanguageState(next);
  };
  useEffect(() => {
    document.documentElement.lang = language;
    localizeDom(language, document.body);
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) localizeDom(language, node as Element);
          else if (node.nodeType === Node.TEXT_NODE && node.parentNode)
            localizeDom(language, node.parentNode);
        });
        if (mutation.type === "characterData" && mutation.target.parentNode) {
          localizeDom(language, mutation.target.parentNode);
        }
      }
    });
    observer.observe(document.body, { subtree: true, childList: true, characterData: true });
    return () => observer.disconnect();
  }, [language]);
  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      setLanguage,
      t: (key) => translate(language, key),
      role: (role) => roleLabel(language, role),
      district: (district) => districtLabel(language, district),
    }),
    [language],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used within I18nProvider");
  return value;
}
