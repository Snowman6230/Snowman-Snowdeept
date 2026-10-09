"""Lag RTCM 3-straumar (base: 1006+1004+1019, rover: 1004) av RTKLIB-testdata 0759/3040 – til test av SNOWMAN-RTK."""
import pyrtklib as R
D="./rtklib/test/data/rinex/"
OUT="./"
import sys
MSG=int(sys.argv[1]) if len(sys.argv)>1 else 1004
nav=R.nav_t(); R.readrnx(D+"07590920.05n",0,"",R.obs_t(),nav,R.sta_t())
def enc(obsfile,rcv,staid,with_base,with_eph):
    obs,sta=R.obs_t(),R.sta_t(); R.readrnx(D+obsfile,rcv,"",obs,R.nav_t(),sta)
    ep={}
    for i in range(obs.n):
        d=obs.data[i]; ep.setdefault((d.time.time,d.time.sec),[]).append(i)
    r=R.rtcm_t(); R.init_rtcm(r); r.staid=staid
    for k in range(3): r.sta.pos[k]=sta.pos[k]
    out=bytearray(); sent=set()
    def put(t):
        n=R.gen_rtcm3(r,t,0,0)
        if n: out.extend(bytes(r.buff[i] for i in range(r.nbyte)) if not isinstance(r.buff[0],int) or True else b"")
        return n
    for key in sorted(ep):
        idx=ep[key]; r.time=obs.data[idx[0]].time; r.obs.n=len(idx)
        for j,i in enumerate(idx): r.obs.data[j]=obs.data[i]
        if with_base and not len(out)%5==99: put(1006)
        if with_eph:
            for e in range(nav.n):
                s=nav.eph[e].sat
                if s not in sent and abs(nav.eph[e].toe.time-key[0])<7200:
                    r.nav.eph[s-1]=nav.eph[e]; r.ephsat=s; put(1019); sent.add(s)
        put(MSG)
    return bytes(out)
b=enc("30400920.05o",2,1234,True,True); open(OUT+"base.rtcm3","wb").write(b)
v=enc("07590920.05o",1,0,False,False); open(OUT+"rover.rtcm3","wb").write(v)
print(len(b),len(v))
