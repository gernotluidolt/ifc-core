import ifcopenshell
from .spatial import get_spatial_tree, get_entity_counts
from .psets import get_psets
from .classifications import get_classification_tree
from .materials import get_materials, get_layered_materials

class DiscoveryAggregator:
    def __init__(self, model: ifcopenshell.file):
        self.model = model
        self._cache = {}

    def clear_cache(self):
        self._cache.clear()

    def get_spatial_tree(self, parent_guid: str | None = None):
        if parent_guid:
            return get_spatial_tree(self.model, parent_guid)
        
        if "spatial_tree" not in self._cache:
            self._cache["spatial_tree"] = get_spatial_tree(self.model)
        return self._cache["spatial_tree"]

    def get_entity_counts(self):
        if "entity_counts" not in self._cache:
            self._cache["entity_counts"] = get_entity_counts(self.model)
        return self._cache["entity_counts"]

    def get_psets(self):
        if "psets" not in self._cache:
            self._cache["psets"] = get_psets(self.model)
        return self._cache["psets"]

    def get_classification_tree(self):
        if "classification_tree" not in self._cache:
            self._cache["classification_tree"] = get_classification_tree(self.model)
        return self._cache["classification_tree"]

    def get_materials(self):
        if "materials" not in self._cache:
            self._cache["materials"] = get_materials(self.model)
        return self._cache["materials"]

    def get_layered_materials(self):
        if "layered_materials" not in self._cache:
            self._cache["layered_materials"] = get_layered_materials(self.model)
        return self._cache["layered_materials"]
