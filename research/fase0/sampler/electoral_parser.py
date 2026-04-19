"""
Parser del CSV electoral 2023 CABA (data.buenosaires.gob.ar).

Devuelve distribucion de voto condicional por comuna: dada una comuna,
probabilidad de votar cada agrupacion (solo votos positivos, descartando
blanco/nulo/impugnado).
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd


# Mapeo corto para los nombres de agrupaciones (el CSV los trae en mayusculas)
PARTY_SHORT = {
    "UNION POR LA PATRIA": "UxP",
    "JUNTOS POR EL CAMBIO": "JxC",
    "LA LIBERTAD AVANZA": "LLA",
    "FRENTE DE IZQUIERDA Y DE TRABAJADORES - UNIDAD": "FIT",
}


def load_electoral(
    path: Path,
    cargo: str = "JEF",
    solo_nativos: bool = True,
) -> pd.DataFrame:
    """
    Leer CSV electoral y devolver DataFrame con votos positivos agrupados.

    Args:
        path: Ruta al CSV.
        cargo: 'JEF' (Jefe Gob), 'LEG' (Legisladores), 'COM' (Junta Comunal).
        solo_nativos: Si True, excluye mesas de extranjeros (que solo votan
            cargos locales y distorsionan comparaciones con poblacion general).

    Returns:
        DataFrame con columnas: comuna, agrupacion, party, votos, total_positivos, pct.
    """
    df = pd.read_csv(path, sep=";", encoding="utf-8")
    df = df[(df["cargo_nombre"] == cargo) & (df["votos_tipo"] == "POSITIVO")]
    if solo_nativos:
        df = df[df["mesa_tipo"] == "NATIVOS"]

    agg = (
        df.groupby(["seccion_id", "agrupacion_nombre"])["votos_cantidad"]
        .sum()
        .reset_index()
        .rename(columns={"seccion_id": "comuna", "agrupacion_nombre": "agrupacion", "votos_cantidad": "votos"})
    )
    totals = agg.groupby("comuna")["votos"].sum().rename("total_positivos")
    agg = agg.merge(totals, on="comuna")
    agg["pct"] = (agg["votos"] / agg["total_positivos"] * 100).round(2)
    agg["party"] = agg["agrupacion"].map(PARTY_SHORT).fillna(agg["agrupacion"])
    return agg[["comuna", "agrupacion", "party", "votos", "total_positivos", "pct"]]


def vote_distribution_by_comuna(electoral_df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot: una fila por comuna, columnas por party, valores = pct.
    Util para joinear con perfiles demograficos.
    """
    pivot = electoral_df.pivot_table(
        index="comuna", columns="party", values="pct", aggfunc="first"
    ).fillna(0.0)
    pivot.columns = [f"pct_{c}" for c in pivot.columns]
    return pivot.reset_index()


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    csv_path = Path(__file__).resolve().parents[1] / "data" / "caba" / "generales_2023_caba.csv"
    df = load_electoral(csv_path, cargo="JEF", solo_nativos=True)
    print("Distribucion de voto (cargo=JEF, solo nativos):")
    print(df.head(10).to_string(index=False))

    print("\nPivot por comuna:")
    pivot = vote_distribution_by_comuna(df)
    print(pivot.to_string(index=False))

    print(f"\nTotal de votos positivos agregados: {df['votos'].sum():,}")
