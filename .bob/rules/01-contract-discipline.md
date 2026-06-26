# Contract Discipline Rule

**Contract changes require coordinated updates.**

## The Two Contracts

The system has two JSON contracts that decouple all stages:

1. **`Requirement`** - Output of Part 1 (extraction), input of Part 2 (assessment)
2. **`Finding`** - Output of Part 2 (assessment), input of Parts 3 & 4 (alerting, dashboard)

## Single Source of Truth

**Pydantic models in `contracts/models.py` are the SINGLE source of truth.**

- JSON schemas (`requirement.schema.json`, `finding.schema.json`) are **GENERATED** from models
- Never edit JSON schemas manually
- CI validates that schemas match models (drift = build failure)

## When Modifying a Contract

If you need to change a contract model, follow this process:

1. **Update the Pydantic model** in `contracts/models.py`
2. **Regenerate schemas**: `uv run python contracts/export_schemas.py`
3. **Update fixtures** in `contracts/fixtures/` to match the new structure
4. **Update all consumers** (services that read/write this contract)
5. **Commit everything together** in the same change

## Why This Matters

- Contracts are **process boundaries** between services
- Each service can be built and tested independently against fixtures
- Schema validation catches interface drift immediately
- Breaking a contract breaks the entire pipeline

## CI Validation

The CI pipeline:
1. Re-runs `export_schemas.py`
2. Compares generated schemas with committed schemas
3. **Fails if they differ** (someone changed a model without regenerating schemas)

This is the early warning system that prevents contract drift.

## Example: Adding a Field

```python
# 1. Update contracts/models.py
class Requirement(BaseModel):
    # ... existing fields ...
    new_field: str = Field(description="New field description")

# 2. Regenerate schemas
# $ uv run python contracts/export_schemas.py

# 3. Update fixtures/requirements.sample.json
# Add "new_field": "example value" to all entries

# 4. Update consumers
# - extraction_service: populate new_field when creating Requirements
# - assessment_service: handle new_field when reading Requirements

# 5. Commit all changes together
```

## Consequences of Violation

- Services fail at runtime with validation errors
- Tests break
- CI fails
- Pipeline stops working
- Team loses time debugging

## Best Practices

✅ **DO:**
- Treat contracts as sacred interfaces
- Discuss contract changes with the team first
- Update everything in one atomic commit
- Run tests after contract changes
- Document breaking changes

❌ **DON'T:**
- Edit JSON schemas directly
- Change a model without regenerating schemas
- Update only one consumer and forget others
- Make breaking changes without team discussion
- Commit model changes without fixture updates
