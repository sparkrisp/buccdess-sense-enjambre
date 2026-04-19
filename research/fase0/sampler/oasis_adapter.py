"""
Adapta perfiles sinteticos (Perfil) al formato OasisAgentProfile de MiroFish.

Genera bio/persona en texto natural con templates. No usa LLM (eso lo hace
OASIS despues). El objetivo es darle al agente CONTEXTO DEMOGRAFICO y POLITICO
REAL para que actue coherentemente en la simulacion.
"""
from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .cohort_builder import Perfil


# Nombres argentinos comunes. Muestra curada, no pretende ser exhaustiva.
NOMBRES_F = [
    "Maria", "Sofia", "Valentina", "Martina", "Lucia", "Camila", "Agustina",
    "Emilia", "Renata", "Catalina", "Mia", "Olivia", "Paula", "Julieta",
    "Florencia", "Gabriela", "Carolina", "Laura", "Patricia", "Silvia",
    "Monica", "Beatriz", "Norma", "Cristina",
]
NOMBRES_M = [
    "Santiago", "Mateo", "Benjamin", "Lautaro", "Thiago", "Juan", "Martin",
    "Facundo", "Tomas", "Ignacio", "Lucas", "Nicolas", "Gabriel", "Diego",
    "Sebastian", "Matias", "Gonzalo", "Federico", "Rodrigo", "Pablo",
    "Alejandro", "Roberto", "Carlos", "Jorge",
]
APELLIDOS = [
    "Gonzalez", "Rodriguez", "Fernandez", "Lopez", "Martinez", "Garcia",
    "Perez", "Sanchez", "Gomez", "Diaz", "Romero", "Torres", "Ruiz", "Flores",
    "Acosta", "Ramirez", "Castro", "Rojas", "Silva", "Alvarez", "Benitez",
    "Sosa", "Gutierrez", "Vazquez", "Molina",
]


# Comuna -> barrios caracteristicos (solo descriptivo, para la persona)
COMUNA_BARRIOS = {
    1:  "Retiro, San Nicolas, Puerto Madero",
    2:  "Recoleta",
    3:  "Balvanera, San Cristobal",
    4:  "La Boca, Barracas, Parque Patricios",
    5:  "Almagro, Boedo",
    6:  "Caballito",
    7:  "Flores, Parque Chacabuco",
    8:  "Villa Soldati, Villa Lugano, Villa Riachuelo",
    9:  "Mataderos, Liniers, Parque Avellaneda",
    10: "Villa Real, Monte Castro, Versalles, Floresta, Velez Sarsfield",
    11: "Villa Devoto, Villa del Parque, Villa Santa Rita",
    12: "Saavedra, Coghlan, Villa Urquiza, Villa Pueyrredon",
    13: "Belgrano, Nuñez, Colegiales",
    14: "Palermo",
    15: "Chacarita, Villa Crespo, Paternal, Agronomia, Parque Chas",
}

PARTY_NARRATIVE = {
    "UxP": "voto a Union por la Patria (peronismo / Massa)",
    "JxC": "voto a Juntos por el Cambio (PRO / Bullrich)",
    "LLA": "voto a La Libertad Avanza (Milei)",
    "FIT": "voto al Frente de Izquierda",
}

EDU_NARRATIVE = {
    "ninguno": "sin estudios formales completos",
    "primario": "primario completo",
    "secundario": "secundario completo",
    "terciario": "terciario completo o universitario en curso",
    "universitario": "universitario completo o posgrado",
}

ACT_NARRATIVE = {
    "ocupada": "trabaja",
    "desocupada": "esta buscando trabajo",
    "inactiva": "no esta buscando trabajo (estudia, jubilado/a, u otra razon)",
}


def _age_from_group(grupo: str, rng: random.Random) -> int:
    """Samplear edad dentro del grupo quinquenal."""
    if grupo == "80+":
        return rng.randint(80, 90)
    if grupo == "14":
        return 14
    lo, hi = grupo.split("-")
    return rng.randint(int(lo), int(hi))


MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]


@dataclass
class OasisProfileDict:
    """Formato compatible con OasisAgentProfile de MiroFish."""
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    age: int
    gender: str          # 'male' | 'female'
    country: str         # 'Argentina'
    profession: str
    mbti: str
    interested_topics: list[str] = field(default_factory=list)
    karma: int = 1000
    follower_count: int = 150
    friend_count: int = 100
    statuses_count: int = 500
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    source: str = "caba_cohort_2023"

    def to_reddit_dict(self) -> dict[str, Any]:
        """Formato EXACTO consumido por OASIS/MiroFish para Reddit.

        Espejado de oasis_profile_generator.py:_save_reddit_json:1166-1188.
        """
        item: dict[str, Any] = {
            "user_id": self.user_id,
            "username": self.user_name,
            "name": self.name,
            "bio": self.bio[:150],
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
        }
        if self.profession:
            item["profession"] = self.profession
        if self.interested_topics:
            item["interested_topics"] = self.interested_topics
        return item

    def to_twitter_row(self, idx: int) -> dict[str, Any]:
        """Formato EXACTO consumido por OASIS/MiroFish para Twitter.

        Espejado de oasis_profile_generator.py:_save_twitter_csv:1070-1119.
        Campos: user_id, name, username, user_char, description.
        """
        user_char = self.bio
        if self.persona and self.persona != self.bio:
            user_char = f"{self.bio} {self.persona}"
        user_char = user_char.replace("\n", " ").replace("\r", " ")
        description = self.bio.replace("\n", " ").replace("\r", " ")
        return {
            "user_id": idx,
            "name": self.name,
            "username": self.user_name,
            "user_char": user_char,
            "description": description,
        }


def perfil_to_oasis(perfil: Perfil, rng: random.Random | None = None) -> OasisProfileDict:
    """Convierte un Perfil a OasisProfileDict listo para OASIS."""
    rng = rng or random.Random(perfil.id)

    # Nombre + apellido ficticios
    first_pool = NOMBRES_F if perfil.sexo == "F" else NOMBRES_M
    first = rng.choice(first_pool)
    last = rng.choice(APELLIDOS)
    full_name = f"{first} {last}"
    username = f"{first.lower()}.{last.lower()}_{perfil.id:04d}"

    age = _age_from_group(perfil.edad, rng)
    gender = "female" if perfil.sexo == "F" else "male"
    barrios = COMUNA_BARRIOS.get(perfil.comuna, f"Comuna {perfil.comuna}")

    profession_core = {
        "ocupada": "empleado/a" if perfil.educacion in ("ninguno", "primario", "secundario") else "profesional",
        "desocupada": "busca trabajo",
        "inactiva": "jubilado/a" if age >= 65 else "inactivo/a",
    }[perfil.actividad]

    # Bio: corto, estilo declarativo
    bio = (
        f"{age} anios, {gender}, {barrios} (CABA). "
        f"{EDU_NARRATIVE[perfil.educacion].capitalize()}. "
        f"{profession_core.capitalize()}."
    )

    # Persona: mas largo, para el system prompt del LLM de OASIS
    persona = (
        f"{full_name}, {age} anios, se identifica como {gender}. "
        f"Vive en {barrios} (Comuna {perfil.comuna} de la Ciudad de Buenos Aires). "
        f"Tiene {EDU_NARRATIVE[perfil.educacion]} como nivel educativo alcanzado. "
        f"Actualmente {ACT_NARRATIVE[perfil.actividad]}. "
        f"En las elecciones generales de 2023 para Jefe de Gobierno porteno {PARTY_NARRATIVE[perfil.voto]}. "
        f"Su perspectiva esta moldeada por su contexto socioeconomico barrial, "
        f"su nivel educativo, su situacion laboral y su preferencia politica. "
        f"Habla en espaniol rioplatense (voseo) como porteno/a tipico/a."
    )

    # interested_topics: combinamos senales
    topics = ["Argentina", "CABA", "politica argentina"]
    if perfil.voto == "LLA":
        topics.extend(["libertarios", "economia", "Milei"])
    elif perfil.voto == "JxC":
        topics.extend(["PRO", "Bullrich", "seguridad"])
    elif perfil.voto == "UxP":
        topics.extend(["peronismo", "Massa", "derechos sociales"])
    elif perfil.voto == "FIT":
        topics.extend(["izquierda", "trabajadores", "Bregman"])
    if perfil.educacion == "universitario":
        topics.append("educacion superior")
    if perfil.actividad == "desocupada":
        topics.append("empleo")

    return OasisProfileDict(
        user_id=perfil.id,
        user_name=username,
        name=full_name,
        bio=bio,
        persona=persona,
        age=age,
        gender=gender,
        country="Argentina",
        profession=profession_core,
        mbti=rng.choice(MBTI_TYPES),
        interested_topics=topics,
    )


def perfiles_to_oasis(perfiles: list[Perfil], seed: int | None = None) -> list[OasisProfileDict]:
    rng = random.Random(seed)
    return [perfil_to_oasis(p, rng) for p in perfiles]


def save_reddit_json(profiles: list[OasisProfileDict], path: Path) -> None:
    """Escribir array JSON en el formato que MiroFish/OASIS espera."""
    data = [p.to_reddit_dict() for p in profiles]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_twitter_csv(profiles: list[OasisProfileDict], path: Path) -> None:
    """Escribir CSV con los 5 campos que OASIS Twitter espera."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["user_id", "name", "username", "user_char", "description"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, p in enumerate(profiles):
            writer.writerow(p.to_twitter_row(idx))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    from .cohort_builder import CohortBuilder

    root = Path(__file__).resolve().parents[1]
    builder = CohortBuilder(
        censo_dir=root / "data" / "censo",
        electoral_csv=root / "data" / "caba" / "generales_2023_caba.csv",
    )
    perfiles = builder.sample(n=5, seed=42)
    oasis = perfiles_to_oasis(perfiles, seed=42)

    for p, o in zip(perfiles, oasis):
        print(f"\n{'=' * 70}")
        print(f"Perfil #{p.id}: Comuna {p.comuna}, {p.sexo}, {p.edad}, {p.actividad}, {p.educacion}, voto {p.voto}")
        print(f"{'-' * 70}")
        print(f"Nombre: {o.name} (@{o.user_name}, user_id={o.user_id})")
        print(f"Bio:    {o.bio}")
        print(f"Persona: {o.persona}")
        print(f"Topics: {o.interested_topics}")
