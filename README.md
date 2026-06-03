# devcats-reports

Плагин с двумя скиллами для отчётов из Jira (jira.demo.io). Устанавливаешь один плагин — получаешь оба скилла.

## Что внутри

**ai-team-weekly-report** — недельный отчёт по всей команде. Работает по
сохранённому списку email-ов (ростер), пишет безличный отчёт от лица тимлида,
начиная с фразы «На этой неделе команда выполнила следующие задачи:».
Период: с понедельника текущей недели по сегодня включительно.
Ростер ведётся командой `manage_emails.py` (list / add / remove / clear).

**ai-employee-monthly-report** — месячный отчёт по одному сотруднику. Email и
месяц задаются в запросе на естественном языке (например «отчёт
demo@demo.io за февраль»). Период — с 1-го числа месяца по конец месяца, а для
текущего месяца — по сегодня включительно. Пишется от первого лица.

## Установка с GitHub

```
/plugin marketplace add r-mobile/claude_skill_team_report
/plugin install devcats-reports@devcats-reports
```

## Обновление

После изменения файлов плагина:

```
/plugin marketplace update devcats-reports
/plugin update devcats-reports
```

## Использование

- Недельный командный отчёт: «сделай недельный отчёт по команде»
- Управление ростером: «добавь ivan@demo.io в команду», «покажи список команды»
- Месячный отчёт по сотруднику: «отчёт ivan@demo.io за май»

## Структура репозитория

```
.claude-plugin/
  plugin.json          # манифест плагина
  marketplace.json     # манифест маркетплейса
README.md
skills/
  ai-team-weekly-report/
    SKILL.md
    emails.json
    scripts/
      manage_emails.py
  ai-employee-monthly-report/
    SKILL.md
    scripts/
      month_window.py
```
