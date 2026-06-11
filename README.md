# TG Contact Extractor

**[English version below](#english)**

---

## Описание

Десктопное приложение для извлечения структурированных данных из экспортов Telegram-чатов с помощью LLM (Large Language Model). Работает локально, без сервера.

Загружаете JSON-экспорт из Telegram Desktop, выбираете промпт (что извлекать), нажимаете "Запустить" — получаете JSON + Excel с результатами.

## Возможности

- Парсинг экспортов Telegram Desktop (`result.json`)
- Извлечение данных через бесплатные LLM-модели (OpenRouter API)
- Настраиваемые промпты — извлекайте вакансии, контакты, реквизиты или что угодно
- Двойной вывод: JSON (для анализа) + Excel (для людей)
- GUI с тёмной темой (CustomTkinter) и CLI-режим
- Менеджер промптов: создание, редактирование, выбор из сохранённых
- Инкрементальное сохранение — при сбое данные не теряются
- Сборка в один `.exe` файл через PyInstaller

## Быстрый старт

### Установка

```bash
git clone https://github.com/YOUR_USERNAME/tg-contact-extractor.git
cd tg-contact-extractor
pip install -r requirements.txt
```

### Запуск GUI

```bash
python -m src.app
```

### Запуск CLI

```bash
python -m src.app ./ChatExport/result.json --api-key sk-or-... --prompt vacancies
```

### Настройка

1. Получите бесплатный API-ключ на [openrouter.ai](https://openrouter.ai)
2. Создайте файл `.env` в корне проекта:
   ```
   OPENROUTER_API_KEY=sk-or-ваш-ключ
   ```
3. Или введите ключ в GUI

## Скриншот

```
+------------------------------------------+
|  TG Contact Extractor            v3.0    |
|  Извлечение данных из экспорта Telegram   |
|                                          |
|  [Извлечение]  [Промпт]                 |
|                                          |
|  ФАЙЛ ЭКСПОРТА                           |
|  [result.json                  ] [Обзор] |
|                                          |
|  API KEY              МОДЕЛЬ             |
|  [********] [*]    [Gemini 2.0 Flash  v] |
|                                          |
|  ПРОГРЕСС                                |
|  [========================] 100%         |
|                                          |
|  [Запустить]  [JSON]  [Excel]            |
+------------------------------------------+
```

## Промпты

Промпты хранятся в папке `prompts/` как `.txt` файлы. В комплекте:

| Файл | Назначение |
|------|-----------|
| `vacancies.txt` | Извлечение вакансий, компаний, рекрутеров |
| `contacts_general.txt` | Общее извлечение любых контактов |

Создавайте свои промпты через вкладку "Промпт" в GUI или вручную в папке `prompts/`.

## Модели

Протестированные бесплатные модели (OpenRouter):

| Модель | Скорость | Качество |
|--------|----------|----------|
| **Gemini 2.0 Flash** (по умолчанию) | ~5 сек | Отличное |
| StepFun 3.5 Flash | ~13 сек | Отличное |
| OpenAI GPT-OSS 120B | ~28 сек | Отличное |
| NVIDIA Nemotron 3 Super 120B | ~44 сек | Отличное |
| Qwen 3.6 Plus | ~66 сек | Отличное+ |
| MiniMax M2.5 | ~117 сек | Отличное |

Запуск бенчмарка: `python benchmark.py`

## Формат вывода

### JSON

```json
{
  "extraction_meta": {
    "source": "ChatExport/result.json",
    "total_messages": 12450,
    "processed_batches": 249,
    "date": "2026-04-06",
    "prompt": "..."
  },
  "contacts": [
    {
      "source_message_id": 4521,
      "from_user": "Анна",
      "context": "Вакансия Python-разработчика",
      "extracted": [
        {"type": "вакансия", "value": "Python Developer"},
        {"type": "компания", "value": "ООО Ромашка"},
        {"type": "email", "value": "hr@romashka.ru"}
      ]
    }
  ]
}
```

### Excel

Автоматически генерируется из JSON:
- Динамические столбцы на основе найденных типов
- Лист "Сводка" со статистикой и использованным промптом
- Автофильтр, заморозка заголовков, зебра-полоски

## Структура проекта

```
tg-contact-extractor/
├── src/
│   ├── config.py        # Конфигурация, .env, список моделей
│   ├── parser.py        # Парсинг Telegram JSON
│   ├── batcher.py       # Группировка сообщений в пакеты
│   ├── extractor.py     # LLM API + менеджер промптов
│   ├── writer.py        # JSON-вывод с метаданными
│   ├── to_excel.py      # JSON -> Excel конвертер
│   └── app.py           # GUI (CustomTkinter) + CLI
├── tests/               # 46 тестов (pytest)
├── prompts/             # Сохранённые промпты (.txt)
├── docs/                # GRACE-документация
├── benchmark.py         # Бенчмарк моделей
├── requirements.txt
└── .env.example
```

## Сборка в .exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "TG-Contact-Extractor" src/app.py
```

Результат: `dist/TG-Contact-Extractor.exe` (~37 MB). Положите рядом `.env` и папку `prompts/`.

## Тесты

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

## Лицензия

MIT

---

<a name="english"></a>

# TG Contact Extractor (English)

Desktop application for extracting structured data from Telegram chat exports using LLM. Runs locally, no server required.

## Features

- Parse Telegram Desktop exports (`result.json`)
- Extract data via free LLM models (OpenRouter API / Gemini Flash)
- Customizable prompts — extract job postings, contacts, bank details, or anything
- Dual output: JSON (for analysis) + Excel (for humans)
- Dark-themed GUI (CustomTkinter) + CLI mode
- Prompt manager: create, edit, select from saved prompts
- Incremental saving — no data loss on crashes
- Single `.exe` build via PyInstaller

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/tg-contact-extractor.git
cd tg-contact-extractor
pip install -r requirements.txt
```

### Get API Key

1. Register at [openrouter.ai](https://openrouter.ai) (free)
2. Create `.env` file:
   ```
   OPENROUTER_API_KEY=sk-or-your-key
   ```

### Run GUI

```bash
python -m src.app
```

### Run CLI

```bash
python -m src.app ./ChatExport/result.json --prompt vacancies
```

## How It Works

```
Telegram Export (JSON)
        |
        v
    [Parser] — normalize messages
        |
        v
    [Batcher] — group into chunks
        |
        v
    [Extractor] — send to LLM with custom prompt
        |
        v
    [Writer] — save JSON with metadata
        |
        v
    [Excel] — generate formatted spreadsheet
```

## Prompts

Prompts are `.txt` files in the `prompts/` folder. Included:

- `vacancies.txt` — extract job postings, companies, recruiters
- `contacts_general.txt` — extract any contact information

Create your own via the GUI "Prompt" tab or manually.

## Models (Benchmarked)

| Model | Speed | Quality |
|-------|-------|---------|
| **Gemini 2.0 Flash** (default) | ~5s | Excellent |
| StepFun 3.5 Flash | ~13s | Excellent |
| OpenAI GPT-OSS 120B | ~28s | Excellent |
| NVIDIA Nemotron 3 Super 120B | ~44s | Excellent |
| Qwen 3.6 Plus | ~66s | Excellent+ |
| MiniMax M2.5 | ~117s | Excellent |

Run benchmark: `python benchmark.py`

## Build .exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "TG-Contact-Extractor" src/app.py
```

Place `.env` and `prompts/` folder next to the `.exe`.

## Tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
# 46 tests, all passing
```

## License

MIT
