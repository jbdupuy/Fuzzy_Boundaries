from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('opening_screen.html')

@app.route('/project_manager')
def project_manager():
    return render_template('project_manager.html')

@app.route('/data_logger')
def data_logger():
    return "Hello, Data Logger!"

@app.route('/show_maps')
def show_maps():
    return "Hello, Maps!"

if __name__ == '__main__':
    app.run(port=5000, debug=True)
    
    
    
