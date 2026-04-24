import ifcopenshell
from .spatial import get_spatial_tree, get_entity_counts
from .psets import get_psets
from .classifications import get_classification_tree
from .materials import get_materials, get_layered_materials

class DiscoveryAggregator:
    def __init__(self, model: ifcopenshell.file):
        self.model = model

    def get_spatial_tree(self, parent_guid: str | None = None):
        return get_spatial_tree(self.model, parent_guid)

    def get_entity_counts(self):
        return get_entity_counts(self.model)

    def get_psets(self):
        return get_psets(self.model)

    def get_classification_tree(self):
        return get_classification_tree(self.model)

    def get_materials(self):
        return get_materials(self.model)

    def get_layered_materials(self):
        return get_layered_materials(self.model)
