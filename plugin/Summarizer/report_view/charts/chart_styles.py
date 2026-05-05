from __future__ import annotations

ANIMATION_DURATIONS_MS = {
    "hover": 185,
    "selection": 200,
    "filter": 300,
    "data": 320,
    "entry": 360,
    "type": 390,
}

ANIMATION_INTENSITY_MULTIPLIERS = {
    "normal": 1.0,
    "reduced": 0.72,
    "off": 0.0,
}

TYPE_LABELS = {
    "bar": "Barras",
    "barh": "Barras horizontais",
    "pie": "Pizza",
    "donut": "Rosca",
    "line": "Linha",
    "area": "Área",
    "card": "Card",
    "matrix": "Matrix",
    "slicer": "Slicer",
    "column_clustered": "Coluna agrupada",
    "column_stacked": "Coluna empilhada",
    "bar100_stacked": "Barra 100% empilhada",
    "combo": "Combo",
    "scatter": "Scatter / bolha",
    "treemap": "Treemap",
    "gauge": "Gauge",
    "kpi": "KPI",
    "waterfall": "Waterfall",
    "funnel": "Funnel",
}

TYPE_GROUPS = [
    ("Comparação", ["barh", "column_stacked", "bar100_stacked"]),
    ("Tendência", ["line", "area"]),
    ("Composição", ["pie", "donut", "treemap", "waterfall"]),
    ("Indicadores", ["kpi", "gauge"]),
    ("Análise", ["funnel"]),
]

TYPE_PRIORITY = ["card", "matrix", "slicer", "column_clustered", "combo", "scatter"]

PALETTE_LABELS = {
    "default": "Paleta padrão",
    "single": "Cor única",
    "category": "Cores por categoria",
    "purple": "Paleta roxa",
    "blue": "Paleta azul",
    "teal": "Paleta teal",
    "sunset": "Paleta sunset",
    "grayscale": "Paleta cinza",
}

SORT_LABELS = {
    "default": "Ordem padrão",
    "asc": "Ordenar crescente",
    "desc": "Ordenar decrescente",
}

FONT_SCALE_PRESETS = [
    (0.82, "Pequena"),
    (1.0, "Normal"),
    (1.18, "Grande"),
    (1.38, "Ampliada"),
]

MAX_PIE_SLICES = 8
MAX_RENDER_ITEMS = 160
MAX_LABELS = 14
