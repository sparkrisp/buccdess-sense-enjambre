"""
Fase 0 — Exploración inicial: Generales 2023 CABA
Validar granularidad, completitud y shape de los datos electorales oficiales.
"""
import pandas as pd
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "caba"

df = pd.read_csv(DATA / "generales_2023_caba.csv", sep=";", encoding="utf-8")

print("=" * 70)
print("SHAPE Y MEMORIA")
print("=" * 70)
print(f"Filas: {len(df):,} | Columnas: {len(df.columns)}")
print(f"Memoria: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
print(f"Columnas: {list(df.columns)}")

print("\n" + "=" * 70)
print("CARGOS ELECTIVOS")
print("=" * 70)
print(df["cargo_nombre"].value_counts())

print("\n" + "=" * 70)
print("COMUNAS (secciones)")
print("=" * 70)
print(df["seccion_nombre"].value_counts().sort_index())

print("\n" + "=" * 70)
print("GRANULARIDAD: conteos unicos por nivel")
print("=" * 70)
print(f"Secciones (comunas): {df['seccion_id'].nunique()}")
print(f"Circuitos:           {df['circuito_id'].nunique()}")
print(f"Mesas:               {df['mesa_id'].nunique()}")

print("\n" + "=" * 70)
print("AGRUPACIONES POLITICAS (Jefe de Gobierno)")
print("=" * 70)
jef = df[df["cargo_nombre"] == "JEF"]
print(jef["agrupacion_nombre"].value_counts())

print("\n" + "=" * 70)
print("TIPOS DE VOTO")
print("=" * 70)
print(df["votos_tipo"].value_counts())

print("\n" + "=" * 70)
print("TIPOS DE MESA")
print("=" * 70)
print(df["mesa_tipo"].value_counts())

print("\n" + "=" * 70)
print("SAMPLE DE FILAS")
print("=" * 70)
print(df.head(10).to_string())

print("\n" + "=" * 70)
print("RESULTADOS AGREGADOS POR COMUNA (Jefe de Gobierno, votos POSITIVOS)")
print("=" * 70)
jef_pos = df[(df["cargo_nombre"] == "JEF") & (df["votos_tipo"] == "POSITIVO")]
pivot = (
    jef_pos.groupby(["seccion_nombre", "agrupacion_nombre"])["votos_cantidad"]
    .sum()
    .unstack(fill_value=0)
)
pivot["TOTAL"] = pivot.sum(axis=1)
for col in pivot.columns[:-1]:
    pivot[f"{col}_%"] = (pivot[col] / pivot["TOTAL"] * 100).round(1)
print(pivot.iloc[:, -len(pivot.columns) // 2 :].to_string())
