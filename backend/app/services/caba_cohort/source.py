"""
CabaCohortSource: genera perfiles OASIS desde la cohorte electoral CABA.

Adapter entre el sampler (que devuelve Perfil) y el backend MiroFish (que
espera OasisAgentProfile). Compatible drop-in con OasisProfileGenerator.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from ..oasis_profile_generator import OasisAgentProfile
from ...utils.logger import get_logger

from .cohort_builder import CohortBuilder, Perfil


logger = get_logger("mirofish.caba_cohort")


MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]

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
    13: "Belgrano, Nunez, Colegiales",
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
    if grupo == "80+":
        return rng.randint(80, 90)
    if grupo == "14":
        return 14
    lo, hi = grupo.split("-")
    return rng.randint(int(lo), int(hi))


@dataclass
class CohortConfig:
    """Configuracion para samplear una cohorte."""
    n: int = 500
    comuna: Optional[int | list[int]] = None
    edad_min: int = 18
    seed: Optional[int] = None
    cargo: str = "JEF"  # JEF (Jefe Gob) | LEG | COM
    use_ecological_inference: bool = False  # Fase C: ajusta voto por perfil individual


class CabaCohortSource:
    """Genera perfiles OASIS con distribucion real de CABA 2023.

    Interfaz compatible con OasisProfileGenerator: devuelve List[OasisAgentProfile].
    No requiere Zep ni LLM (los atributos se derivan de datos publicos y templates).
    """

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        self.data_dir = Path(data_dir)
        self._builders: dict[str, CohortBuilder] = {}

    def _builder(self, cargo: str, use_ei: bool) -> CohortBuilder:
        """Lazy init del CohortBuilder para el cargo dado."""
        key = f"{cargo}__ei={use_ei}"
        if key not in self._builders:
            logger.info(f"Inicializando CohortBuilder cargo={cargo} ei={use_ei} desde {self.data_dir}")
            self._builders[key] = CohortBuilder(
                censo_dir=self.data_dir,
                electoral_csv=self.data_dir / "generales_2023_caba.csv",
                cargo=cargo,
                use_ecological_inference=use_ei,
            )
        return self._builders[key]

    def generate_profiles(
        self,
        config: CohortConfig,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[OasisAgentProfile]:
        """Samplea n perfiles y los convierte a OasisAgentProfile."""
        builder = self._builder(config.cargo, config.use_ecological_inference)

        logger.info(
            f"Sampleando {config.n} perfiles CABA "
            f"(comuna={config.comuna}, edad_min={config.edad_min}, seed={config.seed}, "
            f"ecological_inference={config.use_ecological_inference})"
        )
        perfiles = builder.sample(
            n=config.n,
            comuna=config.comuna,
            edad_min=config.edad_min,
            seed=config.seed,
        )

        rng = random.Random(config.seed)
        total = len(perfiles)
        profiles: List[OasisAgentProfile] = []

        for i, p in enumerate(perfiles):
            profile = self._perfil_to_oasis(p, rng)
            profiles.append(profile)
            if progress_callback and (i % 50 == 0 or i == total - 1):
                progress_callback(i + 1, total, f"Generados {i + 1}/{total}")

        logger.info(f"Generados {len(profiles)} perfiles OASIS")
        return profiles

    @staticmethod
    def _perfil_to_oasis(perfil: Perfil, rng: random.Random) -> OasisAgentProfile:
        first_pool = NOMBRES_F if perfil.sexo == "F" else NOMBRES_M
        first = rng.choice(first_pool)
        last = rng.choice(APELLIDOS)
        full_name = f"{first} {last}"
        username = f"{first.lower()}.{last.lower()}_{perfil.id:04d}"

        age = _age_from_group(perfil.edad, rng)
        gender = "female" if perfil.sexo == "F" else "male"
        barrios = COMUNA_BARRIOS.get(perfil.comuna, f"Comuna {perfil.comuna}")

        profession_core = {
            "ocupada": "empleado/a" if perfil.educacion in ("ninguno", "primario", "secundario")
                        else "profesional",
            "desocupada": "busca trabajo",
            "inactiva": "jubilado/a" if age >= 65 else "inactivo/a",
        }[perfil.actividad]

        bio = (
            f"{age} anios, {gender}, {barrios} (CABA). "
            f"{EDU_NARRATIVE[perfil.educacion].capitalize()}. "
            f"{profession_core.capitalize()}."
        )

        persona = (
            f"{full_name}, {age} anios, se identifica como {gender}. "
            f"Vive en {barrios} (Comuna {perfil.comuna} de la Ciudad de Buenos Aires). "
            f"Tiene {EDU_NARRATIVE[perfil.educacion]} como nivel educativo alcanzado. "
            f"Actualmente {ACT_NARRATIVE[perfil.actividad]}. "
            f"En las elecciones generales de 2023 para Jefe de Gobierno porteno "
            f"{PARTY_NARRATIVE[perfil.voto]}. "
            f"Su perspectiva esta moldeada por su contexto socioeconomico barrial, "
            f"su nivel educativo, su situacion laboral y su preferencia politica. "
            f"Habla en espaniol rioplatense (voseo) como porteno/a tipico/a."
        )

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

        return OasisAgentProfile(
            user_id=perfil.id,
            user_name=username,
            name=full_name,
            bio=bio,
            persona=persona,
            age=age,
            gender=gender,
            mbti=rng.choice(MBTI_TYPES),
            country="Argentina",
            profession=profession_core,
            interested_topics=topics,
            source_entity_uuid=f"caba-cohort-{perfil.id}",
            source_entity_type="caba_electoral_cohort_2023",
        )
