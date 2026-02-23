"""Connectors for integrating external datasets (GIS, databases, etc.) into the MRV estimator.

This package provides *lightweight, dependency-minimal* loaders that convert common
exchange formats (CSV/JSON) into the internal dataclasses used by the estimator.

Design goals:
- Keep the estimator pure (no I/O inside calculation modules).
- Provide auditable provenance fields (source, version, notes).
- Make it easy to extend (add PostGIS, STAC, APIs later).
"""
