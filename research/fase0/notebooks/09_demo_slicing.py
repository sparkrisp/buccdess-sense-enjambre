"""
Demo slicing: 4 casos de uso reales del sampler CABA.

Cada escenario muestra:
- Medida/evento que se simularia
- Query exacta al sampler
- Composicion resultante (distribucion demografica y electoral)
- Perfiles ejemplo
- Lectura analitica: que cohorte obtuvimos y que predice intuitivamente
"""
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sampler.cohort_builder import CohortBuilder
from sampler.oasis_adapter import perfiles_to_oasis


BAR = "=" * 76
SUB = "-" * 76


def summarize(perfiles, label: str) -> None:
    if not perfiles:
        print(f"  (sin resultados para {label})")
        return
    df = pd.DataFrame([{
        "comuna": p.comuna, "sexo": p.sexo, "edad": p.edad,
        "actividad": p.actividad, "edu": p.educacion, "voto": p.voto,
    } for p in perfiles])
    print(f"  Tamano efectivo: {len(df)} agentes")
    print(f"  Sexo:       {dict((df['sexo'].value_counts(normalize=True)*100).round(1))}")
    print(f"  Voto:       {dict((df['voto'].value_counts(normalize=True)*100).round(1))}")
    print(f"  Educacion:  {dict((df['edu'].value_counts(normalize=True)*100).round(1))}")
    print(f"  Actividad:  {dict((df['actividad'].value_counts(normalize=True)*100).round(1))}")
    top_edad = df["edad"].value_counts().head(3)
    print(f"  Top edades: {dict(top_edad)}")


def show_sample(perfiles, oasis_profiles, n_samples: int = 2) -> None:
    for p, o in list(zip(perfiles, oasis_profiles))[:n_samples]:
        print(f"\n  >>> {o.name} ({o.age}, {o.gender}, Comuna {p.comuna})")
        print(f"      {o.bio}")
        print(f"      voto 2023: {p.voto}")


def main():
    builder = CohortBuilder(
        censo_dir=ROOT / "data" / "censo",
        electoral_csv=ROOT / "data" / "caba" / "generales_2023_caba.csv",
    )

    # -----------------------------------------------------------------
    # ESCENARIO 1: Programa de empleo joven en zonas populares (Comuna 8, 9)
    # -----------------------------------------------------------------
    print("\n" + BAR)
    print("ESCENARIO 1: Programa de empleo joven en zonas populares")
    print(BAR)
    print("Medida simulada:")
    print("  Subsidio del 50% al empleador por 6 meses para contrataciones <35 anios.")
    print("  Apunta a Lugano/Soldati (C8) y Mataderos/Liniers (C9).")
    print(f"\n{SUB}")
    print("Query:  builder.sample(n=500, comuna=[8, 9], edad_min=18, edad_max=35, seed=1)")
    print(SUB)
    perfiles_1 = builder.sample(n=500, comuna=[8, 9], edad_min=18, edad_max=35, seed=1)
    summarize(perfiles_1, "escenario 1")
    oasis_1 = perfiles_to_oasis(perfiles_1, seed=1)
    show_sample(perfiles_1, oasis_1)
    print("\nLectura: cohorte joven de zonas sur, educacion media-baja, mix UxP/LLA fuerte.")
    print("Hipotesis de simulacion: alta receptividad al anuncio, pero escepticismo")
    print("por antecedentes incumplidos; rechazo de segmentos LLA al gasto publico.")

    # -----------------------------------------------------------------
    # ESCENARIO 2: Mensaje pro-seguridad dirigido a universitarios JxC
    # -----------------------------------------------------------------
    print("\n" + BAR)
    print("ESCENARIO 2: Mensaje pro-seguridad a universitarios del norte")
    print(BAR)
    print("Medida simulada:")
    print("  Refuerzo de patrullaje con Gendarmeria en barrios porteños.")
    print("  Apunta a Recoleta (C2), Belgrano (C13), Palermo (C14).")
    print(f"\n{SUB}")
    print("Query:  builder.sample(n=300, comuna=[2,13,14], educacion='universitario', seed=2)")
    print(SUB)
    perfiles_2 = builder.sample(
        n=300, comuna=[2, 13, 14], educacion="universitario", seed=2,
    )
    summarize(perfiles_2, "escenario 2")
    oasis_2 = perfiles_to_oasis(perfiles_2, seed=2)
    show_sample(perfiles_2, oasis_2)
    print("\nLectura: target historico de JxC (clase alta educada del norte). Mayoria")
    print("deberia mostrarse a favor, pero segmento progre-universitario mas joven")
    print("puede objetar la militarizacion.")

    # -----------------------------------------------------------------
    # ESCENARIO 3: Reforma previsional - cohorte jubilada
    # -----------------------------------------------------------------
    print("\n" + BAR)
    print("ESCENARIO 3: Reforma previsional - percepcion de jubilados")
    print(BAR)
    print("Medida simulada:")
    print("  Actualizacion de haberes por inflacion trimestral (vs mensual actual).")
    print("  Apunta a toda CABA, grupo 60-80+.")
    print(f"\n{SUB}")
    print("Query:  builder.sample(n=400, edad_min=60, edad_max=100, seed=3)")
    print(SUB)
    perfiles_3 = builder.sample(n=400, edad_min=60, edad_max=100, seed=3)
    summarize(perfiles_3, "escenario 3")
    oasis_3 = perfiles_to_oasis(perfiles_3, seed=3)
    show_sample(perfiles_3, oasis_3)
    print("\nLectura: cohorte mayor, mix JxC/UxP marcado (JxC mas fuerte que en joven).")
    print("Alta sensibilidad a cualquier alteracion en el mecanismo de actualizacion.")
    print("Predecible: rechazo generalizado, intensidad mayor en UxP.")

    # -----------------------------------------------------------------
    # ESCENARIO 4: Focus mujeres desocupadas (politicas de genero + empleo)
    # -----------------------------------------------------------------
    print("\n" + BAR)
    print("ESCENARIO 4: Focus mujeres desocupadas - politicas activacion laboral")
    print(BAR)
    print("Medida simulada:")
    print("  Anuncio de creditos para emprendedurismo femenino con tasa subsidiada.")
    print(f"\n{SUB}")
    print("Query:  builder.sample(n=200, sexo='F', actividad='desocupada', edad_min=25, edad_max=55, seed=4)")
    print(SUB)
    perfiles_4 = builder.sample(
        n=200, sexo="F", actividad="desocupada", edad_min=25, edad_max=55, seed=4,
    )
    summarize(perfiles_4, "escenario 4")
    oasis_4 = perfiles_to_oasis(perfiles_4, seed=4)
    show_sample(perfiles_4, oasis_4)
    print("\nLectura: muestra chica y dispersa geograficamente (desocupacion femenina")
    print("25-55 no es dominante en CABA). Fuerte sesgo hacia zonas populares.")
    print("Probable reaccion mixta: interes por la oportunidad + dudas por la letra chica.")

    # -----------------------------------------------------------------
    # Tabla comparativa
    # -----------------------------------------------------------------
    print("\n" + BAR)
    print("COMPARATIVA DE COHORTES")
    print(BAR)

    scenarios = [
        ("#1 Empleo joven sur", perfiles_1),
        ("#2 Seguridad uni norte", perfiles_2),
        ("#3 Jubilados", perfiles_3),
        ("#4 Mujeres desocupadas", perfiles_4),
    ]

    def pct(perfs, key, value) -> float:
        if not perfs:
            return 0.0
        return sum(1 for p in perfs if getattr(p, key) == value) / len(perfs) * 100

    rows = []
    for name, perfs in scenarios:
        if not perfs:
            rows.append((name, 0, 0, 0, 0, 0))
            continue
        rows.append((
            name,
            len(perfs),
            round(pct(perfs, "voto", "JxC"), 1),
            round(pct(perfs, "voto", "UxP"), 1),
            round(pct(perfs, "voto", "LLA"), 1),
            round(pct(perfs, "educacion", "universitario"), 1),
        ))

    print(f"{'Cohorte':<28}{'N':>6}{'JxC%':>8}{'UxP%':>8}{'LLA%':>8}{'Uni%':>8}")
    print(SUB)
    for row in rows:
        print(f"{row[0]:<28}{row[1]:>6}{row[2]:>8}{row[3]:>8}{row[4]:>8}{row[5]:>8}")

    print("\n" + BAR)
    print("Cada cohorte se puede exportar como JSON/CSV de OASIS y disparar una")
    print("simulacion via POST /api/simulation/prepare-from-cohort")
    print(BAR)


if __name__ == "__main__":
    main()
