from typing import Any, Optional


class PivotFormatter:
    @staticmethod
    def format_value(value: Any, aggregation: str) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "Sim" if value else "Nao"
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        if aggregation in {"count", "unique"}:
            try:
                return str(int(round(float(value))))
            except Exception:
                return str(value)
        if isinstance(value, float):
            rounded = round(value, 2)
            if rounded.is_integer():
                return str(int(rounded))
            return f"{rounded:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return str(value)

    @staticmethod
    def format_percent(value: Optional[float]) -> str:
        if value is None:
            return ""
        return f"{value * 100:.1f}%"

    @staticmethod
    def format_header_tuple(values: tuple) -> str:
        if not values:
            return "Total"
        parts = []
        for value in values:
            if value in (None, ""):
                parts.append("Sem valor")
            else:
                parts.append(str(value))
        return " / ".join(parts)
