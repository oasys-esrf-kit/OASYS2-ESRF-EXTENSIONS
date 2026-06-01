#
# FilterBlock contains a list of Filters
# FilterBox contains a list of FilterBlock
#

from orangecontrib.esrf.syned.util.syned_filter_with_density import FilterWithDensity

from syned.syned_object import SynedObject
from collections import OrderedDict

class FilterBlock(SynedObject):
    """A single attenuator block (axis): an ordered list of FilterWithDensity foils.

    All foils in a block are physically stacked and inserted together as one unit.
    """

    def __init__(self, filters_list=None):
        """
        Parameters
        ----------
        filters_list : list of FilterWithDensity, optional
            Ordered list of foils that make up this block. Defaults to empty list.
        """
        if filters_list is None:
            self._filters_list = []
        else:
            self._filters_list = filters_list

        # support text containg name of variable, help text and unit. Will be stored in self._support_dictionary
        self._set_support_text([
                    ("filters_list",  "Filters list", ""),
            ] )


    # # overwrites the SynedObject method for dealing with list
    def to_dictionary(self):
        """Return an ordered dictionary representation of this block.

        Returns
        -------
        dict
            Keys: CLASS_NAME, filters_list (list of filter dictionaries).
        """
        dict_to_save = OrderedDict()
        dict_to_save.update({"CLASS_NAME":self.__class__.__name__})
        dict_to_save["filters_list"] = [el.to_dictionary() for el in self._filters_list]
        return dict_to_save

    def get_n(self):
        """Return the number of foils in this block.

        Returns
        -------
        int
        """
        return len(self._filters_list)

    def get_item(self, index):
        """Return the foil at the given index.

        Parameters
        ----------
        index : int

        Returns
        -------
        FilterWithDensity
        """
        return self._filters_list[index]

    def get_lists_materials_thicknesses_densities(self, cumulate=False):
        """Return the materials, thicknesses and densities of all foils in this block.

        Parameters
        ----------
        cumulate : bool, optional
            If True, foils sharing the same material and density are merged by
            summing their thicknesses, regardless of their position in the list.
            Order of first appearance is preserved. Default is False.

        Returns
        -------
        materials : list of str
        thicknesses : list of float
            Foil thicknesses in mm.
        densities : list of float
            Foil densities in g/cm³.
        """
        materials   = [f.get_material()  for f in self._filters_list]
        thicknesses = [f.get_thickness() for f in self._filters_list]
        densities   = [f.get_density()   for f in self._filters_list]
        if cumulate:
            seen = {}  # (material, density) -> index in output lists
            cum_mat, cum_thick, cum_dens = [], [], []
            for mat, thick, dens in zip(materials, thicknesses, densities):
                key = (mat, dens)
                if key in seen:
                    cum_thick[seen[key]] += thick
                else:
                    seen[key] = len(cum_mat)
                    cum_mat.append(mat)
                    cum_thick.append(thick)
                    cum_dens.append(dens)
            return cum_mat, cum_thick, cum_dens
        return materials, thicknesses, densities

class FilterBox(SynedObject):
    """A box of attenuator blocks (axes): an ordered list of FilterBlock objects.

    Each block is an independent attenuator unit. The selection state records
    which filter position is active in each block.
    """

    def __init__(self, filter_blocks_list=None):
        """
        Parameters
        ----------
        filter_blocks_list : list of FilterBlock, optional
            Ordered list of attenuator blocks. Defaults to empty list.
        """
        if filter_blocks_list is None:
            self._filter_blocks_list = []
        else:
            self._filter_blocks_list = filter_blocks_list

        self.__selection = [] # to save the status

        # support text containg name of variable, help text and unit. Will be stored in self._support_dictionary
        self._set_support_text([
                    ("filter_blocks_list",  "list of blocks (axes) of filters", ""),
            ] )


    # # overwrites the SynedObject method for dealing with list
    def to_dictionary(self):
        """Return an ordered dictionary representation of this box.

        Returns
        -------
        dict
            Keys: CLASS_NAME, filter_blocks_list (list of block dictionaries).
        """
        dict_to_save = OrderedDict()
        dict_to_save.update({"CLASS_NAME":self.__class__.__name__})
        dict_to_save["filter_blocks_list"] = [el.to_dictionary() for el in self._filter_blocks_list]
        return dict_to_save

    def get_n(self):
        """Return the number of blocks (axes) in this box.

        Returns
        -------
        int
        """
        return len(self._filter_blocks_list)

    def get_item(self, index):
        """Return the FilterBlock at the given index.

        Parameters
        ----------
        index : int

        Returns
        -------
        FilterBlock
        """
        return self._filter_blocks_list[index]

    def get_lists_materials_thicknesses_densities(self, cumulate=False):
        """Return the materials, thicknesses and densities of all foils across all blocks.

        Parameters
        ----------
        cumulate : bool, optional
            If True, foils sharing the same material and density are merged by
            summing their thicknesses globally across all blocks, regardless of
            their position. Order of first appearance is preserved. Default is False.

        Returns
        -------
        materials : list of str
        thicknesses : list of float
            Foil thicknesses in mm.
        densities : list of float
            Foil densities in g/cm³.
        """
        materials, thicknesses, densities = [], [], []
        for block in self._filter_blocks_list:
            m, t, d = block.get_lists_materials_thicknesses_densities()
            materials.extend(m)
            thicknesses.extend(t)
            densities.extend(d)
        if cumulate:
            seen = {}
            cum_mat, cum_thick, cum_dens = [], [], []
            for mat, thick, dens in zip(materials, thicknesses, densities):
                key = (mat, dens)
                if key in seen:
                    cum_thick[seen[key]] += thick
                else:
                    seen[key] = len(cum_mat)
                    cum_mat.append(mat)
                    cum_thick.append(thick)
                    cum_dens.append(dens)
            return cum_mat, cum_thick, cum_dens
        return materials, thicknesses, densities

    def get_selection(self):
        """Return the current filter selection for each block.

        Returns
        -------
        list of int
            Index of the active filter in each block.
        """
        return self.__selection

    def set_selection(self, selection):
        """Set the active filter index for each block.

        The list is clipped to the number of blocks, so passing a longer list
        (e.g. from a widget with more slots than loaded blocks) is safe.

        Parameters
        ----------
        selection : list of int
        """
        self.__selection = selection[:self.get_n()]

if __name__ == "__main__":

    # f1 = FilterWithDensity(name='f1', material='Si', thickness=30e-6)
    # f2 = FilterWithDensity(name='f2', material='W', thickness=30e-6)
    # f3 = FilterWithDensity(name='f3', material='K', thickness=30e-6)
    # f4 = FilterWithDensity(name='f4', material='Cu', thickness=30e-6)
    # f5 = FilterWithDensity(name='f5', material='Ag', thickness=30e-6)
    #
    # bf = FilterBlock(filters_list=[f1,f2,f3,f4])
    #
    # # print(bf.info())
    # # print(bf.to_dictionary())
    # # print(bf.to_json())
    #
    # box = FilterBox(filter_blocks_list=[bf, bf])
    #
    # print(box.to_json(file_name="tmp.json"))

    # from syned.util.json_tools import load_from_json_file
    # from orangecontrib.syned.util.filter_block import FilterBlock, FilterBox
    #
    # tmp = load_from_json_file("tmp.json",
    #                           exec_commands=[
    #                               "from orangecontrib.syned.util.filter_with_density import FilterWithDensity",
    #                               "from orangecontrib.syned.util.filter_block import FilterBlock, FilterBox",
    #                           ])
    #
    # print(tmp.info())

    # create json with suned FilterBox

    if 0:
        import os
        import json
        import orangecanvas.resources as resources
        file_json = os.path.join(resources.package_dirname("orangecontrib.esrf.xoppy.data"), 'bm05_wb_attenuators.json')
        with open(file_json) as att_file:
            att_dic = json.load(att_file)

        n_keys = 0
        keys = []
        for key in att_dic.keys():
            n_keys += 1
            keys.append(key)

        # update combo boxes
        block_list = []
        for i in range(n_keys):
            items = []
            for filter in att_dic[keys[i]].keys():
                item = att_dic[keys[i]][filter]
                f = FilterWithDensity(name=item['name'],
                                      material=item['substance'],
                                      thickness=item['thickness'],
                                      density=item['density'])
                items.append(f)

            block_list.append(FilterBlock(filters_list=items))

        box = FilterBox(filter_blocks_list=block_list)

        print(box.to_json(file_name='tmp.json'))

    # read the syned json file

    if 1:
        from syned.util.json_tools import load_from_json_file
        tmp = load_from_json_file("tmp.json",
                                  exec_commands=(
                                      "from orangecontrib.syned.util.filter_with_density import FilterWithDensity\n"
                                      "from orangecontrib.syned.util.filter_block import FilterBlock, FilterBox"))

        print(tmp.info())

