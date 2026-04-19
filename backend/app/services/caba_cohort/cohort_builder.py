"""
Cohort builder: samplea perfiles sinteticos con distribucion REAL de CABA.

Algoritmo (MVP, asume independencia condicional para educacion y actividad):
  1. Sampleo conjunto comuna x sexo x edad con pesos = poblacion_14plus
  2. Condicional a (comuna, sexo, edad) sampleo actividad (ocupada/desocupada/inactiva)
  3. Condicional a (comuna, sexo, edad) sampleo educacion (5 niveles)
  4. Condicional a comuna sampleo voto (4 agrupaciones + abstencion implicita)

Limitaciones MVP:
  - Asume independencia entre educacion y actividad dado (comuna, sexo, edad).
    En realidad estan correlacionadas (universitarios se ocupan mas). Fase 2
    podria usar actividad_economica_c10 que cruza ambas.
  - Voto condicional solo a comuna, no a (comuna, educacion). Hace ecological
    inference implicita via sampleo demografico pero no modela la correlacion
    educacion-voto explicitamente. Fase 2 podria ajustar con regresion.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .censo_parser import load_censo_master, AGE_GROUPS_14PLUS
from .electoral_parser import load_electoral
from .ecological_inference import fit_ecological_model, EcologicalModel


ACTIVIDADES = ["ocupada", "desocupada", "inactiva"]
EDU_LEVELS = ["ninguno", "primario", "secundario", "terciario", "universitario"]


@dataclass
class Perfil:
    id: int
    comuna: int
    sexo: str
    edad: str
    actividad: str  # 'ocupada' | 'desocupada' | 'inactiva'
    educacion: str  # EDU_LEVELS
    voto: str       # 'UxP' | 'JxC' | 'LLA' | 'FIT'


class CohortBuilder:
    """Construye cohortes sinteticas de CABA a partir de datos publicos."""

    def __init__(
        self,
        censo_dir: Path,
        electoral_csv: Path,
        cargo: str = "JEF",
        use_ecological_inference: bool = False,
    ):
        self.censo = load_censo_master(censo_dir)
        self.electoral = load_electoral(electoral_csv, cargo=cargo, solo_nativos=True)
        self.use_ecological_inference = use_ecological_inference
        self._eco_model: EcologicalModel | None = None
        self._prepare()
        if use_ecological_inference:
            self._eco_model = fit_ecological_model(self.censo, self.electoral)

    def _prepare(self):
        """Precomputar distribuciones normalizadas."""
        df = self.censo.copy()

        df["tot_edu"] = df[EDU_LEVELS].sum(axis=1)

        # Distribucion actividad condicional a (comuna, sexo, edad)
        df["act_total"] = df["ocupada"] + df["desocupada"] + df["pnea"]
        df["p_ocupada"] = df["ocupada"] / df["act_total"].where(df["act_total"] > 0, 1)
        df["p_desocupada"] = df["desocupada"] / df["act_total"].where(df["act_total"] > 0, 1)
        df["p_inactiva"] = df["pnea"] / df["act_total"].where(df["act_total"] > 0, 1)

        # Distribucion educacion condicional a (comuna, sexo, edad).
        # Cuando tot_edu == 0 (ej: grupo '14' que solo esta en actividad), usamos
        # distribucion uniforme como fallback.
        uniform = 1.0 / len(EDU_LEVELS)
        for lvl in EDU_LEVELS:
            p = df[lvl] / df["tot_edu"].where(df["tot_edu"] > 0, np.nan)
            df[f"p_{lvl}"] = p.fillna(uniform)

        self._cells = df  # cada fila es una celda (comuna, sexo, edad) con sus probabilidades

        # Distribucion de voto por comuna (normalizada sobre votantes positivos)
        vote_pivot = self.electoral.pivot_table(
            index="comuna", columns="party", values="pct", aggfunc="first"
        ).fillna(0.0)
        # Normalizar a sumar 1
        self._vote_probs = vote_pivot.div(vote_pivot.sum(axis=1), axis=0)

    def _pick(self, probs: np.ndarray, labels: list[str], rng: np.random.Generator) -> str:
        """Samplear un label con probs (deben sumar ~1)."""
        probs = np.asarray(probs, dtype=float)
        s = probs.sum()
        if s == 0:
            return labels[0]
        probs = probs / s
        return rng.choice(labels, p=probs)

    def sample(
        self,
        n: int,
        comuna: Optional[int | list[int]] = None,
        edad_min: Optional[int] = None,
        edad_max: Optional[int] = None,
        sexo: Optional[str] = None,
        actividad: Optional[str | list[str]] = None,
        educacion: Optional[str | list[str]] = None,
        seed: Optional[int] = None,
    ) -> list[Perfil]:
        """
        Samplear n perfiles con filtros demograficos opcionales.

        Args:
            n: Cantidad de perfiles.
            comuna: Filtro geografico (int o list).
            edad_min/edad_max: Rango etario (grupos quinquenales que caen dentro).
            sexo: 'F' o 'M'.
            actividad/educacion: post-sample filter sobre atributos sampleados.
            seed: Reproducibilidad.
        """
        rng = np.random.default_rng(seed)
        cells = self._cells.copy()

        if comuna is not None:
            if isinstance(comuna, int):
                comuna = [comuna]
            cells = cells[cells["comuna"].isin(comuna)]

        if sexo is not None:
            cells = cells[cells["sexo"] == sexo]

        def age_lower(g: str) -> int:
            if g == "80+":
                return 80
            if "-" in g:
                return int(g.split("-")[0])
            return int(g)

        def age_upper(g: str) -> int:
            if g == "80+":
                return 100
            if "-" in g:
                return int(g.split("-")[1])
            return int(g)

        if edad_min is not None:
            cells = cells[cells["edad"].apply(lambda g: age_lower(g) >= edad_min)]
        if edad_max is not None:
            cells = cells[cells["edad"].apply(lambda g: age_upper(g) <= edad_max)]

        if cells.empty:
            raise ValueError("No hay celdas demograficas despues de aplicar filtros")

        # Paso 1: sample de celda (comuna, sexo, edad) ponderado por poblacion_14plus
        weights = cells["poblacion_14plus"].to_numpy(dtype=float)
        weights = weights / weights.sum()
        cell_idx = rng.choice(len(cells), size=n, p=weights)

        perfiles: list[Perfil] = []
        for i, idx in enumerate(cell_idx):
            row = cells.iloc[idx]
            c = int(row["comuna"])

            # Paso 2: actividad
            act = self._pick(
                [row["p_ocupada"], row["p_desocupada"], row["p_inactiva"]],
                ACTIVIDADES, rng,
            )
            # Paso 3: educacion
            edu = self._pick(
                [row[f"p_{lvl}"] for lvl in EDU_LEVELS],
                EDU_LEVELS, rng,
            )
            # Paso 4: voto
            if self._eco_model is not None:
                # Ajustado a (comuna, edu, edad, sexo) via Ecological Inference
                probs_eco = self._eco_model.predict(
                    comuna=c,
                    edad=str(row["edad"]),
                    sexo=str(row["sexo"]),
                    educacion=edu,
                )
                labels = list(probs_eco.keys())
                voto = self._pick([probs_eco[p] for p in labels], labels, rng)
            else:
                # Fallback: solo condicional a comuna
                vote_row = self._vote_probs.loc[c]
                voto = self._pick(vote_row.to_numpy(), list(vote_row.index), rng)

            perfiles.append(
                Perfil(
                    id=i,
                    comuna=c,
                    sexo=str(row["sexo"]),
                    edad=str(row["edad"]),
                    actividad=act,
                    educacion=edu,
                    voto=voto,
                )
            )

        # Post-sample filters sobre actividad/educacion (se podrian hacer mejor
        # via rejection sampling previo, pero asi es mas simple y trazable)
        if actividad is not None:
            needed = {actividad} if isinstance(actividad, str) else set(actividad)
            perfiles = [p for p in perfiles if p.actividad in needed]
        if educacion is not None:
            needed = {educacion} if isinstance(educacion, str) else set(educacion)
            perfiles = [p for p in perfiles if p.educacion in needed]

        # Re-id post-filter
        for i, p in enumerate(perfiles):
            p.id = i

        return perfiles

    def sample_df(self, n: int, **kwargs) -> pd.DataFrame:
        """Wrapper que devuelve DataFrame."""
        return pd.DataFrame([asdict(p) for p in self.sample(n, **kwargs)])


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    root = Path(__file__).resolve().parents[1]
    builder = CohortBuilder(
        censo_dir=root / "data" / "censo",
        electoral_csv=root / "data" / "caba" / "generales_2023_caba.csv",
        cargo="JEF",
    )

    # Sampleo 1000 agentes de CABA completa
    df = builder.sample_df(n=1000, edad_min=18, seed=42)

    print(f"Sample: {len(df)} perfiles")
    print("\n=== DISTRIBUCION POR COMUNA ===")
    print(df["comuna"].value_counts().sort_index().to_string())

    print("\n=== VOTO (global) ===")
    print((df["voto"].value_counts(normalize=True) * 100).round(1).to_string())

    print("\n=== EDUCACION ===")
    print((df["educacion"].value_counts(normalize=True) * 100).round(1).to_string())

    print("\n=== ACTIVIDAD ===")
    print((df["actividad"].value_counts(normalize=True) * 100).round(1).to_string())

    print("\n=== MUESTRA ===")
    print(df.head(12).to_string(index=False))
