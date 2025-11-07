#
# FilterBlock contains a list of Filters
# FilterBox contains a list of FilterBlock
#

from orangecontrib.esrf.syned.util.syned_filter_with_density import FilterWithDensity

from syned.syned_object import SynedObject
from collections import OrderedDict

class FilterBlock(SynedObject):
    def __init__(self, filters_list=None):
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
        """
        Returns a dictionary with the object fields.

        Returns
        -------
        dict
            A dictionary with the data.

        """
        dict_to_save = OrderedDict()
        dict_to_save.update({"CLASS_NAME":self.__class__.__name__})
        dict_to_save["filters_list"] = [el.to_dictionary() for el in self._filters_list]
        return dict_to_save

    def get_n(self):
        return len(self._filters_list)

    def get_item(self, index):
        return self._filters_list[index]

class FilterBox(SynedObject):
    def __init__(self, filter_blocks_list=None):
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
        """
        Returns a dictionary with the object fields.

        Returns
        -------
        dict
            A dictionary with the data.

        """
        dict_to_save = OrderedDict()
        dict_to_save.update({"CLASS_NAME":self.__class__.__name__})
        dict_to_save["filter_blocks_list"] = [el.to_dictionary() for el in self._filter_blocks_list]
        return dict_to_save

    def get_n(self):
        return len(self._filter_blocks_list)

    def get_item(self, index):
        return self._filter_blocks_list[index]

    def get_selection(self):
        return self.__selection

    def set_selection(self, selection):
        self.__selection = selection

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
                                      density=item['thickness'])
                items.append(f)

            block_list.append(FilterBlock(filters_list=items))

        box = FilterBox(filter_blocks_list=block_list)

        print(box.to_json(file_name='tmp.json'))

    # read the syned json file

    if 1:
        from syned.util.json_tools import load_from_json_file
        tmp = load_from_json_file("tmp.json",
                                  exec_commands=[
                                      "from orangecontrib.syned.util.filter_with_density import FilterWithDensity",
                                      "from orangecontrib.syned.util.filter_block import FilterBlock, FilterBox",
                                  ])

        print(tmp.info())

