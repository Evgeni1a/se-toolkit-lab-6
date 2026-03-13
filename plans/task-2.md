# План реализации Task 2: The Documentation Agent

## Обзор задачи

Расширяем агента из Task 1, добавляя:
1. **Инструменты** (`read_file`, `list_files`) для работы с файлами проекта
2. **Агентовый цикл** — LLM вызывает инструменты, получает результаты, принимает решения
3. **Безопасность путей** — защита от выхода за пределы проекта (`../` traversal)

---

## 1. Определение схем инструментов (Tool Schemas)

### Подход
Используем формат OpenAI Function Calling для описания инструментов. Каждая функция описывается как JSON-схема с:
- `name` — имя инструмента
- `description` — что делает инструмент
- `parameters` — параметры (JSON Schema)

### Схема `read_file`
```python
{
    "name": "read_file",
    "description": "Read a file from the project repository",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
            }
        },
        "required": ["path"]
    }
}
```

### Схема `list_files`
```python
{
    "name": "list_files",
    "description": "List files and directories at a given path",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative directory path from project root (e.g., 'wiki')"
            }
        },
        "required": ["path"]
    }
}
```

### Регистрация в запросе к LLM
Передаём схемы через параметр `tools` в `client.chat.completions.create()`:
```python
response = client.chat.completions.create(
    model=model,
    messages=messages,
    tools=[read_file_schema, list_files_schema],
    tool_choice="auto"  # LLM сам решает, вызывать ли инструмент
)
```

---

## 2. Реализация агентового цикла

### Алгоритм
```
1. Инициализация:
   - messages = [system_prompt, user_question]
   - tool_calls_log = []
   - max_iterations = 10

2. Цикл (до 10 итераций):
   а) Отправить messages к LLM
   б) Если LLM вернул tool_calls:
      - Для каждого tool_call:
        * Выполнить инструмент (read_file / list_files)
        * Получить результат
        * Добавить в tool_calls_log
        * Добавить результат в messages как role="tool"
      - Продолжить цикл
   в) Если LLM вернул текстовый ответ (без tool_calls):
      - Это финальный ответ
      - Извлечь answer и source
      - Вывести JSON и завершить

3. Если достигнуто 10 итераций:
   - Использовать имеющийся ответ
   - Вывести JSON
```

### Структура данных
```python
messages = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "How do you resolve a merge conflict?"},
    {"role": "assistant", "content": None, "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "..."},
    ...
]
```

### Обработка ответов LLM
- **tool_calls присутствует**: LLM хочет вызвать инструменты
- **content присутствует, tool_calls нет**: финальный ответ

### Извлечение ответа и источника
Финальный ответ LLM должен содержать:
- `answer` — текстовый ответ
- `source` — ссылка на файл wiki (например, `wiki/git-workflow.md#resolving-merge-conflicts`)

Парсим ответ LLM или просим LLM вернуть JSON напрямую через system prompt.

---

## 3. Безопасность путей (Path Security)

### Проблема
Злоупотребление: пользователь может попросить прочитать `../../../etc/passwd`.

### Решение
1. **Нормализация пути**: используем `os.path.normpath()` для разрешения `..` и `.`
2. **Проверка выхода за пределы**: убеждаемся, что нормализованный путь начинается с корня проекта
3. **Запрет абсолютных путей**: если путь начинается с `/` (Unix) или буквы с `:` (Windows) — ошибка

### Реализация
```python
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

def validate_path(relative_path: str) -> Path:
    """Проверяет, что путь не выходит за пределы проекта."""
    # Запрет абсолютных путей
    if os.path.isabs(relative_path):
        raise ValueError(f"Absolute paths not allowed: {relative_path}")
    
    # Нормализация (разрешает .. и .)
    normalized = os.path.normpath(relative_path)
    
    # Полный путь
    full_path = PROJECT_ROOT / normalized
    
    # Проверка: путь должен начинаться с PROJECT_ROOT
    try:
        full_path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        raise ValueError(f"Path traversal detected: {relative_path}")
    
    return full_path
```

### Для `read_file`
```python
def read_file(path: str) -> str:
    full_path = validate_path(path)
    if not full_path.exists():
        return f"Error: File not found: {path}"
    if not full_path.is_file():
        return f"Error: Not a file: {path}"
    return full_path.read_text()
```

### Для `list_files`
```python
def list_files(path: str) -> str:
    full_path = validate_path(path)
    if not full_path.exists():
        return f"Error: Directory not found: {path}"
    if not full_path.is_dir():
        return f"Error: Not a directory: {path}"
    
    entries = []
    for entry in full_path.iterdir():
        suffix = "/" if entry.is_dir() else ""
        entries.append(entry.name + suffix)
    
    return "\n".join(sorted(entries))
```

---

## 4. System Prompt

Стратегия подсказки:
1. Объяснить роль агента (помощник по документации проекта)
2. Описать доступные инструменты
3. Указать рабочий процесс:
   - Использовать `list_files` для обнаружения файлов wiki
   - Использовать `read_file` для чтения содержимого
   - Найти ответ в документации
   - Вернуть `answer` + `source` (файл + якорь раздела)

### Пример system prompt
```
You are a documentation assistant for a software engineering project.
You have access to the project wiki files through two tools:

1. list_files(path) - lists files in a directory
2. read_file(path) - reads file contents

Workflow:
1. Use list_files("wiki") to discover available documentation files
2. Use read_file() to read relevant files and find the answer
3. Look for section headers (# Section Name) to create precise source anchors
4. Return your final answer with:
   - answer: the concise answer
   - source: file path with section anchor (e.g., wiki/git-workflow.md#resolving-merge-conflicts)

Always cite the exact file path and section that contains the answer.
```

---

## 5. Структура выходного JSON

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

---

## 6. Пошаговый план реализации

### Шаг 1: Константы и утилиты
- Определить `PROJECT_ROOT`
- Реализовать `validate_path()`

### Шаг 2: Инструменты
- Реализовать `read_file(path)`
- Реализовать `list_files(path)`
- Обработка ошибок (файл не найден, не файл, не директория)

### Шаг 3: Схемы инструментов
- Определить `TOOL_SCHEMAS` для передачи в LLM

### Шаг 4: System prompt
- Написать prompt, описывающий workflow

### Шаг 5: Агентовый цикл
- Цикл `while iterations < 10`
- Вызов LLM с `tools=TOOL_SCHEMAS`
- Обработка `tool_calls`
- Добавление результатов как `role="tool"`
- Обработка финального ответа

### Шаг 6: Парсинг ответа
- Извлечь `answer` и `source` из ответа LLM
- Сформировать итоговый JSON

### Шаг 7: Тестирование
- Протестировать на вопросах:
  - `"How do you resolve a merge conflict?"`
  - `"What files are in the wiki?"`

---

## 7. Риски и решения

| Риск | Решение |
|------|---------|
| LLM не возвращает source в нужном формате | Попросить в system prompt возвращать JSON с полями answer/source |
| LLM зацикливается на инструментах | Лимит 10 итераций |
| Path traversal через сложные пути | `os.path.normpath()` + проверка `relative_to()` |
| Windows-специфичные пути | Использовать `pathlib.Path` для кроссплатформенности |

---

## 8. Критерии приёмки

- [ ] `plans/task-2.md` существует (этот файл)
- [ ] `read_file` и `list_files` определены как tool schemas
- [ ] Агентовый цикл выполняет tool calls и передаёт результаты обратно в LLM
- [ ] `tool_calls` в выходном JSON заполнен
- [ ] `source` содержит путь к файлу wiki с якорем
- [ ] Инструменты не читают файлы вне проекта
- [ ] `AGENT.md` обновлён с документацией
- [ ] 2 регрессионных теста проходят
