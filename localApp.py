import psycopg2
import numpy as np
from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image
from io import BytesIO
from shapely import wkb
from shapely.geometry import Point, Polygon
from flask import Flask, render_template, jsonify
import geopandas as gpd
from sqlalchemy import create_engine
from pyproj import CRS
from geopandas import GeoSeries
import matplotlib.pyplot as plt
from shapely.ops import unary_union

app = Flask(__name__)

# Database connection parameters
hostname = 'localhost'
port = 5432
database = 'fuzzyBoundaries'
username = 'postgres'
password = 'pw'

# Establish the database connection
conn = psycopg2.connect(
    host=hostname,
    port=port,
    database=database,
    user=username,
    password=password
)

# Create a connection string
connection_string = f'postgresql://{username}:{password}@{hostname}:{port}/{database}'

# Create the projects table if it doesn't exist
create_projects_table_query = '''
    CREATE TABLE IF NOT EXISTS projects (
        id SERIAL PRIMARY KEY,
        project_name VARCHAR(255) UNIQUE NOT NULL,
        map_center_lat DOUBLE PRECISION NOT NULL,
        map_center_lng DOUBLE PRECISION NOT NULL,
        map_zoom INTEGER NOT NULL
    );
'''

# Create the polygons table if it doesn't exist
create_polygons_table_query = '''
    CREATE TABLE IF NOT EXISTS polygons (
        id SERIAL PRIMARY KEY,
        project_id INTEGER REFERENCES projects(id),
        project_name VARCHAR(255) NOT NULL,
        coordinates GEOMETRY(Polygon, 4326) NOT NULL
    );
'''

# Execute the table creation query
with conn.cursor() as cursor:
    cursor.execute(create_projects_table_query)
    cursor.execute(create_polygons_table_query)
    conn.commit()

@app.route('/')
def opening_screen():
    return render_template('opening_screen.html')


@app.route('/project_manager')
def project_manager():
    return render_template('project_manager.html')

@app.route('/project_creation', methods=['POST'])
def project_creation():
    project_name = request.form.get('project_name')
    map_center_lat = request.form.get('map_center_lat')
    map_center_lng = request.form.get('map_center_lng')
    map_zoom = request.form.get('map_zoom')

    cursor = conn.cursor()
    try:
        # Check if project name already exists
        cursor.execute("SELECT COUNT(*) FROM projects WHERE project_name = %s", (project_name,))
        count = cursor.fetchone()[0]
        if count > 0:
            return "A project with that name already exists. Please return to the previous page and enter a different name."

        # Insert the project into the database
        cursor.execute("INSERT INTO projects (project_name, map_center_lat, map_center_lng, map_zoom) VALUES (%s, %s, %s, %s)", (project_name, map_center_lat, map_center_lng, map_zoom))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return "An error occurred while creating the project: " + str(e)
    finally:
        cursor.close()

    return "Project created successfully!"


@app.route('/data_logger')
def data_logger():
    return render_template('data_logger.html')

@app.route('/draw_and_store_polygon', methods=['GET', 'POST'])
def draw_and_store_polygon():
    if request.method == 'GET':
        project_name = request.args.get('project_name')
        # Retrieve project details from the database based on the project name
        cursor = conn.cursor()
        #print("hello 1, project name: ", project_name)
        cursor.execute("SELECT id, map_center_lat, map_center_lng, map_zoom FROM projects WHERE project_name = %s", (project_name,))
        project_data = cursor.fetchone()
        cursor.close()

        if not project_data:
            return "Project not found."

        project_id, map_center_lat, map_center_lng, map_zoom = project_data

        # Render the draw_and_store_polygon.html template and pass the project details
        return render_template('draw_and_store_polygon.html', project_id=project_id, project_name=project_name, map_center_lat=map_center_lat, map_center_lng=map_center_lng, map_zoom=map_zoom)

    elif request.method == 'POST':
        project_name = request.form.get('project_name')
        coordinates = request.form.get('coordinates')

    if not coordinates:
        return "No polygon data received."

    # Retrieve the project_id based on the project_name
    cursor = conn.cursor()
    #print("hello 2, project name: ", project_name)
    cursor.execute("SELECT id FROM projects WHERE project_name = %s", (project_name,))
    project_data = cursor.fetchone()
    cursor.close()

    if not project_data:
        return "Project not found.", project_name

    project_id = project_data[0]

    # Insert the polygon into the polygons table with the project_id
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO polygons (project_id, project_name, coordinates) VALUES (%s, %s, ST_GeomFromText(%s, 4326))", (project_id, project_name, coordinates))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return "An error occurred while storing the polygon: " + str(e)
    finally:
        cursor.close()

    return "Polygon stored successfully!"


@app.route('/display_project_list')
def display_project_list():
    projects = get_projects()
    return render_template('display_project_list.html', projects=projects)

def get_projects():
    cursor = conn.cursor()
    cursor.execute("""
        SELECT projects.id, projects.project_name, COUNT(polygons.id) AS num_polygons
        FROM projects
        LEFT JOIN polygons ON projects.id = polygons.project_id
        GROUP BY projects.id
        ORDER BY num_polygons DESC
    """)
    project_data = cursor.fetchall()
    cursor.close()

    projects = []
    for row in project_data:
        project_id, project_name, num_polygons = row
        projects.append({
            'project_id': project_id,
            'project_name': project_name,
            'num_polygons': num_polygons
        })

    return projects


from shapely.geometry import Polygon

# @app.route('/display_map/<string:project_name>')
# def display_map(project_name):
#     # Retrieve project details based on the project_name
#     cursor = conn.cursor()
#     cursor.execute("SELECT id, map_center_lat, map_center_lng, map_zoom FROM projects WHERE project_name = %s", (project_name,))
#     project_data = cursor.fetchone()
#     cursor.close()

#     if not project_data:
#         return "Project not found."

#     project_id, map_center_lat, map_center_lng, map_zoom = project_data
    
#     # Connect to the database
#     engine = create_engine(connection_string)
    
#     # Query the polygons from the database
#     query = 'SELECT id, project_name, coordinates FROM polygons WHERE project_name = %s'
#     params = (project_name,)
#     gdf = gpd.GeoDataFrame.from_postgis(query, engine, geom_col='coordinates', params=params)
    
#     # Set CRS to WGS 1984 (EPSG:4326)
#     gdf.crs = 'EPSG:4326'
    
#     # Reproject geometries to a projected CRS (EPSG:3857)
#     gdf = gdf.to_crs('EPSG:3857')
    
#     # Define the color categories and percentage intervals
#     color_categories = {
#         (95, 100): '#008000',  # Dark green
#         (75, 95): '#00FF00',   # Light green
#         (50, 75): '#FFFF00',   # Yellow
#         (0, 50): '#FFA500'     # Orange
#     }
#     default_color = 'none'
    
#     # Perform overlay analysis to calculate percentage of overlap
#     overlay = gpd.overlay(gdf.reset_index(drop=True), gdf.reset_index(drop=True), how='union')

#     # Calculate the percentage of overlap for each polygon
#     gdf['overlap_percentage'] = gdf.area / gdf.geometry.boundary.union(overlay.boundary).area * 100

#     # Assign colors to the polygons based on overlap percentage
#     gdf['color'] = default_color

#     for (min_percentage, max_percentage), color in color_categories.items():
#         mask = (gdf['overlap_percentage'] >= min_percentage) & (gdf['overlap_percentage'] < max_percentage)
#         gdf.loc[mask, 'color'] = color
    
#     # Convert the GeoDataFrame to GeoJSON
#     geojson = gdf.to_crs('EPSG:4326').to_json()

#     return render_template('display_map.html', geojson=geojson, project_id=project_id, project_name=project_name,
#                            map_center_lat=map_center_lat, map_center_lng=map_center_lng,
#                            map_zoom=map_zoom)





# @app.route('/display_map/<string:project_name>')
# def display_map(project_name):
#     # Retrieve project details based on the project_name
#     cursor = conn.cursor()
#     cursor.execute("SELECT id, map_center_lat, map_center_lng, map_zoom FROM projects WHERE project_name = %s", (project_name,))
#     project_data = cursor.fetchone()
#     cursor.close()

#     if not project_data:
#         return "Project not found."

#     project_id, map_center_lat, map_center_lng, map_zoom = project_data
    
#     # Connect to the database
#     engine = create_engine(connection_string)
    
#     # Query the polygons from the database
#     query = 'SELECT id, project_name, coordinates FROM polygons WHERE project_name = %s'
#     params = (project_name,)
#     gdf = gpd.GeoDataFrame.from_postgis(query, engine, geom_col='coordinates', params=params)

#     # Calculate the intersection of all polygons
#     intersection = gdf.unary_union

#     # Create a buffer around the intersection polygon
#     buffered_polygon = intersection.buffer(distance=0.001)

#     # Create a new GeoDataFrame with the buffered polygon
#     dark_green_polygons = gpd.GeoDataFrame(geometry=[buffered_polygon])

#     # Convert the GeoDataFrame to GeoJSON
#     dark_green_geojson = dark_green_polygons.to_crs(epsg=4326).to_json()

#     return render_template('display_map.html', dark_green_geojson=dark_green_geojson, project_id=project_id, project_name=project_name,
#                            map_center_lat=map_center_lat, map_center_lng=map_center_lng,
#                            map_zoom=map_zoom)

# // Colored layers for HTML template
#         var coloredLayers = {{ colored_layers|tojson }};

#         for (var i = 0; i < coloredLayers.length; i++) {
#             var layer = L.geoJSON(coloredLayers[i].geojson, {
#                 style: {
#                     color: coloredLayers[i].color,
#                     fillColor: coloredLayers[i].color,
#                     fillOpacity: 0.5
#                 }
#             }).addTo(map);
#         }

# @app.route('/display_map/<string:project_name>')
# def display_map(project_name):
#     # Retrieve project details based on the project_name
#     cursor = conn.cursor()
#     cursor.execute("SELECT id, map_center_lat, map_center_lng, map_zoom FROM projects WHERE project_name = %s", (project_name,))
#     project_data = cursor.fetchone()
#     cursor.close()

#     if not project_data:
#         return "Project not found."

#     project_id, map_center_lat, map_center_lng, map_zoom = project_data
    
#     # Connect to the database
#     engine = create_engine(connection_string)
    
#     # Query the polygons from the database
#     query = 'SELECT id, project_name, coordinates FROM polygons WHERE project_name = %s'
#     params = (project_name,)
#     gdf = gpd.GeoDataFrame.from_postgis(query, engine, geom_col='coordinates', params=params)

#     # Perform overlay analysis to calculate overlap percentages
#     overlay = gpd.overlay(gdf, gdf, how='union')
#     gdf['overlap_percentage'] = gdf.area / gdf.geometry.boundary.union(overlay.boundary).area * 100

#     # Define color categories and default color
#     color_categories = {
#         (95, 100): '#008000',  # Dark green
#         (75, 95): '#00FF00',   # Light green
#         (50, 75): '#FFFF00',   # Yellow
#         (0, 50): '#FFA500'     # Orange
#     }
#     default_color = 'none'

#     # Assign colors to the polygons based on overlap percentage
#     for (min_percentage, max_percentage), color in color_categories.items():
#         mask = (gdf['overlap_percentage'] >= min_percentage) & (gdf['overlap_percentage'] < max_percentage)
#         gdf.loc[mask, 'color'] = color

#     # Create colored layers as GeoJSON representations
#     colored_layers = []

#     # Calculate the intersection percentage for each polygon
#     gdf['intersection_percentage'] = gdf.geometry.apply(lambda geom: calculate_intersection_percentage(geom, gdf.geometry))

#     # Filter polygons for dark green color (95% or more intersections)
#     dark_green_polygons = gdf[gdf['intersection_percentage'] >= 95]
#     dark_green_features = []
#     for index, row in dark_green_polygons.iterrows():
#         feature = {
#             'type': 'Feature',
#             'geometry': row['geometry'].__geo_interface__,
#             'properties': {}  # Add any additional properties if needed
#         }
#         dark_green_features.append(feature)

#     dark_green_layer = {
#         'geojson': {
#             'type': 'FeatureCollection',
#             'features': dark_green_features
#         },
#         'color': '#008000'  # Dark green color
#     }
#     colored_layers.append(dark_green_layer)

#     return render_template('display_map.html', colored_layers=colored_layers, project_id=project_id, project_name=project_name,
#                            map_center_lat=map_center_lat, map_center_lng=map_center_lng,
#                            map_zoom=map_zoom)





















# @app.route('/display_map/<int:project_id>')
# def display_map(project_id):
#     # Retrieve project details based on the project_id
#     cursor = conn.cursor()
#     cursor.execute("SELECT project_name, map_center_lat, map_center_lng, map_zoom FROM projects WHERE id = %s", (project_id,))
#     project_data = cursor.fetchone()
#     cursor.close()

#     if not project_data:
#         return "Project not found."

#     project_name, map_center_lat, map_center_lng, map_zoom = project_data

#     return render_template('display_map.html', project_id=project_id, project_name=project_name,
#                            map_center_lat=map_center_lat, map_center_lng=map_center_lng,
#                            map_zoom=map_zoom)


@app.route('/display_map/<string:project_name>')
def display_map(project_name):
    # Retrieve project details based on the project_name
    cursor = conn.cursor()
    cursor.execute("SELECT id, map_center_lat, map_center_lng, map_zoom FROM projects WHERE project_name = %s", (project_name,))
    project_data = cursor.fetchone()
    cursor.close()

    if not project_data:
        return "Project not found."

    project_id, map_center_lat, map_center_lng, map_zoom = project_data
    
    # Connect to the database
    engine = create_engine(connection_string)
    
    # Query the polygons from the database
    query = 'SELECT id, project_name, coordinates FROM polygons WHERE project_name = %s'
    params = (project_name,)
    gdf = gpd.GeoDataFrame.from_postgis(query, engine, geom_col='coordinates', params=params)
    
    # Check if there are no polygons
    if gdf.empty:
        return "No polygons found for the project."

    # Split the polygons based on intersections
    split_geometries = gpd.overlay(gdf, gdf, how='identity')

    # Calculate the number of intersections for each split part
    split_geometries['intersecting_polygons_count'] = split_geometries.apply(
        lambda row: gdf[gdf.intersects(row.geometry)].shape[0],
        axis=1
    )

    # Create a new GeoDataFrame with split parts and intersecting polygons count
    split_gdf = gpd.GeoDataFrame(split_geometries[['intersecting_polygons_count', 'geometry']])

    # Convert GeoDataFrame to GeoJSON
    geojson = split_gdf.to_json()

    return render_template('display_map.html', geojson=geojson, project_id=project_id, project_name=project_name,
                           map_center_lat=map_center_lat, map_center_lng=map_center_lng,
                           map_zoom=map_zoom)



#This one works with current display_map

# @app.route('/display_map/<string:project_name>')
# def display_map(project_name):
#     # Retrieve project details based on the project_name
#     cursor = conn.cursor()
#     cursor.execute("SELECT id, map_center_lat, map_center_lng, map_zoom FROM projects WHERE project_name = %s", (project_name,))
#     project_data = cursor.fetchone()
#     cursor.close()

#     if not project_data:
#         return "Project not found."

#     project_id, map_center_lat, map_center_lng, map_zoom = project_data
    
#     # Connect to the database
#     engine = create_engine(connection_string)
    
#     # Query the polygons from the database
#     query = 'SELECT id, project_name, coordinates FROM polygons WHERE project_name = %s'
#     params = (project_name,)
#     gdf = gpd.GeoDataFrame.from_postgis(query, engine, geom_col='coordinates', params=params)
    
#     # Check if there are no polygons
#     if gdf.empty:
#         return "No polygons found for the project."

#     # Convert the GeoDataFrame to GeoJSON
#     geojson = gdf.to_crs(epsg=4326).to_json()

#     return render_template('display_map.html', geojson=geojson, project_id=project_id, project_name=project_name,
#                            map_center_lat=map_center_lat, map_center_lng=map_center_lng,
#                            map_zoom=map_zoom)



# THIS IS THE ONE THAT WORKS W NO BULLSHIT

# @app.route('/display_map_working/<string:project_name>')
# def display_map(project_name):
#     # Retrieve project details based on the project_name
#     cursor = conn.cursor()
#     cursor.execute("SELECT id, map_center_lat, map_center_lng, map_zoom FROM projects WHERE project_name = %s", (project_name,))
#     project_data = cursor.fetchone()
#     cursor.close()

#     if not project_data:
#         return "Project not found."

#     project_id, map_center_lat, map_center_lng, map_zoom = project_data
    
#     # Connect to the database
#     engine = create_engine(connection_string)
    
#     # Query the polygons from the database
#     query = 'SELECT id, project_name, coordinates FROM polygons WHERE project_name = %s'
#     params = (project_name,)
#     gdf = gpd.GeoDataFrame.from_postgis(query, engine, geom_col='coordinates', params=params)

#     # Convert the GeoDataFrame to GeoJSON
#     geojson = gdf.to_crs(epsg=4326).to_json()

#     return render_template('display_map_working.html', geojson=geojson, project_id=project_id, project_name=project_name,
#                            map_center_lat=map_center_lat, map_center_lng=map_center_lng,
#                            map_zoom=map_zoom)


# def calculate_overlap_percentage(polygon, overlay):
#     polygon = Polygon(polygon)

#     if not overlay.is_valid.any() or not overlay.geom_type.eq('Polygon').any():
#         return 0

#     # Reproject geometries to a projected CRS
#     geographic_crs = CRS('EPSG:4326')  # Assuming the geographic CRS is EPSG:4326
#     projected_crs = CRS('EPSG:3857')   # Choose a projected CRS suitable for your region
#     overlay = overlay.to_crs(projected_crs)
#     polygon = GeoSeries([polygon], crs=geographic_crs).to_crs(projected_crs).iloc[0]

#     total_area = overlay.union(polygon).area
#     intersection_area = polygon.intersection(overlay).area
#     overlap_percentage = (intersection_area / total_area) * 100
#     return overlap_percentage



# @app.route('/get_polygons/<int:project_id>')
# def get_polygons(project_id):
#     # Connect to the database
#     engine = create_engine(connection_string)

#     # Query the polygons from the database
#     query = 'SELECT id, project_name, coordinates FROM polygons WHERE project_name = %s', (project_id,)
#     gdf = gpd.GeoDataFrame.from_postgis(query, engine, geom_col='coordinates')

#     # Convert the GeoDataFrame to GeoJSON
#     geojson = gdf.to_crs(epsg=4326).to_json()

#     print(geojson)
    
#     return geojson

# // Retrieve the polygon data from the server
#     fetch('/get_polygons/{{project.project_name}}')
#       .then(response => response.json())
#       .then(data => {
#         // Create a GeoJSON layer from the polygon data
#         L.geoJSON(data, {
#           style: function (feature) {
#             // Apply custom symbology based on properties of each polygon
#             var color = feature.properties.color;
#             return { fillColor: color, fillOpacity: 0.5, stroke: true, color: '#000000' };
#           }
#         }).addTo(map);
#       })
#       .catch(error => console.error('Error:', error));

if __name__ == '__main__':
    app.run(port=7777, debug=True)
    
# Close the connection
#conn.close()
    
