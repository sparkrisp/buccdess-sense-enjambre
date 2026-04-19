"""
Demo FINAL: agentes sampleados del sampler CABA reaccionando a una medida
con LLM real (Gemini 2.5 Flash via OpenAI-compatible endpoint).

Cierra el loop: datos publicos -> sampler -> persona -> LLM -> reaccion.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Cargar .env desde la raiz del proyecto
load_dotenv(ROOT.parent.parent / ".env", override=True)

from sampler.cohort_builder import CohortBuilder
from sampler.oasis_adapter import perfiles_to_oasis


MEDIDA = (
    "URGENTE: El Gobierno Nacional anuncia que desde el lunes proximo "
    "aumenta un 40% el boleto de subte y colectivo en CABA y GBA, y se "
    "eliminan los subsidios al transporte publico."
)

client = OpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
)
MODEL = os.environ["LLM_MODEL_NAME"]


def agent_react(persona: str, medida: str) -> str:
    """El agente ve la medida en X/Twitter y postea su reaccion (1-2 oraciones)."""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": (
                persona
                + " Tu tarea: estas scrolleando X (Twitter) y ves esta noticia. "
                "Postea TU reaccion en 1-2 oraciones MAXIMO, como hablarias vos "
                "(en rioplatense coloquial, con emocion genuina acorde a tu perfil). "
                "No expliques tu persona, solo reacciona."
            )},
            {"role": "user", "content": f"Noticia: {medida}\n\nTu tweet:"},
        ],
        max_tokens=600,
        temperature=0.85,
        extra_body={"reasoning_effort": "none"},  # gemini 2.5: minimizar thinking invisible
    )
    return resp.choices[0].message.content.strip()


def main():
    print("=" * 78)
    print("DEMO FINAL: Agentes CABA reaccionando a una medida con LLM (Gemini 2.5)")
    print("=" * 78)
    print(f"\nMedida simulada:\n{MEDIDA}\n")
    print("Sampleando 12 agentes representativos (seed=2026)...")

    builder = CohortBuilder(
        censo_dir=ROOT / "data" / "censo",
        electoral_csv=ROOT / "data" / "caba" / "generales_2023_caba.csv",
        use_ecological_inference=True,
    )

    # Mezcla deliberada: algunas comunas ricas, algunas populares
    # La Boca, Recoleta, Lugano, Belgrano, Caballito, Palermo
    comunas_mix = [2, 4, 6, 8, 13, 14]

    # Sampleo 2 por comuna
    perfiles = []
    for c in comunas_mix:
        ps = builder.sample(n=2, comuna=c, edad_min=18, seed=2026 + c)
        perfiles.extend(ps)

    # Re-id
    for i, p in enumerate(perfiles):
        p.id = i

    oasis = perfiles_to_oasis(perfiles, seed=2026)
    print(f"OK: {len(oasis)} agentes generados.\n")

    print("=" * 78)
    print("REACCIONES")
    print("=" * 78)

    for i, (p, o) in enumerate(zip(perfiles, oasis)):
        header = (
            f"[{i+1}/{len(oasis)}] {o.name} ({o.age}a, {o.gender}) - "
            f"Comuna {p.comuna} - {p.educacion}/{p.actividad} - voto 2023: {p.voto}"
        )
        print("\n" + "-" * len(header))
        print(header)
        print("-" * len(header))

        try:
            tweet = agent_react(o.persona, MEDIDA)
            # Clean up
            tweet = tweet.replace('"', "").strip()
            print(f"Tweet: {tweet}")
        except Exception as e:
            print(f"ERROR LLM: {e}")

    print("\n" + "=" * 78)
    print("FIN. Notar como las reacciones correlacionan con el perfil:")
    print("  - Universitarios JxC zona norte:  reaccion tipica anti-inflacion peronista")
    print("  - Jovenes LLA secundario:         reaccion pro-ajuste o liberal")
    print("  - UxP Lugano secundario:          reaccion rechazo al ajuste y los recortes")
    print("  - Jubilados zona sur:             reaccion sobre pension y costo de vida")
    print("=" * 78)


if __name__ == "__main__":
    main()
