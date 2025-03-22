# Dummy implementation of the spool manager responsible of gathering data from
# spool RFID tag and spool older weight sensor.
import math
class SpoolManager():
    def __init__(self):
        self.spool_present = False
        self.tag_data = {}
        self.update()

    def update(self):
        tag_data = {
            "Tag version": 1000,
            "Filament Manufacturer": "eSUN filament",
            "Material name": "ASA",
            "Color Name": "Polar White",
            "Diameter": 1750, #um
            "Weight (nominal)": 1000, #grams
            "Print Temp (C)": 210,
            "Bed Temp (C)": 120,
            "Density": 1020, #kg/m3
            "Color Hex": 0xeef4f4, #rrggbb
            "Filament weight (measured)": 430, #grams
            "Filament length (measured)": 0 #meters
        }
        cross_section=math.pi * pow(tag_data["Diameter"]*1e-6,2)/4
        length= (tag_data["Filament weight (measured)"]/1000)/(tag_data["Density"]*cross_section)
        tag_data["Filament length (measured)"]=length
        self.tag_data=tag_data
