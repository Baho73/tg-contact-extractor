# FILE: src/app.py
# VERSION: 3.0.0
# START_MODULE_CONTRACT
#   PURPOSE: Entry point — CLI and GUI (CustomTkinter) with prompt management, dual output (JSON+Excel)
#   SCOPE: Argument parsing, tabbed GUI, prompt editor, async pipeline orchestration
#   DEPENDS: M-CONFIG, M-PARSER, M-BATCHER, M-EXTRACTOR, M-WRITER, M-EXCEL
#   LINKS: M-APP
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   main — CLI entry point with argparse
#   run_pipeline — async orchestration: parse -> batch -> extract -> write JSON + Excel
#   AppGUI — CustomTkinter tabbed GUI class
# END_MODULE_MAP

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from src.batcher import make_batches
from src.config import AppConfig, FREE_MODELS, load_config, save_config
from src.extractor import (
    ContactRecord,
    DEFAULT_PROMPT_NAME,
    list_prompts,
    load_prompt,
    process_all_batches,
    save_prompt,
)
from src.parser import parse_export
from src.to_excel import json_to_excel
from src.writer import ExtractionMeta, flush_incremental, write_json

logger = logging.getLogger(__name__)

FLUSH_EVERY = 10

# START_BLOCK_THEME_COLORS
COLOR_BG = "#0f1117"
COLOR_SURFACE = "#1a1d27"
COLOR_SURFACE_2 = "#242836"
COLOR_BORDER = "#2e3347"
COLOR_TEXT = "#e4e6f0"
COLOR_TEXT_DIM = "#6b7194"
COLOR_ACCENT = "#4f8ff7"
COLOR_ACCENT_HOVER = "#6ba0ff"
COLOR_SUCCESS = "#34d399"
COLOR_ERROR = "#f87171"
COLOR_WARNING = "#fbbf24"
# END_BLOCK_THEME_COLORS


# START_CONTRACT: run_pipeline
#   PURPOSE: Async orchestration — parse, batch, extract, write JSON + Excel
#   INPUTS: { export_path, config, system_prompt, on_progress }
#   OUTPUTS: { tuple[Path, Path] — JSON path, Excel path }
#   SIDE_EFFECTS: File I/O, HTTP requests
#   LINKS: M-APP
# END_CONTRACT: run_pipeline
async def run_pipeline(
    export_path: Path,
    config: AppConfig,
    system_prompt: str,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> tuple[Path, Path]:
    def _report(done: int, total: int, msg: str) -> None:
        if on_progress:
            on_progress(done, total, msg)

    # START_BLOCK_PIPELINE_PARSE
    _report(0, 0, "Парсинг сообщений...")
    messages = parse_export(export_path)
    _report(0, 0, f"Найдено {len(messages)} сообщений")
    # END_BLOCK_PIPELINE_PARSE

    # START_BLOCK_PIPELINE_BATCH
    batches = make_batches(messages, config.batch_size, config.max_tokens_per_batch)
    total = len(batches)
    _report(0, total, f"Создано {total} пакетов, начинаю извлечение...")
    # END_BLOCK_PIPELINE_BATCH

    # START_BLOCK_PIPELINE_EXTRACT
    all_contacts: list[ContactRecord] = []
    skipped: list[list[int]] = []
    temp_path = export_path.parent / ".contacts_temp.jsonl"
    temp_path.unlink(missing_ok=True)

    done = 0
    async for batch_idx, contacts, failed_ids in process_all_batches(batches, config, system_prompt):
        all_contacts.extend(contacts)
        if failed_ids:
            skipped.append(failed_ids)
        done += 1
        _report(done, total, f"Пакет {done}/{total} — извлечено {len(contacts)} контактов")
        if done % FLUSH_EVERY == 0:
            flush_incremental(contacts, temp_path)
    # END_BLOCK_PIPELINE_EXTRACT

    # START_BLOCK_PIPELINE_WRITE
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_name = f"contacts_{timestamp}.json"
    json_path = export_path.parent / json_name

    meta = ExtractionMeta(
        source=str(export_path),
        total_messages=len(messages),
        processed_batches=total,
        skipped_batches=skipped,
        date=timestamp,
        prompt=system_prompt,
    )

    write_json(all_contacts, meta, json_path)
    _report(total, total, f"JSON: {len(all_contacts)} контактов -> {json_name}")

    # Generate Excel from JSON
    xlsx_path = json_to_excel(json_path)
    _report(total, total, f"Excel: {xlsx_path.name}")

    if temp_path.exists():
        temp_path.unlink()

    return json_path, xlsx_path
    # END_BLOCK_PIPELINE_WRITE


class AppGUI:
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("TG Contact Extractor")
        self.root.geometry("720x700")
        self.root.minsize(650, 620)
        self.root.configure(fg_color=COLOR_BG)

        self.config = load_config()
        self._running = False
        self._result_json: Path | None = None
        self._result_xlsx: Path | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        # --- Header ---
        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(20, 0))

        ctk.CTkLabel(
            header, text="TG Contact Extractor",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")

        ctk.CTkLabel(
            header, text="v2.0",
            font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM,
        ).pack(side="left", padx=(8, 0), pady=(6, 0))

        ctk.CTkLabel(
            self.root,
            text="Извлечение данных из экспорта Telegram с помощью LLM",
            font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=28, pady=(2, 12))

        # --- Tabview ---
        self.tabs = ctk.CTkTabview(
            self.root, fg_color=COLOR_SURFACE, corner_radius=12,
            border_width=1, border_color=COLOR_BORDER,
            segmented_button_fg_color=COLOR_SURFACE_2,
            segmented_button_selected_color=COLOR_ACCENT,
            segmented_button_unselected_color=COLOR_SURFACE_2,
            text_color=COLOR_TEXT,
        )
        self.tabs.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        tab_main = self.tabs.add("Извлечение")
        tab_prompt = self.tabs.add("Промпт")

        self._build_main_tab(tab_main)
        self._build_prompt_tab(tab_prompt)

    # START_BLOCK_GUI_MAIN_TAB
    def _build_main_tab(self, parent: ctk.CTkFrame) -> None:
        inner = ctk.CTkFrame(parent, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        # File picker
        self._section_label(inner, "ФАЙЛ ЭКСПОРТА")
        file_row = ctk.CTkFrame(inner, fg_color="transparent")
        file_row.pack(fill="x", pady=(0, 12))

        self.path_var = ctk.StringVar()
        ctk.CTkEntry(
            file_row, textvariable=self.path_var,
            placeholder_text="Выберите result.json или папку экспорта...",
            height=36, font=ctk.CTkFont(size=13),
            fg_color=COLOR_SURFACE_2, border_color=COLOR_BORDER, text_color=COLOR_TEXT,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            file_row, text="Обзор", width=80, height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT,
            command=self._browse,
        ).pack(side="right")

        # API Key + Model row
        settings_row = ctk.CTkFrame(inner, fg_color="transparent")
        settings_row.pack(fill="x", pady=(0, 12))
        settings_row.columnconfigure(0, weight=1)
        settings_row.columnconfigure(1, weight=1)

        # API Key
        key_frame = ctk.CTkFrame(settings_row, fg_color="transparent")
        key_frame.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._section_label(key_frame, "API KEY")

        key_inner = ctk.CTkFrame(key_frame, fg_color="transparent")
        key_inner.pack(fill="x")

        self.key_var = ctk.StringVar(value=self.config.openrouter_api_key)
        self.key_entry = ctk.CTkEntry(
            key_inner, textvariable=self.key_var, show="\u2022",
            height=36, font=ctk.CTkFont(size=13),
            fg_color=COLOR_SURFACE_2, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, placeholder_text="sk-or-...",
        )
        self.key_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.eye_btn = ctk.CTkButton(
            key_inner, text="\u25C9", width=36, height=36,
            font=ctk.CTkFont(size=16),
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT_DIM,
            command=self._toggle_key_visibility,
        )
        self.eye_btn.pack(side="right")
        self._key_visible = False

        # Model
        model_frame = ctk.CTkFrame(settings_row, fg_color="transparent")
        model_frame.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self._section_label(model_frame, "МОДЕЛЬ")

        self.model_names = [m["name"] for m in FREE_MODELS]
        self.model_ids = [m["id"] for m in FREE_MODELS]
        self.model_var = ctk.StringVar()

        if self.config.model in self.model_ids:
            idx = self.model_ids.index(self.config.model)
            self.model_var.set(self.model_names[idx])
        else:
            self.model_var.set(self.model_names[0])

        ctk.CTkComboBox(
            model_frame, variable=self.model_var, values=self.model_names,
            height=36, font=ctk.CTkFont(size=13), dropdown_font=ctk.CTkFont(size=12),
            fg_color=COLOR_SURFACE_2, border_color=COLOR_BORDER,
            button_color=COLOR_BORDER, button_hover_color=COLOR_ACCENT,
            dropdown_fg_color=COLOR_SURFACE, dropdown_hover_color=COLOR_SURFACE_2,
            text_color=COLOR_TEXT, dropdown_text_color=COLOR_TEXT,
            state="readonly", command=self._on_model_change,
        ).pack(fill="x")

        # Progress
        self._section_label(inner, "ПРОГРЕСС")
        ctk.CTkProgressBar(
            inner, height=8, corner_radius=4,
            fg_color=COLOR_SURFACE_2, progress_color=COLOR_ACCENT,
        ).pack(fill="x", pady=(0, 2))
        self.progress_bar = inner.winfo_children()[-1]
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(
            inner, text="Ожидание запуска...",
            font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM, anchor="w",
        )
        self.progress_label.pack(fill="x", pady=(0, 10))

        # Log
        self._section_label(inner, "ЛОГ")
        self.log_box = ctk.CTkTextbox(
            inner, height=100, font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=COLOR_BG, border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_DIM, corner_radius=8,
        )
        self.log_box.pack(fill="both", expand=True, pady=(0, 12))
        self.log_box.configure(state="disabled")

        # Buttons
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        self.btn_start = ctk.CTkButton(
            btn_row, text="  Запустить  ", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#ffffff", corner_radius=8, command=self._start,
        )
        self.btn_start.pack(side="left", padx=(0, 8))

        self.btn_open_json = ctk.CTkButton(
            btn_row, text="  JSON  ", height=40, font=ctk.CTkFont(size=13),
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT_DIM,
            corner_radius=8, state="disabled", command=lambda: self._open(self._result_json),
        )
        self.btn_open_json.pack(side="left", padx=(0, 4))

        self.btn_open_xlsx = ctk.CTkButton(
            btn_row, text="  Excel  ", height=40, font=ctk.CTkFont(size=13),
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT_DIM,
            corner_radius=8, state="disabled", command=lambda: self._open(self._result_xlsx),
        )
        self.btn_open_xlsx.pack(side="left")

        self.stats_label = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM,
        )
        self.stats_label.pack(side="right")

    # END_BLOCK_GUI_MAIN_TAB

    # START_BLOCK_GUI_PROMPT_TAB
    def _build_prompt_tab(self, parent: ctk.CTkFrame) -> None:
        inner = ctk.CTkFrame(parent, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        # Prompt selector row
        sel_row = ctk.CTkFrame(inner, fg_color="transparent")
        sel_row.pack(fill="x", pady=(0, 10))

        self._section_label(sel_row, "ВЫБОР ПРОМПТА")

        combo_row = ctk.CTkFrame(inner, fg_color="transparent")
        combo_row.pack(fill="x", pady=(0, 10))

        prompt_names = list_prompts() or [DEFAULT_PROMPT_NAME]
        self.prompt_var = ctk.StringVar(value=prompt_names[0])

        self.prompt_combo = ctk.CTkComboBox(
            combo_row, variable=self.prompt_var, values=prompt_names,
            height=36, font=ctk.CTkFont(size=13), dropdown_font=ctk.CTkFont(size=12),
            fg_color=COLOR_SURFACE_2, border_color=COLOR_BORDER,
            button_color=COLOR_BORDER, button_hover_color=COLOR_ACCENT,
            dropdown_fg_color=COLOR_SURFACE, dropdown_hover_color=COLOR_SURFACE_2,
            text_color=COLOR_TEXT, dropdown_text_color=COLOR_TEXT,
            state="readonly", command=self._on_prompt_select,
        )
        self.prompt_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            combo_row, text="Обновить", width=90, height=36,
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_SURFACE_2, hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER, text_color=COLOR_TEXT,
            command=self._refresh_prompts,
        ).pack(side="right")

        # Prompt editor
        self._section_label(inner, "ТЕКСТ ПРОМПТА")

        self.prompt_editor = ctk.CTkTextbox(
            inner, font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=COLOR_BG, border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT, corner_radius=8, wrap="word",
        )
        self.prompt_editor.pack(fill="both", expand=True, pady=(0, 10))

        # Load default prompt
        try:
            default_text = load_prompt(self.prompt_var.get())
            self.prompt_editor.insert("1.0", default_text)
        except FileNotFoundError:
            pass

        # Save row
        save_row = ctk.CTkFrame(inner, fg_color="transparent")
        save_row.pack(fill="x")

        self._section_label(save_row, "СОХРАНИТЬ КАК")

        name_row = ctk.CTkFrame(inner, fg_color="transparent")
        name_row.pack(fill="x")

        self.save_name_var = ctk.StringVar()
        ctk.CTkEntry(
            name_row, textvariable=self.save_name_var,
            placeholder_text="Имя нового промпта (без .txt)...",
            height=36, font=ctk.CTkFont(size=13),
            fg_color=COLOR_SURFACE_2, border_color=COLOR_BORDER, text_color=COLOR_TEXT,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            name_row, text="Сохранить", width=100, height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#ffffff", corner_radius=8,
            command=self._save_prompt,
        ).pack(side="right")

    # END_BLOCK_GUI_PROMPT_TAB

    # START_BLOCK_GUI_ACTIONS
    def _on_prompt_select(self, _choice: str | None = None) -> None:
        name = self.prompt_var.get()
        try:
            text = load_prompt(name)
            self.prompt_editor.delete("1.0", "end")
            self.prompt_editor.insert("1.0", text)
            self._log(f"Промпт загружен: {name}")
        except FileNotFoundError:
            self._log(f"Промпт не найден: {name}")

    def _refresh_prompts(self) -> None:
        names = list_prompts()
        if names:
            self.prompt_combo.configure(values=names)
            self._log(f"Найдено промптов: {len(names)}")

    def _save_prompt(self) -> None:
        name = self.save_name_var.get().strip()
        if not name:
            # Save over current
            name = self.prompt_var.get()

        text = self.prompt_editor.get("1.0", "end").strip()
        if not text:
            self._log("Промпт пустой, сохранение отменено")
            return

        save_prompt(name, text)
        self._refresh_prompts()
        self.prompt_var.set(name)
        self.save_name_var.set("")
        self._log(f"Промпт сохранён: {name}")

    def _get_current_prompt(self) -> str:
        """Get prompt text from the editor."""
        text = self.prompt_editor.get("1.0", "end").strip()
        if text:
            return text
        return load_prompt(DEFAULT_PROMPT_NAME)

    # -------------------------------------------------- Actions
    @staticmethod
    def _section_label(parent: ctk.CTkFrame, text: str) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(0, 6))

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Выберите result.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.path_var.set(path)
            self._log(f"Выбран: {Path(path).name}")

    def _toggle_key_visibility(self) -> None:
        self._key_visible = not self._key_visible
        self.key_entry.configure(show="" if self._key_visible else "\u2022")
        self.eye_btn.configure(text="\u25CE" if self._key_visible else "\u25C9")

    def _on_model_change(self, _choice: str | None = None) -> None:
        idx = self.model_names.index(self.model_var.get())
        self.config.model = self.model_ids[idx]
        save_config(self.config)
        self._log(f"Модель: {self.model_var.get()}")

    def _log(self, msg: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{timestamp}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _on_progress(self, done: int, total: int, msg: str) -> None:
        self.root.after(0, self._update_progress, done, total, msg)

    def _update_progress(self, done: int, total: int, msg: str) -> None:
        if total > 0:
            ratio = done / total
            self.progress_bar.set(ratio)
            self.progress_label.configure(
                text=f"{done}/{total} ({ratio:.0%})",
                text_color=COLOR_SUCCESS if done == total else COLOR_TEXT_DIM,
            )
        self._log(msg)

    def _start(self) -> None:
        if self._running:
            return

        path_str = self.path_var.get().strip()
        if not path_str:
            self._log("Укажите путь к файлу экспорта!")
            self.progress_label.configure(text="Укажите файл", text_color=COLOR_WARNING)
            return

        key = self.key_var.get().strip()
        if not key:
            self._log("Введите OpenRouter API ключ!")
            self.progress_label.configure(text="Введите API ключ", text_color=COLOR_WARNING)
            return

        self.config.openrouter_api_key = key
        save_config(self.config)

        prompt = self._get_current_prompt()

        self._running = True
        self.btn_start.configure(state="disabled", text="  Обработка...  ")
        self.btn_open_json.configure(state="disabled")
        self.btn_open_xlsx.configure(state="disabled")
        self.progress_bar.set(0)
        self.progress_label.configure(text="Запуск...", text_color=COLOR_ACCENT)
        self.stats_label.configure(text="")

        thread = threading.Thread(
            target=self._run_in_thread,
            args=(Path(path_str), prompt),
            daemon=True,
        )
        thread.start()

    def _run_in_thread(self, export_path: Path, prompt: str) -> None:
        loop = asyncio.new_event_loop()
        try:
            json_path, xlsx_path = loop.run_until_complete(
                run_pipeline(export_path, self.config, prompt, self._on_progress)
            )
            self._result_json = json_path
            self._result_xlsx = xlsx_path
            self.root.after(0, self._on_done)
        except Exception as exc:
            self.root.after(0, self._on_error, str(exc))
        finally:
            loop.close()

    def _on_done(self) -> None:
        self._running = False
        self.btn_start.configure(state="normal", text="  Запустить  ")

        for btn in (self.btn_open_json, self.btn_open_xlsx):
            btn.configure(
                state="normal", fg_color=COLOR_SUCCESS,
                hover_color="#2fb886", text_color="#ffffff", border_width=0,
            )

        self.progress_label.configure(text="Завершено!", text_color=COLOR_SUCCESS)
        self._log("Обработка завершена!")

        if self._result_xlsx:
            size = self._result_xlsx.stat().st_size / 1024
            self.stats_label.configure(text=f"{self._result_xlsx.name} | {size:.0f} KB")

    def _on_error(self, error: str) -> None:
        self._running = False
        self.btn_start.configure(state="normal", text="  Запустить  ")
        self.progress_label.configure(text="Ошибка!", text_color=COLOR_ERROR)
        self._log(f"ОШИБКА: {error}")

    @staticmethod
    def _open(path: Path | None) -> None:
        if path and path.exists():
            os.startfile(path)

    # END_BLOCK_GUI_ACTIONS

    def run(self) -> None:
        self.root.mainloop()


# START_BLOCK_CLI
def _run_cli(args: argparse.Namespace) -> None:
    config = load_config()

    if args.api_key:
        config.openrouter_api_key = args.api_key
    if args.model:
        config.model = args.model

    if not config.openrouter_api_key:
        config.openrouter_api_key = input("OpenRouter API Key: ").strip()
        save_config(config)

    # Load prompt
    prompt_name = args.prompt or DEFAULT_PROMPT_NAME
    try:
        system_prompt = load_prompt(prompt_name)
    except FileNotFoundError:
        print(f"Prompt '{prompt_name}' not found. Available: {', '.join(list_prompts())}")
        return

    export_path = Path(args.export_path)

    def cli_progress(done: int, total: int, msg: str) -> None:
        if total > 0:
            pct = done / total * 100
            bar_len = 30
            filled = int(bar_len * done // total)
            bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
            print(f"\r[{bar}] {pct:.0f}% ({done}/{total}) {msg}", end="", flush=True)
        else:
            print(msg)

    json_path, xlsx_path = asyncio.run(
        run_pipeline(export_path, config, system_prompt, cli_progress)
    )
    print(f"\nJSON:  {json_path}")
    print(f"Excel: {xlsx_path}")
# END_BLOCK_CLI


def main() -> None:
    parser = argparse.ArgumentParser(description="TG Contact Extractor")
    parser.add_argument("export_path", nargs="?", help="result.json or export folder")
    parser.add_argument("--api-key", help="OpenRouter API key")
    parser.add_argument("--model", help="OpenRouter model ID")
    parser.add_argument("--prompt", help="Prompt name from prompts/ folder")
    parser.add_argument("--gui", action="store_true", help="Force GUI mode")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    if args.export_path and not args.gui:
        _run_cli(args)
    else:
        app = AppGUI()
        app.run()


if __name__ == "__main__":
    main()


# START_CHANGE_SUMMARY
#   LAST_CHANGE: [v3.0.0 — Tabbed GUI: prompt editor tab with load/save/select, dual output JSON+Excel,
#     prompt stored in metadata, CLI --prompt flag]
# END_CHANGE_SUMMARY
