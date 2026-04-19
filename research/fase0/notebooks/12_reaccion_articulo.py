"""
Reaccion de una cohorte CABA a un articulo real (URL o texto).

Uso:
    # URL
    uv run python notebooks/12_reaccion_articulo.py --url https://www.lanacion.com.ar/...

    # Archivo de texto
    uv run python notebooks/12_reaccion_articulo.py --file articulo.txt --n 20

    # Texto directo
    uv run python notebooks/12_reaccion_articulo.py --text "Anuncian ..." --n 15

    # Default demo
    uv run python notebooks/12_reaccion_articulo.py
"""
import argparse
import json
import os
import sys
import textwrap
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT.parent.parent / ".env", override=True)

from sampler.cohort_builder import CohortBuilder
from sampler.oasis_adapter import perfiles_to_oasis


DEFAULT_ARTICLE = """
El Gobierno Nacional anuncio hoy la eliminacion total de los subsidios al
transporte publico en el Area Metropolitana de Buenos Aires. La medida,
que entrara en vigencia el proximo lunes, implica un aumento promedio
del 350 por ciento en el boleto de subte y de entre 200 y 400 por ciento
en colectivos segun la linea.

El Ministro de Economia justifico la medida: "El Estado no puede seguir
financiando la movilidad de la clase media portena. Es una distorsion
historica que debe terminar". Desde la oposicion, el bloque peronista
denuncio un "tarifazo brutal" que "va a golpear sobre todo a los
laburantes y jubilados". Gremios del transporte ya convocaron a un paro
para el martes en rechazo a la medida.
""".strip()


REACT_SYSTEM_TEMPLATE = """{persona}

Tu tarea ahora: acabas de ver este articulo en redes sociales. Reaccionas
POSTEANDO un comentario como lo harias vos en X (Twitter), con tu estilo,
tu emocion, tu lenguaje cotidiano.

Devolves un JSON con esta estructura EXACTA:
{{
  "tweet": "tu reaccion de 1 a 3 oraciones, en rioplatense, con emocion",
  "sentiment": "uno de: a_favor | en_contra | neutro | ambiguo",
  "razon_principal": "resumen corto de la razon de tu reaccion, 1 oracion"
}}

Nada de explicaciones extra, solo el JSON."""


def fetch_article(args) -> tuple[str, str]:
    """Devuelve (titulo, contenido) del articulo."""
    if args.url:
        import trafilatura
        downloaded = trafilatura.fetch_url(args.url)
        if not downloaded:
            raise RuntimeError(f"No pude descargar: {args.url}")
        metadata = trafilatura.extract_metadata(downloaded)
        title = metadata.title if metadata else "(sin titulo)"
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if not text:
            raise RuntimeError("trafilatura no pudo extraer texto")
        return title, text
    if args.file:
        p = Path(args.file)
        return p.stem, p.read_text(encoding="utf-8")
    if args.text:
        return "(texto directo)", args.text
    return "(demo: tarifazo subte)", DEFAULT_ARTICLE


def react(
    client: OpenAI,
    model: str,
    persona: str,
    title: str,
    article: str,
) -> dict:
    """Una llamada al LLM, devuelve dict con tweet/sentiment/razon."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": REACT_SYSTEM_TEMPLATE.format(persona=persona)},
            {"role": "user", "content": (
                f"Articulo (titulo: {title}):\n\n{article[:3500]}\n\n"
                "Tu reaccion en JSON:"
            )},
        ],
        response_format={"type": "json_object"},
        max_tokens=800,
        temperature=0.85,
        extra_body={"reasoning_effort": "none"},
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"tweet": content[:200], "sentiment": "neutro", "razon_principal": "(parse error)"}


def print_banner(text: str, char: str = "=") -> None:
    print("\n" + char * 78)
    print(text)
    print(char * 78)


def pct(d: dict, key) -> float:
    total = sum(d.values())
    return round(d.get(key, 0) / total * 100, 1) if total else 0.0


def main():
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--url", help="URL del articulo")
    g.add_argument("--file", help="Archivo de texto con el articulo")
    g.add_argument("--text", help="Texto directo")
    parser.add_argument("--n", type=int, default=12, help="Cantidad de agentes")
    parser.add_argument("--comuna", type=int, nargs="*", default=None,
                        help="Lista de comunas. Default: toda CABA")
    parser.add_argument("--edad-min", type=int, default=18)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--no-ei", action="store_true",
                        help="Desactivar Ecological Inference")
    args = parser.parse_args()

    # 1) Articulo
    title, article = fetch_article(args)

    print_banner("ARTICULO")
    print(f"Titulo: {title}")
    print(f"Largo:  {len(article)} caracteres, {len(article.split())} palabras")
    print(f"Preview:")
    for line in textwrap.wrap(article[:600], 74):
        print(f"  {line}")
    if len(article) > 600:
        print("  [...]")

    # 2) Cohorte
    print_banner("COHORTE")
    builder = CohortBuilder(
        censo_dir=ROOT / "data" / "censo",
        electoral_csv=ROOT / "data" / "caba" / "generales_2023_caba.csv",
        use_ecological_inference=not args.no_ei,
    )
    perfiles = builder.sample(
        n=args.n,
        comuna=args.comuna,
        edad_min=args.edad_min,
        seed=args.seed,
    )
    oasis = perfiles_to_oasis(perfiles, seed=args.seed)
    print(f"Sampleados: {len(oasis)} agentes | EI: {not args.no_ei} | "
          f"comuna: {args.comuna or 'todas'} | edad_min: {args.edad_min} | seed: {args.seed}")

    # 3) LLM
    client = OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"])
    model = os.environ["LLM_MODEL_NAME"]
    print(f"LLM: {model}")

    # 4) Reacciones
    print_banner("REACCIONES INDIVIDUALES")
    results = []
    for i, (p, o) in enumerate(zip(perfiles, oasis)):
        header = (
            f"[{i+1}/{len(oasis)}] {o.name} ({o.age}a, {o.gender}, Comuna {p.comuna}) "
            f"| {p.educacion}/{p.actividad} | voto 2023: {p.voto}"
        )
        print("\n" + "-" * min(len(header), 78))
        print(header)
        try:
            r = react(client, model, o.persona, title, article)
        except Exception as e:
            r = {"tweet": f"(error: {e})", "sentiment": "neutro", "razon_principal": str(e)[:80]}
        results.append({"perfil": p, "oasis": o, **r})
        tweet = r.get("tweet", "").replace("\n", " ")
        print(f"[{r.get('sentiment', '?').upper():<10}] {tweet}")
        print(f"            > {r.get('razon_principal', '')}")

    # 5) Analisis agregado
    print_banner("ANALISIS AGREGADO")

    # Sentiment global
    sentiments = Counter(r["sentiment"] for r in results)
    print("\nDistribucion de sentiment (total cohorte):")
    for s in ("a_favor", "en_contra", "neutro", "ambiguo"):
        print(f"  {s:<12}: {pct(sentiments, s):>5}%  ({sentiments.get(s, 0)})")

    # Sentiment por voto 2023
    print("\nSentiment por voto 2023:")
    by_voto = defaultdict(Counter)
    for r in results:
        by_voto[r["perfil"].voto][r["sentiment"]] += 1
    header = f"{'voto':<8}{'a_favor':>10}{'en_contra':>12}{'neutro':>10}{'ambiguo':>10}  N"
    print("  " + header)
    for voto in ("UxP", "JxC", "LLA", "FIT"):
        c = by_voto[voto]
        n = sum(c.values())
        if n == 0:
            continue
        print(
            f"  {voto:<8}{pct(c,'a_favor'):>9}% {pct(c,'en_contra'):>11}% "
            f"{pct(c,'neutro'):>9}% {pct(c,'ambiguo'):>9}%  {n}"
        )

    # Sentiment por educacion
    print("\nSentiment por nivel educativo:")
    by_edu = defaultdict(Counter)
    for r in results:
        by_edu[r["perfil"].educacion][r["sentiment"]] += 1
    print("  " + header.replace("voto", "edu"))
    for edu in ("ninguno", "primario", "secundario", "terciario", "universitario"):
        c = by_edu[edu]
        n = sum(c.values())
        if n == 0:
            continue
        print(
            f"  {edu:<8}{pct(c,'a_favor'):>9}% {pct(c,'en_contra'):>11}% "
            f"{pct(c,'neutro'):>9}% {pct(c,'ambiguo'):>9}%  {n}"
        )

    # Guardar JSON con todo
    out_dir = ROOT / "data" / "exports" / "reacciones"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"reaccion_{args.seed}_n{len(oasis)}.json"
    export = {
        "articulo": {"titulo": title, "texto": article},
        "cohorte": {
            "n": len(oasis), "comuna": args.comuna, "edad_min": args.edad_min,
            "seed": args.seed, "use_ei": not args.no_ei,
        },
        "reacciones": [
            {
                "agente": {
                    "name": r["oasis"].name, "age": r["oasis"].age,
                    "gender": r["oasis"].gender, "comuna": r["perfil"].comuna,
                    "educacion": r["perfil"].educacion,
                    "actividad": r["perfil"].actividad,
                    "voto_2023": r["perfil"].voto,
                },
                "tweet": r.get("tweet"),
                "sentiment": r.get("sentiment"),
                "razon_principal": r.get("razon_principal"),
            }
            for r in results
        ],
    }
    out_path.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nExport guardado: {out_path}")


if __name__ == "__main__":
    main()
