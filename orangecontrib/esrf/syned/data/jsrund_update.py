#!/usr/bin/env python
"""
Python equivalent of the "Save All ..." button of jsrund (Storage Ring Undulators report,
JIdConfig.jar, jidconfig.undulatorsReporting): reads the undulator properties from the Tango
database and writes the same CSV file, without GUI and without Java.

Requires PyTango (pip install pytango).

Usage:
    python jsrund_save.py [output.csv] [--show-carriage] [--tango-host acs:10000]
    (default output: jsrund_YYYYMMDD_HHMMSS.csv in the current directory)

Logic (as in JIdConfig 11.5):
  - devices of class "Undulator" of all the instances of the server "Undulator"
  - for each undulator: CarriageDevName, UndulatorName, Period, Length, PowerParameters (A0..A6);
    from the carriage: HardwareType, SrPosition; MinPosition from the gap device (carriage -> gap)
  - SrPosition = straight section + 0.1 * position (1: UpStream, 2: Middle, 3: DownStream)
  - Length not defined: 1600 (JIdConfig default)
  - undulators with SrPosition undefined, < 1 or >= 33, and straight section 8, are ignored
"""
import argparse
import datetime
import decimal
import math
import os

import tango

IGNORE_IDS = (8,)
POSITION_LABELS = ("", "UpStream", "Middle", "DownStream")
COL_HEADERS = ("Straight Section", "Name", "Location", "Period [mm]", "Length [mm]", "Gap min. [mm]",
               "A(0)", "A(1)", "A(2)", "A(3)", "A(4)", "A(5)", "A(6)")
COL_WITH_CARR_HEADERS = COL_HEADERS[:3] + ("Carriage", "HW Type") + COL_HEADERS[3:]
FORMATS = ((4, 1), (7, 2), (7, 3), (7, 4))  # (width, decimals) of period, length, gap min, power parameters
DEFAULT_LENGTH = 1600.0  # default Length of the undulators in JIdConfig (UndulatorProperties)
N_POWER_PARAMETERS = 7
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class TangoDb:
    """Property access with the same error handling as jidconfig.tangodb.TangoDbUtil."""

    def __init__(self, tango_host):
        host, port = tango_host.split(":")
        self.db = tango.Database(host, int(port))

    def values(self, device, prop):
        if device is None: return None
        try:
            return list(self.db.get_device_property(device, prop)[prop])
        except Exception:
            return None

    def string(self, device, prop):  # None if not found
        v = self.values(device, prop)
        return None if v is None else "\n".join(v)

    def double(self, device, prop):  # NaN if not found or not a number
        try:
            return float(self.values(device, prop)[0])
        except Exception:
            return math.nan

    def doubles(self, device, prop):  # None if not found or not numbers
        try:
            return [float(x) for x in self.values(device, prop)]
        except Exception:
            return None


class UndulatorStatus:

    def __init__(self, tdb, device):
        self.device = device
        self.carr_dev_name = tdb.string(device, "CarriageDevName")
        self.carr_hw_type = tdb.string(self.carr_dev_name, "HardwareType")
        gap_dev_name = None if self.carr_dev_name is None else \
            self.carr_dev_name.lower().replace("carriage", "gap")
        self.sr_position = tdb.double(self.carr_dev_name, "SrPosition")
        self.straight_section, self.ss_position = 0, 0
        if not math.isnan(self.sr_position):
            self.straight_section = int(self.sr_position)
            self.ss_position = int(self.sr_position * 10.0) - self.straight_section * 10
        self.name = tdb.string(device, "UndulatorName")
        self.period = tdb.double(device, "Period")
        self.length = tdb.double(device, "Length")
        if math.isnan(self.length): self.length = DEFAULT_LENGTH
        self.power_parameters = [math.nan] * N_POWER_PARAMETERS
        values = tdb.doubles(device, "PowerParameters")
        if values is not None:
            for i, v in enumerate(values[:N_POWER_PARAMETERS]):
                self.power_parameters[i] = v
        self.gap_min = tdb.double(gap_dev_name, "MinPosition")

    @staticmethod
    def _str(value):  # Java null -> "null" (as in the Java string concatenation)
        return "null" if value is None else value

    @staticmethod
    def _carriage_name(name):  # "domain/family/member" -> "family"
        if name is None: return None
        i, j = name.find("/") + 1, name.rfind("/")
        if not (0 <= i < len(name)) or not (0 <= j < len(name)): return None
        return name[i:j]

    @staticmethod
    def _double(index, value):
        # as Java String.format: rounding HALF_UP of the shortest decimal representation of the double
        # (e.g. 0.18045 -> 0.1805, where Python "%7.4f" gives 0.1804); undefined value -> " "
        if math.isnan(value): return " "
        width, decimals = FORMATS[index]
        rounded = decimal.Decimal(repr(value)).quantize(decimal.Decimal(1).scaleb(-decimals), decimal.ROUND_HALF_UP)
        return format(rounded, "%d.%df" % (width, decimals))

    def report_string(self, show_carriage=False):
        s = "%d,%s,%s," % (self.straight_section, self._str(self.name), POSITION_LABELS[self.ss_position])
        if show_carriage:
            s += self._str(self._carriage_name(self.carr_dev_name)) + ","
            s += self._str(self.carr_hw_type) + ","
        s += self._double(0, self.period) + ","
        s += self._double(1, self.length) + ","
        s += self._double(2, self.gap_min) + ","
        for p in self.power_parameters:
            s += self._double(3, p) + ","
        return s


def get_undulators(tdb):
    """Dictionary {"idNN": [UndulatorStatus sorted by position in the straight section]}."""
    und_map = {}
    try:
        instances = tdb.db.get_instance_name_list("undulator")
    except Exception:
        instances = []
    for instance in instances:
        for device in tdb.db.get_device_name("Undulator/" + instance, "Undulator"):
            und = UndulatorStatus(tdb, device)
            pos = und.sr_position
            if math.isnan(pos) or pos < 1 or pos >= 33: continue
            if und.straight_section in IGNORE_IDS: continue
            und_map.setdefault("id%02d" % und.straight_section, []).append(und)
    for undulators in und_map.values():
        undulators.sort(key=lambda u: u.ss_position)  # stable, as Java Collections.sort
    return und_map


def write_report(filename, und_map, show_carriage=False):
    headers = COL_WITH_CARR_HEADERS if show_carriage else COL_HEADERS
    now = datetime.datetime.now()
    with open(filename, "w") as f:
        f.write("%02d-%s-%02d , %s\n" % (now.day, MONTHS[now.month - 1], now.year % 100, now.strftime("%H:%M:%S")))
        f.write("," * len(headers) + "\n")
        f.write("".join(h + "," for h in headers) + "\n")
        for key in sorted(und_map):
            for und in und_map[key]:
                f.write(und.report_string(show_carriage) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Storage Ring undulators report (as "Save All ..." of jsrund)')
    parser.add_argument("output", nargs="?",
                        default=datetime.datetime.now().strftime("jsrund_%Y%m%d_%H%M%S.csv"))
    parser.add_argument("--show-carriage", "-ShowCarriage", action="store_true",
                        help="add the Carriage and HW Type columns (as jsrund -ShowCarriage)")
    parser.add_argument("--tango-host", default="acs:10000", help="Tango database (default acs:10000, as jsrund)")
    args = parser.parse_args()

    und_map = get_undulators(TangoDb(args.tango_host))
    write_report(args.output, und_map, show_carriage=args.show_carriage)
    print("File written: %s (%d undulators)" % (os.path.abspath(args.output), sum(len(v) for v in und_map.values())))
