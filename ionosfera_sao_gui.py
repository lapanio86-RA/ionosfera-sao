# -*- coding: utf-8 -*-
"""
Ionosfera SAO - Consulta simples de ionossonda INPE/Embrace

Aplicativo desktop em Python/Tkinter para baixar e interpretar arquivos .SAO
(DPS-4D/ARTIST) da rede Embrace/INPE.

Versao: 1.0
"""

import csv
import math
import os
import re
import sys
import threading
import traceback
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

BASE_URL_DEFAULT = "https://embracedata.inpe.br/ionosonde"
STATION_DEFAULT = "CAJ2M"
DAYS_BACK_DEFAULT = 2
LAST_COUNT_DEFAULT = 5

BRT = timezone(timedelta(hours=-3), name="BRT")
UTC = timezone.utc


# ---------------------------------------------------------------------------
# Dados / parsing SAO
# ---------------------------------------------------------------------------

GROUP4_FIELDS = [
    ("foF2", "MHz", "F2 vertical"),
    ("foF1", "MHz", "F1 vertical"),
    ("M_D", "", "fator M(3000)F2 / MUF(D)/foF2"),
    ("MUF_D", "MHz", "MUF(3000)F2 / MUF(D)"),
    ("fmin", "MHz", "menor frequência com eco"),
    ("foEs", "MHz", "E esporádica"),
    ("fminF", "MHz", "fminF"),
    ("fminE", "MHz", "fminE"),
    ("foE", "MHz", "E normal"),
    ("fxI", "MHz", "máximo traço F"),
    ("hF", "km", "altura virtual F"),
    ("hF2", "km", "altura virtual F2"),
    ("hE", "km", "altura virtual E"),
    ("hEs", "km", "altura virtual Es"),
    ("hmE", "km", "pico/modelo E"),
    ("yE", "km", "semi-espessura E"),
    ("QF", "km", "QF"),
    ("QE", "km", "QE"),
    ("DownF", "km", "DownF"),
    ("DownE", "km", "DownE"),
    ("DownEs", "km", "DownEs"),
    ("FF", "MHz", "FF"),
    ("FE", "MHz", "FE"),
    ("D", "km", "distância usada no cálculo"),
    ("fMUF", "MHz", "frequência MUF auxiliar"),
    ("hMUF", "km", "altura MUF auxiliar"),
    ("delta_foF2", "MHz", "delta foF2"),
    ("foEp", "MHz", "E prevista"),
    ("f_hF", "MHz", "f(h'F)"),
    ("f_hF2", "MHz", "f(h'F2)"),
    ("foF1p", "MHz", "F1 prevista"),
    ("hmF2", "km", "pico real/modelado F2"),
    ("hmF1", "km", "pico real/modelado F1"),
    ("zhalfNm", "km", "z half Nm"),
    ("foF2p", "MHz", "F2 prevista"),
    ("fminEs", "MHz", "fminEs"),
    ("yF2", "km", "semi-espessura F2"),
    ("yF1", "km", "semi-espessura F1"),
    ("TEC", "10^16 m^-2", "conteúdo eletrônico total"),
    ("scaleF2", "km", "escala F2"),
    ("B0", "km", "parâmetro IRI B0"),
    ("B1", "", "parâmetro IRI B1"),
    ("D1", "", "D1"),
    ("foEa", "MHz", "foEa"),
    ("hEa", "km", "hEa"),
    ("foP", "MHz", "foP"),
    ("hP", "km", "hP"),
    ("fbEs", "MHz", "fbEs"),
    ("typeEs", "", "tipo Es"),
]

FIELD_META = {key: (unit, label) for key, unit, label in GROUP4_FIELDS}

DISPLAY_NAMES = {
    "hF": "h'F",
    "hF2": "h'F2",
    "hE": "h'E",
    "hEs": "h'Es",
    "M_D": "M(3000)F2",
    "MUF_D": "MUF(3000)F2",
}


@dataclass
class SaoFileItem:
    filename: str
    url: str | None
    timestamp_utc: datetime
    text: str | None = None
    origin: str = "remote"
    path: str | None = None


@dataclass
class ParsedSAO:
    station: str | None
    station_name: str | None
    system_description: str
    timestamp_utc: datetime | None
    data_index: list[int]
    raw_group4: list[float | None]
    scaled: dict[str, float | None]
    group4_count: int


def fmt_num(v, decimals=3):
    if v is None:
        return "sem dado"
    if isinstance(v, str):
        return v
    try:
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        s = f"{v:.{decimals}f}".rstrip("0").rstrip(".")
        return s
    except Exception:
        return str(v)


def fmt_unit(v, unit="", decimals=3):
    if v is None:
        return "sem dado"
    return f"{fmt_num(v, decimals)} {unit}".strip()


def clean_value(v):
    if v is None:
        return None
    if not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    if abs(v - 9999.0) < 0.001:
        return None
    if abs(v - 999.9) < 0.001:
        return None
    return v


def day_of_year_utc(dt):
    start = datetime(dt.year, 1, 1, tzinfo=UTC)
    current = datetime(dt.year, dt.month, dt.day, tzinfo=UTC)
    return (current - start).days + 1


def parse_sao_filename(filename):
    m = re.match(r"^([A-Z0-9]+)_(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})\.SAO$", filename, re.I)
    if not m:
        return None
    station, year, doy, hh, mm, ss = m.groups()
    base = datetime(int(year), 1, 1, tzinfo=UTC) + timedelta(days=int(doy) - 1)
    dt = base.replace(hour=int(hh), minute=int(mm), second=int(ss), microsecond=0)
    return {
        "station": station.upper(),
        "year": int(year),
        "doy": int(doy),
        "date": dt,
    }


def fetch_text(url, timeout=25):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 IonosferaSAO/1.0",
            "Accept": "text/html,text/plain,*/*",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return data.decode("utf-8", errors="replace")


def list_remote_sao(station, base_url, days_back, last_count):
    station = station.upper().strip()
    now = datetime.now(UTC)
    items = []

    for offset in range(days_back + 1):
        dt = now - timedelta(days=offset)
        year = dt.year
        doy = str(day_of_year_utc(dt)).zfill(3)
        dir_url = f"{base_url.rstrip('/')}/{station}/{year}/{doy}/"
        try:
            html = fetch_text(dir_url)
        except Exception:
            continue

        pattern = re.compile(rf"{re.escape(station)}_\d{{13}}\.SAO", re.I)
        filenames = sorted(set(pattern.findall(html)))
        for name in filenames:
            info = parse_sao_filename(name)
            if not info:
                continue
            items.append(SaoFileItem(
                filename=name,
                url=dir_url + name,
                timestamp_utc=info["date"],
                origin="remote",
            ))

    items.sort(key=lambda x: x.timestamp_utc, reverse=True)
    return items[:last_count]


def list_local_sao(folder, station=None, last_count=5):
    p = Path(folder)
    items = []
    for f in p.glob("*.SAO"):
        info = parse_sao_filename(f.name)
        if not info:
            continue
        if station and info["station"].upper() != station.upper().strip():
            continue
        items.append(SaoFileItem(
            filename=f.name,
            url=None,
            timestamp_utc=info["date"],
            origin="local",
            path=str(f),
        ))
    items.sort(key=lambda x: x.timestamp_utc, reverse=True)
    return items[:last_count]


def parse_data_index(lines):
    raw = (lines[0] if len(lines) > 0 else "").ljust(120) + (lines[1] if len(lines) > 1 else "").ljust(120)
    vals = []
    for i in range(0, 240, 3):
        s = raw[i:i+3].strip()
        vals.append(int(s) if s else 0)
    return [0] + vals  # 1-based


def take_fixed(lines, pos, count, width, per_line):
    n_lines = math.ceil(count / per_line) if count else 0
    raw = "".join(line.ljust(width * per_line) for line in lines[pos:pos+n_lines])
    values = []
    for i in range(count):
        s = raw[i*width:(i+1)*width].strip()
        try:
            values.append(float(s) if s else None)
        except Exception:
            values.append(None)
    return values, pos + n_lines


def take_text(lines, pos, count, mode="chars"):
    if mode == "lines":
        text = "\n".join(lines[pos:pos+count])
        return text, pos + count
    n_lines = math.ceil(count / 120) if count else 0
    text = "".join(line.ljust(120) for line in lines[pos:pos+n_lines])[:count]
    return text, pos + n_lines


def parse_timestamp_group3(g3):
    # Exemplo observado: FF20261540603152000...
    if not g3 or len(g3) < 19:
        return None
    try:
        year = int(g3[2:6])
        month = int(g3[9:11])
        day = int(g3[11:13])
        hour = int(g3[13:15])
        minute = int(g3[15:17])
        second = int(g3[17:19])
        return datetime(year, month, day, hour, minute, second, tzinfo=UTC)
    except Exception:
        return None


def parse_sao_text(text):
    lines = text.replace("\r", "").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if len(lines) < 3:
        raise ValueError("Arquivo .SAO muito curto ou inválido.")

    idx = parse_data_index(lines)
    pos = 2

    # Grupo 1: geofísicos
    _, pos = take_fixed(lines, pos, idx[1] if len(idx) > 1 else 0, 7, 16)

    # Grupo 2: descrição da estação
    g2, pos = take_text(lines, pos, idx[2] if len(idx) > 2 else 0, "lines")

    # Grupo 3: timestamp/configuração
    g3, pos = take_text(lines, pos, idx[3] if len(idx) > 3 else 0, "chars")

    # Grupo 4: características ionosféricas escaladas
    group4_count = idx[4] if len(idx) > 4 else 0
    g4, pos = take_fixed(lines, pos, group4_count, 8, 15)

    cleaned = [clean_value(v) for v in g4]
    scaled = {}
    for i, (key, _unit, _label) in enumerate(GROUP4_FIELDS):
        scaled[key] = cleaned[i] if i < len(cleaned) else None

    system_description = g2.strip()
    station_match = re.search(r"/([A-Z0-9]+)\b", system_description)
    name_match = re.search(r"\bNAME\s+([^,]+)", system_description, re.I)

    return ParsedSAO(
        station=station_match.group(1) if station_match else None,
        station_name=name_match.group(1).strip() if name_match else None,
        system_description=system_description,
        timestamp_utc=parse_timestamp_group3(g3),
        data_index=idx[1:80],
        raw_group4=g4,
        scaled=scaled,
        group4_count=group4_count,
    )


def get_value(parsed, key):
    return parsed.scaled.get(key)


def calc_muf(parsed):
    foF2 = get_value(parsed, "foF2")
    m = get_value(parsed, "M_D")
    field = get_value(parsed, "MUF_D")
    calc = foF2 * m if foF2 is not None and m is not None else None
    diff = calc - field if calc is not None and field is not None else None
    pct = (diff / field * 100.0) if diff is not None and field not in (None, 0) else None
    ref = calc if calc is not None else field
    return {"foF2": foF2, "m": m, "field": field, "calc": calc, "diff": diff, "pct": pct, "ref": ref}


def estimated_muf_by_distance(parsed):
    # Estimativa geométrica simples ajustada ao M(3000)F2.
    # Útil como panorama, não substitui o modelo do portal.
    foF2 = get_value(parsed, "foF2")
    h = get_value(parsed, "hmF2") or get_value(parsed, "hF2") or 300.0
    m3000 = get_value(parsed, "M_D")
    distances = [100, 200, 400, 600, 800, 1000, 1500, 3000]
    rows = []
    if not foF2:
        return rows
    for d in distances:
        if d == 3000 and m3000:
            factor = m3000
            note = "ajustada ao M(3000)F2"
        else:
            factor = math.sqrt(1.0 + (d / (2.0 * h)) ** 2)
            # Evita fator maior que M(3000), caso altura/modelo gere extrapolação estranha.
            if m3000:
                factor = min(factor, m3000)
            note = "estimativa secante"
        rows.append({
            "distância": f"{d} km",
            "fator estimado": fmt_num(factor, 3),
            "MUF estimada": fmt_unit(foF2 * factor, "MHz", 3),
            "observação": note,
        })
    return rows


def band_status(parsed):
    muf = calc_muf(parsed)["ref"]
    foF2 = get_value(parsed, "foF2")
    fmin = get_value(parsed, "fmin")

    rows = []

    def local_status(band, freq):
        if foF2 is None:
            return ("sem dado", "foF2 ausente")
        if fmin is not None and fmin > freq:
            return ("absorção/sem eco", f"fmin {fmt_unit(fmin, 'MHz')} acima de {fmt_unit(freq, 'MHz')}")
        if foF2 >= freq:
            if band == "80m":
                return ("possível, depende do horário", f"foF2 {fmt_unit(foF2, 'MHz')}; fmin {fmt_unit(fmin, 'MHz')}")
            return ("boa local/regional", f"foF2 {fmt_unit(foF2, 'MHz')}; fmin {fmt_unit(fmin, 'MHz')}")
        if foF2 >= freq * 0.9:
            return ("limítrofe", f"foF2 {fmt_unit(foF2, 'MHz')} perto de {fmt_unit(freq, 'MHz')}")
        return ("baixa", f"foF2 {fmt_unit(foF2, 'MHz')} abaixo de {fmt_unit(freq, 'MHz')}")

    for band, freq, use in [("80m", 3.6, "local/regional"), ("40m", 7.1, "local/regional")]:
        st, base = local_status(band, freq)
        rows.append({"banda": band, "ref.": f"{freq:g} MHz", "uso": use, "status simples": st, "base": base})

    for band, freq in [("20m", 14.0), ("15m", 21.0), ("12m", 24.9), ("10m", 28.0)]:
        if muf is None:
            st = "sem dado"
            base = "MUF ausente"
        else:
            margin = muf - freq
            pct = margin / freq * 100.0
            if freq <= muf * 0.80:
                st = "boa para DX"
            elif freq <= muf * 0.93:
                st = "boa/seletiva"
            elif freq <= muf:
                st = "aberta/seletiva"
            elif freq <= muf * 1.05:
                st = "perto/acima da MUF; monitorar"
            else:
                st = "acima da MUF"
            base = f"MUF ref. {fmt_unit(muf, 'MHz')}; margem {margin:+.2f} MHz ({pct:+.1f}%)"
        rows.append({"banda": band, "ref.": f"{freq:g} MHz", "uso": "DX F2", "status simples": st, "base": base})

    return rows


def trend_rows(items_parsed):
    rows = []
    # Exibir em ordem cronológica
    for item, parsed in sorted(items_parsed, key=lambda x: x[0].timestamp_utc):
        cm = calc_muf(parsed)
        rows.append({
            "utc": item.timestamp_utc.strftime("%H:%M"),
            "arquivo": item.filename,
            "foF2": fmt_num(get_value(parsed, "foF2")),
            "MUF_SAO": fmt_num(cm["field"]),
            "MUF_calc": fmt_num(cm["calc"]),
            "diff": fmt_num(cm["diff"]),
            "foE": fmt_num(get_value(parsed, "foE")),
            "foEs": fmt_num(get_value(parsed, "foEs")),
            "fmin": fmt_num(get_value(parsed, "fmin")),
            "hmF2": fmt_num(get_value(parsed, "hmF2")),
            "TEC": fmt_num(get_value(parsed, "TEC")),
        })
    return rows


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class IonosferaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ionosfera SAO - INPE/Embrace")
        self.geometry("1120x760")
        self.minsize(980, 650)

        self.current_items = []
        self.current_parsed = []
        self.current_main = None

        self._setup_style()
        self._build_ui()

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("classic")
        except Exception:
            pass
        self.configure(bg="#c0c0c0")
        style.configure("TFrame", background="#c0c0c0")
        style.configure("TLabel", background="#c0c0c0", foreground="#000000", font=("MS Sans Serif", 9))
        style.configure("TButton", font=("MS Sans Serif", 9))
        style.configure("Treeview", font=("MS Sans Serif", 9), rowheight=22)
        style.configure("Treeview.Heading", font=("MS Sans Serif", 9, "bold"))
        style.configure("Header.TLabel", font=("MS Sans Serif", 14, "bold"), background="#c0c0c0")
        style.configure("Small.TLabel", font=("MS Sans Serif", 8), background="#c0c0c0")

    def _build_ui(self):
        top = ttk.Frame(self, padding=8, relief="raised", borderwidth=2)
        top.pack(fill="x")

        ttk.Label(top, text="Ionosfera SAO", style="Header.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 16))

        ttk.Label(top, text="Estação:").grid(row=0, column=1, sticky="e")
        self.station_var = tk.StringVar(value=STATION_DEFAULT)
        ttk.Entry(top, textvariable=self.station_var, width=10).grid(row=0, column=2, sticky="w", padx=4)

        ttk.Label(top, text="Últimos:").grid(row=0, column=3, sticky="e")
        self.last_var = tk.StringVar(value=str(LAST_COUNT_DEFAULT))
        ttk.Entry(top, textvariable=self.last_var, width=4).grid(row=0, column=4, sticky="w", padx=4)

        self.online_btn = ttk.Button(top, text="Atualizar online", command=self.update_online)
        self.online_btn.grid(row=0, column=5, padx=4)

        self.local_btn = ttk.Button(top, text="Abrir pasta local", command=self.open_local_folder)
        self.local_btn.grid(row=0, column=6, padx=4)

        self.copy_btn = ttk.Button(top, text="Copiar resumo", command=self.copy_summary)
        self.copy_btn.grid(row=0, column=7, padx=4)

        self.export_btn = ttk.Button(top, text="Exportar CSV", command=self.export_csv)
        self.export_btn.grid(row=0, column=8, padx=4)

        self.status_var = tk.StringVar(value="Pronto. Clique em Atualizar online.")
        ttk.Label(top, textvariable=self.status_var, style="Small.TLabel").grid(row=1, column=0, columnspan=9, sticky="w", pady=(6, 0))

        top.columnconfigure(9, weight=1)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_resumo = ttk.Frame(self.nb, padding=6)
        self.tab_freq = ttk.Frame(self.nb, padding=6)
        self.tab_alt = ttk.Frame(self.nb, padding=6)
        self.tab_muf = ttk.Frame(self.nb, padding=6)
        self.tab_group4 = ttk.Frame(self.nb, padding=6)
        self.tab_trend = ttk.Frame(self.nb, padding=6)
        self.tab_tech = ttk.Frame(self.nb, padding=6)

        self.nb.add(self.tab_resumo, text="Resumo")
        self.nb.add(self.tab_freq, text="Frequências críticas")
        self.nb.add(self.tab_alt, text="Alturas")
        self.nb.add(self.tab_muf, text="MUF / Modelo")
        self.nb.add(self.tab_group4, text="Grupo 4 completo")
        self.nb.add(self.tab_trend, text="Tendência")
        self.nb.add(self.tab_tech, text="Coleta / Técnico")

        self.summary_tree = self._make_tree(self.tab_resumo, ["item", "valor", "observação"], height=8)
        ttk.Label(self.tab_resumo, text="Status simples por banda", style="Header.TLabel").pack(anchor="w", pady=(8, 3))
        self.band_tree = self._make_tree(self.tab_resumo, ["banda", "ref.", "uso", "status simples", "base"], height=8)
        note = (
            "A tabela por banda é apenas um auxílio rápido baseado em foF2, fmin, foEs e MUF(3000). "
            "A decisão final depende do caminho, horário, ruído, antena, potência e atividade real na banda."
        )
        ttk.Label(self.tab_resumo, text=note, wraplength=1000, style="Small.TLabel").pack(anchor="w", pady=(6, 0))

        self.freq_tree = self._make_tree(self.tab_freq, ["sigla", "valor", "unidade", "leitura"], height=16)
        self.alt_tree = self._make_tree(self.tab_alt, ["sigla", "valor", "unidade", "leitura"], height=16)
        self.muf_tree = self._make_tree(self.tab_muf, ["sigla", "valor", "unidade", "leitura"], height=18)
        ttk.Label(self.tab_muf, text="MUF estimada por distância", style="Header.TLabel").pack(anchor="w", pady=(8, 3))
        self.muf_dist_tree = self._make_tree(self.tab_muf, ["distância", "fator estimado", "MUF estimada", "observação"], height=9)

        self.group4_tree = self._make_tree(self.tab_group4, ["posição", "sigla", "valor", "unidade", "leitura"], height=24)
        self.trend_tree = self._make_tree(self.tab_trend, ["utc", "arquivo", "foF2", "MUF_SAO", "MUF_calc", "diff", "foE", "foEs", "fmin", "hmF2", "TEC"], height=18)
        self.tech_tree = self._make_tree(self.tab_tech, ["item", "valor"], height=22)

    def _make_tree(self, parent, columns, height=10):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, pady=2)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=height)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        for col in columns:
            tree.heading(col, text=col)
            width = 130
            if col in ("arquivo", "url", "valor", "base", "observação", "condição", "leitura"):
                width = 260
            if col in ("item",):
                width = 200
            tree.column(col, width=width, anchor="w", stretch=True)
        return tree

    def _set_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.online_btn.configure(state=state)
        self.local_btn.configure(state=state)
        self.copy_btn.configure(state=state)
        self.export_btn.configure(state=state)

    def _last_count(self):
        try:
            return max(1, min(30, int(self.last_var.get().strip())))
        except Exception:
            return LAST_COUNT_DEFAULT

    def update_online(self):
        station = self.station_var.get().strip().upper() or STATION_DEFAULT
        last_count = self._last_count()
        self._set_busy(True)
        self.status_var.set("Buscando diretório remoto e baixando arquivos .SAO...")
        threading.Thread(target=self._online_worker, args=(station, last_count), daemon=True).start()

    def _online_worker(self, station, last_count):
        try:
            items = list_remote_sao(station, BASE_URL_DEFAULT, DAYS_BACK_DEFAULT, last_count)
            if not items:
                raise RuntimeError("Nenhum arquivo .SAO encontrado no servidor nos últimos dias.")
            parsed_pairs = []
            for item in items:
                item.text = fetch_text(item.url)
                parsed_pairs.append((item, parse_sao_text(item.text)))
            self.after(0, lambda: self._load_result(parsed_pairs, "remote"))
        except Exception as e:
            tb = traceback.format_exc()
            self.after(0, lambda: self._show_error(str(e), tb))

    def open_local_folder(self):
        folder = filedialog.askdirectory(title="Selecione a pasta com arquivos .SAO")
        if not folder:
            return
        station = self.station_var.get().strip().upper() or None
        last_count = self._last_count()
        self._set_busy(True)
        self.status_var.set("Lendo arquivos .SAO locais...")
        threading.Thread(target=self._local_worker, args=(folder, station, last_count), daemon=True).start()

    def _local_worker(self, folder, station, last_count):
        try:
            items = list_local_sao(folder, station, last_count)
            if not items:
                raise RuntimeError("Nenhum arquivo .SAO válido encontrado na pasta selecionada.")
            parsed_pairs = []
            for item in items:
                item.text = Path(item.path).read_text(encoding="utf-8", errors="replace")
                parsed_pairs.append((item, parse_sao_text(item.text)))
            self.after(0, lambda: self._load_result(parsed_pairs, "local"))
        except Exception as e:
            tb = traceback.format_exc()
            self.after(0, lambda: self._show_error(str(e), tb))

    def _show_error(self, msg, tb):
        self._set_busy(False)
        self.status_var.set("Erro na coleta/leitura.")
        messagebox.showerror("Erro", f"{msg}\n\nDetalhes:\n{tb[-1800:]}")

    def _clear_tree(self, tree):
        tree.delete(*tree.get_children())

    def _insert_rows(self, tree, rows, columns=None):
        self._clear_tree(tree)
        if columns is None:
            columns = tree["columns"]
        for row in rows:
            if isinstance(row, dict):
                vals = [row.get(c, "") for c in columns]
            else:
                vals = row
            tree.insert("", "end", values=vals)

    def _load_result(self, parsed_pairs, source):
        self.current_parsed = parsed_pairs
        self.current_items = [x[0] for x in parsed_pairs]
        main_item, main_parsed = max(parsed_pairs, key=lambda x: x[0].timestamp_utc)
        self.current_main = (main_item, main_parsed)

        self._populate_all(main_item, main_parsed, parsed_pairs, source)
        age_min = round((datetime.now(UTC) - main_item.timestamp_utc).total_seconds() / 60)
        self.status_var.set(f"Dados carregados: {main_item.filename} | {main_item.timestamp_utc.isoformat()} | idade: {age_min} min")
        self._set_busy(False)

    def _populate_all(self, item, p, parsed_pairs, source):
        cm = calc_muf(p)
        ts = p.timestamp_utc or item.timestamp_utc
        brt = ts.astimezone(BRT)
        age_min = round((datetime.now(UTC) - item.timestamp_utc).total_seconds() / 60)

        summary_rows = [
            {"item": "Estação", "valor": f"{p.station or ''} - {p.station_name or ''}".strip(" -"), "observação": ""},
            {"item": "Horário do ionograma", "valor": f"{ts.isoformat()} ({brt.strftime('%H:%M BRT')})", "observação": ""},
            {"item": "foF2", "valor": fmt_unit(get_value(p, "foF2"), "MHz"), "observação": "referência principal para F2/NVIS"},
            {"item": "fmin", "valor": fmt_unit(get_value(p, "fmin"), "MHz"), "observação": "frequência mínima com eco"},
            {"item": "foE", "valor": fmt_unit(get_value(p, "foE"), "MHz"), "observação": "camada E normal"},
            {"item": "foEs", "valor": fmt_unit(get_value(p, "foEs"), "MHz"), "observação": "E esporádica; valores baixos não indicam 6m"},
            {"item": "MUF(3000) ref.", "valor": fmt_unit(cm["ref"], "MHz"), "observação": f"campo SAO: {fmt_unit(cm['field'], 'MHz')}"},
            {"item": "TEC", "valor": fmt_unit(get_value(p, "TEC"), "TECU"), "observação": "informação complementar; não decide banda sozinho"},
        ]
        self._insert_rows(self.summary_tree, summary_rows)
        self._insert_rows(self.band_tree, band_status(p))

        freq_rows = []
        for key, label in [
            ("foF2", "F2 vertical"), ("foF1", "F1 vertical"), ("foF1p", "F1 prevista"),
            ("foE", "E normal"), ("foEp", "E prevista"), ("foEs", "E esporádica"),
            ("fxI", "máximo traço F"), ("fmin", "menor frequência com eco"),
            ("fminF", "fminF"), ("fminE", "fminE"), ("fminEs", "fminEs"),
        ]:
            unit = FIELD_META.get(key, ("", ""))[0]
            freq_rows.append({"sigla": DISPLAY_NAMES.get(key, key), "valor": fmt_num(get_value(p, key)), "unidade": unit, "leitura": label})
        self._insert_rows(self.freq_tree, freq_rows)

        alt_rows = []
        for key, label in [
            ("hF", "altura virtual F"), ("hF2", "altura virtual F2"), ("hE", "altura virtual E"),
            ("hEs", "altura virtual Es"), ("hmF2", "pico real/modelado F2"),
            ("hmF1", "pico real/modelado F1"), ("hmE", "pico/modelo E"),
            ("hMUF", "altura MUF auxiliar"), ("hEa", "hEa"), ("hP", "hP"),
        ]:
            unit = FIELD_META.get(key, ("km", ""))[0]
            alt_rows.append({"sigla": DISPLAY_NAMES.get(key, key), "valor": fmt_num(get_value(p, key)), "unidade": unit, "leitura": label})
        self._insert_rows(self.alt_tree, alt_rows)

        muf_rows = [
            {"sigla": "M(3000)F2", "valor": fmt_num(cm["m"]), "unidade": "", "leitura": "fator M(3000)F2"},
            {"sigla": "MUF(3000) campo SAO", "valor": fmt_num(cm["field"]), "unidade": "MHz", "leitura": "campo direto do Grupo 4"},
            {"sigla": "MUF(3000) calculado", "valor": fmt_num(cm["calc"]), "unidade": "MHz", "leitura": "foF2 × M(3000)F2"},
            {"sigla": "diferença calc - campo", "valor": fmt_num(cm["diff"]), "unidade": "MHz", "leitura": f"{fmt_num(cm['pct'])} %" if cm["pct"] is not None else "sem dado"},
        ]
        for key in ["D", "fMUF", "hMUF", "delta_foF2", "yF2", "yF1", "yE", "zhalfNm", "scaleF2", "B0", "B1", "D1", "TEC"]:
            unit, label = FIELD_META.get(key, ("", key))
            muf_rows.append({"sigla": DISPLAY_NAMES.get(key, key), "valor": fmt_num(get_value(p, key)), "unidade": unit, "leitura": label})
        self._insert_rows(self.muf_tree, muf_rows)
        self._insert_rows(self.muf_dist_tree, estimated_muf_by_distance(p))

        group4_rows = []
        for i, (key, unit, label) in enumerate(GROUP4_FIELDS):
            v = p.scaled.get(key)
            raw_v = p.raw_group4[i] if i < len(p.raw_group4) else None
            val = fmt_num(v) if v is not None else f"sem dado (raw {fmt_num(raw_v)})" if raw_v is not None else "sem dado"
            group4_rows.append({
                "posição": i + 1,
                "sigla": DISPLAY_NAMES.get(key, key),
                "valor": val,
                "unidade": unit,
                "leitura": label,
            })
        self._insert_rows(self.group4_tree, group4_rows)

        self._insert_rows(self.trend_tree, trend_rows(parsed_pairs))

        tech_rows = [
            {"item": "fonte", "valor": "servidor INPE/Embrace online" if source == "remote" else "arquivos locais"},
            {"item": "modo", "valor": "dinâmico; lista o diretório remoto e baixa o último .SAO disponível a cada execução" if source == "remote" else "local; lê arquivos .SAO da pasta selecionada"},
            {"item": "estação", "valor": p.station or self.station_var.get().strip().upper()},
            {"item": "nome", "valor": p.station_name or ""},
            {"item": "base_url", "valor": BASE_URL_DEFAULT},
            {"item": "dias_pesquisados", "valor": f"hoje + {DAYS_BACK_DEFAULT} dia(s) para trás" if source == "remote" else "não aplicável"},
            {"item": "arquivos_analisados", "valor": len(parsed_pairs)},
            {"item": "arquivo_mais_recente", "valor": item.filename},
            {"item": "timestamp_arquivo_utc", "valor": item.timestamp_utc.isoformat()},
            {"item": "timestamp_sao_utc", "valor": ts.isoformat() if ts else "sem dado"},
            {"item": "idade_do_dado", "valor": f"{age_min} min" if source == "remote" else "não aplicável"},
            {"item": "hora_execução_utc", "valor": datetime.now(UTC).isoformat()},
            {"item": "url", "valor": item.url or item.path or ""},
            {"item": "descrição do sistema", "valor": p.system_description},
            {"item": "observação", "valor": "ao vivo aqui significa o último ionograma publicado no servidor, não uma medição instantânea em tempo real" if source == "remote" else "leitura baseada em arquivo local"},
        ]
        self._insert_rows(self.tech_tree, tech_rows)

    def copy_summary(self):
        if not self.current_main:
            messagebox.showinfo("Copiar resumo", "Nenhum dado carregado.")
            return
        item, p = self.current_main
        cm = calc_muf(p)
        lines = [
            "Ionosfera SAO - resumo",
            f"Estação: {p.station or ''} {p.station_name or ''}".strip(),
            f"Ionograma: {item.timestamp_utc.isoformat()}",
            f"foF2: {fmt_unit(get_value(p, 'foF2'), 'MHz')}",
            f"fmin: {fmt_unit(get_value(p, 'fmin'), 'MHz')}",
            f"foE: {fmt_unit(get_value(p, 'foE'), 'MHz')}",
            f"foEs: {fmt_unit(get_value(p, 'foEs'), 'MHz')}",
            f"MUF(3000) ref.: {fmt_unit(cm['ref'], 'MHz')} (campo SAO: {fmt_unit(cm['field'], 'MHz')})",
            "",
            "Bandas:",
        ]
        for row in band_status(p):
            lines.append(f"- {row['banda']} ({row['ref.']}): {row['status simples']} — {row['base']}")
        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("Resumo copiado para a área de transferência.")

    def export_csv(self):
        if not self.current_main:
            messagebox.showinfo("Exportar CSV", "Nenhum dado carregado.")
            return
        filename = filedialog.asksaveasfilename(
            title="Salvar dados em CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if not filename:
            return
        item, p = self.current_main
        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["arquivo", item.filename])
                w.writerow(["timestamp_utc", item.timestamp_utc.isoformat()])
                w.writerow([])
                w.writerow(["posicao", "sigla", "valor", "unidade", "leitura"])
                for i, (key, unit, label) in enumerate(GROUP4_FIELDS):
                    w.writerow([i+1, DISPLAY_NAMES.get(key, key), fmt_num(p.scaled.get(key)), unit, label])
            self.status_var.set(f"CSV salvo: {filename}")
        except Exception as e:
            messagebox.showerror("Erro ao salvar", str(e))


def main():
    app = IonosferaApp()
    app.mainloop()


if __name__ == "__main__":
    main()
