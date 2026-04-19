"""
Ecological Inference (Goodman 1953) para estimar P(voto | demografia).

Problema: tenemos resultados electorales AGREGADOS por comuna y composicion
demografica AGREGADA por comuna. No tenemos microdata individual (nadie
publico "individuo X, universitario, mujer, 30 anios, voto JxC").

Solucion (Goodman ecological regression): para cada party P, ajustar OLS:

    pct_voto_P_comuna = alpha_P + beta_P_uni * share_universitario_comuna
                                 + beta_P_65plus * share_65mas_comuna
                                 + beta_P_female * share_femenino_comuna

Con 15 comunas (datapoints) y 3 predictores, tenemos un modelo simple pero
interpretable. Los betas aproximan el EFECTO MARGINAL ecologico: cuanto
cambia el % de voto a P cuando aumenta 1pp el % de universitarios en la
poblacion (comuna).

Limitaciones conocidas:
- Ecological fallacy: inferencia sobre individuos desde datos agregados puede
  fallar si existe heterogeneidad dentro de comuna.
- 15 comunas son POCAS: R^2 inflado, betas ruidosos en la cola.
- Confundidos: % universitarios correlaciona con % alto ingreso; el modelo
  no puede separarlos.

Lo usamos solo como AJUSTE sobre el baseline P(voto|comuna): el sampler
sigue respetando la distribucion marginal por comuna, pero dentro de cada
comuna ajusta hacia arriba o abajo segun el perfil individual.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


PARTIES = ["UxP", "JxC", "LLA", "FIT"]
EDU_LEVELS = ["ninguno", "primario", "secundario", "terciario", "universitario"]

# Grupos etarios que consideramos "adultos mayores" (desde 65)
OLDER_AGE_GROUPS = {"65-69", "70-74", "75-79", "80+"}


def _age_lower(g: str) -> int:
    if g == "80+":
        return 80
    if "-" in g:
        return int(g.split("-")[0])
    return int(g)


@dataclass
class EcologicalModel:
    """Modelo ecologico ajustado. Permite estimar P(voto|c,edu,sexo,edad)."""

    # Coeficientes: {party: {"intercept": val, "uni": val, "65plus": val, "female": val}}
    coefs: dict[str, dict[str, float]] = field(default_factory=dict)

    # Shares promedio de la comuna (para baseline)
    comuna_shares: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Baseline observado (pct voto real por comuna/party)
    baseline: pd.DataFrame = field(default_factory=pd.DataFrame)

    # R^2 por party
    r_squared: dict[str, float] = field(default_factory=dict)

    # Factor de atenuacion aplicado al shift individual. Los coefs OLS se
    # estiman sobre comunas cuyos shares varian en rango acotado (ej. share_fem
    # solo va de 0.53 a 0.57). Extrapolar a individuos (I=0 o 1) amplifica
    # en exceso. 0.5 atenua el shift al 50% -> deja pasar senal sin destrozar
    # el baseline observado.
    SHIFT_ATTENUATION = 0.5

    def predict(
        self,
        comuna: int,
        edad: str,
        sexo: str,
        educacion: str,
    ) -> dict[str, float]:
        """
        P(voto=p | c, edu, sexo, edad) aproximado.

        Formula:
          1. baseline_p_c = pct observado de voto a p en comuna c.
          2. shift_p = SHIFT_ATTENUATION * Σ_x beta_p_x * (I_x(individuo) - share_x_c).
          3. P = clamp(baseline + shift, 0, 1), luego renormalizar.
        """
        row = self.comuna_shares.loc[comuna]
        ind_uni = 1.0 if educacion == "universitario" else 0.0
        ind_old = 1.0 if edad in OLDER_AGE_GROUPS else 0.0

        probs: dict[str, float] = {}
        for party in PARTIES:
            base = float(self.baseline.loc[comuna, party])
            c = self.coefs[party]
            raw_shift = (
                c["uni"] * (ind_uni - row["share_uni"])
                + c["65plus"] * (ind_old - row["share_65plus"])
            )
            shift = self.SHIFT_ATTENUATION * raw_shift
            probs[party] = max(0.0, min(1.0, base + shift))

        total = sum(probs.values())
        if total == 0:
            return {p: 1.0 / len(PARTIES) for p in PARTIES}
        return {p: v / total for p, v in probs.items()}


def _compute_comuna_shares(censo: pd.DataFrame) -> pd.DataFrame:
    """Calcular shares demograficos por comuna desde el censo master."""
    rows = []
    for c in sorted(censo["comuna"].unique()):
        sub = censo[censo["comuna"] == c]
        pop_14plus = sub["poblacion_14plus"].sum()
        female_pop = sub[sub["sexo"] == "F"]["poblacion_14plus"].sum()
        old_pop = sub[sub["edad"].isin(OLDER_AGE_GROUPS)]["poblacion_14plus"].sum()

        tot_edu = sub[EDU_LEVELS].sum().sum()
        uni_edu = sub["universitario"].sum()

        rows.append({
            "comuna": c,
            "share_female": female_pop / pop_14plus if pop_14plus > 0 else 0.5,
            "share_65plus": old_pop / pop_14plus if pop_14plus > 0 else 0.15,
            "share_uni": uni_edu / tot_edu if tot_edu > 0 else 0.2,
        })
    return pd.DataFrame(rows).set_index("comuna")


def _compute_baseline(electoral: pd.DataFrame) -> pd.DataFrame:
    """% voto por (comuna, party), normalizado a [0, 1]."""
    pivot = electoral.pivot_table(
        index="comuna", columns="party", values="pct", aggfunc="first"
    ).fillna(0.0) / 100.0
    # Re-normalizar por si suma != 1
    return pivot.div(pivot.sum(axis=1), axis=0)


def fit_ecological_model(
    censo: pd.DataFrame,
    electoral: pd.DataFrame,
) -> EcologicalModel:
    """Ajusta el modelo ecologico via OLS por party."""
    shares = _compute_comuna_shares(censo)
    baseline = _compute_baseline(electoral)

    # Solo share_uni y share_65plus como predictores.
    # share_female varia solo de 0.53 a 0.57 entre comunas -> no tiene variacion
    # suficiente para estimar un efecto confiable y infla el coef hasta romper
    # las predicciones individuales. Dropped.
    X = np.column_stack([
        np.ones(len(shares)),
        shares["share_uni"].to_numpy(),
        shares["share_65plus"].to_numpy(),
    ])
    col_names = ["intercept", "uni", "65plus"]

    coefs: dict[str, dict[str, float]] = {}
    r_squared: dict[str, float] = {}

    # Alinear indices (pivot puede tener comunas en distinto orden que shares)
    baseline = baseline.loc[shares.index]

    for party in PARTIES:
        y = baseline[party].to_numpy()
        # OLS cerrado: beta = (X'X)^-1 X'y
        beta, residuals, rank, sv = np.linalg.lstsq(X, y, rcond=None)
        y_pred = X @ beta
        ss_res = float(((y - y_pred) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        coefs[party] = dict(zip(col_names, beta.tolist()))
        r_squared[party] = r2

    return EcologicalModel(
        coefs=coefs,
        comuna_shares=shares,
        baseline=baseline,
        r_squared=r_squared,
    )


def print_model_summary(model: EcologicalModel) -> None:
    """Debug/inspeccion del modelo ajustado."""
    print("=" * 72)
    print("ECOLOGICAL INFERENCE MODEL (Goodman)")
    print("=" * 72)
    print("\nR^2 por party (ajuste en 15 comunas):")
    for p, r2 in model.r_squared.items():
        print(f"  {p}: R^2 = {r2:.3f}")

    print("\nCoeficientes (efecto ecologico marginal):")
    print(f"{'party':<6}{'interc':>10}{'uni':>10}{'65plus':>10}")
    for party, c in model.coefs.items():
        print(
            f"{party:<6}{c['intercept']:>10.3f}{c['uni']:>10.3f}"
            f"{c['65plus']:>10.3f}"
        )

    print("\nShares promedio por comuna (primeras 5):")
    print(model.comuna_shares.head().round(3).to_string())


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    from sampler.censo_parser import load_censo_master
    from sampler.electoral_parser import load_electoral

    root = Path(__file__).resolve().parents[1]
    censo = load_censo_master(root / "data" / "censo")
    electoral = load_electoral(
        root / "data" / "caba" / "generales_2023_caba.csv",
        cargo="JEF", solo_nativos=True,
    )

    model = fit_ecological_model(censo, electoral)
    print_model_summary(model)

    # Ejemplo: universitaria mujer joven de Recoleta vs hombre sin instruccion de Lugano
    print("\n" + "=" * 72)
    print("PREDICCIONES DE EJEMPLO")
    print("=" * 72)

    print("\nMujer universitaria 30 anios de Recoleta (C2):")
    probs = model.predict(comuna=2, edad="30-34", sexo="F", educacion="universitario")
    for p, v in probs.items():
        print(f"  P(voto={p}) = {v:.1%}")

    print("\nHombre sin instruccion 45 anios de Lugano (C8):")
    probs = model.predict(comuna=8, edad="45-49", sexo="M", educacion="ninguno")
    for p, v in probs.items():
        print(f"  P(voto={p}) = {v:.1%}")

    print("\nBaseline comuna 2 (observado):", dict(model.baseline.loc[2].round(3)))
    print("Baseline comuna 8 (observado):", dict(model.baseline.loc[8].round(3)))
