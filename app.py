from __future__ import annotations

import asyncio
import logging
import os
import queue
import tempfile
import threading
from typing import Any, Generator

import gradio as gr
import pandas as pd

from scrapers.base import ContactResult
from scrapers.scraper_karir import ScraperKarir

logger = logging.getLogger(__name__)

STEP: dict[str, str] = {
    "INIT": "APP.01",
    "SCRAPE_CALL": "APP.02",
    "THREAD_CRASH": "APP.03",
    "NO_RESULTS": "APP.04",
}


def _s(key: str) -> str:
    return f"[{STEP[key]}]"


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT, force=True)


setup_logging()


def _result_to_row(r: ContactResult) -> list[str]:
    phones = ", ".join(r.phones) if r.phones else "-"
    emails = ", ".join(r.emails) if r.emails else "-"
    error = r.error if r.error else "-"
    return [r.url, phones, emails, error]


_active_cancel_event: threading.Event | None = None


def scrape_handler(
    url: str,
    proxy_url: str,
    max_links: int,
    max_pages: int,
) -> Generator[tuple[list[list[str]], str, Any, Any], None, None]:
    global _active_cancel_event

    if not url.strip():
        yield (
            [["-", "-", "-", "URL tidak boleh kosong"]],
            "URL tidak boleh kosong.",
            gr.update(visible=True),
            gr.update(visible=False),
        )
        return

    cancel_event = threading.Event()
    _active_cancel_event = cancel_event

    q: queue.Queue[tuple[str, Any]] = queue.Queue()

    def run_scraper() -> None:
        async def _run() -> None:
            proxy = proxy_url.strip() if proxy_url.strip() else None
            logger.info(
                "%s Init ScraperKarir: url=%s, proxy=%s, max_links=%d",
                _s("INIT"),
                url.strip(),
                proxy,
                max_links,
            )
            scraper = ScraperKarir(
                headless=True,
                proxy_url=proxy,
                max_scroll=30,
                max_links=int(max_links),
                max_pages=int(max_pages),
            )

            def on_progress(pct: float, desc: str) -> None:
                q.put(("status", desc))

            def on_batch_result(
                batch_idx: int,
                total_batches: int,
                completed: int,
                total: int,
                batch: list[ContactResult],
            ) -> None:
                q.put(("batch", (batch_idx, total_batches, completed, total, batch)))

            logger.info("%s Mulai scraper.scrape()", _s("SCRAPE_CALL"))

            results = await scraper.scrape(
                url.strip(),
                progress_fn=on_progress,
                cancel_event=cancel_event,
                on_batch_result=on_batch_result,
            )

            if not results:
                logger.warning(
                    "%s Tidak ditemukan kontak di %s",
                    _s("NO_RESULTS"),
                    url.strip(),
                )
                q.put(("done", []))
                return

            phones_found = sum(len(r.phones) for r in results if r.phones)
            emails_found = sum(len(r.emails) for r in results if r.emails)
            summary = (
                f"Selesai! {len(results)} halaman diproses. "
                f"Ditemukan {phones_found} nomor telepon dan {emails_found} email."
            )
            logger.info(
                "%s Selesai: %d halaman diproses",
                _s("SCRAPE_CALL"),
                len(results),
            )
            q.put(("done", summary))

        try:
            asyncio.run(_run())
        except Exception as e:
            logger.error("%s Scraper thread crash: %s", _s("THREAD_CRASH"), e)
            q.put(
                (
                    "batch",
                    (
                        1,
                        1,
                        1,
                        1,
                        [
                            ContactResult(
                                url=url.strip(),
                                error=f"{_s('THREAD_CRASH')} {type(e).__name__}: {e}",
                            )
                        ],
                    ),
                )
            )
            q.put(("done", f"Error: {e}"))

    t = threading.Thread(target=run_scraper, daemon=True)
    t.start()

    current_table: list[list[str]] = []
    show_scrape = gr.update(visible=True)
    show_cancel = gr.update(visible=False)
    hide_scrape = gr.update(visible=False)
    show_cancel_active = gr.update(visible=True)
    no_change_scrape = gr.update()
    no_change_cancel = gr.update()

    yield current_table, "Memulai scraping...", hide_scrape, show_cancel_active

    while True:
        item = q.get()
        msg_type = item[0]

        if msg_type == "status":
            status_text: str = item[1]
            yield current_table, status_text, no_change_scrape, no_change_cancel

        elif msg_type == "batch":
            batch_idx, total_batches, completed, total, batch_results = item[1]
            for r in batch_results:
                current_table.append(_result_to_row(r))
            yield (
                current_table,
                f"Batch {batch_idx}/{total_batches} selesai ({completed}/{total} link)...",
                no_change_scrape,
                no_change_cancel,
            )

        elif msg_type == "done":
            payload = item[1]
            if isinstance(payload, list) and len(payload) == 0:
                yield (
                    (
                        current_table
                        if current_table
                        else [
                            [
                                "-",
                                "-",
                                "-",
                                "Tidak ditemukan kontak di URL tersebut",
                            ]
                        ]
                    ),
                    "Tidak ditemukan kontak di URL tersebut.",
                    show_scrape,
                    show_cancel,
                )
            elif isinstance(payload, str):
                yield current_table, payload, show_scrape, show_cancel
            return


def cancel_handler() -> tuple[list[list[str]], str, Any, Any]:
    global _active_cancel_event
    if _active_cancel_event is not None:
        _active_cancel_event.set()
        _active_cancel_event = None
    return (
        [],
        "Scraping dibatalkan.",
        gr.update(visible=True),
        gr.update(visible=False),
    )


HEADERS = ["URL", "Telepon", "Email", "Error"]


def _ensure_dataframe(data: pd.DataFrame | list[list[str]]) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data
    return pd.DataFrame(data, columns=HEADERS)


def export_csv(data: pd.DataFrame | list[list[str]]) -> str | None:
    df = _ensure_dataframe(data)
    if df.empty:
        return None
    tmp = tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w", encoding="utf-8"
    )
    df.to_csv(tmp.name, index=False)
    tmp.close()
    return tmp.name


def export_excel(data: pd.DataFrame | list[list[str]]) -> str | None:
    df = _ensure_dataframe(data)
    if df.empty:
        return None
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    df.to_excel(tmp.name, index=False, engine="openpyxl")
    tmp.close()
    return tmp.name


def export_json(data: pd.DataFrame | list[list[str]]) -> str | None:
    df = _ensure_dataframe(data)
    if df.empty:
        return None
    tmp = tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w", encoding="utf-8"
    )
    tmp.write(df.to_json(orient="records", indent=2, force_ascii=False) or "")
    tmp.close()
    return tmp.name


def build_ui() -> gr.Blocks:
    with gr.Blocks(
        title="Scraping Info Loker Indonesia",
    ) as app:
        gr.Markdown(
            "# Tools Scraping Info Loker Indonesia\n"
            "Ekstrak nomor telepon dan email dari halaman lowongan kerja secara otomatis."
        )

        with gr.Row():
            url_input = gr.Textbox(
                label="URL Halaman Lowongan",
                placeholder="https://www.karir.com/cari?q=programmer",
                lines=1,
            )

        with gr.Row():
            max_links_slider = gr.Slider(
                minimum=10,
                maximum=500,
                value=100,
                step=10,
                label="Maksimal Link yang Di-scrape",
                info="Default: 100",
            )
            max_pages_slider = gr.Slider(
                minimum=1,
                maximum=20,
                value=10,
                step=1,
                label="Maksimal Halaman Pagination",
                info="Default: 10",
            )

        with gr.Group():
            proxy_input = gr.Textbox(
                label="Proxy URL (opsional)",
                placeholder="http://user:pass@proxy:port",
                lines=1,
            )

        with gr.Row():
            scrape_btn = gr.Button(
                "Mulai Scraping",
                variant="primary",
                size="lg",
            )
            cancel_btn = gr.Button(
                "Cancel Scraping",
                variant="stop",
                size="lg",
                visible=False,
            )

        status_output = gr.Textbox(
            label="Status",
            value="Belum dimulai. Masukkan URL lalu klik 'Mulai Scraping'.",
            interactive=False,
            lines=2,
        )

        results_table = gr.Dataframe(
            headers=["URL", "Telepon", "Email", "Error"],
            label="Hasil Scraping",
            row_count=10,
            column_count=4,
        )

        with gr.Row():
            csv_btn = gr.DownloadButton("Export CSV")
            excel_btn = gr.DownloadButton("Export Excel")
            json_btn = gr.DownloadButton("Export JSON")

        with gr.Row():
            with gr.Accordion("Apa itu Proxy URL?", open=False):
                gr.Markdown(
                    "Proxy adalah **perantara** antara komputer Anda dan website target.\n\n"
                    "**Kegunaan:**\n"
                    "- Menghindari blokir IP dari website target\n"
                    "- Menyembunyikan identitas IP asli Anda\n"
                    "- Akses dari IP Indonesia jika menggunakan VPS luar negeri\n\n"
                    "**Format:** `http://username:password@alamatproxy:port`\n\n"
                    "**Contoh:** `http://admin:secret123@103.50.10.5:8080`\n\n"
                    "Kosongkan jika tidak memiliki proxy. Scraping tetap bisa "
                    "berjalan tanpa proxy."
                )

        gr.Markdown(
            "---\n"
            "**Tips:**\n"
            "- Semakin banyak link, semakin lama proses scraping.\n"
            "- Semakin spesifik input linknya, semakin cepat proses scraping.\n"
            "- Alur: `Klik Mulai Scraping` -> `Harvest Link (Auto scroll)` -> "
            "`Scrape setiap link (ambil email & kontak)` -> `Tampilkan Hasil`.\n"
            "\n"
            "**Dibuat dengan:** Python, Playwright, Gradio"
        )

        scrape_btn.click(
            fn=scrape_handler,
            inputs=[
                url_input,
                proxy_input,
                max_links_slider,
                max_pages_slider,
            ],
            outputs=[results_table, status_output, scrape_btn, cancel_btn],
            show_progress="hidden",
        )

        cancel_btn.click(
            fn=cancel_handler,
            inputs=[],
            outputs=[results_table, status_output, scrape_btn, cancel_btn],
        )

        csv_btn.click(fn=export_csv, inputs=[results_table], outputs=[csv_btn])
        excel_btn.click(fn=export_excel, inputs=[results_table], outputs=[excel_btn])
        json_btn.click(fn=export_json, inputs=[results_table], outputs=[json_btn])

    return app


def _parse_auth_users() -> list[tuple[str, str]]:
    raw = os.environ.get("AUTH_USERS", "")
    if raw:
        users = []
        for pair in raw.split(","):
            parts = pair.strip().split(":")
            if len(parts) == 2:
                users.append((parts[0].strip(), parts[1].strip()))
        if users:
            return users
    return [("admin", "admin")]


app = build_ui().queue()


def main() -> None:
    server_name = os.environ.get("SERVER_NAME", "127.0.0.1")
    server_port = int(os.environ.get("SERVER_PORT", "7890"))
    app.launch(
        server_name=server_name,
        server_port=server_port,
        auth=_parse_auth_users(),
    )


if __name__ == "__main__":
    main()
