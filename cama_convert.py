import calendar
import json
import math
import os.path
import shutil
import subprocess
import numpy
# Custom import
from dropbox_connect import DropBox


class CamaConvert:
    def __init__(self, mongo_client):
        file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json")
        with open(file_path) as f:
            config = json.load(f)
            f.close()
        self.BASE_PATH = config["CAMA_BASE_PATH"]
        self.DROPBOX = DropBox()
        self.MONGO_CLIENT = mongo_client
        self.YEAR = None  # the year to evaluate
        self.PRE_PATH = ""  # file path to the pre-restoration modelling results
        self.POST_PATH = ""  # file path to the post-restoration modelling results
        self.TMP_DIR = ""  # directory where the results are stored
        self.LAT = 0
        self.LON = 0
        self.LAT_MAT = [0]
        self.LON_MAT = [0]

    def pos2dis(self, lat1, lon1, lat2, lon2):
        # approximate radius of earth in km
        if abs(lat1) > 90 or abs(lat2) > 90 or abs(lon1) > 360 or abs(lon2) > 360:
            raise Exception("Wrong arguments passed")
        if lon1 < 0:
            lon1 = lon1 + 360
        if lon2 < 0:
            lon2 = lon2 + 360

        r_average = 6374
        deg2rad = math.pi / 180
        lat1 = lat1 * deg2rad
        lon1 = lon1 * deg2rad
        lat2 = lat2 * deg2rad
        lon2 = lon2 * deg2rad
        distance = r_average * math.acos(math.cos(lat1) * math.cos(lat2) * math.cos(lon1 - lon2) + math.sin(lat1) * math.sin(lat2))
        return distance

    def is_number(self, in_string):
        try:
            float(in_string)
            return True
        except ValueError:
            return False

    def set_configuration(self, new_config):
        TMP_DIR = os.path.join(os.getcwd(), "temp")

        if not os.path.exists(TMP_DIR):
            os.makedirs(TMP_DIR)
        if "year" in new_config:
            self.YEAR = new_config["year"]
        if "pre_path" in new_config:
            path = new_config["pre_path"].split("/")
            folder_name = path[1]
            file_name = path[2]
            self.DROPBOX.download_file(folder_name, file_name)
            self.PRE_PATH = os.path.join(os.getcwd(), "temp", folder_name, file_name)
        if "post_path" in new_config:
            path = new_config["post_path"].split("/")
            folder_name = path[1]
            file_name = path[2]
            self.DROPBOX.download_file(folder_name, file_name)
            self.POST_PATH = os.path.join(os.getcwd(), "temp", folder_name, file_name)
        if "lat" in new_config:
            self.LAT = new_config["lat"]
        if "lon" in new_config:
            self.LON = new_config["lon"]

    def init_matrix(self, rows, cols, init_val):
        # noinspection PyUnusedLocal
        return [[init_val for i in range(cols)] for j in range(rows)]

    def days_in_year(self, year):
        if calendar.isleap(year):
            return 366
        return 365

    def coord_to_grid_cell(self, p_lat=0.0, p_lon=0.0):
        if p_lat == 0:
            p_lat = self.LAT
        if p_lon == 0:
            p_lon = self.LON

        lat_baseline = 34.95
        lon_baseline = 104.05
        return math.floor((lat_baseline - p_lat) * 10) * 90 + math.floor(((lon_baseline + p_lon) * 10) + 1)

    def veg_to_manning(self, veg_type=""):
        veg_type = veg_type.lower()
        if veg_type == "crop" or veg_type == "crops":
            return 0.05
        elif veg_type == "pasture" or veg_type == "pastures":
            return 0.05
        elif veg_type == "bush" or veg_type == "bushes":
            return 0.16
        elif veg_type == "tree" or veg_type == "trees":
            return 0.2
        else:
            return None  # not a recognized type of vegetation

    def update_groundwater(self, day1, month1, year1, day2, month2, year2, wetland_loc_multiple, flow_value):
        file_path = os.path.join(self.BASE_PATH, "map", "hamid", "lonlat_vic_op_cmf_ip")
        lon_lat = numpy.loadtxt(file_path)
        file_path = os.path.join(self.BASE_PATH, "inp", "hamid_dates_1915_2011")
        dates = numpy.loadtxt(file_path, dtype=numpy.int32)
        min_lonlat_index_list = []
        # Finding nearest lon_lat to the wetland location
        for wetland_loc in wetland_loc_multiple:
            distance = [self.pos2dis(wetland_loc[0], wetland_loc[1], location[1], location[0]) for location in lon_lat]
            nearest_lon_lat_index = distance.index(min(distance))
            min_lonlat_index_list.append(nearest_lon_lat_index)

        dates_start_idx = numpy.where((dates[:, 0] == year1) & (dates[:, 1] == month1) & (dates[:, 2] == day1))
        dates_end_idx = numpy.where((dates[:, 0] == year2) & (dates[:, 1] == month2) & (dates[:, 2] == day2))
        dates_in_range = dates[dates_start_idx[0][0]: dates_end_idx[0][0] + 1]
        flow = flow_value / len(dates_in_range)
        for cur_date in dates_in_range:
            file_name = "Roff___" + "".join(map(lambda x: str(x).zfill(2), cur_date)) + ".bin"
            file_path = os.path.join(self.BASE_PATH, "inp", "hamid", file_name)
            with open(file_path, "r") as f:
                flood_input = numpy.fromfile(f, dtype=numpy.float32)
                f.close()

            for min_lonlat_index in min_lonlat_index_list:
                flood_input[min_lonlat_index] += flow * 0.0256

            with open(file_path, "w") as f:
                flood_input.tofile(f)
                f.close()

            print("flow updated for ", file_name)

    def delta_max_q_y(self, p_cell=0):
        if not str(self.YEAR).isdigit():
            raise ValueError("No configuration available for this conversion; use 'set_configuration'.")
        if p_cell == 0:
            p_cell = self.coord_to_grid_cell()

        grid_number = p_cell
        day_count = self.days_in_year(self.YEAR)
        flow_denom = 90 * 61

        raw_pre_input = numpy.fromfile(open(self.PRE_PATH, "r"), dtype=numpy.float32)
        raw_post_input = numpy.fromfile(open(self.POST_PATH, "r"), dtype=numpy.float32)
        pre_restore_flow = [0] * day_count
        post_restore_flow = [0] * day_count
        for day in range(day_count):
            input_index = numpy.mod(grid_number, flow_denom) + (flow_denom * day)
            pre_restore_flow[day] = raw_pre_input[input_index - 1]
            post_restore_flow[day] = raw_post_input[input_index - 1]

        post_restore_flow_max = numpy.amax(post_restore_flow)
        # compute the difference between the results, in the week surrounding the annual peak
        max_index = post_restore_flow.index(post_restore_flow_max)
        current_day_range = 1  # always start by looking at the preceding or following day, not the current day itself
        left_index = max_index - current_day_range
        right_index = max_index + current_day_range
        delta_max_result = max(pre_restore_flow[max_index] - post_restore_flow[max_index], 0)
        while left_index >= 0 and right_index < day_count and current_day_range < 6 and \
                (pre_restore_flow[left_index] > post_restore_flow[left_index] or
                 pre_restore_flow[right_index] > post_restore_flow[right_index]):
            left_max = max(pre_restore_flow[left_index] - post_restore_flow[left_index], 0)
            right_max = max(pre_restore_flow[right_index] - post_restore_flow[right_index], 0)
            delta_max_result += left_max + right_max
            current_day_range += 1
            left_index = max_index - current_day_range
            right_index = max_index + current_day_range
        return delta_max_result

    def delta_min_q_y(self, p_cell=0):
        if not str(self.YEAR).isdigit():
            raise ValueError("No configuration available for this conversion; use 'set_configuration'.")
        if p_cell == 0:
            p_cell = self.coord_to_grid_cell()

        grid_number = p_cell
        day_count = self.days_in_year(self.YEAR)
        flow_denom = 90 * 61
        # let's measure the pre-restoration base flow
        raw_input = numpy.fromfile(open(self.PRE_PATH, "r"), dtype=numpy.float32)
        pre_restore_flow = [0] * day_count
        weekly_flow = [0] * (day_count - 6)
        for day in range(day_count):
            input_index = numpy.mod(grid_number, flow_denom) + (flow_denom * day)
            pre_restore_flow[day] = raw_input[input_index - 1]

        for day in range(day_count - 6):
            weekly_flow[day] = sum(pre_restore_flow[day:day + 6])
        week_start = weekly_flow.index(min(weekly_flow))
        pre_avg_min = numpy.average(weekly_flow[week_start:week_start + 6])

        # now we measure the post-restoration base flow (which we expect to have risen)
        raw_input = numpy.fromfile(open(self.POST_PATH, "r"), dtype=numpy.float32)
        post_restore_flow = [0] * day_count
        weekly_flow = [0] * (day_count - 6)
        for day in range(day_count):
            input_index = numpy.mod(grid_number, flow_denom) + (flow_denom * day)
            post_restore_flow[day] = raw_input[input_index - 1]

        for day in range(day_count - 6):
            weekly_flow[day] = sum(post_restore_flow[day:day + 6])
        week_start = weekly_flow.index(min(weekly_flow))
        post_avg_min = numpy.average(weekly_flow[week_start:week_start + 6])

        return post_avg_min - pre_avg_min

    def plot_hydrograph_from_wetlands(self):
        grid_cell = self.coord_to_grid_cell()
        # plot the data after transforming it
        line1 = self.map_input_to_flow(self.PRE_PATH, grid_cell, 0, True)
        line2 = self.map_input_to_flow(self.POST_PATH, grid_cell, 0, True)
        return line1, line2

    def map_input_to_flow(self, file_path, grid_cell, p_year=0, p_clean=False):
        raw_input = numpy.fromfile(open(file_path, "r"), dtype=numpy.float32)
        if p_year == 0:
            p_year = self.YEAR
        if p_clean:
            # ensure that all overly-large values are zeroed out
            for i in range(len(raw_input)):
                if raw_input[i] > 100000:
                    raw_input[i] = 0

        year_days = self.days_in_year(p_year)
        flow = []
        k = 0
        for i in range(year_days):
            k += 1
            idx = (grid_cell % (90 * 61)) + (90 * 61 * i) - 1
            flow.append(raw_input[idx].item())
        return flow

    def build_flow_grids(self):
        # load ancillary data, including reservoir locations and mappings
        file_path = os.path.join(self.BASE_PATH, "res", "nextxy.txt")
        next_xy_raw = numpy.loadtxt(file_path, usecols=range(2))
        next_xx = next_xy_raw[:, 0]
        next_yy = next_xy_raw[:, 1]
        # divvy up the next_xx and next_yy arrays into columns
        # noinspection PyUnusedLocal
        self.LAT_MAT = [[0 for i in range(90)] for j in range(61)]
        # noinspection PyUnusedLocal
        self.LON_MAT = [[0 for i in range(90)] for j in range(61)]
        for ctr in range(1, 62):
            first = ((ctr - 1) * 90) + 1
            second = (ctr * 90)
            self.LON_MAT[ctr - 1] = next_xx[first - 1:second - 1]
            self.LAT_MAT[ctr - 1] = next_yy[first - 1:second - 1]

    def grid_cell_of_wetlands_outlet(self, p_lat=0.0, p_lon=0.0):
        if p_lat == 0:
            p_lat = self.LAT
        if p_lon == 0:
            p_lon = self.LON

        coord_offset = self.coord_to_grid_cell(p_lat, p_lon)

        if len(self.LAT_MAT) == 1 | len(self.LON_MAT) == 1:
            self.build_flow_grids()  # we haven't cached the flow grids yet

        # find the wetlands outlet, and use that to calculate the offset
        xx_temp = int(coord_offset % 90) + 1
        yy_temp = math.floor(coord_offset / 90) + 1
        candidate = int(xx_temp + (yy_temp * 90)) + 1
        return candidate  # and now we finally have a grid_offset that we can use in our main function

    def grid_cell_of_river_mouth(self, p_lat=0.0, p_lon=0.0):
        if p_lat == 0:
            p_lat = self.LAT
        if p_lon == 0:
            p_lon = self.LON

        coord_offset = self.coord_to_grid_cell(p_lat, p_lon)

        if len(self.LAT_MAT) == 1 | len(self.LON_MAT) == 1:
            self.build_flow_grids()  # we haven't cached the flow grids yet

        # find the nearest reservoir, and use that to calculate the offset
        xx_temp = int(coord_offset % 90) + 1
        yy_temp = math.floor(coord_offset / 90) + 1
        found_mouth = False
        candidate = 0
        while not found_mouth:
            candidate = xx_temp + ((yy_temp - 1) * 90)
            results = (int(self.LON_MAT[yy_temp - 1][xx_temp - 1]), int(self.LAT_MAT[yy_temp - 1][xx_temp - 1]))
            xx_temp = results[0]
            yy_temp = results[1]
            if xx_temp == -9999:
                found_mouth = True
        return candidate  # and now we finally have a grid_offset that we can use in our main function

    def grid_cell_of_reservoir(self, p_lat=0.0, p_lon=0.0):
        # fixed reservoir path for server deployment
        if p_lat == 0:
            p_lat = self.LAT
        if p_lon == 0:
            p_lon = self.LON

        coord_offset = self.coord_to_grid_cell(p_lat, p_lon)

        # note: reservoir locations are [lon,lat], in contradiction of ISO 6709
        file_path = os.path.join(self.BASE_PATH, "res", "Reservoir_xy.txt")
        reservoir_raw = numpy.loadtxt(file_path, usecols=range(2))
        reservoir_offset = []
        for row in range(len(reservoir_raw)):
            reservoir_offset.append(self.coord_to_grid_cell(reservoir_raw[row][1], reservoir_raw[row][0]))

        if len(self.LAT_MAT) == 1 | len(self.LON_MAT) == 1:
            self.build_flow_grids()  # we haven't cached the flow grids yet

        # find the nearest reservoir, and use that to calculate the offset
        xx_temp = int(coord_offset % 90) + 1
        yy_temp = math.floor(coord_offset / 90) + 1
        found_reservoir = False
        candidate = 0
        while not found_reservoir:
            candidate = xx_temp + ((yy_temp - 1) * 90)
            if candidate not in reservoir_offset:
                results = (int(self.LON_MAT[yy_temp - 1][xx_temp - 1]), int(self.LAT_MAT[yy_temp - 1][xx_temp - 1]))
                xx_temp = results[0]
                yy_temp = results[1]
            else:
                found_reservoir = True
        return candidate  # and now we finally have a grid_offset that we can use in our main function

    def plot_hydrograph_nearest_reservoir(self, p_lat=0.0, p_lon=0.0):
        if p_lat == 0:
            p_lat = self.LAT
        if p_lon == 0:
            p_lon = self.LON

        grid_offset = self.grid_cell_of_reservoir(p_lat, p_lon)
        line1 = self.map_input_to_flow(self.PRE_PATH, grid_offset, self.YEAR, True)
        line2 = self.map_input_to_flow(self.POST_PATH, grid_offset, self.YEAR, True)
        return line1, line2

    def delta_max_all(self):
        # run three times to compare:
        line1 = self.delta_max_q_y(self.grid_cell_of_wetlands_outlet()) * 3600 * 24  # 1) the wetlands outlet
        line2 = self.delta_max_q_y(self.grid_cell_of_reservoir()) * 3600 * 24  # 2) the nearest reservoir
        line3 = self.delta_max_q_y(self.grid_cell_of_river_mouth()) * 3600 * 24  # 3) the river mouth
        return line1, line2, line3

    def config_cama(self, model, s_year, e_year):
        # this function is for configuring the post-restoration ONLY
        # this is because all the pre-restoration results have been pre-computed
        if e_year > 2011:
            e_year = 2011
        if s_year < 1916:
            s_year = 1916
        try:
            file_name = "hamid_<MODEL>_template.sh".replace("<MODEL>", model)
            file_path = os.path.join(self.BASE_PATH, "gosh", file_name)
            with open(file_path, "r") as file:
                cama_config = file.read()
                file.close()
            cama_config = cama_config.replace("<SYEAR>", str(s_year))
            cama_config = cama_config.replace("<EYEAR>", str(e_year))
            file_path = os.path.join(self.BASE_PATH, "gosh", "hamid_<MODEL>.sh".replace("<MODEL>", model))
            with open(file_path, "w") as file:
                file.write(cama_config)
                file.close()
        except IOError as e:
            return "IOError:" + str(e)
        return "Success"

    def peak_flow(self, folder_name, p_lat=0.0, p_lon=0.0, floodpeak=10):
        """Returns a year which has maximal difference / minimum flow(working)"""
        if p_lat == 0:
            p_lat = self.LAT
        if p_lon == 0:
            p_lon = self.LON

        grid_cell = self.coord_to_grid_cell(p_lat, p_lon)
        # grid_cell = 3674  # DEBUG *****

        # what kind of flood peak window are we using
        if floodpeak == 10:
            logbase = numpy.log(numpy.log(10 / 9))  # 10-year flood
        elif floodpeak == 100:
            logbase = numpy.log(numpy.log(100 / 99))  # 100-year flood
        else:
            return 0

        # for each year in the range
        year_peaks = [0] * 97
        for i in range(1916, 2012):
            # Downloading the file from dropbox
            self.DROPBOX.download_file(folder_name, "outflw" + str(i) + ".bin")
            output_file = os.path.join(os.getcwd(), "temp", folder_name, "outflw" + str(i) + ".bin")
            year_flow = self.map_input_to_flow(output_file, grid_cell, i, False)
            year_peaks[i - 1916] = max(year_flow)

        # calculate the gumbel distribution
        flow_mean = numpy.nanmean(year_peaks)
        flow_sdev = numpy.nanstd(year_peaks, ddof=1)  # ddof=1 emulates matlab's bias-compensation default
        kt_gumbel = ((-6 ** 0.5) / 3.14) * (0.5772 + logbase)
        xt_gumbel = flow_mean + (kt_gumbel * flow_sdev)

        # find the year with the maximal difference / minimum flow
        curr_year = 1915
        min_year = 0
        min_val = float("inf")
        for val in year_peaks:
            curr_year += 1
            this_flow = numpy.abs(xt_gumbel - val)
            if this_flow < min_val:
                min_year = curr_year
                min_val = this_flow
        return min_year

    def run_cama_pre(self, s_year, e_year, folder_name):
        # expects cama to be pre-configured
        try:
            folder_collection = self.MONGO_CLIENT["output"]["folder"]
            # Check if there is no existing model running
            folder_list = list(folder_collection.find({"status": "running"}))
            if len(folder_list) > 0:
                return "there is model in execution, pls retry after sometime"

            # Check if there exist no such document with the folder_name in the DB and in dropbox
            folder = folder_collection.find_one({"folder_name": folder_name})
            if folder is None and not self.DROPBOX.folder_exists(folder_name):
                metadata = {"start_year": s_year, "end_year": e_year}
                new_file = dict({"model": "preflow", "status": "running", "folder_name": folder_name, "metadata": metadata})
                # Creating the folder in dropbox, and in database
                folder_collection.insert_one(new_file)
                self.DROPBOX.create_folder(folder_name)

                # Config the Cama to run from s_year to e_year
                self.config_cama("pre", s_year, e_year)

                # Starting the execution of the model
                subprocess.Popen("sudo " + self.BASE_PATH + "/gosh/hamid_pre.sh", shell=True)
            else:
                raise Exception("folder name already exists")
        except Exception as e:
            raise e
        return "Execution queued"

    def run_cama_post(self, start_day, start_month, start_year, end_day, end_month, end_year, wetland_loc_multiple, flow_value, folder_name):
        try:
            folder_collection = self.MONGO_CLIENT["output"]["folder"]
            # Check if there is no existing model running
            folder_list = list(folder_collection.find({"status": "running"}))
            if len(folder_list) > 0:
                return "there is model in execution, pls retry after sometime"

            # Check if there exist no such document with the folder_name in the DB and in dropbox
            folder = folder_collection.find_one({"folder_name": folder_name})
            if folder is None and not self.DROPBOX.folder_exists(folder_name):
                metadata = {"start_day": start_day, "start_month": start_month, "start_year": start_year, "end_day": end_day, "end_month": end_month,
                            "end_year": end_year, "flow_value": flow_value, "wetland_loc_multiple": wetland_loc_multiple}
                new_folder = dict({"model": "postflow", "status": "running", "folder_name": folder_name, "metadata": metadata})
                # Creating the folder in dropbox, and in database
                folder_collection.insert_one(new_folder)
                self.DROPBOX.create_folder(folder_name)

                # Config the Cama to run from s_year to e_year
                self.config_cama("post", start_year - 1, end_year)

                # Update the groundwater in the input
                self.update_groundwater(start_day, start_month, start_year, end_day, end_month, end_year, wetland_loc_multiple, flow_value)

                # Starting the execution of the model
                subprocess.Popen("sudo " + self.BASE_PATH + "/gosh/hamid_post.sh", shell=True)
            else:
                raise Exception("folder name already exists")
        except Exception as e:
            raise e
        return "Execution queued"

    def clean_up(self):
        """Deleting all content of the temp folder"""
        directory = os.path.join(os.getcwd(), "temp")
        if os.path.exists(directory) and os.path.isdir(directory):
            shutil.rmtree(directory)

    def cama_status(self, folder_name):
        try:
            folder_collection = self.MONGO_CLIENT["output"]["folder"]
            folder = folder_collection.find_one({"folder_name": folder_name})
            if folder is None:
                return "Record doesn't exist"
            else:
                return folder["status"]
        except Exception as e:
            raise e

    def remove_output_folder(self, folder_name):
        folder_collection = self.MONGO_CLIENT["output"]["folder"]
        folder = folder_collection.find_one({"folder_name": folder_name})
        if folder is None and not self.DROPBOX.folder_exists(folder_name):
            raise Exception("unable to delete the folder")
        if folder is not None:
            folder_collection.delete_one({"_id": folder["_id"]})
        if self.DROPBOX.folder_exists(folder_name):
            self.DROPBOX.delete_folder(folder_name)
        return "Deletion Successful"

    def compare_flow(self):
        file_path = os.path.join(self.BASE_PATH, "map", "hamid", "lonlat")
        lon_lat = numpy.loadtxt(file_path)
        no_of_lon_lat = lon_lat.shape[0]
        no_of_days = self.days_in_year(self.YEAR)
        # Finding nearest lon_lat to the wetland location
        distance = [self.pos2dis(self.LAT, self.LON, location[1], location[0]) for location in lon_lat]
        grid_cell = distance.index(min(distance))

        # plotting preflow
        preflow = []
        with open(self.PRE_PATH, "r") as f:
            outflow = numpy.fromfile(f, dtype=numpy.float32)
            f.close()

        # ensure that all overly-large values are zeroed out
        for i in range(len(outflow)):
            if outflow[i] > 100000:
                outflow[i] = 0

        for i in range(0, no_of_lon_lat):
            idx = i
            flow = []
            for day in range(1, no_of_days + 1):
                flow.append(outflow[idx])
                idx += no_of_lon_lat
            preflow.append(flow)

        preflow = numpy.asarray(preflow)

        # plotting the postflow
        postflow = []
        with open(self.POST_PATH, "r") as f:
            outflow = numpy.fromfile(f, dtype=numpy.float32)
            f.close()

        # ensure that all overly-large values are zeroed out
        for i in range(len(outflow)):
            if outflow[i] > 100000:
                outflow[i] = 0

        for i in range(0, no_of_lon_lat):
            idx = i
            flow = []
            for day in range(1, no_of_days + 1):
                flow.append(outflow[idx])
                idx += no_of_lon_lat
            postflow.append(flow)

        postflow = numpy.asarray(postflow)

        # Generating dates
        file_path = os.path.join(self.BASE_PATH, "inp", "hamid_dates_1915_2011")
        dates = numpy.loadtxt(file_path, dtype=numpy.int32)
        dates_in_range = dates[dates[:, 0] == self.YEAR]
        data = numpy.column_stack([dates_in_range, preflow[grid_cell] * 35.31, postflow[grid_cell] * 35.31])
        return data.tolist()

    def do_request(self, p_request_json):
        try:
            if p_request_json["request"] == "plot_hydrograph_from_wetlands" or p_request_json["request"] == "plot_hydrograph_nearest_reservoir" or \
                    p_request_json["request"] == "plot_hydrograph_deltas" or p_request_json["request"] == "plot_compare_flow":
                # startup and configuration
                config = dict()
                config["pre_path"] = p_request_json["pre_path"]
                config["post_path"] = p_request_json["post_path"]
                config["year"] = int(p_request_json["year"])
                config["lat"] = float(p_request_json["lat"])
                config["lon"] = float(p_request_json["lon"])
                self.set_configuration(config)

            result = None
            if p_request_json["request"] == "plot_hydrograph_from_wetlands":
                result = self.plot_hydrograph_from_wetlands()
            elif p_request_json["request"] == "plot_hydrograph_nearest_reservoir":
                result = self.plot_hydrograph_nearest_reservoir(p_request_json["lat"], p_request_json["lon"])
            elif p_request_json["request"] == "peak_flow":
                result = self.peak_flow(p_request_json["folder_name"], p_request_json["lat"], p_request_json["lon"], p_request_json["return_period"])
            elif p_request_json["request"] == "plot_hydrograph_deltas":
                result = self.delta_max_all()
            elif p_request_json["request"] == "veg_lookup":
                result = self.veg_to_manning(p_request_json["veg_type"])
            elif p_request_json["request"] == "coord_to_grid":
                result = self.coord_to_grid_cell(p_request_json["lat"], p_request_json["lon"])
            elif p_request_json["request"] == "update_manning":
                result = dict()
                self.update_manning(p_request_json["lat"], p_request_json["lon"], p_request_json["riv_pre"], p_request_json["riv_post"],
                                    p_request_json["fld_pre"], p_request_json["fld_post"], p_request_json["size_wetland"])
                result["succeeded"] = True
            elif p_request_json["request"] == "cama_status":
                result = dict()
                message = self.cama_status(p_request_json["folder_name"])
                result["message"] = message
            elif p_request_json["request"] == "cama_run_pre":
                result = dict()
                message = self.run_cama_pre(p_request_json["start_year"], p_request_json["end_year"], p_request_json["folder_name"])
                result["message"] = message
            elif p_request_json["request"] == "cama_run_post":
                result = dict()
                message = self.run_cama_post(p_request_json["start_day"], p_request_json["start_month"], p_request_json["start_year"],
                                             p_request_json["end_day"], p_request_json["end_month"], p_request_json["end_year"],
                                             p_request_json["wetland_loc_multiple"], p_request_json["flow_value"], p_request_json["folder_name"])
                result["message"] = message
            elif p_request_json["request"] == "remove_output_folder":
                result = dict()
                message = self.remove_output_folder(p_request_json["folder_name"])
                result["message"] = message
            elif p_request_json["request"] == "plot_compare_flow":
                result = self.compare_flow()
            else:
                print("Invalid API request: " + p_request_json["request"])  # no valid API request

            # Deleting the temp folder
            self.clean_up()

            if result is not None:
                return json.dumps(result)  # this is where the data actually is sent back to the API
        except Exception as e:
            raise e
