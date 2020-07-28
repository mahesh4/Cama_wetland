# Cama

## Documentation ##
https://documenter.getpostman.com/view/4504366/Szf6Y8oi?version=latest

## Requirements ##
Ubuntu Server
MongDB Server
Dropbox Account

## Installation ##
pip install shapely

pip install Flask

pip install -U flask-cors

pip install geojson

pip install numpy

pip install dropbox

python -m pip install pymongo

pip install sshtunnel

## Setup ##
Set CAMADIR and APIDIR to the path of CAMA directory and Project directory respectively in hamid_pre_template.sh and hamid_post_template.sh 
files in the template/ folder in project directory

Copy the hamid_pre_template.sh and hamid_post_template.sh files from the template/ folder in project directory to gosh/ folder in CAMA directory

Place nextxy.txt and Reservoir_xy.txt files in a folder named "res" and place the folder inside the CAMA directory

Place the hamid_dates_1915_2011 file inside the "inp" folder in CAMA directory

Create a copy of the files in the "hamid" directory in "map" folder and place it in the under the folder name "hamid_copy" in the same "map" directory

Deploy a MONGO Server and create a database named "output" and a collection named "folder"

Setup config.json in project directory

## Deploy command ##
uwsgi --socket 0.0.0.0:5000 --protocol=http -w wsgi:app --logto #pathOfLogFile --master --processes 4 --threads 2 &


