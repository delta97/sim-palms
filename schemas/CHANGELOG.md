# Schema changelog

Two versioned artifacts. Full policy: `plans/detailed/01-architecture.md#ws10-data-contract-versioning-policy`.

| Artifact | Field | Form | Current |
|---|---|---|---|
| `palms.geojson` | `schema_version` | `"MAJOR.MINOR"` string | `"1.0"` |
| Region YAML | `config_version` | integer | `1` |

The region field is an integer because YAML reads an unquoted `1.0` as a float.

## Policy

**palms.geojson**

- **MAJOR (breaking):** remove or rename a field; change a type, unit, CRS or meaning; make an optional field required; narrow a range or enum so old files fail; change how `palm_id` or GUID inputs are derived.
- **MINOR (additive):** a new optional field; a new enum value; a wider range.
- **No bump:** `x_*` experimental fields. Consumers never depend on them.
- **Writers** write only `PALMS_SCHEMA_VERSION`.
- **Readers:** different major raises `ContractError` (exit 3). Same major, same or older minor: full validation. Newer minor: relaxed validation, one warning, unknown fields kept in `Palm.extra`.
- **Change procedure** (one task, one review): edit the schema; bump `PALMS_SCHEMA_VERSION` and `SUPPORTED`; add an entry below; add `tests/fixtures/palmcore/palms/valid_v<major>_<minor>.geojson`. All older `valid_v1_*` fixtures must still pass.
- `buildings.geojson` follows the same MAJOR/MINOR rules (schema `1.0`).

**Region config**

- A new optional key with a default needs no bump; old files still load.
- Removing or renaming a key, or changing its meaning, bumps `config_version`. The loader migrates (`_migrate_v1_to_v2(raw)`, run before validation) or refuses with a message naming the change.
- Unknown keys are errors (usually typos).

## palms.geojson 1.0 (2026-11-21)

Initial contract between palmscan, palmgen and palmlive: Point features with species, height, crown, provenance and exclusion radius, plus file-level `region`, `generated_at`, `data_version`, `generator` and `config_sha256`. Also adds the secondary `buildings.geojson` 1.0 schema (Polygon or MultiPolygon with `building_id` and `source`).

## region config_version 1 (2026-11-21)

Initial region YAML format (`regions/*.yaml`), validated by `schemas/region.schema.json`.
