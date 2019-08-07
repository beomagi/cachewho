#!/usr/bin/python3

from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import threading
from urllib.parse import urlparse
import time
import json
import sys, os
import pickle


myname=sys.argv[0]
Helps="""
  About:
    {myname} is a small quick keyvalue store.
    once running as a server, interface with it as any rest API. This makes it convenient for most languages.
  
  Usage:
    {myname} -server
      Starts the server
    {myname} -server <PORT>
      Starts the server on a specific port (default 8084). e.g. {myname} -server 1234
  

  Curl examples:

    PUT - one or more entries to the dictionary:
       curl 127.0.0.1:8084 -X POST -d '{"put":{"dog":"cat","Terry":"Crews"}}'
       [{"dog": "cat"}, {"Terry": "Crews"}]

    GET - one or more entries from the dictionary:
       curl 127.0.0.1:8383 -X POST -d '{"get":["Terry","dog","Frappachino"]}'
       {"hood": "rat"}
       {"dog": "cat"}
       {"dsdfsd": null}

       entries that do not exist in the dictionary will return null
"""
Helps=Helps.replace('{myname}',myname)

serverip='127.0.0.1'
serverpt=8084 #default port
locserver=serverip+":"+str(serverpt)
polltime=5 #seconds between stat polls
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


    def __simpget(self,jrequest):
        keyval=jrequest.get("get")
        with safelk:
            if type(keyval)==type([]):
                msg=[]
                for eachval in keyval:
                    data=keyvaluestore.get(eachval)
                    msg.append(json.dumps({eachval:data}))
                getmessage="\n".join(msg)
            else:
                getmessage=keyvaluestore.get(keyval)
            print(getmessage)
            return getmessage

    def __simpput(self,jrequest):
        keyval=jrequest.get("put")
        puts=getputs(keyval)
        msgoutput=[]
        with safelk:
            for items in puts:
                for keys in items:
                    keyvaluestore[keys]=items[keys]
                    msgoutput.append(items)
        return(json.dumps(msgoutput))

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
        if path=="/stats" or path=="/": message=statsdata()
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
        message=""
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
            message+=str(self.__simpput(jrequest))

        if jrequest.get("get"):
            message+=str(self.__simpget(jrequest))

        self.send_response(200)
        self.end_headers()
        self.wfile.write(message.encode())
        self.wfile.write('\n'.encode())
        return


        print(gnow+" "+str(json.dumps(jrequest))) #.dumps to suppress unicode u


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    HTTPServer.request_queue_size=10000


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



def runserver(port):
    global threadlist
    global maxthreads
    print("starting timing thread")
    threading.Thread(target=timemgmt,args=()).start()
    print("setting up http server")
    server = ThreadedHTTPServer(('0.0.0.0',port), Handler)
    print("starting server on port {}".format(port))
    server.serve_forever()


def main():
    global locserver
    global pidfile
    global serverpt

    args=sys.argv
    prms=len(args)
    if "--server" in args:
        port=serverpt
        comindex=args.index('--server')
        if len(args) > comindex+1:
            port=int(args[comindex+1])
        runserver(port)
        exit()
    else:
        print(Helps)


if __name__ == "__main__":
    main()
