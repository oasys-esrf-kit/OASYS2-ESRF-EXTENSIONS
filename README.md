# OASYS2-ESRF-Extensions
OASYS2 extensions for the ESRF

This repository contains extensions to Oasys developed at ESRF. 

## Install as user

To install the add-on as user: 

+ In the Oasys window, open "Options->Add-ons..."
+ click the button "Add more" and enter "OASYS2-ESRF-Extensions". You will see a new entry "ESRFExtensions" in the add-on list. Check it and click "OK"
+ Restart Oasys.

![addon menu](https://github.com/oasys-esrf-kit/OASYS2-ESRF-Extensions/blob/main/images/image2.png "addon menu")


Once it is installed, it should populate the widget bar on the side.

![side menu](https://github.com/oasys-esrf-kit/OASYS2-ESRF-Extensions/blob/main/images/image1.png "side menu")


## Install as developper

To install it as developper, download it from github:
```
git clone  https://github.com/oasys-esrf-kit/OASYS2-ESRF-Extensions
cd OASYS2-ESRF-Extensions
```

Then link the source code to your Oasys python (note that you must use the python that Oasys uses):  
```
python -m pip install -e . --no-deps --no-binary :all:
```

When restarting Oasys, you will see the ESRF addons there.

## Upload new version to the pypi server

First create a new version using your developper installation. Do not forget to increment the version number in setup.py

+ Then run:

```
python setup.py sdist
```

+ Followed by:

```
python -m twine upload dist/OASYS2-ESRF-Extensions-X.X.X.tar.gz
```

You need an account in pypi.org and be authorized in https://pypi.org/project/OASYS2-ESRF-Extensions/
