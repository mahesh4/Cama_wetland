# Cama

## Documentation ##
https://documenter.getpostman.com/view/4504366/T1DngcuP?version=latest 

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

Setup config.json in project directory

## Deploy command ##
uwsgi --socket 0.0.0.0:5000 --protocol=http -w wsgi:app --logto #pathOfLogFile --master --processes 4 --threads 2 &


