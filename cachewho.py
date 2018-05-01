#!/usr/bin/python

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import httplib
import json
import pickle
import sys, os
import time
import thread, threading
import urlparse


serverip='127.0.0.1'
serverpt=8084
locserver=serverip+":"+str(serverpt)
polltime=30
mypath=os.path.dirname(os.path.realpath(sys.argv[0]))
datastoreloc=mypath+os.sep
pidfile=mypath+os.sep+"cachewhopid"


"""
todo:
    item count status
    requests per second
"""
examples="""
Version: sqrt(pi)
Usage:

To interact with the cachewho server, use cachewho.py or curl
Examples below show both methods for interacting with cachewho


e.g. put one and get one (put, get and jget functions)
    Use cachewho directly
    >>>>> ./cachewho.py put 'key-f' 89
    >>>>> ./cachewho.py get 'key-f'
    89
    >>>>> ./cachewho.py jget 'key-f'
    {"key":"key-f","val":"89","age":"9.901"}


    >>>>> ./cachewho.py json '{"cmd":"put","key":"yourdata","val":"stuff"}'
    >>>>> ./cachewho.py json '{"cmd":"get","key":"yourdata"}'
    stuff
    >>>>> ./cachewho.py json '{"cmd":"jget","key":"yourdata"}'
    {"key":"yourdata","val":"stuff","age":"12.443"}

    >>>>> curl -X POST -d '{"cmd": "put","key":"moredata","val":"morestuff"}' 127.0.0.1:8084
    >>>>> curl -X POST -d '{"cmd": "get","key":"moredata"}' 127.0.0.1:8084
    morestuff
    >>>>> curl -X POST -d '{"cmd": "jget","key":"moredata"}' 127.0.0.1:8084
    {"key":"moredata","val":"morestuff","age":"256.613"}


e.g. Put many to add multiple key,value pairs at once (mput)
    >>>>> curl -X POST -d '{"cmd": "mput","items": [{"key1": 3}, {"key2": 5}]}' 127.0.0.1:8084
    >>>>> ./cachewho.py json '{"cmd": "mput","items": [{"keybee": "buzz"}, {"beeboo": "belly"}]}'


e.g. Get many on a defined list of keys (mget)
    >>>> curl -X POST -d '{"cmd": "mget","items": ["key1","key2","keyx"]}' 127.0.0.1:8084
    [
    {"key":"key1","val":"3","age":"10213.538"},
    {"key":"key2","val":"5","age":"10213.538"},
    {"key":"keyx","val":"Charles Xavier","age":"9890.759"}
    ]

    >>>>> ./cachewho.py json '{"cmd": "mget","items": ["key1","key2","keyx"]}'
    [
    {"key":"key1","val":"3","age":"10259.559"},
    {"key":"key2","val":"5","age":"10259.559"},
    {"key":"keyx","val":"Charles Xavier","age":"9936.78"}
    ]

e.g. Get list of keys defined by substring (getlike)
    >>>>> curl -X POST -d '{"cmd": "getlike","key": "bee"}' http://127.0.0.1:8084
    [
    {"key:":"keybee","val:":"buzz","age:":"4062.554"},
    {"key:":"beeboo","val:":"belly","age:":"4062.554"}
    ]

    >>>>> ./cachewho.py json '{"cmd": "getlike","key": "bee"}'
    [
    {"key:":"keybee","val:":"buzz","age:":"4304.626"},
    {"key:":"beeboo","val:":"belly","age:":"4304.626"}
    ]


e.g. health check - is the server running? Note, there's a GET method for easy browser access
    >>>>> ./cachewho.py json '{"cmd":"health"}'
    OK
    >>>>> curl 127.0.0.1:8084/health
    OK
    >>>>> curl -X POST -d '{"cmd":"health"}' http://127.0.0.1:8084
    OK

e.g. browser shortcuts:
    http://127.0.0.1:8084/help/     - help page
    http://127.0.0.1:8084/          - lists all items
    http://127.0.0.1:8084/health/   - cachewho health
    http://127.0.0.1:8084/key/thing - gets the lone value of key "thing"
    http://127.0.0.1:8084/save/file - saves the current dictionary to "file"
    http://127.0.0.1:8084/load/file - loads the current dictionary from "file"
    http://127.0.0.1:8084/status/   - shows server statistics


"""

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


def jr_put(jrequest,tnow,gnow):
    global saftey
    global itemwrit
    global safewrit
    retval=""
    if ('key' in jrequest) and ('val' in jrequest):
        with saftey:
            keyvaluestore[jrequest['key']]=(str(jrequest['val']),tnow)
        with safewrit: itemwrit+=1
        print(gnow+" Store key:'"+jrequest['key']+"' value:'"+jrequest['val']+"'")

def jr_mput(jrequest,tnow,gnow):
    global saftey
    global itemwrit
    global safewrit
    cntr=0
    if ('items' in jrequest):
        datapairs=jrequest['items']
        for pairs in datapairs:
            if len(pairs)==1:
                pkey,pval=pairs.items()[0]
                with saftey:
                    keyvaluestore[pkey]=(str(pval),tnow)
                    cntr+=1
                print(gnow+" Store key:'"+str(pkey)+"' value:'"+str(pval)+"'")
            else:
                print(gnow+" ERROR expected single length dictionary per list item")
        with safewrit: itemwrit+=cntr
    else:
        print(gnow+" Error expected items tag in multiget/put")

def jr_pop(jrequest,tnow,gnow):
    global itemwrit
    global safewrit
    global saftey
    retval=""
    chk=0
    if ('key' in jrequest):
        with saftey:
            if jrequest['key'] in keyvaluestore:
                retval=str(keyvaluestore[jrequest['key']][0])
                keyvaluestore.pop(jrequest['key'])
                chk=1
        if chk==1: # out of other lock's scope to prevent possible deadlock
            with safewrit: itemwrit+=cntr
    return(retval)

def jr_get(jrequest,tnow,gnow):
    global saftey
    global itemread
    global saferead
    retval=""
    chk=0
    if ('key' in jrequest):
        with saftey:
            if jrequest['key'] in keyvaluestore:
                retval=str(keyvaluestore[jrequest['key']][0])
                chk=1
        if chk==1:
            with saferead: itemread+=1
    return(retval)


def jr_jget(jrequest,tnow,gnow):
    global saftey
    global itemread
    global saferead
    retval=""
    chk=0
    if ('key' in jrequest):
        with saftey:
            if jrequest['key'] in keyvaluestore:
                keyp="\"key\":\""+str(jrequest['key'])+"\""
                valp="\"val\":\""+str(keyvaluestore[jrequest['key']][0])+"\""
                agep=round((tnow-keyvaluestore[jrequest['key']][1]),3)
                timep="\"age\":\""+str(agep)+"\""
                retval="{"+keyp+","+valp+","+timep+"}"
                chk=1
        if chk==1:
            with saferead: itemread+=1
    return retval

def jr_mget(jrequest,tnow,gnow):
    global saftey
    global itemread
    global saferead
    retval=""
    if ('items' in jrequest):
        keys=jrequest['items']
        itemlist=[]
        for oneky in keys:
            with saftey:
                if oneky in keyvaluestore:
                    keyp="\"key\":\""+str(oneky)+"\""
                    valp="\"val\":\""+str(keyvaluestore[oneky][0])+"\""
                    agep=round((tnow-keyvaluestore[oneky][1]),3)
                    timep="\"age\":\""+str(agep)+"\""
                    retval="{"+keyp+","+valp+","+timep+"}"
                    itemlist.append("{"+keyp+","+valp+","+timep+"}")
        retval=",\n".join(itemlist)
        retval="[\n"+retval+"\n]"
        with saferead: itemread+=len(itemlist)
    else:
        print(gnow+" Error expected items tag in multiget/put")
    return retval

def jr_getlike(jrequest,tnow,gnow):
    global saftey
    global itemread
    global saferead
    retval=""
    if ('key' in jrequest):
        matches=[]
        searchkey=jrequest['key']
        with saftey: #all needs to be checked, copy all under lock to tmp
            keyvaluestoretmp=keyvaluestore
        for allk in keyvaluestoretmp:
            if allk.find(searchkey)>=0:
                keyp='"key":"'+allk+'"'
                valp='"val":"'+str(keyvaluestoretmp[allk][0])+'"'
                agep=str(round((tnow-keyvaluestoretmp[allk][1]),3))
                timp='"age":"'+agep+'"'
                matches.append("{"+keyp+","+valp+","+timp+"}")
        with saferead: itemread+=len(matches)
        retval=",\n".join(matches)
        retval="[\n"+retval+"\n]"
    return(retval)

def htmlsyn(itext):
    htmlfinal=[]
    htmlparta="""<!DOCTYPE html><head></head><html>
<style>
body { background-color:white; color:black; font-family: "Lucida Console", Monaco, monospace;font-size: 0.8em}
.version {color:#0044dd;} .usage   {color:#009999;}
.eg      {color:#006666;} .prompt  {color:#884422;}
.json    {color:#990099;} .normal  {color:#003300;}
.web     {color:#0000ff;}</style><body>"""
    htmlpartb="""</body></html>"""
    lines=itext.split("\n")
    spantype="normal"
    for line in lines:
        trimline=line.strip().lower()
        if trimline.startswith('version') : spantype="version"
        if trimline.startswith('usage') : spantype="usage"
        if trimline.startswith('>>>>>') : spantype="prompt"
        if trimline.startswith('e.g.') : spantype="eg"
        if trimline.startswith('[') : spantype="json"
        if trimline.startswith('{') : spantype="json"
        if trimline.startswith('http') : spantype="web"
        pline=line.replace('"','&quot;').replace("'",'&#39;').replace(' ','&nbsp;').replace('>','&gt;').replace('>','&lt;')
        pline='<span class="'+spantype+'">'+pline+'</span><br/>'
        htmlfinal.append(pline)
    htmlpage=htmlparta+'\n'.join(htmlfinal)+htmlpartb
    return(htmlpage)


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
        if parsed_data.geturl().startswith("/health"):
            message="OK"
        elif parsed_data.geturl().startswith("/key/"):
            keyp=parsed_data.geturl().replace("/key/","").replace("%20"," ")
            print(gnow+" GET request for "+keyp)
            chk=0
            with saftey:
                if keyp in keyvaluestore:
                    message=keyvaluestore[keyp][0]
                    chk=1
            if chk==1:
                with saferead: itemread+=1
        elif parsed_data.geturl().startswith("/save/"):
            pfile=parsed_data.geturl().replace("/save/","")
            if os.path.isfile(pfile):
                message="file "+pfile+" already exists"
                print(gnow+" "+message)
            else:
                with saftey:
                    keyvaluestoretmp=keyvaluestore
                pickle.dump(keyvaluestoretmp,open(datastoreloc+pfile,'wb'))
                message="key-value hash table has been stored in "+datastoreloc+pfile
                print(gnow+" "+message)
        elif parsed_data.geturl().startswith("/load/"):
            loaded=1
            pfile=parsed_data.geturl().replace("/load/","")
            print(gnow+" attempting to load "+pfile)
            try:
                keyvaluestoretmp=pickle.load(open(datastoreloc+pfile,'r'))
            except:
                Message="ERROR Cannot load "+pfile
                print(gnow+" "+message)
                loaded=0
            if loaded==1:
                with saftey:
                    keyvaluestore=keyvaluestoretmp
                message="key-value hash table has been loaded from "+datastoreloc+pfile
                print(gnow+" "+message)
        elif parsed_data.geturl().startswith("/help/"):
            message=htmlsyn(examples)
        elif parsed_data.geturl().startswith("/status/"):
            val_items_written=0
            val_items_read=0
            val_requests_made=0
            val_items_writtenps=0
            val_items_readps=0
            val_requests_madeps=0
            with safeps:
                val_items_writtenps=itemwritps
                val_items_readps=itemreadps
                val_requests_madeps=reqcountps
            with saftey:
                keyvaluestoretmp=keyvaluestore
            with saferead: val_items_read=itemread
            with safewrit: val_items_written=itemwrit
            with safereqs: val_requests_made=reqcount
            timenow=time.time()
            uptime=timenow-server_start_timeunx
            up_sec=uptime%60
            up_min=int(uptime/60)%60
            up_hrs=int(uptime/3600)%24
            up_day=int(uptime/86400)
            readableuptime=str(up_day)+" days, "+str(up_hrs)+" hours, "+str(up_min)+" minutes, "+str(up_sec)+" seconds"
            statmsg=[]
            statmsg.append('{')
            statmsg.append(' "Total items stored"     : "'+str(len(keyvaluestoretmp))+'",')
            statmsg.append(' "Total item memory"      : "'+str(sys.getsizeof(keyvaluestoretmp))+'",')
            statmsg.append(' "requests per second"    : "'+str(val_requests_madeps)+'",')
            statmsg.append(' "item reads per second"  : "'+str(val_items_readps)+'",')
            statmsg.append(' "item writes per second" : "'+str(val_items_writtenps)+'",')
            statmsg.append(' "Total requests"         : "'+str(val_requests_made)+'",')
            statmsg.append(' "Total items read"       : "'+str(val_items_read)+'",')
            statmsg.append(' "Total items written"    : "'+str(val_items_written)+'",')
            statmsg.append(' "Server start time"      : "'+fmt_server_start_time+'",')
            statmsg.append(' "Server uptime(s)"       : "'+str(uptime)+'",')
            statmsg.append(' "Server uptime"          : "'+readableuptime+'"')
            statmsg.append('}')
            message="\n".join(statmsg)
        else: #general print alll items
            itemlist=[]
            message=""
            with saftey: #store in temp variable so hold lock a minimum
                keyvaluestoretmp=keyvaluestore
                print(keyvaluestoretmp)
            with saferead: itemread+=len(keyvaluestoretmp)
            for items in keyvaluestoretmp:
                keyp="\"key\":\""+str(items)+"\""
                valp="\"val\":\""+str(keyvaluestoretmp[items][0])+"\""
                agep=str(round(tnow-keyvaluestoretmp[items][1],2))
                timp="\"age\":\""+agep+"\""
                itemlist.append("{"+keyp+","+valp+","+timp+"}")
                itemlist.sort()
            message=",\n".join(itemlist)
            message="[\n"+message+"\n]" #json list output
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
        retval=""
        if ('cmd' in jrequest):
            if jrequest['cmd'].lower()=='pop':
                jr_pop(jrequest,tnow,gnow)
            if jrequest['cmd'].lower()=='put':
                jr_put(jrequest,tnow,gnow)
            if jrequest['cmd'].lower()=='mput':
                jr_mput(jrequest,tnow,gnow)
            if jrequest['cmd'].lower()=='get':
                retval=jr_get(jrequest,tnow,gnow)
            if jrequest['cmd'].lower()=='jget':
                retval=jr_jget(jrequest,tnow,gnow)
            if jrequest['cmd'].lower()=='mget':
                retval=jr_mget(jrequest,tnow,gnow)
            if jrequest['cmd'].lower()=='getlike':
                retval=jr_getlike(jrequest,tnow,gnow)
            if jrequest['cmd'].lower()=='health':
                retval="OK"
        else:
            retval="Error: format json as {\"cmd\":\"get|put|jget\",\"key\":\"<key>\"[,\"val\":\"<value>\"]}"
        self.send_response(200)
        self.end_headers()
        self.wfile.write(str(retval))
        self.wfile.write('\n')
        return
    def log_message(self, format, *args):
        return


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    HTTPServer.request_queue_size=1000
    pass


def timemgmt(verbo):
    global itemread, itemread_last
    global itemwrit, itemwrit_last
    global saferead, safewrit, safereqs
    global reqcount, reqcount_last
    global reqcountps, itemreadps, itemwritps
    global polltime
    earlier=time.time()
    while True:
        time.sleep(polltime)
        now=time.time()
        elapsed_time=now-earlier
        val_items_written=0
        val_items_read=0
        val_requests_made=0
        with safewrit: val_items_written=itemwrit
        with saferead: val_items_read=itemread
        with safereqs: val_requests_made=reqcount
        with safeps:
            reqcountps=(val_requests_made-reqcount_last)/elapsed_time
            itemreadps=(val_items_read-itemread_last)/elapsed_time
            itemwritps=(val_items_written-itemwrit_last)/elapsed_time
            reqcount_last=reqcount
            itemread_last=itemread
            itemwrit_last=itemwrit
        earlier=now


def runserver():
    global threadlist
    global maxthreads
    print("starting timing thread")
    thread.start_new_thread(timemgmt,("",))
    print("setting up http server")
    server = ThreadedHTTPServer(('0.0.0.0',serverpt), Handler)
    print("starting server")
    server.serve_forever()




def  argchk(args, param, option=None):
    if param in args:
        if option == None:
            return True
        else:
            optidx=args.index(param)+1
            if optidx < len(args):
                return args[optidx]
    return None



def main():
    global locserver
    global pidfile
    global serverpt
    args=sys.argv

    if argchk(args,"-s",1):
        try:
            servercheck=jsonrequest("/",'{"cmd":"health"}',locserver).strip()
            if servercheck=="OK":
                print("The Server is already running")
        except Exception, e:
            print(pidfile)
            with open(pidfile,'w') as pidinfo:
                pidinfo.write(str(os.getpid()))
            runserver()
        ex

"""
    if prms>=2:
        for idx in range(len(args)):
            if args[idx]=="-s":
                if idx < (len(args)-1):
                    locserver=args[idx+1]
                    args.pop(idx+1)
                    args.pop(idx)
                    prms-=2
                    if prms==1:
                        try:
                            servercheck=jsonrequest("/",'{"cmd":"health"}',locserver).strip()
                            if servercheck=="OK":
                                print("The Server is already running")
                        except Exception, e:
                            print(pidfile)
                            with open(pidfile,'w') as pidinfo:
                                pidinfo.write(str(os.getpid()))
                            if ':' in locserver:
                                serverpt=int(locserver.split(":")[1])
                            runserver()
                        exit
                    break
        if args[1].lower()=="put":
            if prms>=4:
                jsonrequest("/",'{"cmd":"put","key":"'+args[2]+'","val":"'+args[3]+'"}',locserver)
            else:
                print("Error : 3 parameters needed, put <key> <value>")
        elif args[1].lower()=="get":
            if prms>=3:
                qury=jsonrequest("/",'{"cmd":"get","key":"'+args[2]+'"}',locserver)
                print(qury)
            else:
                print("Error : 2 parameters needed, get <key>")
        elif args[1].lower()=="jget":
            if prms>=3:
                qury=jsonrequest("/",'{"cmd":"jget","key":"'+args[2]+'"}',locserver)
                print(qury)
            else:
                print("Error : 2 parameters needed, jget <key>")
        elif args[1].lower()=="json":
            qury=jsonrequest("/",args[2],locserver)
            print(qury)
        else:
            print(examples)
"""


if __name__ == '__main__':
    main()

