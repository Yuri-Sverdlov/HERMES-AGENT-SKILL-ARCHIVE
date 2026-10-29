# Supabase / Postgres schema work without Dashboard access

Used when a TASK asks for SQL migrations, an audit of existing tables, or "why is the counter
broken" on a Supabase project — and you have neither `psql` nor a secret key nor Dashboard
access. Everything below was executed against a live project from the coder role.

## 1. Three layers of evidence, cheapest first

| Layer | Gives | Costs |
|---|---|---|
| REST probe with the publishable (anon) key | column exists? / type / row count | seconds, no permission needed |
| An `inspect*.sql` file you author for the user to run | PK, FK, CHECK, UNIQUE, indexes, NOT NULL, defaults, exact policy names | one user round-trip |
| The user's pasted SQL Editor output | authoritative text for the baseline/delta | one user round-trip |

Run layer 1 before writing anything. It usually resolves the question that otherwise forces
you to invent schema or stall the whole task waiting for a paste.

Two traps when the layer-2 paste arrives: the SQL Editor grid **visually truncates long policy
names** (names of 32–33 characters were cut mid-word, indistinguishable from genuinely short
names) — include `char_length(policyname)` in the policies query so truncation is detectable, and
write the name exactly as dumped instead of "reconstructing" the missing tail. And ask for the
blocks one at a time, so each result can be copied whole.

### Column probe (200 = exists, 400 = does not)

```bash
KEY=$(grep -m1 '^VITE_SUPABASE_ANON_KEY=' .env.local | cut -d= -f2- | tr -d '\r')
URL=$(grep -m1 '^VITE_SUPABASE_URL=' .env.local | cut -d= -f2- | tr -d '\r')
echo "key len=${#KEY}"        # print only the length — never the key itself
curl -s -o /dev/null -w '%{http_code}\n' --max-time 15 \
  "$URL/rest/v1/comments?select=body&limit=1" \
  -H "apikey: $KEY" -H "Authorization: Bearer $KEY"
```

Loop a candidate-name list (id, user_id, story_id, created_at, updated_at, body, content,
text, title, name, author_name, email, status, approved, …) and print only the names that
return 200. Within that list the answer is exact: a 400 means the column truly is absent, and
comparing two tables' sets tells you which needs an added column.

**What the loop does NOT prove — say the bound, never "no other columns".** 200/400 answers only
for the names you passed; the list is your guess, so a real column outside it is invisible. A
28-name sweep of one table missed an existing boolean flag, and the miss only surfaced in the
user's `information_schema` output — after the REPORT had already claimed "no extra columns".
So:

- Phrase the result as "none beyond the checked list", keep the authoritative column set as an
  open `TODO` until the audit paste arrives, and drop the columns you did *not* expect into the
  audit file's `information_schema` query so the user's paste closes the question.
- If a previous REPORT overstated the reach of the check, restate the corrected sentence in the
  next REPORT. A bounded check presented as complete is a wrong fact, not a rounding error.

### After the user applies the migration, re-probe exactly what your code selects

The repo states what *should* exist; only a probe states what *does*. Before writing UI/API code
that selects newly added columns, re-run the probe on those columns — it separates "the migration
never ran / ran partially" from "my code is wrong" before you debug the wrong layer:

```bash
comments?select=id,author_name,body,created_at   -> 200   (delta applied)
guestbook_entries?select=author_name             -> 200   (rename applied)
guestbook_entries?select=name                    -> 400   column ... does not exist (old name gone)
```

### A DevTools paste can be non-evidence — read the row back yourself

A browser console line like `{success: true, error: null, data: Array(1), count: null, status: 201, …}`
is a **collapsed** object: it proves the request succeeded, not what was stored. When the check is
about the *values* (a forced `created_at`, a flag the trigger was supposed to override), close it
with a read-only REST `select` of the rows just created and quote the actual columns:

```bash
curl -s "$URL/rest/v1/comments?select=author_name,body,created_at,is_author_reply&order=created_at.asc" \
  -H "apikey: $KEY" -H "Authorization: Bearer $KEY"
```

That also gives the row count that proves a refused insert really wrote nothing, and the before/
after pair for «подделка перезаписана сервером». Ask the user only for what a read cannot give (an
error message, an SQL Editor result) — not for an expanded DevTools object.

### Type discovery — from the operator-mismatch error text

```bash
curl -s "$URL/rest/v1/comments?select=story_id&story_id=like.*x*&limit=1" -H "apikey: $KEY"
# {"code":"42883","message":"operator does not exist: uuid ~~ unknown"}      -> uuid
# "operator does not exist: timestamp with time zone ~~ unknown"              -> timestamptz
# HTTP 200 with []                                                            -> text-ish
```

### Is the table empty? (decides whether NOT NULL / CHECK are safe)

```bash
curl -s -D - -o /dev/null "$URL/rest/v1/comments?select=id&limit=1" \
  -H "apikey: $KEY" -H 'Prefer: count=exact' -H 'Range: 0-0'
# Content-Range: */0   -> 0 rows: adding NOT NULL / CHECK cannot fail on existing data
#   (a plain `select=*&limit=1` returning [] says nothing — an empty table and a table of
#    zero visible rows under RLS look identical; count=exact is the measurement)
```

### The OpenAPI root is not an option

`GET /rest/v1/` returns `401 {"message":"Secret API key required"}` under the anon key. Do not
reach for a `service_role` key to get the whole schema — probe columns instead.

## 2. Never author DDL from a brief alone

- The brief is the *target*; the delta must come from the *actual* schema. Read the column set
  (layer 1) and the constraints (layer 2) before writing a single `ALTER`.
- Anything the evidence does not cover (PK, existing FK/CHECK names, indexes, NOT NULL,
  defaults) is written as an explicit `TODO` comment in the migration and as a numbered item in
  the REPORT. Invented constraints are worse than missing ones: they look authoritative.
- When the brief names a column the table already has under a different name (brief
  `author_name` vs DB `name`), **do not rename**. Apply the constraint to the existing column,
  state the divergence in the REPORT, and offer both options. Add the rename as a commented-out
  block and note which is cheaper: on an empty table a rename is free *now* and expensive later.
  Say which option you recommend, then let the architect decide.
- If your own earlier audit file did not collect what the next task needs, say so plainly
  ("the (3) block requested columns for one table only") and add the missing query — do not
  paper over it or guess the columns.

## 3. Idempotent delta patterns

Every migration file is re-runnable, because the user may run it twice after a partial failure:

- `alter table t add column if not exists c text;`
- `alter table t drop constraint if exists t_c_check; alter table t add constraint t_c_check check (...);`
- `alter table t alter column c set default now();` (re-setting the same default is a no-op)
- `create or replace function ...` / `drop trigger if exists ... ; create trigger ...`
- **Existing FK/constraint names are unknown — never guess them.** Guard with an existence
  check instead of dropping by a name you invented:

```sql
 do $$
begin
  if not exists (
    select 1 from pg_constraint c
    where c.conrelid = 'public.comments'::regclass
      and c.contype = 'f' and c.confrelid = 'public.stories'::regclass
  ) then
    alter table public.comments add constraint comments_story_id_fkey
      foreign key (story_id) references public.stories(id) on delete cascade;
  else
    raise notice 'FK already exists — untouched';
  end if;
end $$;
```

  The `raise notice` lines double as evidence in the user's SQL Editor output.
- Put an explicit rollback block at the bottom, commented out.
- Only `add column` / `add constraint` — never a bare `create table` for an object the project
  already has; that fails with "already exists" and reads as a broken migration.

## 4. Rate-limit trigger the Supabase way

One function for several tables, table name taken from `TG_TABLE_NAME`, so the quota is per
table automatically:

```sql
create or replace function public.enforce_write_rate_limit()
returns trigger language plpgsql security definer
set search_path = public, pg_temp          -- immutable search_path for SECURITY DEFINER
as $function$
declare recent_count integer; current_user_id uuid := auth.uid();
begin
  if current_user_id is null then
    raise exception 'Sign in to post' using errcode = '42501';
  end if;
  execute format(
    'select count(*) from public.%I where user_id = $1 and created_at > now() - interval ''1 minute''',
    tg_table_name) into recent_count using current_user_id;
  if recent_count >= 3 then
    raise exception 'Too many messages: max 3 per minute' using errcode = 'P0001';
  end if;
  return new;
end; $function$;
```

- `auth.uid()` inside a SECURITY DEFINER function still returns the *caller* (it reads the
  request JWT claims), so the guard is correct; DEFINER is needed only so the `count(*)` is not
  filtered by the caller's RLS.
- Write the user-facing message **in the project's language directly in `RAISE EXCEPTION`** — the
  front end then shows it as-is instead of needing a code→text dictionary. Front-end counterpart:
  map only the English transport/RLS/CHECK errors and **pass any message containing
  project-language characters through verbatim** (a simple regex test on the message). The DB
  stays the single source of truth for its own refusals, so rewording an exception never needs a
  code change on the client.
- Leave existing RLS policies alone when they already satisfy the brief: describe them in a
  comment block and report "no changes" rather than rewriting a working policy. Note explicitly
  whether UPDATE/DELETE policies exist (their absence is the interesting fact).

## 4b. Admin-only RPCs: the ACL is part of the guard, not decoration

A `SECURITY DEFINER` function that checks `is_admin()` inside is still callable by anyone with
EXECUTE. Supabase grants EXECUTE on new `public` functions **broadly** — the audit's ACL column
shows it plainly (`=X/postgres`, `anon=X/postgres`, `authenticated=X/postgres` on an existing
function), so an admin RPC written without an explicit ACL is reachable with the anon key:

```sql
revoke all on function public.admin_delete_user_messages(uuid) from public;
revoke all on function public.admin_delete_user_messages(uuid) from anon;
grant execute on function public.admin_delete_user_messages(uuid) to authenticated;
```

- Keep the internal `is_admin()` check as the second barrier — the ACL is the outer one, and the
  refusal a caller sees should be the project-language «доступно только автору», not a bare
  `permission denied`. Report both layers.
- `revoke … from public` alone is not enough: Supabase's default privileges grant to `anon`
  directly, so revoke from `anon` by name.
- RLS policies that call `is_admin()` on the same table that `is_admin()` reads are safe: the
  function is SECURITY DEFINER, so its owner bypasses RLS inside it and there is no recursion.
  Say that in the report — it is the first thing a reviewer asks.
- Two functions, not one mode flag, when the UI needs a dry run: `admin_count_…` (returns the
  numbers for the confirmation dialog, deletes nothing) and `admin_delete_…` (returns what it
  actually deleted). Return **both** the direct counts and the cascaded rows
  (`author_replies_deleted`) — a confirm dialog that promises only N and M is wrong when a
  `parent_id … on delete cascade` takes extra rows with it.

## 5. Prove the file before handing it over — real parser, not a read-through

```bash
# check_sql.py: parser.parse_sql(text) -> print count + statement kinds; exit 1 on error
uv run --with pglast python check_sql.py supabase/migrations/000X_x.sql
```

- `pglast` wraps libpg_query — the same parser PostgreSQL itself uses, so a syntax error is
  caught before the user burns a round-trip.
- Run it on a **previously accepted** `.sql` file in the same repo as a control. A checker that
  only ever prints OK has proven nothing (same class as a green selftest that never fails).
- State the limit honestly: the parser proves **syntax only** — `plpgsql` bodies and `DO $$ … $$`
  blocks reach it as string literals. To verify what a trigger *does* without touching prod, run
  it against a local embedded PostgreSQL (5b). The user's SQL-Editor run stays the only proof in
  the real project.

### 5b. Verify trigger/RPC *semantics* on a local embedded PostgreSQL (`pgserver`)

A migration whose whole payload is trigger logic (forcing `created_at`, overriding a flag,
counting a rate limit) has nothing a parser can check, and prod runs cost a user round-trip per
iteration. Run it against a throwaway local cluster instead — no install, no service, works from
this terminal:

```bash
uv run --with pgserver python -X utf8 verify_migration.py
```

The script shape that worked (`pgserver.get_server(<dir in scratch>)`;
`db.psql(<multi-statement string>)` accepts a whole file, so no statement splitting):

1. `select version()` — print the real server version as evidence.
2. Create the tables the trigger touches, mirroring the project's DDL from the user's audit
   (`stories`, `comments`, `guestbook_entries` with the real column set), plus
   `create schema if not exists auth;` and
   `create or replace function auth.uid() returns uuid language sql stable as $$
   select nullif(current_setting('app.test_uid', true), '')::uuid $$;` so the trigger's
   `auth.uid()` is drivable: `set app.test_uid = '<uuid>'` = signed in, `''` = anonymous.
3. Apply the migration file **twice** — the second run is the idempotence proof.
4. **Give the harness the two objects a Supabase cluster has for free, or half the file fails at
   DDL time:** `create table if not exists auth.users (id uuid primary key, email text unique);`
   (any `user_id uuid references auth.users(id)` — admin/ban tables — refuses without it) and the
   roles the ACL statements name: `create role anon nologin;`+`create role authenticated nologin;`
   (a bare cluster has neither, so `revoke … from anon` / `grant … to authenticated` error out).
   Insert one row per test account into `auth.users` too. Order matters: the roles must exist
   **before** a file that mixes DDL with `revoke`/`grant` runs.
5. **A privileged insert that silently failed looks like a bug in the trigger.** With the admin
   table empty, `is_admin()` is false and every author-only path behaves exactly like a reader's
   (the "author" then trips the 3/min quota). When author-only behaviour misbehaves, print
   `select * from public.site_admins` before touching the migration.
6. `select proname, prosecdef, proconfig from pg_proc ...` — asserts `SECURITY DEFINER` and
   `search_path` (the hardening a reviewer asks about) from the catalog, not from the source text.
7. Assert the trigger exists (`pg_trigger` where `not tgisinternal`) **before** any behavioural
   assertion, then run the cases: forged payload (`created_at: '2000-01-01'`,
   `is_author_reply: true`) → expect the forced value; 4 inserts under one uid → expect the
   project-language quota exception; same table without login → expect the auth exception; RPC
   counter before/after.
8. **Run every step in a transaction with a sentinel row, and classify the outcome.** `psql`
   without `ON_ERROR_STOP` keeps going after an error, so a `db.psql()` call whose statement was
   refused still returns "success" and the step looks green. Wrap each step as
   `begin; <sql>; select 'HERMES_OK' as sentinel; commit;`, treat a missing sentinel as *failed*,
   and pass each step's expectation in ("ожидание: отказ …") so an expected refusal is recorded
   as `отказ (ожидаемо)` while a step that passes where a refusal was expected is flagged
   `НЕОЖИДАННО`. Print a final `label | verdict` table — that table is what a reviewer reads, and
   it separates «проверка отсекла действие» from «проверка сломалась». A run where every step is
   green while the feature plainly does not work is the signature of steps that never executed
   (see the ordering rules above).
9. `select count(*)` per table at the end — confirms the *number* of accepted rows matches the
   number of expected successes (3 accepted + 1 refused), which is what proves the refusals did
   not silently half-write.

- **Create the triggers AFTER applying the migration, and assert they exist.** Trigger DDL that
  references `public.enforce_write_rate_limit()` fails if the function is not there yet, and the
  script keeps going: every later check then shows the *pre-migration* behaviour, which reads
  exactly like "the migration does not work". When **all** checks fail in the same direction,
  suspect the harness first — list `pg_trigger` and confirm the function bodies in `pg_proc` are
  the ones you just wrote, before you touch the migration.
- `psql` writes errors to **stderr**, which `pgserver` streams separately from the stdout tables,
  so the expected `ERROR:` lines appear at the top of the captured output, detached from the
  section that caused them. Say that in the REPORT instead of letting a reviewer think the
  output is scrambled; the tell that it is the *right* refusal is the `CONTEXT: PL/pgSQL function
  <name>() line N at RAISE` line.
- Honest bounds to write in the REPORT: this is a model, not the project's database — `auth.uid()`
  is a GUC stub (in Supabase it is a JWT claim) and the JWT/GoTrue mechanics are not reproduced.
  Also note that Supabase triggers may not be recreated by the migration at all — a
  `create or replace function` keeps the existing trigger bound, which is why the local harness
  has to create them itself.
- **RLS is testable locally too: replicate the policies, then `set role`.** Copy the project's
  real policies from the user's audit into the harness (`create policy "…" for select using (true)`,
  `for insert with check (auth.uid() = user_id)`), grant the test role what Supabase grants
  (`grant usage on schema public, auth`, `grant select, insert, delete on <tables>`,
  `grant execute on all functions in schema public`, `grant execute on function auth.uid()`), then
  run steps as `set role authenticated; set app.test_uid = '<uid>';`. The role is not the table
  owner, so policies and the SECURITY DEFINER bypass both behave as in prod — that is how you
  prove «читатель не удаляет свой комментарий» (`DELETE 0`, no error), «insert в stories отклонён»
  (`new row violates row-level security policy`), «читатель не читает служебную таблицу»
  (0 rows) and «автор удаляет чужой комментарий» (`DELETE 1`) **before** the user's own run.
  Classify the two outcomes correctly: a policy that filters silently returns `UPDATE 0` /
  `DELETE 0` (a pass), only `INSERT`/`WITH CHECK` violations raise an error.
- Don't assert a count on a row that was never created: «автор удаляет чужой комментарий» pointed
  at a body that every earlier name-check refused returns `DELETE 0` and proves nothing. Confirm
  the setup row exists first.
- Keep the harness in the scratch dir, not the repo: it is one-off evidence, not project code.
- Install path: the interpreter Hermes runs (`python`) is its own venv and has **no pip**, and a
  system Python311 may not exist. `uv run --with <pkg> python <script>` is the route that works
  without touching any environment.
- Never apply a migration yourself — the task's rule is that the user runs it in the SQL Editor.
  Expected success shape to tell them: `Success. No rows returned` plus the `NOTICE` lines.

## 6. Reporting this class of task

- **Say which lines are meant to be run separately, or the user will ask.** The hand-off blocks
  that follow the DDL — the post-apply verification queries and «step 2, grant yourself admin» —
  are written into the migration file as `--` comments *on purpose*: pasting the whole file runs
  only sections 1–9 and silently skips them. A question like «пункт 10 и пункт 11 — это вставлять
  в SQL-редактор потом?» means the hand-off never said it. Spell out the sequence: (1) paste the
  whole file → Run, expected `Success. No rows returned`; (2) then paste the un-commented blocks
  one at a time as separate queries, each with its expected output. Nothing needs uncommenting in
  the file — they copy the lines without `--`.
- **Privilege-granting steps: key them on email and always add a control select.** How the account
  was created is irrelevant — the site's `/register` page, the Dashboard and an invite all produce
  the same `auth.users` row, so `insert into public.site_admins (user_id) select id from
  auth.users where email = '<addr>'` works for all of them (email confirmation matters for *login*,
  not for the grant). Pair it with `select … join auth.users` and tell the user that an empty
  result means the stored address differs from the one they typed, so they should send what
  `auth.users` actually holds instead of re-running blindly.
- **`Success. No rows returned` proves the command parsed, not that a row was written.** A grant
  whose `where email = …` matched nothing reports exactly the same success line as a real insert,
  so never record «права выданы» in the REPORT on the strength of it — the control select is the
  only confirmation, and «не выдано» is the honest status until its output arrives. Same for any
  hand-off mutation (a DELETE, an UPDATE): ask for the affected-row count or a follow-up select.
- **The identifier's spelling is data, not a spec.** A TASK/BRIEF email, login or slug is a claim
  about the outside world and can be wrong — one hand-off said `sverdlovy@…` while `auth.users`
  held `sverdlov.y@…`, and the grant silently inserted 0 rows. Take the value from the source of
  truth (`select id, email from auth.users order by created_at desc`), and note that mail-provider
  aliasing (Yandex ignoring dots in the local part, Gmail ignoring `+tag`) exists only in mail
  routing: `auth.users` compares the string exactly. Robust hand-off form lists both spellings —
  `where email in ('a.b@x', 'ab@x')` — which inserts whatever account really exists; flag the
  divergence to the architect so the canon docs stop carrying the wrong address.

- The REPORT carries the migration table (file | needed? | applied by user? | notes), the exact
  commands whose output proves the probe results, and a section the user fills with the inspect
  output.
- The audit output belongs in a file in the repo (`supabase/Вывод inspect-sql.txt`) so the
  baseline can cite it; do not paste thousands of characters into chat.
- Chaotic input artifacts (a dashboard screenshot dropped in the repo root, a stale file the
  user says to ignore) are reported as untracked and left alone — never committed as scope.
