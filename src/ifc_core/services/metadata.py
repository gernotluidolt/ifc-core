import ifcopenshell

from ..models.ifc import ModelMetadata


def get_model_info(
    model: ifcopenshell.file, filename: str | None = None
) -> ModelMetadata:
    header = model.header

    # Detect multilayered elements
    # Many standard exports use IfcBuildingElementPart for layers
    # Others use IfcMaterialLayerSetUsage/IfcMaterialLayer directly
    has_parts = len(model.by_type("IfcBuildingElementPart")) > 0
    has_layer_sets = len(model.by_type("IfcMaterialLayerSetUsage")) > 0

    return ModelMetadata(
        schema_version=model.schema,
        author=header.file_name.author[0] if header.file_name.author else "Unknown",
        timestamp=header.file_name.time_stamp,
        file_name=filename,
        has_multilayered_elements=has_parts or has_layer_sets,
    )
