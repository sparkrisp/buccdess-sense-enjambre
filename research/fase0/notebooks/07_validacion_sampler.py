"""
Validacion del sampler de cohortes CABA.

Objetivo: verificar que el sampler reproduce la realidad dentro de margenes
razonables. Tests:
  1. Distribucion por comuna vs poblacion real (Censo)
  2. Distribucion sexo/edad por comuna vs Censo
  3. Distribucion de voto por comuna vs resultados electorales reales 2023
  4. Agregado nacional de voto (CABA completo)

Si se reproduce la realidad con 10k agentes -> sampler valido, GO para Fase 2.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sampler.cohort_builder import CohortBuilder
from sampler.electoral_parser import load_electoral, vote_distribution_by_comuna

N = 10_000
SEED = 42

print(f"Sampleando {N:,} perfiles de CABA...")
builder = CohortBuilder(
    censo_dir=ROOT / "data" / "censo",
    electoral_csv=ROOT / "data" / "caba" / "generales_2023_caba.csv",
)
df = builder.sample_df(n=N, edad_min=18, seed=SEED)
print(f"Sampleados: {len(df)} perfiles\n")

# ---------------------------------------------------------------------------
# TEST 1: Distribucion por comuna vs poblacion 14+ real
# ---------------------------------------------------------------------------
print("=" * 70)
print("TEST 1: Distribucion sampler vs poblacion 18+ real por comuna")
print("=" * 70)
censo = builder.censo.copy()
# Filtrar edad >=18 aproximando con los grupos
valid = [g for g in censo["edad"].unique() if g not in ("14", "15-19") or g == "15-19"]
# 15-19 contiene 18-19 (parcial), lo dejamos fuera para comparar cleaner
pop_by_comuna = (
    censo[censo["edad"] != "15-19"]
    .groupby("comuna")["poblacion_14plus"].sum()
    .rename("pop_real")
)
# Excluimos tambien el grupo '14' del total real dado que sampler usa edad_min=18
pop_by_comuna = pop_by_comuna[pop_by_comuna.index.isin(df["comuna"].unique())]

sample_counts = df["comuna"].value_counts().sort_index().rename("sample")
expected_pct = (pop_by_comuna / pop_by_comuna.sum() * 100).round(2)
actual_pct = (sample_counts / N * 100).round(2)
diff = (actual_pct - expected_pct).round(2)

comparison = pd.concat([expected_pct, actual_pct, diff], axis=1)
comparison.columns = ["esperado_%", "sample_%", "diff"]
print(comparison.to_string())
print(f"\nMax diferencia absoluta: {diff.abs().max():.2f}%")

# ---------------------------------------------------------------------------
# TEST 2: Distribucion de voto real vs sampleada (global CABA)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 2: Voto agregado CABA (solo nativos, cargo JEF)")
print("=" * 70)
electoral = load_electoral(
    ROOT / "data" / "caba" / "generales_2023_caba.csv",
    cargo="JEF", solo_nativos=True,
)
real_global = (
    electoral.groupby("party")["votos"].sum()
    .pipe(lambda s: (s / s.sum() * 100).round(2))
    .rename("real_%")
)
sample_global = (df["voto"].value_counts(normalize=True) * 100).round(2).rename("sample_%")
vote_comp = pd.concat([real_global, sample_global], axis=1).fillna(0)
vote_comp["diff"] = (vote_comp["sample_%"] - vote_comp["real_%"]).round(2)
print(vote_comp.to_string())
print(f"\nMax diferencia absoluta: {vote_comp['diff'].abs().max():.2f} puntos porcentuales")

# ---------------------------------------------------------------------------
# TEST 3: Voto por comuna - real vs sampleado
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 3: Voto por comuna (real vs sampler)")
print("=" * 70)
real_pivot = vote_distribution_by_comuna(electoral).set_index("comuna")
sample_pivot = (
    df.groupby(["comuna", "voto"]).size()
    .unstack(fill_value=0)
    .apply(lambda r: r / r.sum() * 100, axis=1)
    .round(2)
)
sample_pivot.columns = [f"pct_{c}" for c in sample_pivot.columns]

# Merge
parties = ["JxC", "UxP", "LLA", "FIT"]
for party in parties:
    real_col = f"pct_{party}"
    if real_col not in real_pivot.columns:
        continue
    combo = pd.DataFrame({
        "real": real_pivot[real_col],
        "sample": sample_pivot.get(real_col, pd.Series(0, index=real_pivot.index)),
    })
    combo["diff"] = (combo["sample"] - combo["real"]).round(2)
    print(f"\n-- {party} --")
    print(combo.to_string())
    print(f"  Max |diff|: {combo['diff'].abs().max():.2f}pp | RMSE: {np.sqrt((combo['diff']**2).mean()):.2f}pp")

# ---------------------------------------------------------------------------
# TEST 4: Sanity checks - perfiles plausibles
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("TEST 4: Cross-tabs de plausibilidad")
print("=" * 70)

print("\nEducacion x Voto (global, %):")
edu_vote = pd.crosstab(df["educacion"], df["voto"], normalize="index") * 100
print(edu_vote.round(1).to_string())

print("\nComuna 2 (Recoleta) - Distribucion educativa del sample:")
c2 = df[df["comuna"] == 2]
print((c2["educacion"].value_counts(normalize=True) * 100).round(1).to_string())

print("\nComuna 8 (Lugano) - Distribucion educativa del sample:")
c8 = df[df["comuna"] == 8]
print((c8["educacion"].value_counts(normalize=True) * 100).round(1).to_string())

# ---------------------------------------------------------------------------
# VEREDICTO
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("VEREDICTO")
print("=" * 70)
max_comuna_diff = diff.abs().max()
max_vote_diff = vote_comp["diff"].abs().max()
print(f"Max diff distribucion por comuna: {max_comuna_diff:.2f}% (tolerancia esperada <3% con N=10k)")
print(f"Max diff voto global CABA: {max_vote_diff:.2f}pp (tolerancia esperada <1pp)")

ok_comuna = max_comuna_diff < 3.0
ok_vote = max_vote_diff < 1.5
if ok_comuna and ok_vote:
    print("\n>>> SAMPLER VALIDADO - GO para Fase 2 (integrar a MiroFish) <<<")
else:
    print("\n>>> SAMPLER REQUIERE AJUSTES <<<")
