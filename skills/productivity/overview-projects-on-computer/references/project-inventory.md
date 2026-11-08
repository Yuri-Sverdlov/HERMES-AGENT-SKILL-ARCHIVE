# project-inventory (перенесено из отдельного скилла)

> Перенесено project-inventory → overview-projects-on-computer. Бывший отдельный скилл, вычищенный curator'ом; содержание сохранено здесь целиком.

# Project Inventory — .docx Summary

Scan a directory of projects, collect info by reading key files, and produce a structured Word document (.docx) in text format (no tables).

## When to Use

- User asks to "catalog" or "map out" projects in a directory
- User wants a summary of all their projects with statuses
- Inventory for migration, cleanup, or portfolio documentation
- Audit of what exists across multiple directories

## Workflow

### 1. Scan the Directory

```bash
ls -la "/path/to/directory/"
```

Identify subdirs (potential projects) and standalone files.

### 2. For Each Project, Gather Context

Read up to 30–40 lines from these files, in priority order:

1. **README.md** — quick project summary
2. **AGENTS.md** / **CLAUDE.md** — project instructions, tech stack
3. **CONTEXT.md** — memory/knowledge base of the project
4. **ТЗ_*.md** / **TASK.md** — technical specs, if present
5. **requirements.txt** / **package.json** — dependencies
6. Source entry points (main.py, server.py, app.py) — first 20 lines

For empty folders: note as empty.

For known third-party tools (ComfyUI, Pinokio, etc.): note as "cloned/installed third-party tool, not an author project."

### 3. For Each Project, Write Section

Format (text only, no tables):

```
## N. PROJECT-NAME
Описание: <goals + tech stack + key files/tools. Max 60–70 words.>
Статус: <completed/in development/percentage estimate/notes.>
```

### 4. Non-Project Items

For root-level files that are not projects (docs, notes, charts, images), create a separate section called "Файлы в корне директории" with bullet points.

### 5. Generate .docx with python-docx

```python
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()
style = doc.styles['Normal']
style.font.name = 'Calibri'
style.font.size = Pt(11)

# Title
title = doc.add_heading('DIR_NAME — Обзор проектов', 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

# Date line
sub = doc.add_paragraph(f'Директория: {path} | Дата: {date}')
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub.runs[0].font.size = Pt(10)
sub.runs[0].font.color.rgb = RGBColor(0x60, 0x60, 0x60)

# Project section
for project in projects:
    h = doc.add_heading(project["name"], level=2)
    desc = doc.add_paragraph()
    desc.add_run("Описание: ").bold = True
    desc.add_run(project["desc"])
    status = doc.add_paragraph()
    status.add_run("Статус: ").bold = True  # blue color
    status.runs[0].font.color.rgb = RGBColor(0x1F, 0x5C, 0x99)
    status.add_run(project["status"]).font.color.rgb = RGBColor(0x1F, 0x5C, 0x99)
    doc.add_paragraph()

doc.save(output_path)
```

### 6. Verify

```bash
python3 -c "from docx import Document; doc = Document('output.docx'); [print(p.text[:100]) for p in doc.paragraphs if p.text.strip()]"
```

## Reference File

See [references/project-summary-example.md](references/project-summary-example.md) for a worked example from a real session.

## Pitfalls

1. **Empty folders** — note as empty, don't skip. User may want to clean them up.
2. **Third-party tools** — distinguish between author projects and cloned/installed tools. Note which are the user's own work and which are not.
3. **Russian language** — this user prefers descriptions in Russian.
4. **No tables** — use text format with headings, bold labels, and colored status. No HTML-like tables or grid layouts.
5. **Variable description length** — default: 60–70 words. BUT: if the user asks for a deeper dive, or the project has unusually interesting tools/architecture, expand freely with bullet-lists of key files, scripts, and patterns. The cap is a guideline, not a wall. Signal: user says «подробнее», «увеличь описание», «интересные инструменты».
6. **python-docx on Windows** — use `python3 -m pip install python-docx` (not `pip` which may point to a different interpreter). The sandbox `python` in execute_code may not have docx — fall back to `python3` in terminal.
7. **Status color** — use RGBColor(0x1F, 0x5C, 0x99) for blue status text.
8. **Sort/skip folders** — folders starting with `!!`, `_`, or named «Сортироват» are user-defined staging areas. Skip them or note briefly: «папка для сортировки, пропущена». Ask once if unsure.
9. **Output file naming** — save in the root of the scanned directory with a recognizable name based on the folder: `MY-PROGRAMMING-{N}-SUMMERY.docx` (or `INVENTORY-{SHORTNAME}-SUMMERY.docx`). The name should be ASCII-only for Windows compatibility.
10. **Cross-directory references** — if a project's docs reference a sibling project living in a different directory, note it in the description («соседний проект не в этой папке, расположен в ...»).
