"""
Extraccion de ontologia (grafo de entidades + relaciones) de un articulo,
via Gemini structured output.

Devuelve JSON:
{
  "entities": [{"id": "e1", "name": "Milei", "type": "persona", "role": "presidente"}, ...],
  "relationships": [{"from": "e1", "to": "e2", "label": "conflicto con"}, ...],
  "themes": ["ajuste economico", "tensiones con justicia", ...]
}

No usa Zep. Un solo LLM call.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger("mirofish.article_ontology")


SYSTEM_PROMPT = """Sos un analista político y experto en análisis de redes de actores.
Dado un artículo, extraé:

1. ENTIDADES: personas, instituciones, grupos, conceptos clave. Para cada una: id único, nombre, tipo (persona/institucion/grupo/concepto/evento), y role descriptivo corto.
2. RELACIONES: conexiones entre entidades. Cada relación: from (entity id), to (entity id), label (verbo corto que describe la relación).
3. TEMAS: 3-7 ejes temáticos/conflictos principales del artículo.

IMPORTANTE:
- Máximo 20 entidades (las más relevantes)
- Máximo 25 relaciones
- IDs cortos tipo "e1", "e2", ...
- Labels de relaciones en español, verbos activos y concisos ("pidió acuerdo a", "rechazó", "critica", etc)
- Devolvé SOLO el JSON, sin texto adicional.

Ejemplo de estructura:
{
  "entities": [
    {"id": "e1", "name": "Milei", "type": "persona", "role": "presidente"},
    {"id": "e2", "name": "Caputo", "type": "persona", "role": "ministro economía"}
  ],
  "relationships": [
    {"from": "e2", "to": "e1", "label": "reporta a"},
    {"from": "e2", "to": "e3", "label": "pide acuerdo urgente a"}
  ],
  "themes": ["ajuste económico agotado", "tensiones en la coalición"]
}"""


def extract_ontology_from_article(
    article: str,
    model: str | None = None,
) -> Dict[str, Any]:
    """
    Extrae un grafo estructurado de entidades y relaciones del artículo.

    Args:
        article: Texto crudo del artículo.
        model: Nombre del modelo LLM a usar. Si None, usa Config.LLM_MODEL_NAME.

    Returns:
        Dict con keys: entities, relationships, themes.
    """
    client = OpenAI(
        api_key=Config.LLM_API_KEY,
        base_url=Config.LLM_BASE_URL,
    )

    response = client.chat.completions.create(
        model=model or Config.LLM_MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Artículo:\n\n{article[:12000]}\n\nExtraé el grafo:"},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=4000,
        extra_body={"reasoning_effort": "none"},
    )

    raw = response.choices[0].message.content
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}. Raw: {raw[:400]}")
        raise ValueError(f"LLM devolvió JSON inválido: {e}")

    # Validación mínima + normalización
    entities = data.get("entities", [])
    relationships = data.get("relationships", [])
    themes = data.get("themes", [])

    if not isinstance(entities, list):
        raise ValueError("entities debe ser lista")
    if not isinstance(relationships, list):
        raise ValueError("relationships debe ser lista")

    # Asegurar ids únicos y consistentes
    entity_ids = {e.get("id") for e in entities if e.get("id")}
    relationships = [
        r for r in relationships
        if r.get("from") in entity_ids and r.get("to") in entity_ids
    ]

    return {
        "source": "llm",
        "model": model or Config.LLM_MODEL_NAME,
        "entities": entities,
        "relationships": relationships,
        "themes": themes,
        "stats": {
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "theme_count": len(themes),
        },
    }
