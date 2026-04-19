"""
Extraccion de grafo de entidades/relaciones desde un articulo via Zep Cloud.

Reutiliza la infraestructura de Zep pero sin depender del task manager async
ni de una ontologia pre-definida. El modelo default de Zep extrae entidades
generales automaticamente.

Devuelve la misma estructura que article_ontology.extract_ontology_from_article
para que el frontend consuma indistintamente.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger("mirofish.zep_article_graph")


def _wait_for_processing(client: Zep, graph_id: str, timeout: int = 120) -> None:
    """Espera a que Zep procese los episodios (poll hasta que no queden 'pending')."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            episodes = client.graph.episode.get_by_graph_id(graph_id=graph_id)
            items = getattr(episodes, "episodes", None) or []
            pending = [e for e in items if getattr(e, "processed", True) is False]
            if not pending:
                return
            logger.info(f"Zep procesando: {len(pending)} episodios pendientes...")
            time.sleep(3)
        except Exception as e:
            logger.warning(f"Error consultando episodios: {e}")
            time.sleep(3)
    logger.warning(f"Timeout esperando procesamiento ({timeout}s)")


def extract_ontology_via_zep(
    article: str,
    graph_name_prefix: str = "caba-cohort-article",
) -> Dict[str, Any]:
    """
    Crea un grafo Zep con el articulo y devuelve nodos + aristas.

    Returns:
        Dict con entities, relationships, themes, source, stats.
    """
    if not Config.ZEP_API_KEY or Config.ZEP_API_KEY.startswith("not-used"):
        raise ValueError("ZEP_API_KEY no configurada correctamente")

    client = Zep(api_key=Config.ZEP_API_KEY)

    graph_id = f"{graph_name_prefix}-{uuid.uuid4().hex[:8]}"
    logger.info(f"Creando grafo Zep: {graph_id}")

    client.graph.create(
        graph_id=graph_id,
        name=graph_name_prefix,
        description="Grafo extraído del artículo para cohorte CABA",
    )

    # Chunkear el artículo y subir
    chunks = _chunk_text(article, chunk_size=2000, overlap=100)
    logger.info(f"Subiendo {len(chunks)} chunks a Zep...")
    for chunk in chunks:
        client.graph.add(
            graph_id=graph_id,
            data=chunk,
            type="text",
        )

    # Esperar procesamiento
    _wait_for_processing(client, graph_id, timeout=120)

    # Traer nodos y aristas
    nodes_resp = client.graph.node.get_by_graph_id(graph_id=graph_id)
    edges_resp = client.graph.edge.get_by_graph_id(graph_id=graph_id)

    nodes = getattr(nodes_resp, "nodes", None) or []
    edges = getattr(edges_resp, "edges", None) or []

    # Convertir al formato común
    entities = []
    id_map = {}  # zep uuid -> short id
    for i, node in enumerate(nodes):
        short_id = f"e{i + 1}"
        id_map[node.uuid] = short_id
        labels = getattr(node, "labels", []) or []
        custom_labels = [l for l in labels if l not in ("Entity", "Node")]
        entity_type = custom_labels[0].lower() if custom_labels else "entity"
        entities.append({
            "id": short_id,
            "name": node.name,
            "type": entity_type,
            "role": (getattr(node, "summary", "") or "")[:120],
            "zep_uuid": node.uuid,
        })

    relationships = []
    for edge in edges:
        src = id_map.get(edge.source_node_uuid)
        tgt = id_map.get(edge.target_node_uuid)
        if not src or not tgt:
            continue
        label = getattr(edge, "name", None) or getattr(edge, "fact", None) or "relación"
        relationships.append({
            "from": src,
            "to": tgt,
            "label": str(label)[:120],
        })

    return {
        "source": "zep",
        "zep_graph_id": graph_id,
        "entities": entities,
        "relationships": relationships,
        "themes": [],  # Zep no devuelve temas directamente; podría extraerse con LLM después
        "stats": {
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "theme_count": 0,
        },
    }


def _chunk_text(text: str, chunk_size: int = 2000, overlap: int = 100) -> list[str]:
    """Chunker simple por caracteres con overlap."""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks
