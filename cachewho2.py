#!/usr/bin/python3

from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import threading
from urllib.parse import urlparse
import time
import json
import sys, os
import pickle


serverip='127.0.0.1'
serverpt=8084
locserver=serverip+":"+str(serverpt)
polltime=5
mypath=os.path.dirname(os.path.realpath(sys.argv[0]))
datastoreloc=mypath+os.sep
pidfile=mypath+os.sep+"cachewhopid"

keyvaluestore={} #usually atomic in operation
safelk=threading.RLock() #anal retentive just in case ....
safestats=threading.RLock() #lock for stats (shouldn't be needed, but just in case)
stats={}
stats['reqcount']=0 #total requests since server start
stats['itemwrit']=0 #total single item writes
stats['itemread']=0 #total single item reads
stats['reqcount_last']=0 #for diff calculation
stats['itemwrit_last']=0 #for diff calculation
stats['itemread_last']=0 #for diff calculation
stats['reqcountps']=0 #requests per seconds
stats['itemwritps']=0 #write items per second
stats['itemreadps']=0 #read items per second
server_start_timeunx=time.time()
server_start_time=time.gmtime(server_start_timeunx)
fmt_server_start_time=time.strftime('%Y-%m-%d %H:%M:%S',server_start_time)


def jsonrequest(apiinterface,payload,server):#generic equivalent to curl -X POST
    conn = http.client.HTTPConnection(server, timeout=10)
    headers={"Content-Type":"application/json","Accept": "text/plain"}
    conn.request("POST", apiinterface, payload, headers)
    response = conn.getresponse()
    data = response.read()
    return(data.strip())

def statsdata():
    global tnow
    global gnow
    global keyvaluestore
    global safestats, safelk
    global stats 
    global server_start_time, server_start_timeunx, fmt_server_start_time
    lines=[]
    tnow=time.time()
    gnow=time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(tnow))
    lines.append('"ServerStartTime"     : "{}"'.format(fmt_server_start_time))
    lines.append('"ServerTimeNow"       : "{}"'.format(gnow))
    with safestats: tmpstat=stats
    lines.append('"RequestsSinceStart"  : "{}"'.format(tmpstat['reqcount']))
    lines.append('"ItemWritesSinceStart": "{}"'.format(tmpstat['itemwrit']))
    lines.append('"ItemReadsSinceStart" : "{}"'.format(tmpstat['itemread']))
    lines.append('"RequestsPerSecond"   : "{}"'.format(tmpstat['reqcountps']))
    lines.append('"ItemWritesPerSecond" : "{}"'.format(tmpstat['itemwritps']))
    lines.append('"ItemReadsPerSecond"  : "{}"'.format(tmpstat['itemreadps']))
    statsmessage=",\n".join(lines)
    statsmessage="\n".join(['{',statsmessage,'}'])
    return statsmessage


def getputs(kvdata): #normalize a dict or listof dicts
    puts=[]
    if type(kvdata)==type({}):
        for keys in kvdata.keys():
            puts.append({keys:kvdata.get(keys)})
    if type(kvdata)==type([]):
        for kvs in kvdata:
            if type(kvs)==type({}):
                puts+=getputs(kvs)
    return puts



class Handler(BaseHTTPRequestHandler):


    def do_GET(self):
        global tnow
        global gnow
        global keyvaluestore
        global safestats, safelk
        global stats 
        global server_start_time, server_start_timeunx, fmt_server_start_time

        with safestats: stats['reqcount']+=1
        tnow=time.time()
        gnow=time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(tnow))
        message=""
        parsed_data = urlparse(self.path)
        path=parsed_data.path
        if path=="/stats": message=statsdata()
        if path=="/dump": message=json.dumps(keyvaluestore,indent=2,sort_keys=True)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(message.encode())
        self.wfile.write('\n'.encode())
        return

    def do_POST(self):
        global keyvaluestore
        global safelk, safestats
        global stats 
        with safestats: stats['reqcount']+=1
        tnow=time.time()
        gnow=time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(tnow))
        parsed_path = urlparse(self.path)
        location=parsed_path.path

        length=int(self.headers.get('Content-Length'))
        if length > 0:
            rawrequest=self.rfile.read(int(length))
            rawrequest=str(rawrequest,'utf-8','ignore') #convert the request to string
        try:
            jrequest=json.loads(rawrequest)
        except:
            self.send_response(200)
            self.end_headers()
            self.wfile.write("JSON_parse_error\n".encode())
            return
        if jrequest.get("put"):
            keyval=jrequest.get("put");
            puts=getputs(keyval)
            with safelk:
                for items in puts:
                    for keys in items:
                        keyvaluestore[keys]=items[keys]
        print(gnow+" "+str(json.dumps(jrequest))) #.dumps to suppress unicode u


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    HTTPServer.request_queue_size=10000
    pass


def timemgmt():
    global safelk, safestats
    global stats 
    global polltime
    earlier=time.time()
    while True:
        time.sleep(polltime)
        now=time.time()
        elapsed_time=now-earlier
        if elapsed_time==0: elapsed_time=0.001
        with safestats:
            stats['reqcountps']=float(stats['reqcount']-stats['reqcount_last'])/elapsed_time
            stats['itemreadps']=float(stats['itemread']-stats['itemread_last'])/elapsed_time
            stats['itemwritps']=float(stats['itemwrit']-stats['itemwrit_last'])/elapsed_time
            stats['reqcount_last']=stats['reqcount']
            stats['itemread_last']=stats['itemread']
            stats['itemwrit_last']=stats['itemwrit']
        earlier=time.time()



def runserver():
    global threadlist
    global maxthreads
    print("starting timing thread")
    threading.Thread(target=timemgmt,args=()).start()
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
    if "--server" in args:
        runserver()
        exit()

if __name__ == "__main__":
    main()
