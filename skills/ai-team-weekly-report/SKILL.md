---
name: ai-team-weekly-report
description: Generate a weekly team performance report in Russian from Jira (jira.demo.io) for a saved roster of employee emails. Use when the user asks for a weekly team report, team status summary, «недельный отчёт», «отчёт по команде», or wants to manage (add/remove/list) the employees included in that report. Pulls each person's tasks, bugs, and other issues from Monday through today, splits them into Completed and In Progress, and writes a Team-Lead-style narrative beginning «На этой неделе команда выполнила следующие задачи:».
---

# AI Team Weekly Report

Generates a factual, natural-language weekly report on a team's Jira activity,
written in Russian in the voice of a Team Lead. The set of employees is a
roster of emails stored in `emails.json` and managed through a helper script.

## When to use

- The user wants a weekly team report / «недельный отчёт по команде».
- The user wants to add, remove, list, or clear the employees in the roster.

## Roster management (save / add / remove)

The roster lives in `emails.json` (a JSON array of emails) in the skill root.
Manage it only through `scripts/manage_emails.py` so validation and
de-duplication are applied. Run from the skill directory:

```bash
python scripts/manage_emails.py list                             # show current roster
python scripts/manage_emails.py add a@demo.io b@demo.io   # add one or more
python scripts/manage_emails.py remove a@demo.io             # remove one
python scripts/manage_emails.py clear                            # empty the roster
```

Every command prints the resulting roster as JSON (`{"count": N, "emails": [...]}`).
Invalid emails are rejected with a non-zero exit code; surface the error to the user.

When the user only asks to manage emails, run the relevant command and confirm
the result — do not generate a report.

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

### 1. Load the roster

Run `python scripts/manage_emails.py list` (or read `emails.json`) to get the
emails. If the roster is empty, tell the user and ask them to add emails first
(show the `add` command). Do not invent employees.

### 2. Determine the report window

"Week" means **from Monday of the current week (00:00) through today,
inclusive** — not a rolling 7 days. Compute the Monday date explicitly so it
does not depend on Jira's locale `startOfWeek()` (which may begin on Sunday):

```bash
python3 -c "import datetime; t=datetime.date.today(); print((t - datetime.timedelta(days=t.weekday())).isoformat())"
```

This prints the current week's Monday as `YYYY-MM-DD`. Examples: today Tuesday
→ covers Mon–Tue; today Friday → covers Mon–Fri.

### 3. Fetch each employee's issues — in parallel

For each email, issue a `jira_search` call. Send **all employee searches in a
single message** so they run in parallel. Use this JQL per employee (covers
tasks, bugs, and every other issue type), filtering by the exact workflow
statuses this team uses:

```
assignee = "EMAIL" AND (
  (resolutiondate >= "WEEK_START" AND status in ("Done", "To release", "to merge", "On merge", "Cancelled", "To review", "to test", "Feature test", "Ready for Testing"))
  OR
  (updated >= "WEEK_START" AND status in ("Pause", "Accepted", "In Progress"))
) ORDER BY status DESC
```

Replace `WEEK_START` with the computed Monday date (e.g. `"2026-06-01"`).
Completed tasks are filtered by **resolutiondate** (Дата решения); in-progress
tasks have no resolutiondate so they are filtered by **updated** instead.
Set `fields` to: `summary,status,assignee,issuetype,resolutiondate,updated,description`.
Raise `limit` (up to 50) if a person has many issues; paginate with
`start_at` if `total` exceeds what was returned.

Notes on the response shape (Jira Server/DC at jira.demo.io):
- `issues[].key`, `issues[].summary`, `issues[].description`
- `issues[].status.name` is the **only** grouping key — match it against the
  status names below (case-insensitive).
- **Ignore `issues[].status.category` completely.** It does not match this
  team's grouping. For example «Ready for Testing» has category «В работе»,
  but it is a **Completed** status here. Never decide a task's group from
  `status.category` — always use `status.name`.
- `issues[].issue_type.name` (e.g. «Задача», «Ошибка»/bug, «Dev Task»).
- `issues[].assignee.display_name` / `.email` identify the person.

Aggregate all issues across all employees into one consolidated list, tagging
each with its group (Completed vs In Progress) per the status mapping in
step 5. The roster only defines whose work to fetch — the report itself is
about the team as a whole, so do not track or report who did what.

### 4. Enrich sparse items only if needed

If a summary is too terse to understand at all, call `jira_get_issue` for that
issue key (`fields: "summary,description,issuetype,status"`) to grasp what the
task is about. Do this only for the issues that need it — not for every issue.
Use the description only to extract the essence of the task; never copy long
descriptions into the report.

### 5. Write the report (Russian, Team-Lead voice)

Compose the report in Russian using **only factual data** from Jira. Rules:

#### Structure

The report has exactly two sections in this order. **Each section opens with
its fixed phrase — that phrase IS the section divider. Do not add any separate
header, title, or label before or after it** (no «Завершённые задачи», no
«Задачи в работе», no bold heading of any kind):

1. **Completed** — first line of the entire report, verbatim:
   **«На этой неделе команда выполнила следующие задачи:»**
   Statuses that belong here: **Done, To release, to merge, On merge,
   Cancelled, To review, to test, Feature test, Ready for Testing**.

2. **In Progress** — first line of the second section, verbatim:
   **«В активной работе находятся следующие задачи:»**
   Statuses that belong here: **Pause, Accepted, In Progress**.

Match status names case-insensitively. Group strictly by `status.name` — never
by `status.category`. In particular, «Ready for Testing», «to test»,
«To review», «to merge», «On merge», «Feature test» go to **Completed** even
if their Jira category says «В работе».

#### Tone and phrasing

- Write in flowing prose as a Team Lead summarizing the team's week.
- Group related tasks into a few thematic paragraphs (e.g. платежи и переводы,
  миграция интерфейса, безопасность) — not one sentence per task.
- Describe Completed tasks in past tense («реализована», «исправлено»,
  «завершена»). Describe In Progress tasks in present continuous
  («ведётся», «исправляется», «дорабатывается»).
- For **Cancelled** tasks: do not write «задача отменена» or anything about
  cancellation. Instead describe what was done — investigated, checked,
  reviewed — and that no action was needed, e.g. «Разобрали обращение по X,
  проверили логи — проблем не выявлено», «Проверили предполагаемую ошибку Y,
  воспроизвести не удалось». Write in the same past-tense active style as
  other completed tasks.
- Write about the team as a whole — do not name individuals or attribute tasks
  to specific people.
- State only the essence of each task — do not include long descriptions, full
  ticket text, or issue keys.
- **No technical implementation details.** Do not name specific libraries,
  frameworks, APIs, class names, flags, or language constructs (e.g. no
  `Room`, `Compose BOM`, `Timber`, `SharedPreferences`, `CoroutineScope`,
  `!!`-operators, specific annotation names). Describe *what* was done and
  *why*, not *how* at the code level. For example: instead of «заменили
  CoroutineScope на viewModelScope» write «доработали асинхронные вызовы»;
  instead of «Fragment-ktx, Room, Compose BOM» write «обновили библиотеки до
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
  «В рамках спринта продолжилась работа по…». Start each paragraph directly
  with the concrete action («Реализована интеграция…», «Исправлено
  отображение…»).
- **No filler connectives.** Delete words like «Также», «Активно», «Кроме
  того», «В частности», «При этом» when they appear at the start of a
  sentence or as a sentence opener. Begin the sentence directly with the verb
  or subject.
- **No filler adverbs.** Remove «Активно», «Успешно», «Эффективно» and similar
  intensifiers.
- **No editorial conclusions.** Do not add praise, assessments, or forward-looking
  statements at the end of sections or the report.
- **No bullet lists, numbered lists, or images.**
- **No personal opinions or speculation** — describe only what the Jira data shows.

#### Edge cases

- If a section has no issues: state that plainly, e.g. «На этой неделе
  завершённых задач не зафиксировано.»
- By default present the finished report in the chat. Only save it to a file if
  the user asks.

## Files

- `emails.json` — the roster (JSON array of emails).
- `scripts/manage_emails.py` — list/add/remove/clear the roster.
