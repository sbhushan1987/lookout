#!/usr/bin/env python

PORT = 9890

import flask, os, sys, time, psutil, json, socket, logging
import jsonpickle
import iis_bridge as iis
import iis_bridge.site as site
from flask import send_from_directory
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from logging.handlers import TimedRotatingFileHandler
from tornado.ioloop import IOLoop
from multiprocessing import Process, Manager
from datetime import datetime

def tail(f, window=20):
    """
    Returns the last `window` lines of file `f` as a list.
    f - a byte file-like object
    """
    if window == 0:
        return []
    BUFSIZ = 1024
    f.seek(0, 2)
    bytes = f.tell()
    size = window + 1
    block = -1
    data = []
    while size > 0 and bytes > 0:
        if bytes - BUFSIZ > 0:
            # Seek back one whole BUFSIZ
            f.seek(block * BUFSIZ, 2)
            # read BUFFER
            data.insert(0, f.read(BUFSIZ))
        else:
            # file too small, start from begining
            f.seek(0,0)
            # only read what was not read
            data.insert(0, f.read(bytes))
        linesFound = data[0].count('\n')
        size -= linesFound
        bytes -= BUFSIZ
        block -= 1
    return ''.join(data).splitlines()[-window:]

class WebSite:
  def __init__(self, name, status):
    self.name = name
    self.status = status

if getattr(sys, 'frozen', None):
	static = os.path.join(sys._MEIPASS, 'static')
else:
	static = 'static'

app = flask.Flask(__name__, static_folder=static)

@app.route('/')
def frontend():
	return flask.send_from_directory(app.static_folder, 'index.html')

@app.route('/sites')
def sites():
	sitelist = iis.get_site_names()
	sitestatus = []
	for st in sitelist:
		site1 = WebSite(st,False)
		try:
			site1.status = site.is_running(st)
		except:
			site1.status = False
		sitestatus.append(site1)
	
	return flask.Response(
		jsonpickle.encode(sitestatus, unpicklable=False),
		mimetype='application/json'
	)

@app.route('/raw')
def raw():
	return flask.Response(
		#jsonpickle.encode(stats.copy(), unpicklable=False),
		json.dumps(stats.copy()),
		mimetype='application/json'
	)

@app.route('/logs')
def logs():
	mylist = os.listdir('logs')
	return flask.Response(
		json.dumps(mylist),
		mimetype='application/json'
	)

@app.route('/files/<path:filename>', methods=['GET', 'POST'])
def download(filename):
	uploads = os.path.abspath("")+"\\logs"
	print(filename)
	print(uploads)
	return send_from_directory(directory=uploads, filename=filename,
                               as_attachment=True)

def update(stats):
	logging.getLogger('tornado.access').setLevel(logging.CRITICAL)	
	logger = logging.getLogger(__name__)
	logger.setLevel(logging.DEBUG)
	handler = TimedRotatingFileHandler('logs\\system-data.log',when="h",interval=1, backupCount=10000)
	handler.setLevel(logging.DEBUG)
	formatter = logging.Formatter('%(asctime)s : %(message)s')
	handler.setFormatter(formatter)
	logger.addHandler(handler)
	while True:
		diskused = 0
		disktotal = 0
		for i in psutil.disk_partitions():
			try:
				x = psutil.disk_usage(i.mountpoint)
				diskused += x.used
				disktotal += x.total
			except OSError:
				pass
		logfiles = os.listdir('logs')

		sitelist = iis.get_site_names()
		sitestatus = []
		for st in sitelist:
			site1 = WebSite(st,False)
			try:
				site1.status = site.is_running(st)
			except:
				site1.status = False
			sitestatus.append(site1)
		
		if(len(stats) > 0):
			del stats["logs2"] 		
			del stats["logs3"] 		
			del stats['logs'] 		
			del stats['fqdn'] 		
			del stats['uptime'] 	
			del stats['diskio'] 	
			del stats['diskusage'] 
			del stats['swapusage'] 	
			del stats['sites']

		cput = psutil.cpu_percent(0)
		stats['cpuusage'] = cput
		stats['ramusage'] = psutil.virtual_memory()
		stats['netio'] = psutil.net_io_counters()
		if(cput > 20):
			logger.debug(stats)

		stats['logs'] = logfiles
		stats['fqdn'] = socket.gethostname()
		stats['uptime'] = time.time() - psutil.boot_time()
		stats['diskio'] = psutil.disk_io_counters()
		stats['diskusage'] = [diskused, disktotal]
		stats['swapusage'] = psutil.swap_memory()
		stats['sites'] = jsonpickle.encode(sitestatus, unpicklable=False)
		
		currdatte = datetime.today()
		cyear = currdatte.strftime("%Y")
		cmonth = currdatte.strftime("%m")
		cday = currdatte.strftime("%d")
		fileformat1 = currdatte.strftime('%d%m%Y')
		fileformat2 = currdatte.strftime('%y%m%d')
		logfilepath1 = "D:\\QMSDI.DATA\\{}\\_LOG\\PROXY\\{}\\{}_errors.txt".format(cyear,cmonth,fileformat1)
		logfilepath2 = "D:\\Logfiles\\W3SVC1\\u_ex{}.log".format(fileformat2)
		stats["logs2"] = ""
		stats["logs3"] = ""
		if(os.path.isfile(logfilepath1)):
			f = open(logfilepath1, 'r')
			stats["logs2"] = tail(f,10)
			f.close()

		if(os.path.isfile(logfilepath2)):	 
			f = open(logfilepath2, 'r')
			stats["logs3"] = tail(f,10)
			f.close() 

		time.sleep(1)

if __name__ == '__main__':
	#logger.info('Logger started..')
	stats = Manager().dict()
	Process(target=update, args=(stats, )).start()
	if len(sys.argv) > 1:
		PORT = sys.argv[1]
	server = HTTPServer(WSGIContainer(app))
	print 'Now listening on port ' + str(PORT)
	server.listen(PORT)
	IOLoop.instance().start()
