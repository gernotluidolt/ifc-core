import ifcopenshell
from ..models.ifc import ModelMetadata


def get_model_info(model: ifcopenshell.file) -> ModelMetadata:
    header = model.header
    return ModelMetadata(
        schema_version=model.schema,
        author=header.file_name.author[0] if header.file_name.author else "Unknown",
        timestamp=header.file_name.time_stamp,
    )
