import math
import numpy as np

import nav.structs

r2d = 180.0 / math.pi
d2r = math.pi / 180.0

# this class organizes the filter output in a way that is more
# convenient and direct for matplotlib
class data_store():
    def __init__(self):
        self.data = []
        
        self.time = []
        self.psi = []
        self.the = []
        self.phi = []
        self.lat = []
        self.lon = []
        self.alt = []
        self.vn = []
        self.ve = []
        self.vd = []

        self.ax_bias = []
        self.ay_bias = [] 
        self.az_bias = []
        self.p_bias = []
        self.q_bias = []
        self.r_bias = []

        self.Pp = []
        self.Pvel = []
        self.Patt = []
        self.Pab = []
        self.Pgb = []

        self.p = []
        self.q = []
        self.r = []
        self.ax = []
        self.ay = []
        self.az = []
        
        self.wind_deg = []
        self.wind_kt = []
        self.pitot_scale = []

        self.asi = []
        self.synth_asi = []

    def append(self, insgps, imupt):
        self.data.append(insgps)
        
        self.time.append(insgps.time)
        
        self.psi.append(insgps.psi)
        self.the.append(insgps.the)
        self.phi.append(insgps.phi)
        self.lat.append(insgps.lat)
        self.lon.append(insgps.lon)
        self.alt.append(insgps.alt)
        self.vn.append(insgps.vn)
        self.ve.append(insgps.ve)
        self.vd.append(insgps.vd)

        self.ax_bias.append(insgps.abx)
        self.ay_bias.append(insgps.aby)
        self.az_bias.append(insgps.abz)
        self.p_bias.append(insgps.gbx)
        self.q_bias.append(insgps.gby)
        self.r_bias.append(insgps.gbz)
        
        self.Pp.append( np.array([insgps.Pp0, insgps.Pp1, insgps.Pp2]) )
        self.Pvel.append( np.array([insgps.Pv0, insgps.Pv1, insgps.Pv2]) )
        self.Patt.append( np.array([insgps.Pa0, insgps.Pa1, insgps.Pa2]) )
        self.Pab.append( np.array([insgps.Pabx, insgps.Paby, insgps.Pabz]) )
        self.Pgb.append( np.array([insgps.Pgbx, insgps.Pgby, insgps.Pgbz]) )

        if imupt != None:
            self.p.append(imupt.p)
            self.q.append(imupt.q)
            self.r.append(imupt.r)
            self.ax.append(imupt.ax)
            self.ay.append(imupt.ay)
            self.az.append(imupt.az)
        
    def append_from_filter(self, filterpt):
        self.time.append(filterpt.time)
        self.psi.append(filterpt.psi)
        self.the.append(filterpt.the)
        self.phi.append(filterpt.phi)
        self.lat.append(filterpt.lat)
        self.lon.append(filterpt.lon)
        self.alt.append(filterpt.alt)
        self.vn.append(filterpt.vn)
        self.ve.append(filterpt.ve)
        self.vd.append(filterpt.vd)
        
    def append_from_gps(self, gpspt):
        self.time.append(gpspt.time)
        self.lat.append(gpspt.lat*d2r)
        self.lon.append(gpspt.lon*d2r)
        self.alt.append(gpspt.alt)
        self.vn.append(gpspt.vn)
        self.ve.append(gpspt.ve)
        self.vd.append(gpspt.vd)

    def add_wind(self, wind_deg, wind_kt, pitot_scale):
        self.wind_deg.append(wind_deg)
        self.wind_kt.append(wind_kt)
        self.pitot_scale.append(pitot_scale)

    def add_asi(self, asi_kt, synth_asi_kt):
        self.asi.append(asi_kt)
        self.synth_asi.append(synth_asi_kt)
        
    # return the index corresponding to the given time (or the next
    # index if there is no exact match
    def find_index(self, time):
        for k, t in enumerate(self.time):
            if t >= time:
                return k
        # every time in the set is earlier than the given time, so
        # return the index of the last entry.
        return len(self.time) - 1

# return a record filled in with half the difference between 
def diff_split(nav1, nav2):
    diff = nav.structs.NAVdata()
    
    diff.time = nav1.time
    print ' err t =', diff.time
    diff.psi = (nav1.psi - nav2.psi) * 0.5
    diff.the = (nav1.the - nav2.the) * 0.5
    diff.phi = (nav1.phi - nav2.phi) * 0.5
    print ' att:', diff.phi, diff.the, diff.psi
    diff.lat = (nav1.lat - nav2.lat) * 0.5
    diff.lon = (nav1.lon - nav2.lon) * 0.5
    diff.alt = (nav1.alt - nav2.alt) * 0.5
    print ' pos:', diff.lat, diff.lon, diff.alt
    diff.vn = (nav1.vn - nav2.vn) * 0.5
    diff.ve = (nav1.ve - nav2.ve) * 0.5
    diff.vd = (nav1.vd - nav2.vd) * 0.5
    print ' vel:', diff.vn, diff.ve, diff.vd

    diff.abx = (nav1.abx - nav2.abx) * 0.5
    diff.aby = (nav1.aby - nav2.aby) * 0.5
    diff.abz = (nav1.abz - nav2.abz) * 0.5
    print ' accel bias:', diff.abx, diff.aby, diff.abz
    diff.gbx = (nav1.gbx - nav2.gbx) * 0.5
    diff.gby = (nav1.gby - nav2.gby) * 0.5
    diff.gbz = (nav1.gbz - nav2.gbz) * 0.5
    print ' gyro bias:', diff.gbx, diff.gby, diff.gbz
        
    # [insgps.Pp0, insgps.Pp1, insgps.Pp2]
    # [insgps.Pv0, insgps.Pv1, insgps.Pv2]
    # [insgps.Pa0, insgps.Pa1, insgps.Pa2]
    # [insgps.Pabx, insgps.Paby, insgps.Pabz]
    # [insgps.Pgbx, insgps.Pgby, insgps.Pgbz]
    return diff

# return a weighted average of the two records
def weighted_avg(nav1, nav2, w):
    avg = nav.structs.NAVdata()

    a = w
    b = 1 - w
    
    avg.time = nav1.time
    avg.psi = a*nav1.psi + b*nav2.psi
    avg.the = a*nav1.the + b*nav2.the
    avg.phi = a*nav1.phi + b*nav2.phi
    avg.lat = a*nav1.lat + b*nav2.lat
    avg.lon = a*nav1.lon + b*nav2.lon
    avg.alt = a*nav1.alt + b*nav2.alt
    avg.vn = a*nav1.vn + b*nav2.vn
    avg.ve = a*nav1.ve + b*nav2.ve
    avg.vd = a*nav1.vd + b*nav2.vd
    avg.abx = a*nav1.abx + b*nav2.abx
    avg.aby = a*nav1.aby + b*nav2.aby
    avg.abz = a*nav1.abz + b*nav2.abz
    avg.gbx = a*nav1.gbx + b*nav2.gbx
    avg.gby = a*nav1.gby + b*nav2.gby
    avg.gbz = a*nav1.gbz + b*nav2.gbz
    return avg
    
# return a weighted average of the two records
def sum(nav1, nav2):
    result = nav.structs.NAVdata()

    result.time = nav1.time
    result.psi = nav1.psi + nav2.psi
    result.the = nav1.the + nav2.the
    result.phi = nav1.phi + nav2.phi
    result.lat = nav1.lat + nav2.lat
    result.lon = nav1.lon + nav2.lon
    result.alt = nav1.alt + nav2.alt
    result.vn = nav1.vn + nav2.vn
    result.ve = nav1.ve + nav2.ve
    result.vd = nav1.vd + nav2.vd
    result.abx = nav1.abx + nav2.abx
    result.aby = nav1.aby + nav2.aby
    result.abz = nav1.abz + nav2.abz
    result.gbx = nav1.gbx + nav2.gbx
    result.gby = nav1.gby + nav2.gby
    result.gbz = nav1.gbz + nav2.gbz
    return result
