from syned.beamline.optical_elements.absorbers.filter import Filter

class FilterWithDensity(Filter):
    def __init__(self,
                 name="Undefined",
                 material="Be",
                 thickness=1e-3,
                 density=1.0,
                 boundary_shape=None):
        Filter.__init__(self, name=name, material=material, thickness=thickness, boundary_shape=boundary_shape)
        self._density = density

        # support text containg name of variable, help text and unit. Will be stored in self._support_dictionary
        self._add_support_text([
                    ("name", "Name", ""),  # TODO: this should be in filter!!!
                    ("density"      , "Density",    "g/cm3" ),
            ])

    def get_density(self):
        return self._density

