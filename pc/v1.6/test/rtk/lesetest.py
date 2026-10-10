import socket, threading, time
S="./"
base=open(S+"base.rtcm3","rb").read()
body="GNGGA,120000.00,6223.5498931,N,00635.4713921,E,1,20,0.7,416.0,M,0.0,M,,"
cs=0
for c in body: cs^=ord(c)
GGA=("$"+body+"*%02X\r\n"%cs).encode()
def caster():
    srv=socket.socket(); srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); srv.bind(("127.0.0.1",2198)); srv.listen(5)
    while True:
        c,_=srv.accept(); c.recv(4096); open(S+"caster_tilkopla.txt","a").write("x")
        c.sendall(b"ICY 200 OK\r\n\r\n")
        try:
            while True:
                for i in range(0,len(base),300): c.sendall(base[i:i+300]); time.sleep(0.05)
        except Exception: c.close()
def mottakar():
    srv=socket.socket(); srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); srv.bind(("127.0.0.1",7792)); srv.listen(5)
    while True:
        c,_=srv.accept(); c.settimeout(0.05)
        try:
            while True:
                c.sendall(GGA)
                try:
                    d=c.recv(65536)
                    if d: open(S+"mottakar_fekk.bin","ab").write(d)
                    elif d==b"": break
                except socket.timeout: pass
                time.sleep(0.2)
        except Exception: pass
        c.close()
threading.Thread(target=caster,daemon=True).start(); threading.Thread(target=mottakar,daemon=True).start()
while True: time.sleep(1)
