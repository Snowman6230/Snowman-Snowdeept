"""Falsk NTRIP-caster (base.rtcm3) og falsk mottakar over TCP (rover.rtcm3 + NMEA), i takt: 1 epoke per 0,25 s."""
import socket, threading, time, sys
sys.path.insert(0,"../..")
from rtcm import _bits
S="./"
def frames(b):
    i=0; out=[]
    while i<len(b):
        n=((b[i+1]&3)<<8)|b[i+2]; out.append(b[i:i+n+6]); i+=n+6
    return out
base=[f for f in frames(open(S+"base.rtcm3","rb").read()) if _bits(f[3:],0,12)!=1019]
rov=frames(open(S+"rover.rtcm3","rb").read())
bep=[]; cur=[]
for f in base:
    cur.append(f)
    if _bits(f[3:],0,12) in (1004,1077): bep.append(b"".join(cur)); cur=[]
body="GPGGA,000000.00,3509.6525,N,13936.8303,E,1,08,0.9,70.0,M,0.0,M,,"
cs=0
for ch in body: cs^=ord(ch)
GGA=("$"+body+"*%02X\r\n"%cs).encode()
GO=threading.Event(); T0=[0]
def caster():
    srv=socket.socket(); srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); srv.bind(("127.0.0.1",2199)); srv.listen(5)
    while True:
        c,_=srv.accept(); c.recv(4096)
        def lytt(c=c):
            while True:
                try: d=c.recv(4096)
                except Exception: return
                if not d: return
                open(S+"caster_fekk.txt","ab").write(d)
        threading.Thread(target=lytt,daemon=True).start()
        c.sendall(b"ICY 200 OK\r\nServer: Test Caster\r\n\r\n")
        GO.set()
        while not T0[0]: time.sleep(0.05)
        try:
            for k,e in enumerate(bep):
                while time.time()<T0[0]+k*0.25-0.05: time.sleep(0.01)
                c.sendall(e)
            time.sleep(30)
        except Exception: pass
        c.close()
def mottakar():
    srv=socket.socket(); srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); srv.bind(("127.0.0.1",7791)); srv.listen(5)
    while True:
        c,_=srv.accept()
        GO.wait(); T0[0]=time.time()+1.0
        try:
            for k,f in enumerate(rov):
                while time.time()<T0[0]+k*0.25: time.sleep(0.01)
                g=GGA
                c.sendall(g[:30]+f+g[30:])
            while True: c.sendall(GGA); time.sleep(0.25)
        except Exception: pass
        c.close()
threading.Thread(target=caster,daemon=True).start(); threading.Thread(target=mottakar,daemon=True).start()
print("klar",len(bep),len(rov),flush=True)
while True: time.sleep(1)
