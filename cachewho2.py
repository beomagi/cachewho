#!/usr/bin/python

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import threading
import thread
import urlparse
import httplib
import time
import json
import sys, os
import pickle


serverip='127.0.0.1'
serverpt=8084
locserver=serverip+":"+str(serverpt)
polltime=30
mypath=os.path.dirname(os.path.realpath(sys.argv[0]))
datastoreloc=mypath+os.sep
pidfile=mypath+os.sep+"cachewhopid"


keyvaluestore={} #usually atomic in operation
saftey=threading.RLock()
reqcount=0 #total requests since server start
itemwrit=0 #total single item writes
itemread=0 #total single item reads
reqcount_last=0 #for diff calculation
itemwrit_last=0 #for diff calculation
itemread_last=0 #for diff calculation
reqcountps=0 #requests per seconds
itemwritps=0 #write items per second
itemreadps=0 #read items per second
safereqs=threading.RLock()
safewrit=threading.RLock()
saferead=threading.RLock()
safeps=threading.RLock()
server_start_timeunx=time.time()
server_start_time=time.gmtime(server_start_timeunx)
fmt_server_start_time=time.strftime('%Y.%m.%d-%H:%M:%S',server_start_time)


def jsonrequest(apiinterface,payload,server):#generic equivalent to curl -X POST
    conn = httplib.HTTPConnection(server, timeout=10)
    headers={"Content-Type":"application/json","Accept": "text/plain"}
    conn.request("POST", apiinterface, payload, headers)
    response = conn.getresponse()
    data = response.read()
    return(data.strip())


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        global tnow
        global gnow
        global keyvaluestore
        global safereqs, saferead, safeps
        global reqcount, itemread, itemwrit
        global server_start_time, server_start_timeunx, fmt_server_start_time

        with safereqs: reqcount+=1
        tnow=time.time()
        gnow=time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(tnow))
        message=""
        parsed_data = urlparse.urlparse(self.path)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(message)
        self.wfile.write('\n')
        return

    def do_POST(self):
        global keyvaluestore
        global safereqs
        global reqcount

        with safereqs: reqcount+=1

        tnow=time.time()
        gnow=time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(tnow))
        parsed_path = urlparse.urlparse(self.path)
        location=parsed_path.path
        length=self.headers.getheader('Content-Length')
        if length > 0:
            rawrequest=self.rfile.read(int(length))
        try:
            jrequest=json.loads(rawrequest)
        except:
            self.send_response(200)
            self.end_headers()
            self.wfile.write("JSON_parse_error")
            self.wfile.write('\n')
            return
        print(gnow+" "+str(json.dumps(jrequest))) #.dumps to suppress unicode u


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    HTTPServer.request_queue_size=1000
    pass


def runserver():
    global threadlist
    global maxthreads
    print("starting timing thread")
    thread.start_new_thread(timemgmt,("",))
    print("setting up http server")
    server = ThreadedHTTPServer(('0.0.0.0',serverpt), Handler)
    print("starting server")
    server.serve_forever()


def main():
    global locserver
    global pidfile
    global serverpt

    args=sys.argv
    prms=len(args)
