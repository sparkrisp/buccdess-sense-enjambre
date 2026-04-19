"""
Demo end-to-end del sampler CABA + adapter OASIS.

Genera 100 perfiles, exporta en el formato EXACTO que consume MiroFish/OASIS,
valida contra el schema oficial y muestra ejemplos visuales.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sampler.cohort_builder import CohortBuilder
from sampler.oasis_adapter import (
    perfiles_to_oasis,
    save_reddit_json,
    save_twitter_csv,
)

# Campos requeridos segun oasis_profile_generator.py:_save_reddit_json (linea 1164-1188)
REDDIT_REQUIRED = {
    "user_id", "username", "name", "bio", "persona", "karma",
    "created_at", "age", "gender", "mbti", "country",
}
REDDIT_OPTIONAL = {"profession", "interested_topics"}

TWITTER_REQUIRED = {"user_id", "name", "username", "user_char", "description"}


def validate_reddit_schema(profiles_json: list[dict]) -> tuple[bool, list[str]]:
    """Chequea que el JSON tenga todos los campos requeridos."""
    errors = []
    for i, p in enumerate(profiles_json):
        missing = REDDIT_REQUIRED - set(p.keys())
        if missing:
            errors.append(f"Perfil[{i}] faltan: {missing}")
        if not isinstance(p.get("user_id"), int):
            errors.append(f"Perfil[{i}] user_id debe ser int, es {type(p.get('user_id')).__name__}")
        if not isinstance(p.get("age"), int):
            errors.append(f"Perfil[{i}] age debe ser int")
        if p.get("gender") not in ("male", "female", "other"):
            errors.append(f"Perfil[{i}] gender invalido: {p.get('gender')}")
    return len(errors) == 0, errors


def validate_twitter_schema(csv_path: Path) -> tuple[bool, list[str]]:
    import csv as _csv
    errors = []
    with open(csv_path, encoding="utf-8") as f:
        reader = _csv.DictReader(f)
        if set(reader.fieldnames or []) != TWITTER_REQUIRED:
            errors.append(f"Columnas CSV: {reader.fieldnames} != {TWITTER_REQUIRED}")
        for i, row in enumerate(reader):
            if not row.get("user_char") or not row.get("description"):
                errors.append(f"Fila[{i}] user_char/description vacios")
    return len(errors) == 0, errors


def main():
    print("=" * 70)
    print("DEMO END-TO-END: Sampler CABA -> MiroFish/OASIS")
    print("=" * 70)

    # 1. Sampleo de 100 perfiles
    print("\n[1/4] Generando 100 perfiles CABA...")
    builder = CohortBuilder(
        censo_dir=ROOT / "data" / "censo",
        electoral_csv=ROOT / "data" / "caba" / "generales_2023_caba.csv",
    )
    perfiles = builder.sample(n=100, edad_min=18, seed=2026)
    print(f"    OK: {len(perfiles)} perfiles")

    # 2. Conversion a formato OASIS
    print("\n[2/4] Convirtiendo a formato OasisProfileDict...")
    oasis = perfiles_to_oasis(perfiles, seed=2026)
    print(f"    OK: {len(oasis)} perfiles OASIS")

    # 3. Export a reddit_profiles.json y twitter_profiles.csv
    out_dir = ROOT / "data" / "exports"
    reddit_path = out_dir / "reddit_profiles.json"
    twitter_path = out_dir / "twitter_profiles.csv"

    print(f"\n[3/4] Exportando a {out_dir}...")
    save_reddit_json(oasis, reddit_path)
    save_twitter_csv(oasis, twitter_path)
    print(f"    OK: {reddit_path.name} ({reddit_path.stat().st_size / 1024:.1f} KB)")
    print(f"    OK: {twitter_path.name} ({twitter_path.stat().st_size / 1024:.1f} KB)")

    # 4. Validacion de schema
    print("\n[4/4] Validando schemas contra MiroFish...")
    with open(reddit_path, encoding="utf-8") as f:
        reddit_data = json.load(f)
    reddit_ok, reddit_errs = validate_reddit_schema(reddit_data)
    twitter_ok, twitter_errs = validate_twitter_schema(twitter_path)

    print(f"    Reddit JSON:   {'OK' if reddit_ok else 'FAIL'}")
    if reddit_errs:
        for e in reddit_errs[:5]:
            print(f"        - {e}")
    print(f"    Twitter CSV:   {'OK' if twitter_ok else 'FAIL'}")
    if twitter_errs:
        for e in twitter_errs[:5]:
            print(f"        - {e}")

    # Muestra visual
    print("\n" + "=" * 70)
    print("EJEMPLOS DE PERFILES GENERADOS")
    print("=" * 70)

    samples_of_interest = []
    # Buscar: universitario Recoleta JxC, secundario Lugano UxP, universitario Palermo LLA
    for p, o in zip(perfiles, oasis):
        if p.comuna == 2 and p.educacion == "universitario" and p.voto == "JxC":
            samples_of_interest.append(("Recoleta + universitario + JxC", o))
            break
    for p, o in zip(perfiles, oasis):
        if p.comuna == 8 and p.voto == "UxP":
            samples_of_interest.append(("Lugano + UxP", o))
            break
    for p, o in zip(perfiles, oasis):
        if p.voto == "LLA" and p.educacion == "universitario":
            samples_of_interest.append(("Universitario LLA", o))
            break
    for p, o in zip(perfiles, oasis):
        if p.actividad == "desocupada":
            samples_of_interest.append(("Desocupado/a", o))
            break

    for label, o in samples_of_interest:
        print(f"\n--- {label} ---")
        print(f"Nombre:    {o.name} (@{o.user_name})")
        print(f"Edad/sexo: {o.age} / {o.gender}")
        print(f"Profesion: {o.profession}")
        print(f"MBTI:      {o.mbti}")
        print(f"Bio:       {o.bio}")
        print(f"Persona:")
        # Wrap persona a 68 chars
        import textwrap
        for line in textwrap.wrap(o.persona, 68):
            print(f"  {line}")
        print(f"Topics:    {', '.join(o.interested_topics)}")

    # Primer perfil en JSON (raw, asi ves exactamente lo que MiroFish recibe)
    print("\n" + "=" * 70)
    print("PERFIL #0 EN JSON CRUDO (tal cual lo recibiria OASIS)")
    print("=" * 70)
    print(json.dumps(reddit_data[0], ensure_ascii=False, indent=2))

    # Summary de la cohorte
    import pandas as pd
    df = pd.DataFrame([{
        "comuna": p.comuna,
        "sexo": p.sexo,
        "edad": p.edad,
        "edu": p.educacion,
        "voto": p.voto,
    } for p in perfiles])
    print("\n" + "=" * 70)
    print("COMPOSICION DE LA COHORTE DE 100 AGENTES")
    print("=" * 70)
    print("\nVoto:")
    print((df["voto"].value_counts(normalize=True) * 100).round(1).to_string())
    print("\nEducacion:")
    print((df["edu"].value_counts(normalize=True) * 100).round(1).to_string())
    print("\nTop 5 comunas por cantidad de agentes:")
    print(df["comuna"].value_counts().head().to_string())

    print("\n" + "=" * 70)
    print(f"VEREDICTO: {'compatible con MiroFish' if reddit_ok and twitter_ok else 'schema rompe'}")
    print(f"Archivos listos en: {out_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
