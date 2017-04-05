#!/usr/bin/python
#-------------------------------------------------------------------------------
# Name:        cacheloader
# Purpose:     load db and elastic info into cache
#
# Author:      Ryan Cipriani
#
# Created:     17/03/2016
# Copyright:   left!
# Licence:     poetic
#-------------------------------------------------------------------------------

import json
import subprocess
import time
import random
import sys, os
import glob

mypath=os.path.dirname(os.path.realpath(sys.argv[0]))
jsonlist=glob.glob(mypath+os.sep+"*.json")
cachewholoc=mypath+os.sep+'cachewho.py'
cacheloadercount=mypath+os.sep+"cacheloadercounter"

pywinbin="c:\Python27\python.exe"

sragv=sys.argv
overridejsonlist=[]
while '-f' in sragv:
    paridx=sragv.index('-f')
    overridejsonlist.append(sragv[1+paridx])
    sragv.pop(paridx+1)
    sragv.pop(paridx)
if overridejsonlist<>[]:
    jsonlist=overridejsonlist



proclist={}
cachreturn={}

def pidkillkids(pid):
    if os.sep=="/":
        subprocess.Popen("pkill -TERM -P "+str(pid),shell=True,stdout=subprocess.PIPE, stdin=subprocess.PIPE) #unix way to kill p-tree
    else:
        subprocess.Popen("taskkill /t /pid "+str(pid),shell=True,stdout=subprocess.PIPE, stdin=subprocess.PIPE) #windows way


def tstamp():
    return time.strftime("%Y%m%d-%H:%M:%S",time.gmtime())+(str(time.time()%1)+"000")[1:5]


def cacheloadjson(inputprocfile,maxparallelrequest,jsonpostkeycount):

    cacheloadercount=inputprocfile.replace('.json','.cntr')
    cacheloadererrs=inputprocfile.replace('.json','.dbug')


    with open(cacheloadererrs, 'w') as inf:
        inf.write("Start: "+tstamp()+"\n")


    if len(sragv) >1:
        loadcounter=int(sragv[1])
        with open(cacheloadercount, 'w') as inf:
            inf.write(str(loadcounter))
    else:
        ### manage load counter###
        if os.path.isfile(cacheloadercount):
            with open(cacheloadercount, 'r') as inf:
                loadcounter=int(inf.read())
        else:
            loadcounter=-1
        loadcounter+=1
        with open(cacheloadercount, 'w') as inf:
            inf.write(str(loadcounter))
        ### end manage load counter###

    with open(inputprocfile, 'r') as inf:
        rawdata=inf.read()
    try:
        cmds=json.loads(rawdata)
    except:
        print("Error loading input json "+str(inputprocfile))
        return ()

    popcmds=cmds
    proclist={}
    warntime=time.time()
    while len(popcmds)+len(proclist)>0:
        if len(proclist)<maxparallelrequest:
            if len(popcmds) > 0:
                raffle=random.randrange(len(popcmds))
                timing=popcmds[raffle][2]
                if len(popcmds[raffle])>3:
                    extraparams=popcmds[raffle][3]
                else:
                    extraparams={}
                runit=0

                timingbelt=int(timing.replace("m",""))
                if loadcounter%timingbelt==0 : runit=1

                if runit==1:
                    requestcmd=popcmds[raffle][1]
                    print("RUN: "+str(requestcmd))
                    evtime=time.time()
                    try:
                        prochndl=subprocess.Popen(requestcmd,shell=True,stdout=subprocess.PIPE, stdin=subprocess.PIPE)
                        proclist[prochndl.pid]=(popcmds[raffle][0],prochndl,evtime,timingbelt,extraparams) # append key and process handle
                        with open(cacheloadererrs, 'a') as outf:
                             outf.write(tstamp()+"    INFO --- execute ["+str(prochndl.pid)+"] ["+proclist[prochndl.pid][0]+"]"+requestcmd+"\n")
                    except:
                        print("ERROR: "+requestcmd)
                popcmds.pop(raffle)
        for pids in proclist:
            key,handle,evtime,timinterval,extrasprms=proclist[pids]
            if handle.poll() <> None:
                cachreturn[key]=handle.communicate()[0].strip()
                proclist.pop(pids)
                break
        for pids in proclist:
            key,handle,evtime,timinterval,extrasprms=proclist[pids]
            if (time.time()-evtime)>5:
                if time.time()-warntime>1:
                     warntime=time.time()
                     warning=tstamp()+"    WARN --- WAITING ON :: "+key+"    running for    "+str(warntime-evtime)+" seconds"
                     print(warning)
                     with open(cacheloadererrs, 'a') as outf:
                         outf.write(warning+"\n")
            if (time.time()-evtime)>(10*timinterval):
                warning=tstamp()+"    WARN --- KILL ::  "+str(pids)+"  "+key+"   runtume is beyond call interval"
                print(warning)
                with open(cacheloadererrs, 'a') as outf:
                    outf.write(warning+"\n")
                pidkillkids(pids) #use pkill to kill shell and child processes
                time.sleep(0.5)
                if 'loaddefault' in extrasprms:
                    cachreturn[key]=extrasprms['loaddefault']
                    print("DEFAULT: "+cachreturn[key])
                proclist.pop(pids)
                break



    print(cachreturn)

    while len(cachreturn)>0:
        batchlist=[]
        keylist=[]
        for akey in cachreturn:
            item='{"'+str(akey)+'":"'+str(cachreturn[akey])+'"}'
            batchlist.append(item)
            keylist.append(akey)
            if len(batchlist)>jsonpostkeycount:break
        for stuff in keylist:
            cachreturn.pop(stuff)
        jlist=','.join(batchlist)
        jrequest= '{"cmd": "mput","items": ['+jlist+']}'
        if os.name=="nt":
            prochndl=subprocess.Popen([pywinbin,cachewholoc,'json',jrequest],stdout=subprocess.PIPE, stdin=subprocess.PIPE,shell=True)
        else:
            prochndl=subprocess.Popen([cachewholoc,'json',jrequest],stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        procdone=prochndl.communicate()
        print(prochndl)
        print("done with "+jrequest)



def main():
    print("json list: "+str(jsonlist))
    for eachjson in jsonlist:
        print("processing "+eachjson)
        cacheloadjson(eachjson,8,30)



if __name__ == '__main__':
    main()



