"""CABA electoral cohort source - genera perfiles sinteticos con distribucion
real del electorado porteno (Censo 2022 + Generales 2023).

Uso desde simulation_manager:
    from .caba_cohort import CabaCohortSource
    source = CabaCohortSource()
    profiles = source.generate_profiles(n=500, comuna=[2, 13, 14], seed=42)
"""
from .source import CabaCohortSource, CohortConfig

__all__ = ["CabaCohortSource", "CohortConfig"]
