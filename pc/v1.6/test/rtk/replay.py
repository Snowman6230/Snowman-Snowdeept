import sys, time, statistics as st
sys.path.insert(0,"../..")
import rtkmotor as M
from rtcm import _bits
S="./"
def frames(b):
    i=0; out=[]
    while i<len(b):
        n=((b[i+1]&3)<<8)|b[i+2]; out.append(b[i:i+n+6]); i+=n+6
    return out
base=frames(open(S+"base.rtcm3","rb").read()); rov=frames(open(S+"rover.rtcm3","rb").read())
ggas=[]
m=M.RtkMotor(on_solution=lambda g,i: ggas.append((g,i)))
assert m.start(install=False), M.LIB_ERR
import pyrtklib as R
ep=R.Arr1Ddouble(6)
for k,v in enumerate([2005,4,2,0,0,0]): ep[k]=v
t0=R.epoch2time(ep); m.rb.time=t0; m.rv.time=t0
print("baner frå RINEX:", m.load_nav(S+"rtklib/test/data/rinex/07590920.05n"))
base=[f for f in base if _bits(f[3:],0,12)!=1019]
bi=0
# NMEA-støy frå mottakaren blanda inn i roverstraumen (som når mottakaren sender både GGA og rådata)
noise=b"$GPGGA,000000.00,6216.0,N,00636.0,E,1,08,1.0,100.0,M,0.0,M,,*00\r\n"
texts=b""
for fr in rov:
    while bi<len(base):
        f=base[bi]; bi+=1; m.base_feed(f)
        if _bits(f[3:],0,12) in (1004,1077): break
    texts+=m.rover_bytes(noise[:20]+fr[:7]) ; texts+=m.rover_bytes(fr[7:]+noise[20:])
s=m.status()
print({k:s[k] for k in ("base_obs","rover_obs","eph","sol","fix","float","single","none","base_pos","err","rover_types")})
print("tekst attende ok:", texts.count(b"$GPGGA")==len(rov))
fixg=[g for g,i in ggas if i["stat"]==1]
print("første FIX:", fixg[0] if fixg else None)
import pyrtklib as R
lats=[float(g.split(",")[2]) for g in fixg]; hs=[float(g.split(",")[9]) for g in fixg]
print("FIX", len(fixg), "/", len(ggas), "spreiing breidd (m)", round(st.pstdev(lats)/60*111320,4) if lats else None, "høgd sd", round(st.pstdev(hs),4) if hs else None)
nv=m.nav; got=[(i,nv.eph[i].sat,nv.eph[i].toe.time) for i in range(nv.n) if nv.eph[i].sat>0]
print("eph i nav:", len(got), got[:4])
o=m.rv.obs.data[0]; print("rover obs0 sat",o.sat,"t",o.time.time,"P",list(o.P)[:2],"code",list(o.code)[:2],"n",m.rv.obs.n)
b=m.base_obs[0]; print("base obs0 sat",b.sat,"t",b.time.time,"P",list(b.P)[:2])
