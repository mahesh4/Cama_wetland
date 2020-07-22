from flask import Flask, request, abort
import geojson
import json
from shapely.geometry import MultiPolygon, Polygon
from cama_convert import CamaConvert
from db_connect import DbConnect
from flask import g
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'mongodb'):
        db = DbConnect()
        db.connect_db()
        g.mongodb = db
    return g.mongodb.get_connection()


@app.teardown_appcontext
def close_db(error):
    db = g.pop('mongodb', None)
    if db is not None:
        db.disconnect_db()


@app.route('/')
def index():
    response = {
        'message': 'This service provided by the Center for Assured and Scalable Data Engineering, Arizona State '
                   'University. '
    }
    return response


@app.route('/to_geojson', methods=['POST'])
def to_geojson():
    try:
        request_data = request.get_json()
        input = request_data.operationalLayers[3].featureCollection.layers[0].featureSet.features
        coord_set = [x["geometry"] for x in input]
        polygon_list = [Polygon(cc) for cc in coord_set]
        multipolygon = MultiPolygon(polygon_list)
        response = geojson.Feature(geometry=geojson.MultiPolygon(coord_set))
        response["bbox"] = multipolygon.bounds
        return json.dumps(response)
    except Exception as e:
        abort(400, e)


@app.route('/to_arcgis', methods=['POST'])
def to_arcgis():
    try:
        request_data = request.get_json()
        response = geojson.Feature(geometry=geojson.MultiPolygon(request_data))
        return json.dumps(response)
    except Exception as e:
        abort(400, e)


@app.route("/wetland_flow", methods=["POST"])
def wetland_flow():
    try:
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        request_data = request.get_json()
        mandatory_keys = ["pre_path", "post_path", "year", "lat", "lon"]
        numeric_keys = ["lat", "lon", "year"]
        given_keys = request_data.keys()
        for this_key in mandatory_keys:
            if this_key not in given_keys:
                abort(400, "Missing required input key: " + this_key)

        for this_key in numeric_keys:
            if not cama.is_number(request_data[this_key]):
                abort(400, "Expected number, received: " + this_key + "=" + request_data[this_key])

        request_data["request"] = "plot_hydrograph_from_wetlands"
        response = cama.do_request(request_data)
        return response
    except Exception as e:
        abort(500, e)


@app.route("/reservoir_flow", methods=["POST"])
def reservoir_flow():
    try:
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        request_data = request.get_json()
        mandatory_keys = ["pre_path", "post_path", "year", "lat", "lon"]
        numeric_keys = ["lat", "lon", "year"]
        given_keys = request_data.keys()
        for this_key in mandatory_keys:
            if this_key not in given_keys:
                abort(400, "Missing required input key: " + this_key)

        for this_key in numeric_keys:
            if not cama.is_number(request_data[this_key]):
                abort(400, "Expected number, received: " + this_key + "=" + request_data[this_key])

        request_data["request"] = "plot_hydrograph_nearest_reservoir"
        response = cama.do_request(request_data)
        return response
    except Exception as e:
        abort(500, e)


@app.route("/comparative_flow", methods=["POST"])
def comparative_flow():
    try:
        request_data = request.get_json()
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        mandatory_keys = ["pre_path", "post_path", "year", "lat", "lon", "return_period"]
        numeric_keys = ["lat", "lon", "year", "return_period"]
        given_keys = request_data.keys()
        for this_key in mandatory_keys:
            if this_key not in given_keys:
                abort(400, "Missing required input key: " + this_key)

        for this_key in numeric_keys:
            if not cama.is_number(request_data[this_key]):
                abort(400, "Expected number, received: " + this_key + "=" + request_data[this_key])

        request_data["request"] = "plot_hydrograph_deltas"
        response = cama.do_request(request_data)
        return response
    except Exception as e:
        abort(500, e)


@app.route("/vegetation_lookup", methods=["POST"])
def vegetation_lookup():
    try:
        request_data = request.get_json()
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        mandatory_keys = ["veg_type"]
        given_keys = request_data.keys()
        for this_key in mandatory_keys:
            if this_key not in given_keys:
                abort(400, "Missing required input key: " + this_key)

        request_data["request"] = "veg_lookup"
        response = cama.do_request(request_data)
        return response
    except Exception as e:
        abort(500, e)


@app.route("/cama_status", methods=["POST"])
def cama_status():
    try:
        request_data = request.get_json()
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        mandatory_keys = ["folder_name"]
        given_keys = request_data.keys()
        for this_key in mandatory_keys:
            if this_key not in given_keys:
                abort(400, "Missing required input key: " + this_key)

        request_data["request"] = "cama_status"
        response = cama.do_request(request_data)
        return response
    except Exception as e:
        abort(500, e)


@app.route("/cama_run/pre", methods=["POST"])
def came_run_pre():
    try:
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        request_data = request.get_json()
        mandatory_keys = ["folder_name", "start_year", "end_year"]
        given_keys = request_data.keys()
        for this_key in mandatory_keys:
            if this_key not in given_keys:
                abort(400, "Missing required input key: " + this_key)

        request_data["request"] = "cama_run_pre"
        response = cama.do_request(request_data)
        return response
    except Exception as e:
        abort(500, e)


@app.route("/cama_run/post", methods=["POST"])
def came_run_post():
    try:
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        request_data = request.get_json()
        mandatory_keys = ["folder_name", "start_day", "end_day", "start_month", "end_month", "start_year",  "end_year", "flow_value",
                          "wetland_loc_multiple"]
        numeric_keys = ["start_day", "end_day", "start_month", "end_month", "start_year",  "end_year", "flow_value"]
        wetland_loc_multiple_list = request_data["wetland_loc_multiple"]
        given_keys = request_data.keys()
        for this_key in mandatory_keys:
            if this_key not in given_keys:
                abort(400, "Missing required input key: " + this_key)

        for this_key in numeric_keys:
            if not cama.is_number(request_data[this_key]):
                abort(400, "Expected number, received: " + this_key + "=" + request[this_key])

        for wetland_loc in wetland_loc_multiple_list:
            for loc in wetland_loc:
                if not cama.is_number(loc):
                    abort(400, "Expected number, received: wetland_loc_multiple=" + request_data["wetland_loc_multiple"])

        request_data["request"] = "cama_run_post"
        response = cama.do_request(request_data)
        return response
    except Exception as e:
        abort(500, e)


@app.route("/coord_to_grid", methods=["POST"])
def coord_to_grid():
    try:
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        request_data = request.get_json()
        mandatory_keys = ["lat", "lon"]
        numeric_keys = ["lat", "lon"]
        given_keys = request_data.keys()
        for this_key in mandatory_keys:
            if this_key not in given_keys:
                abort(400, "Missing required input key: " + this_key)

        for this_key in numeric_keys:
            if not cama.is_number(request_data[this_key]):
                abort(400, "Expected number, received: " + this_key + "=" + request_data[this_key])

        request_data["request"] = "coord_to_grid"
        response = CamaConvert.do_request(request_data, mongo_client)
        return response
    except Exception as e:
        abort(500, e)


@app.route("/peak_flow", methods=["POST"])
def peak_flow():
    try:
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        request_data = request.get_json()
        mandatory_keys = ["folder_name", "lat", "lon", "return_period"]
        numeric_keys = ["lat", "lon", "return_period"]
        given_keys = request_data.keys()
        for this_key in mandatory_keys:
            if this_key not in given_keys:
                abort(400, "Missing required input key: " + this_key)

        for this_key in numeric_keys:
            if not cama.is_number(request_data[this_key]):
                abort(400, "Expected number, received: " + this_key + "=" + request_data[this_key])

        request_data["request"] = "peak_flow"
        response = cama.do_request(request_data)
        return response
    except Exception as e:
        abort(500, e)


@app.route("/get_flow", methods=["POST"])
def get_flow():
    # TODO: Work in progress
    try:
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        request_data = request.get_json()
        request_data["request"] = "get_flow"
        response = cama.do_request(request_data)
        return response
    except Exception as e:
        abort(500, e)


@app.route("/remove_output_folder", methods=["POST"])
def remove_output_folder():
    try:
        request_data = request.get_json()
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        mandatory_keys = ["folder_name"]
        given_keys = request_data.keys()
        for this_key in mandatory_keys:
            if this_key not in given_keys:
                abort(400, "Missing required input key: " + this_key)

        request_data["request"] = "remove_output_folder"
        response = cama.do_request(request_data)
        return response
    except Exception as e:
        abort(500, e)


@app.route("/output_folders", methods=["GET"])
def get_output_folders():
    try:
        mongo_client = get_db()
        database = mongo_client["output"]
        folder_collection = database["folder"]
        response = list(folder_collection.find({}, {"_id": 0}))
        return json.dumps(response)
    except Exception as e:
        abort(500, e)


@app.route("/compare_flow", methods=["POST"])
def compare_flow():
    try:
        request_data = request.get_json()
        mongo_client = get_db()
        cama = CamaConvert(mongo_client)
        mandatory_keys = ["lat", "lon", "pre_path", "post_path", "year"]
        numeric_keys = ["lat", "lon", "year"]
        given_keys = request_data.keys()
        for this_key in mandatory_keys:
            if this_key not in given_keys:
                abort(400, "Missing required input key: " + this_key)

        for this_key in numeric_keys:
            if not cama.is_number(request_data[this_key]):
                abort(400, "Expected number, received: " + this_key + "=" + request_data[this_key])

        request_data["request"] = "plot_compare_flow"
        response = cama.do_request(request_data)
        return response
    except Exception as e:
        abort(500, e)


if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)  # run app in debug mode on port 80
