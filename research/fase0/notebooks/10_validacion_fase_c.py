"""
Validacion Fase C - Ecological Inference vs baseline.

Comparar sampler sin EI (solo P(voto|comuna)) vs con EI (P(voto|comuna,edu,edad,sexo)).

Tests:
  1. Agregado global CABA: ambos deben seguir reproduciendo el resultado real.
  2. Agregado por comuna: ambos deben preservar la marginal comunal.
  3. Crosstab educacion x voto: EI debe mostrar MAYOR senal.
  4. Sample de casos concretos: ver si los individuos tienen predicciones
     mas coherentes con su perfil.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sampler.cohort_builder import CohortBuilder
from sampler.electoral_parser import load_electoral

N = 20_000
SEED = 42

print(f"Sampleando {N} perfiles con y sin Ecological Inference (seed={SEED})...")
builder_plain = CohortBuilder(
    censo_dir=ROOT / "data" / "censo",
    electoral_csv=ROOT / "data" / "caba" / "generales_2023_caba.csv",
    use_ecological_inference=False,
)
builder_eco = CohortBuilder(
    censo_dir=ROOT / "data" / "censo",
    electoral_csv=ROOT / "data" / "caba" / "generales_2023_caba.csv",
    use_ecological_inference=True,
)

df_plain = builder_plain.sample_df(n=N, edad_min=18, seed=SEED)
df_eco = builder_eco.sample_df(n=N, edad_min=18, seed=SEED)

electoral = load_electoral(
    ROOT / "data" / "caba" / "generales_2023_caba.csv",
    cargo="JEF", solo_nativos=True,
)

# ---------------------------------------------------------------------------
# TEST 1: Agregado global (ambos deben matchear real)
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("TEST 1: Voto global CABA (sample vs real)")
print("=" * 72)
real_global = (electoral.groupby("party")["votos"].sum()
               .pipe(lambda s: (s / s.sum() * 100).round(2)))
plain_global = (df_plain["voto"].value_counts(normalize=True) * 100).round(2)
eco_global = (df_eco["voto"].value_counts(normalize=True) * 100).round(2)

comp = pd.DataFrame({"real": real_global, "sin_EI": plain_global, "con_EI": eco_global}).fillna(0)
comp["diff_sin_EI"] = (comp["sin_EI"] - comp["real"]).round(2)
comp["diff_con_EI"] = (comp["con_EI"] - comp["real"]).round(2)
print(comp.to_string())
print(f"\nMax diff sin EI: {comp['diff_sin_EI'].abs().max():.2f}pp")
print(f"Max diff con EI: {comp['diff_con_EI'].abs().max():.2f}pp")

# ---------------------------------------------------------------------------
# TEST 2: Por comuna
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("TEST 2: RMSE por comuna (ambos deben preservar marginal comunal)")
print("=" * 72)
from sampler.electoral_parser import vote_distribution_by_comuna
real_pivot = vote_distribution_by_comuna(electoral).set_index("comuna")
for which, df in [("sin_EI", df_plain), ("con_EI", df_eco)]:
    sample_pivot = (df.groupby(["comuna", "voto"]).size()
                     .unstack(fill_value=0)
                     .apply(lambda r: r / r.sum() * 100, axis=1))
    rmses = []
    for p in ["JxC", "UxP", "LLA", "FIT"]:
        real_col = f"pct_{p}"
        real = real_pivot[real_col]
        samp = sample_pivot.get(p, pd.Series(0, index=real_pivot.index))
        rmse = np.sqrt(((samp - real) ** 2).mean())
        rmses.append((p, rmse))
    print(f"  {which}: ", " | ".join(f"{p}:{r:.2f}pp" for p, r in rmses))

# ---------------------------------------------------------------------------
# TEST 3: Crosstab educacion x voto (aca EI deberia mostrar mas senal)
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("TEST 3: Crosstab educacion x voto (% de cada edu que vota a cada party)")
print("=" * 72)
print("\n-- SIN EI (solo baseline comunal, sin correccion individual) --")
ct_plain = pd.crosstab(df_plain["educacion"], df_plain["voto"], normalize="index") * 100
print(ct_plain.round(1).to_string())

print("\n-- CON EI (corregido por uni + 65plus) --")
ct_eco = pd.crosstab(df_eco["educacion"], df_eco["voto"], normalize="index") * 100
print(ct_eco.round(1).to_string())

# Spread = diferencia max-min de JxC% entre niveles educativos
spread_plain = ct_plain["JxC"].max() - ct_plain["JxC"].min()
spread_eco = ct_eco["JxC"].max() - ct_eco["JxC"].min()
print(f"\nSpread JxC% entre niveles educativos:")
print(f"  sin EI: {spread_plain:.1f}pp")
print(f"  con EI: {spread_eco:.1f}pp  (mayor = mejor senal individual)")

# ---------------------------------------------------------------------------
# TEST 4: Crosstab edad x voto
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("TEST 4: 65+ anios vs resto (% voto por grupo)")
print("=" * 72)

OLD = {"65-69", "70-74", "75-79", "80+"}
for which, df in [("sin_EI", df_plain), ("con_EI", df_eco)]:
    df2 = df.copy()
    df2["edad_grupo"] = df2["edad"].map(lambda e: "65+" if e in OLD else "<65")
    ct = pd.crosstab(df2["edad_grupo"], df2["voto"], normalize="index") * 100
    print(f"\n-- {which} --")
    print(ct.round(1).to_string())

# ---------------------------------------------------------------------------
# TEST 5: Universitaria Recoleta vs Sin instruccion Lugano
# ---------------------------------------------------------------------------
print("\n" + "=" * 72)
print("TEST 5: Casos borde - distribucion entre individuos con perfiles opuestos")
print("=" * 72)

def case_votes(df, comuna, edu):
    sub = df[(df["comuna"] == comuna) & (df["educacion"] == edu)]
    if len(sub) == 0:
        return {}
    return (sub["voto"].value_counts(normalize=True) * 100).round(1).to_dict()

print("\nUniversitarios de Recoleta (C2):")
print(f"  sin EI: {case_votes(df_plain, 2, 'universitario')}")
print(f"  con EI: {case_votes(df_eco, 2, 'universitario')}")

print("\nSin instruccion de Lugano (C8):")
print(f"  sin EI: {case_votes(df_plain, 8, 'ninguno')}")
print(f"  con EI: {case_votes(df_eco, 8, 'ninguno')}")
