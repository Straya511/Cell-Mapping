from helpers import log, convert
from datetime import datetime
from pathlib import Path
import zipfile
import folium
import branca
import config
import regex
import time
import csv


class Point:
    def __init__(self, raw_point):
        """Class Structure for data points returned by CellMapper

        Args:
            raw_point (_csv._reader): Datapoint from CSV formatted file
        """
        self.latitude = convert(raw_point[0], float)
        self.longitude = convert(raw_point[1], float)
        self.altitude = convert(raw_point[2], int)
        self.mcc = convert(raw_point[3], int)
        self.mnc = convert(raw_point[4], int)
        self.tac = convert(raw_point[5], int)
        self.cell_id = convert(raw_point[6], int)
        self.raw_signal_strength = convert(raw_point[7], int)
        self.signal_strength = abs(self.raw_signal_strength)
        self.signal_type = convert(raw_point[8], str)
        self.signal_subtype = convert(raw_point[9], str)
        self.rfcn = convert(raw_point[10], int)
        self.lte_physical_id = convert(raw_point[11], int)

    def __repr__(self):
        return str(self.as_list())
    
    def as_list(self):
        return [
            self.latitude,
            self.longitude,
            self.altitude,
            self.mcc,
            self.mnc,
            self.tac,
            self.cell_id,
            self.raw_signal_strength,
            self.signal_strength,
            self.signal_type,
            self.signal_subtype,
            self.rfcn,
            self.lte_physical_id
        ]
    
    def get_coords(self, round_to: int or tuple(int, int) = None) -> tuple[float, float]:
        if round_to is None:
            return (self.latitude, self.longitude)

        if isinstance(round_to, int):
            rounded_lat = round(self.latitude, round_to)
            rounded_long = round(self.longitude, round_to)
            return (rounded_lat, rounded_long)

        elif isinstance(round_to, tuple):
            rounded_lat = round(self.latitude, round_to[0])
            rounded_long = round(self.longitude, round_to[1])
            return (rounded_lat, rounded_long)

        else:
            return (self.latitude, self.longitude)


program_start_time = time.time()
log("Loading CSV Data")
total_points = 0
time_start = time.time()
map_data: list[Point] = []
data_directory = "data/raw_data"
pathlist = Path(data_directory).rglob('*.csv')
for file_path in pathlist:
    with open(file_path) as csv_file:
        csv_data = csv.reader(csv_file)

        previous_coords = []
        for point in csv_data:
            total_points += 1
            data_point = Point(point)
            current_coords = data_point.get_coords(3)
            if current_coords in previous_coords:
                continue
            else:
                previous_coords.append(current_coords)

            map_data.append(data_point)

log(f"CSV loaded into map_data | Total Points: {total_points} | 'Unique' Points Loaded: {len(map_data)}")
log(f"Time taken to Load CSV: {time.time() - time_start}")


if config.Optimisation.distance_prune:
    log("(Optimisation) Starting Distance Prune")
    points_start = len(map_data)
    start_time = time.time()
    points_removed = 0
    points_checked = 0

    min_difference = 9e-4
    min_difference_sqrd = min_difference ** 2
    map_data.sort(key=lambda x: x.latitude)
    for start_index, pointA in enumerate(map_data):
        cutoff = pointA.latitude + min_difference
        points_removed_inner = 0

        for pointB_index, pointB in enumerate(map_data[start_index + 1:]):
            if pointB.latitude > cutoff:
                break

            lat_diff = pointA.latitude - pointB.latitude
            long_diff = pointA.longitude - pointB.longitude
            distance = lat_diff * lat_diff + long_diff * long_diff
            points_checked += 1
            if distance < min_difference_sqrd:
                calculated_index = start_index + pointB_index - points_removed_inner + 1
                map_data.pop(calculated_index)
                points_removed_inner += 1
                points_removed += 1

    log(f"(Optimisation) Distance Prune Complete: {time.time() - start_time} | Points Removed: {points_removed}/{points_start} | Points Checked: {points_checked}")


total_points = len(map_data)
mapit = folium.Map(location=config.Map_Configuration.location,
                   zoom_start=config.Map_Configuration.zoom,
                   prefer_canvas=config.Optimisation.folium_performance_mode)
log("Map Initialised")

log("Creating Colourmap")
#TODO Altitude map
colours = ["green", "yellow", "orange", "red"]
signal_strength_steps = [80, 90, 110, 120]
colourMap = branca.colormap.StepColormap(colors=colours,
                                         index=signal_strength_steps
                                         ).to_linear()
colourMap.caption = f"Low Signal Cutoff: {config.Map_Configuration.low_signal_cutoff} | Total Points: {total_points}"
mapit.add_child(colourMap)
log("Generated Colourmap")


log("Applying datapoints to map")
for point in map_data:
    colour = colourMap(point.signal_strength)
    #TODO Altitude map

    if point.signal_strength >= config.Map_Configuration.low_signal_cutoff:
        colour = "black"
    
    if point.signal_type != "LTE":
        colour = "purple"
    
    folium.Circle(location=point.get_coords(round_to=6),
                  radius=config.Map_Configuration.circle_radius,
                  color=colour,
                  fillColor=colour,
                  opacity=1,
                  fillOpacity=1,
                  ).add_to(mapit)

log(f"Generated Map | Points Added: {len(map_data)}")

input()
if config.Optimisation.cleanup_maps:
    data_directory = "maps"
    pathlist = Path(data_directory).rglob('*.html')
    for file in pathlist:
        with zipfile.ZipFile(f"{data_directory}/{file.stem}.zip", "w", zipfile.ZIP_DEFLATED) as zipped_file:
            zipped_file.write(file, file.name)
        file.unlink(missing_ok=True)

    log("Zipped old map(s)")


log("Saving Map")
dateish = datetime.now().replace(microsecond=0).isoformat().replace("-", "").replace(":", "")
file_name = f"{dateish}_{total_points}_{config.Map_Configuration.include_popups}_{config.Map_Configuration.low_signal_cutoff}"
mapit.save(f"maps/{file_name}.html")
log("Saved map")


if config.Optimisation.trim_html_file:
    log("(Optimisation) Trimming HTML File")
    with open(f"maps/{file_name}.html") as html_file:
        html_text = html_file.read()
        strings_to_prune = [' "dashArray": null, "dashOffset": null,',
                         '"bubblingMouseEvents": true, ',
                         ' "fillRule": "evenodd",',
                         ' "fillColor": "#[\w\d]{8}",',
                         ' "opacity": 1,',
                         ' "lineJoin": "round",',
                         "\n",
                         "\t",
                         "\r"
                         ]
        for string in strings_to_prune:
            html_text = regex.sub(string, "", html_text)
            log(f"(Optimisation) Removed Strings Matching: \{string}")

        with open(f"maps/{file_name}.html", "w") as new_file:
            new_file.write(html_text)
        log("(Optimisation) Wrote trimmed html successfully")


program_finish_date = time.time()
program_runtime = program_finish_date - program_start_time
log(f"Program Runtime: {program_runtime}")
