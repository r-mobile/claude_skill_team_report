---
name: ai-employee-monthly-report
description: Generate a monthly performance report in Russian for ONE employee from Jira (jira.demo.io). The employee's email and the month are given in the request in natural language, e.g. «отчёт demo@demo.io за февраль», «report по ivan@demo.io за прошлый месяц», «месячный отчёт сотрудника за март 2025». Use this skill whenever the user asks for an individual / per-person monthly report, «месячный отчёт по сотруднику», «отчёт за <месяц> по <email>», or names a single email together with a month — even if they don't say the word «отчёт» explicitly. This is the INDIVIDUAL monthly report and is configured independently from the team weekly report; do not reuse the weekly roster or its rules here.
---

# AI Employee Monthly Report

Generates a factual, natural-language **monthly** report on a **single
employee's** Jira activity, written in Russian **in the first person** (as if
the employee is reporting on their own work for the period). The employee is
identified by an email passed in the request, and the month is given in
natural language.

This skill is deliberately separate from the team weekly report. It keeps its
own status mapping and its own wording rules, so you can tune individual
reports without touching the team report and vice-versa.

## When to use

- The user asks for a monthly report about one person, e.g. «отчёт
  demo@demo.io за февраль», «месячный отчёт по ivan@demo.io за март 2025»,
  «отчёт за прошлый месяц по <email>».
- The signal is a **single email + a month**. There is no saved roster — the
  email always comes from the request.

If the request names several people or no email at all, this is probably not the
right skill — ask the user for the one email, or point them to the team report.

## Generating the report

Follow these steps in order.

### 0. Check required MCPs

Before doing anything else, verify that the Jira MCP is available by checking
whether the tool `jira_search` (MCP: `jira`) is listed in your current tool
set. If it is **not** available, stop immediately and show this error to the
user:

```
❌ Ошибка: MCP-коннектор Jira недоступен.
Для работы скилла необходим подключённый Jira MCP.
Проверьте настройки подключения и попробуйте снова.
```

Do not attempt to generate a report without this MCP.

### 1. Parse the email and the month

Pull the employee email straight from the request. If it is missing, ask for it
— never invent one.

Resolve the month window with the helper script (run it from the skill
directory). It accepts natural-language month specs and prints the exact date
range as JSON:

```bash
python scripts/month_window.py "февраль"
python scripts/month_window.py "март 2025"
python scripts/month_window.py "прошлый месяц"
python scripts/month_window.py            # no arg -> current month
```

Output fields:

- `start` — inclusive lower bound (`YYYY-MM-01`).
- `end_exclusive` — exclusive upper bound for JQL. For a finished month this is
  the 1st of the next month; for the **current** month it is **tomorrow**, so
  the window runs from the 1st through today inclusive.
- `end_inclusive` — the last day actually covered, for display only.
- `label` — human label like «февраль 2026», for the intro.
- `is_current_month` — whether the month is still in progress.

The month rule: always from the 1st of the month at 00:00, through the last day
of the month — or, if it is the current month, through today inclusive. A month
name without a year means the most recent past occurrence (if the named month is
later than the current month, it belongs to last year).

### 2. Fetch the employee's issues for that month

Issue a single `jira_search` with this JQL, substituting the email and the two
dates from step 1 (covers tasks, bugs, and every other issue type, filtered by
the exact workflow statuses this team uses):

```
assignee = "EMAIL" AND (
  (resolutiondate >= "START" AND resolutiondate < "END_EXCLUSIVE" AND status in ("Done", "To release", "to merge", "On merge", "Cancelled", "To review", "to test", "Feature test", "Ready for Testing"))
  OR
  (updated >= "START" AND updated < "END_EXCLUSIVE" AND status in ("Pause", "Accepted", "In Progress"))
) ORDER BY status DESC
```

Completed tasks are filtered by **resolutiondate** (Дата решения); in-progress
tasks have no resolutiondate so they are filtered by **updated** instead.
Set `fields` to: `summary,status,assignee,issuetype,resolutiondate,updated,description`.
A month can hold many issues, so set `limit` to 50 and paginate with `start_at`
if `total` exceeds what was returned — make sure you pull the whole month.

Notes on the response shape (Jira Server/DC at jira.demo.io):

- `issues[].key`, `issues[].summary`, `issues[].description`.
- `issues[].status.name` is the **only** grouping key — match it
  case-insensitively against the status lists in step 4.
- **Ignore `issues[].status.category` completely.** It does not match this
  team's grouping (e.g. «Ready for Testing» carries category «В работе» but is a
  **Completed** status here). Always group by `status.name`, never by category.
- `issues[].issue_type.name` (e.g. «Задача», «Ошибка»/bug, «Dev Task»).

Aggregate all issues into a single list for the report.

### 3. Enrich sparse items only if needed

If a summary is too terse to understand at all, call `jira_get_issue` for that
key (`fields: "summary,description,issuetype,status"`) just to grasp the gist.
Do this only for the few issues that need it. Use the description only to
extract the essence; never copy long descriptions into the report.

### 4. Write the report (Russian, first person)

Compose the report in Russian using **only factual data** from Jira, written
from the employee's point of view (first person — «я выполнил», «реализовал»,
«сейчас работаю над»). Rules:

#### Structure

The report has exactly two sections in this order. **Each section opens with
its fixed phrase — that phrase IS the section divider. Do not add any separate
header, title, or label before or after it** (no «Завершённые задачи», no
«Задачи в работе», no bold heading of any kind):

1. **Completed** — first line of the entire report, verbatim:
   **«За этот месяц я выполнил следующие задачи:»**
   Statuses that belong here: **Done, To release, to merge, On merge,
   Cancelled, To review, to test, Feature test, Ready for Testing**.

2. **In Progress** — first line of the second section, verbatim:
   **«Сейчас в работе у меня находятся следующие задачи:»**
   Statuses that belong here: **Pause, Accepted, In Progress**.

Match status names case-insensitively. Group strictly by `status.name` — never
by `status.category`. In particular, «Ready for Testing», «to test»,
«To review», «to merge», «On merge», «Feature test» go to **Completed** even
if their Jira category says «В работе».

#### Tone and phrasing

- Write in flowing prose in the first person, as the employee summarizing their
  own month.
- Group related tasks into a few thematic paragraphs (e.g. платежи и переводы,
  миграция интерфейса, безопасность) — not one sentence per task.
- Describe Completed tasks in past tense, first person («реализовал»,
  «исправил», «завершил»). Describe In Progress tasks in present continuous
  («дорабатываю», «исправляю», «работаю над»).
- For **Cancelled** tasks: do not write «задача отменена» or anything about
  cancellation. Instead describe what was done — investigated, checked,
  reviewed — and that no action was needed, e.g. «Разобрал обращение по X,
  проверил логи — проблем не выявлено», «Проверил предполагаемую ошибку Y,
  воспроизвести не удалось». Write in the same past-tense first-person style
  as other completed tasks.
- Since this is one person's report, freely use «я»/«мной», but do **not**
  name the employee in the third person or mention other people.
- State only the essence of each task — do not include long descriptions, full
  ticket text, or issue keys.
- **No technical implementation details.** Do not name specific libraries,
  frameworks, APIs, class names, flags, or language constructs (e.g. no
  `Room`, `Compose BOM`, `Timber`, `SharedPreferences`, `CoroutineScope`,
  `!!`-operators, specific annotation names). Describe *what* was done and
  *why*, not *how* at the code level. For example: instead of «заменил
  CoroutineScope на viewModelScope» write «доработал асинхронные вызовы»;
  instead of «Fragment-ktx, Room, Compose BOM» write «обновил библиотеки до
  актуальных версий».
- **No product or app names.** Do not name specific apps, services, or
  internal project names (e.g. no «Мой О!», no «Android-приложение» — just
  «приложение»). Exception: names that appear in the task summary itself and
  are essential to understand the task (e.g. a third-party service being
  replaced) may be kept if they add clarity.

#### Forbidden patterns — apply zero tolerance

- **No summary lead-ins.** Never open a paragraph with a sentence that
  describes the theme before listing the work, e.g.: «Значительная часть
  работы была сосредоточена на…», «Основное внимание уделялось…»,
  «В рамках этого месяца продолжилась работа по…». Start each paragraph
  directly with the concrete action («Реализовал интеграцию…», «Исправил
  отображение…»).
- **No filler connectives.** Delete words like «Также», «Активно», «Кроме
  того», «В частности», «При этом» when they appear at the start of a
  sentence. Begin the sentence directly with the verb or subject.
- **No filler adverbs.** Remove «Активно», «Успешно», «Эффективно» and similar
  intensifiers.
- **No editorial conclusions.** Do not add praise, assessments, or forward-looking
  statements.
- **No bullet lists, numbered lists, or images.**
- **No personal opinions or speculation** — describe only what the Jira data shows.

#### Edge cases

- If the **Completed** section has no issues: state that plainly, e.g. «За этот
  месяц завершённых задач не зафиксировано.»
- If the **In Progress** section has no issues: **omit it entirely** — do not
  write the opening phrase or any note about it.
- By default present the finished report in the chat. Only save it to a file if
  the user asks.
- If the month window is the current (in-progress) month, note the covered
  period (e.g. «за период с 1 по 4 июня») so it is clear the month is not yet
  over.

## Files

- `scripts/month_window.py` — resolve a natural-language month into an exact
  `start` / `end_exclusive` date window.
