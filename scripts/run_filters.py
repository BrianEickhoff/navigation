#!/usr/bin/python

"""run_filters.py

This script plays flight data through the selected navigation filters.
The filters are compiled as .so objects and wrapped for python with boost.

A set of customizable input flags are defined at the start of the script.

Initial revision: Hamid M.
Many updates: Curtis L. Olson
"""

import argparse
import math
import numpy as np
import time
import os

import nav.structs

from nav.data import flight_data, aura

import data_store
import wind
import synth_asi

parser = argparse.ArgumentParser(description='nav filter')
parser.add_argument('--flight', help='load specified aura flight log')
parser.add_argument('--aura-flight', help='load specified aura flight log')
parser.add_argument('--px4-sdlog2', help='load specified px4 sdlog2 (csv) flight log')
parser.add_argument('--px4-ulog', help='load specified px4 ulog (csv) base path')
parser.add_argument('--umn-flight', help='load specified .mat flight log')
parser.add_argument('--sentera-flight', help='load specified sentera flight log')
parser.add_argument('--sentera2-flight', help='load specified sentera2 flight log')
parser.add_argument('--recalibrate', help='recalibrate raw imu from some other calibration file')
args = parser.parse_args()

# # # # # START INPUTS # # # # #

#MAT_FILENAME = 'flightdata_595.4961sec.mat'
T_GPSOFF = 350          # Time, above which, mission->haveGPS set to 0.
                        # To always keep GPS, set to: -1
FLAG_PLOT_ATTITUDE = True
FLAG_PLOT_VELOCITIES = True
FLAG_PLOT_GROUNDTRACK = True
FLAG_PLOT_ALTITUDE = True
FLAG_PLOT_WIND = True
FLAG_PLOT_SYNTH_ASI = True
FLAG_PLOT_BIASES = True
SIGNAL_LIST = [0, 1, 8]  # List of signals [0 to 9] to be plotted
FLAG_WRITE2CSV = False # Write results to CSV file.
# # # # # END INPUTS # # # # #

import os
import csv
import numpy as np
from matplotlib import pyplot as plt
import navpy

# filter interfaces
import nav_eigen
import nav_eigen_mag
import nav_openloop
#import MadgwickAHRS

filter1 = nav_eigen.filter()
#filter1 = nav_mag.filter()
#filter1 = nav_eigen.filter()
filter2 = nav_eigen_mag.filter()
#filter2 = nav_openloop.filter()
#filter2 = MadgwickAHRS.filter()

r2d = 180.0 / math.pi
mps2kt = 1.94384

def run_filter(filter, data, call_init=True, start_time=None, end_time=None):
    # for convenience ...
    imu_data = data['imu']
    gps_data = data['gps']
    if 'air' in data:
        air_data = data['air']
    else:
        air_data = []
    filter_data = data['filter']
    if 'pilot' in data:
        pilot_data = data['pilot']
    else:
        pilot_data = []
    if 'act' in data:
        act_data = data['act']
    else:
        act_data = []
        
    data_dict = data_store.data_store()
    # t_store = []
    
    # Using while loop starting at k (set to kstart) and going to end
    # of .mat file
    run_start = time.time()
    gps_index = 0
    air_index = 0
    airpt = nav.structs.Airdata()
    filter_index = 0
    pilot_index = 0
    pilotpt = None
    act_index = 0
    actpt = None
    new_gps = 0
    synth_filt_asi = 0
    if call_init:
        filter_init = False
    else:
        filter_init = True
    k_start = 0
    if start_time != None:
        for k, imu_pt in enumerate(imu_data):
            #print k_start, imu_pt.time, start_time
            if imu_pt.time >= start_time:
                k_start = k
                break
    k_end = len(imu_data)
    if end_time != None:
        for k, imu_pt in enumerate(imu_data):
            if imu_pt.time >= end_time:
                k_end = k
                break
    print k_start, k_end
    for k in range(k_start, k_end):
        imupt = imu_data[k]
        if gps_index < len(gps_data) - 1:
            # walk the gps counter forward as needed
            newData = 0
            while gps_index < len(gps_data) - 1 and gps_data[gps_index+1].time <= imupt.time:
                gps_index += 1
                newData = 1
            gpspt = gps_data[gps_index]
            gpspt.newData = newData
        else:
            # no more gps data, stay on the last record
            gpspt = gps_data[gps_index]
            gpspt.newData = 0
        #print gpspt.time
        if air_index < len(air_data) - 1:
            # walk the airdata counter forward as needed
            while air_index < len(air_data) - 1 and air_data[air_index+1].time <= imupt.time:
                air_index += 1
            airpt = air_data[air_index]
        elif len(air_data):
            # no more air data, stay on the last record
            airpt = air_data[air_index]
        # print airpt.time
        # walk the filter counter forward as needed
        if len(filter_data):
            while filter_index < len(filter_data) - 1 and filter_data[filter_index].time <= imupt.time:
                filter_index += 1
            filterpt = filter_data[filter_index]
        else:
            filterpt = filter_data[filter_index]
        #print "t(imu) = " + str(imupt.time) + " t(gps) = " + str(gpspt.time)
        if 'pilot' in data:
            while pilot_index < len(pilot_data) - 1 and pilot_data[pilot_index].time <= imupt.time:
                pilot_index += 1
            pilotpt = pilot_data[pilot_index]
        elif 'pilot' in data:
            pilotpt = pilot_data[pilot_index]
        if 'act' in data:
            while act_index < len(act_data) - 1 and act_data[act_index].time <= imupt.time:
                act_index += 1
            actpt = act_data[act_index]
            #print act_index, imupt.time, actpt.time, actpt.throttle, actpt.elevator
        elif 'act' in data:
            actpt = act_data[act_index]

        # If k is at the initialization time init_nav else get_nav
        if not filter_init and gps_index > 0:
            print "init:", imupt.time, gpspt.time
            navpt = filter.init(imupt, gpspt, filterpt)
            filter_init = True
        elif filter_init:
            navpt = filter.update(imupt, gpspt, filterpt)

        if filter_init:
            # experimental: run wind estimator
            # print airpt.airspeed
            (wn, we, ps) = wind.update_wind(imupt.time, airpt.airspeed,
                                            navpt.psi, navpt.vn, navpt.ve)
            #print wn, we, math.atan2(wn, we), math.atan2(wn, we)*r2d
            wind_deg = 90 - math.atan2(wn, we) * r2d
            if wind_deg < 0: wind_deg += 360.0
            wind_kt = math.sqrt( we*we + wn*wn ) * mps2kt
            #print wn, we, ps, wind_deg, wind_kt

            # experimental: synthetic airspeed estimator
            if 'act' in data and synth_asi.rbfi == None:
                #print airpt.airspeed, actpt.throttle, actpt.elevator
                synth_asi.append(navpt.phi, actpt.throttle, actpt.elevator,
                                 imupt.q, airpt.airspeed)
            elif 'act' in data:
                asi_kt = synth_asi.est_airspeed(navpt.phi, actpt.throttle,
                                               actpt.elevator, imupt.q)
                synth_filt_asi = 0.9 * synth_filt_asi + 0.1 * asi_kt
                data_dict.add_asi(airpt.airspeed, synth_filt_asi)
            
        # Store the desired results obtained from the compiled test
        # navigation filter and the baseline filter
        if filter_init:
            data_dict.append(navpt, imupt)
            data_dict.add_wind(wind_deg, wind_kt, ps)

        # Increment time up one step for the next iteration of the
        # while loop.
        k += 1

    # proper cleanup
    filter.close()
    run_end = time.time()
    elapsed_sec = run_end - run_start
    return data_dict, elapsed_sec

if args.flight:
    loader = 'aura'
    path = args.flight
elif args.aura_flight:
    loader = 'aura'
    path = args.aura_flight
elif args.px4_sdlog2:
    loader = 'px4_sdlog2'
    path = args.px4_sdlog2
elif args.px4_ulog:
    loader = 'px4_ulog'
    path = args.px4_ulog
elif args.sentera_flight:
    loader = 'sentera1'
    path = args.sentera_flight
elif args.sentera2_flight:
    loader = 'sentera2'
    path = args.sentera2_flight
elif args.umn_flight:
    loader = 'umn1'
    path = args.umn_flight
else:
    loader = None
    path = None
if 'recalibrate' in args:
    recal_file = args.recalibrate
else:
    recal_file = None
data = flight_data.load(loader, path, recal_file)
print "imu records:", len(data['imu'])
print "gps records:", len(data['gps'])
if 'air' in data:
    print "airdata records:", len(data['air'])
print "filter records:", len(data['filter'])
if 'pilot' in data:
    print "pilot records:", len(data['pilot'])
if 'act' in data:
    print "act records:", len(data['act'])
if len(data['imu']) == 0 and len(data['gps']) == 0:
    print "not enough data loaded to continue."
    quit()

if args.flight:
    plotname = os.path.basename(args.flight)    
elif args.aura_flight:
    plotname = os.path.basename(args.aura_flight)
elif args.px4_sdlog2:
    plotname = os.path.basename(args.px4_sdlog2)
elif args.sentera_flight:
    plotname = os.path.basename(args.sentera_flight)
elif args.sentera2_flight:
    plotname = os.path.basename(args.sentera2_flight)
elif args.umn_flight:
    plotname = os.path.basename(args.umn_flight)
else:
    plotname = "plotname not set correctly"

if False:
    # quick hack estimate gyro biases
    p_sum = 0.0
    q_sum = 0.0
    r_sum = 0.0
    for imu in data['imu']:
        p_sum += imu.p
        q_sum += imu.q
        r_sum += imu.r
    p_bias = p_sum / len(data['imu'])
    q_bias = q_sum / len(data['imu'])
    r_bias = r_sum / len(data['imu'])
    print "bias:", p_bias, q_bias, r_bias
    for imu in data['imu']:
        imu.p -= p_bias
        imu.q -= q_bias
        imu.r -= r_bias

if False:
    # quick rough hack at a magnetometer calibration
    x_min = 1000000.0
    y_min = 1000000.0
    z_min = 1000000.0
    x_max = -1000000.0
    y_max = -1000000.0
    z_max = -1000000.0
    for imu in data['imu']:
        if imu.hx < x_min: x_min = imu.hx
        if imu.hy < y_min: y_min = imu.hy
        if imu.hz < z_min: z_min = imu.hz
        if imu.hx > x_max: x_max = imu.hx
        if imu.hy > y_max: y_max = imu.hy
        if imu.hz > z_max: z_max = imu.hz
    print "x:", x_min, x_max
    print "y:", y_min, y_max
    print "z:", z_min, z_max
    dx = x_max - x_min
    dy = y_max - y_min
    dz = z_max - z_min
    cx = (x_min + x_max) * 0.5
    cy = (y_min + y_max) * 0.5
    cz = (z_min + z_max) * 0.5
    for imu in data['imu']:
        imu.hx = ((imu.hx - x_min) / dx) * 2.0 - 1.0
        imu.hy = ((imu.hy - y_min) / dy) * 2.0 - 1.0
        imu.hz = ((imu.hz - z_min) / dz) * 2.0 - 1.0
        
# rearrange flight data for plotting
t_gps = []
lat_gps = []
lon_gps = []
alt_gps = []
vn_gps = []
ve_gps = []
vd_gps = []
for g in data['gps']:
    t_gps.append(g.time)
    lat_gps.append(g.lat)
    lon_gps.append(g.lon)
    alt_gps.append(g.alt)
    vn_gps.append(g.vn)
    ve_gps.append(g.ve)
    vd_gps.append(g.vd)

t_flight = []
psi_flight = []
the_flight = []
phi_flight = []
navlat_flight = []
navlon_flight = []
navalt_flight = []
vn_flight = []
ve_flight = []
vd_flight = []
for f in data['filter']:
    t_flight.append(f.time)
    psi_flight.append(f.psi)
    the_flight.append(f.the)
    phi_flight.append(f.phi)
    navlat_flight.append(f.lat)
    navlon_flight.append(f.lon)
    navalt_flight.append(f.alt)
    vn_flight.append(f.vn)
    ve_flight.append(f.ve)
    vd_flight.append(f.vd)

r_flight = []
for i in data['imu']:
    r_flight.append(i.r)
    
# Default config
# config = nav.structs.NAVconfig()
# config.sig_w_ax = 0.05
# config.sig_w_ay = 0.05
# config.sig_w_az = 0.05
# config.sig_w_gx = 0.00175
# config.sig_w_gy = 0.00175
# config.sig_w_gz = 0.00175
# config.sig_a_d  = 0.1
# config.tau_a    = 100.0
# config.sig_g_d  = 0.00873
# config.tau_g    = 50.0
# config.sig_gps_p_ne = 3.0
# config.sig_gps_p_d  = 5.0
# config.sig_gps_v_ne = 0.5
# config.sig_gps_v_d  = 1.0
# config.sig_mag      = 0.2
# filter2.set_config(config)

# almost no trust in IMU ...
# config = nav.structs.NAVconfig()
# config.sig_w_ax = 2.0
# config.sig_w_ay = 2.0
# config.sig_w_az = 2.0
# config.sig_w_gx = 0.1
# config.sig_w_gy = 0.1
# config.sig_w_gz = 0.1
# config.sig_a_d  = 0.1
# config.tau_a    = 100.0
# config.sig_g_d  = 0.00873
# config.tau_g    = 50.0
# config.sig_gps_p_ne = 3.0
# config.sig_gps_p_d  = 5.0
# config.sig_gps_v_ne = 0.5
# config.sig_gps_v_d  = 1.0
# config.sig_mag      = 0.2
# filter2.set_config(config)

# less than default trust in IMU ...
# config = nav.structs.NAVconfig()
# config.sig_w_ax = 0.1
# config.sig_w_ay = 0.1
# config.sig_w_az = 0.1
# config.sig_w_gx = 0.003
# config.sig_w_gy = 0.003
# config.sig_w_gz = 0.003
# config.sig_a_d  = 0.1
# config.tau_a    = 100.0
# config.sig_g_d  = 0.00873
# config.tau_g    = 50.0
# config.sig_gps_p_ne = 3.0
# config.sig_gps_p_d  = 5.0
# config.sig_gps_v_ne = 0.5
# config.sig_gps_v_d  = 1.0
# config.sig_mag      = 0.2
# filter1.set_config(config)
# filter2.set_config(config)

# too high trust in IMU ...
# config = nav.structs.NAVconfig()
# config.sig_w_ax = 0.02
# config.sig_w_ay = 0.02
# config.sig_w_az = 0.02
# config.sig_w_gx = 0.00175
# config.sig_w_gy = 0.00175
# config.sig_w_gz = 0.00175
# config.sig_a_d  = 0.1
# config.tau_a    = 100.0
# config.sig_g_d  = 0.00873
# config.tau_g    = 50.0
# config.sig_gps_p_ne = 15.0
# config.sig_gps_p_d  = 20.0
# config.sig_gps_v_ne = 2.0
# config.sig_gps_v_d  = 4.0
# config.sig_mag      = 0.3
# filter1.set_config(config)

data_dict1, filter1_sec = run_filter(filter1, data)

print "building synthetic air data estimator..."
if 'act' in data:
    synth_asi.build()

data_dict2, filter2_sec = run_filter(filter2, data)

print "filter1 time = %.4f" % filter1_sec
print "filter2 time = %.4f" % filter2_sec
diff_sec = filter1_sec - filter2_sec
perc = diff_sec / filter1_sec
if perc >= 0.0:
    print "filter2 is %.1f%% faster" % (perc * 100.0)
else:
    print "filter2 is %.1f%% slower" % (-perc * 100.0)

if args.flight or args.aura_flight:
    if args.flight:
        filter_post = os.path.join(args.flight, "filter-post.txt")
    elif args.aura_flight:
        filter_post = os.path.join(args.aura_flight, "filter-post.txt")
    aura.save_filter_result(filter_post, data_dict1)
    
if args.sentera_flight:
    import data_sentera
    file_ins = os.path.join(args.sentera_flight, "filter-post-ins.txt")
    file_mag = os.path.join(args.sentera_flight, "filter-post-mag.txt")
    data_sentera.save_filter_result(file_ins, data_dict1)
    data_sentera.save_filter_result(file_mag, data_dict2)
    data_sentera.rewrite_pix4d_csv(args.sentera_flight, data_dict2)
    data_sentera.rewrite_image_metadata_txt(args.sentera_flight, data_dict2)

nsig = 3
t_store1 = data_dict1.time
t_store2 = data_dict2.time

# Plotting
r2d = np.rad2deg
if FLAG_PLOT_ATTITUDE:
    Patt1 = np.array(data_dict1.Patt, dtype=np.float64)
    Patt2 = np.array(data_dict2.Patt, dtype=np.float64)

    att_fig, att_ax = plt.subplots(3,2, sharex=True)

    # Roll PLot
    phi_nav = data_dict1.phi
    phi_nav_mag = data_dict2.phi
    att_ax[0,0].set_ylabel('Roll (deg)', weight='bold')
    att_ax[0,0].plot(t_flight, r2d(phi_flight), label='On Board', c='g', alpha=.5)
    att_ax[0,0].plot(t_store1, r2d(phi_nav), label=filter1.name, c='r', alpha=.8)
    att_ax[0,0].plot(t_store2, r2d(phi_nav_mag), label=filter2.name, c='b', alpha=.8)
    att_ax[0,0].grid()
    
    att_ax[0,1].plot(t_store1,nsig*np.rad2deg(np.sqrt(Patt1[:,0])),c='r')
    att_ax[0,1].plot(t_store1,-nsig*np.rad2deg(np.sqrt(Patt1[:,0])),c='r')
    att_ax[0,1].plot(t_store2,nsig*np.rad2deg(np.sqrt(Patt2[:,0])),c='b')
    att_ax[0,1].plot(t_store2,-nsig*np.rad2deg(np.sqrt(Patt2[:,0])),c='b')
    att_ax[0,1].set_ylabel('3*stddev', weight='bold')

    # Pitch PLot
    the_nav = data_dict1.the
    the_nav_mag = data_dict2.the
    att_ax[1,0].set_ylabel('Pitch (deg)', weight='bold')
    att_ax[1,0].plot(t_flight, r2d(the_flight), label='On Board', c='g', alpha=.5)
    att_ax[1,0].plot(t_store1, r2d(the_nav), label=filter1.name, c='r', alpha=.8)
    att_ax[1,0].plot(t_store2, r2d(the_nav_mag), label=filter2.name,c='b', alpha=.8)
    att_ax[1,0].grid()

    att_ax[1,1].plot(t_store1,nsig*np.rad2deg(np.sqrt(Patt1[:,1])),c='r')
    att_ax[1,1].plot(t_store1,-nsig*np.rad2deg(np.sqrt(Patt1[:,1])),c='r')
    att_ax[1,1].plot(t_store2,nsig*np.rad2deg(np.sqrt(Patt2[:,1])),c='b')
    att_ax[1,1].plot(t_store2,-nsig*np.rad2deg(np.sqrt(Patt2[:,1])),c='b')
    att_ax[1,1].set_ylabel('3*stddev', weight='bold')

    # Yaw Plot
    psi_nav = data_dict1.psi
    psi_nav_mag = data_dict2.psi
    att_ax[2,0].set_title(plotname, fontsize=10)
    att_ax[2,0].set_ylabel('Yaw (deg)', weight='bold')
    att_ax[2,0].plot(t_flight, r2d(psi_flight), label='On Board', c='g', alpha=.5)
    att_ax[2,0].plot(t_store1, r2d(psi_nav), label=filter1.name, c='r', alpha=.8)
    att_ax[2,0].plot(t_store2, r2d(psi_nav_mag), label=filter2.name,c='b', alpha=.8)
    att_ax[2,0].set_xlabel('Time (sec)', weight='bold')
    att_ax[2,0].grid()
    att_ax[2,0].legend(loc=1)
    
    att_ax[2,1].plot(t_store1,nsig*np.rad2deg(np.sqrt(Patt1[:,2])),c='r')
    att_ax[2,1].plot(t_store1,-nsig*np.rad2deg(np.sqrt(Patt1[:,2])),c='r')
    att_ax[2,1].plot(t_store2,nsig*np.rad2deg(np.sqrt(Patt2[:,2])),c='b')
    att_ax[2,1].plot(t_store2,-nsig*np.rad2deg(np.sqrt(Patt2[:,2])),c='b')
    att_ax[2,1].set_xlabel('Time (sec)', weight='bold')
    att_ax[2,1].set_ylabel('3*stddev', weight='bold')

if FLAG_PLOT_VELOCITIES:
    fig, [ax1, ax2, ax3] = plt.subplots(3,1, sharex=True)

    # vn Plot
    vn_nav = data_dict1.vn
    vn_nav_mag = data_dict2.vn
    ax1.set_title(plotname, fontsize=10)
    ax1.set_ylabel('vn (mps)', weight='bold')
    ax1.plot(t_gps, vn_gps, '-*', label='GPS Sensor', c='g', lw=2, alpha=.5)
    ax1.plot(t_flight, vn_flight, label='On Board', c='k', lw=2, alpha=.5)
    ax1.plot(t_store1, vn_nav, label=filter1.name, c='r', lw=2, alpha=.8)
    ax1.plot(t_store2, vn_nav_mag, label=filter2.name,c='b', lw=2, alpha=.8)
    ax1.grid()
    ax1.legend(loc=0)

    # ve Plot
    ve_nav = data_dict1.ve
    ve_nav_mag = data_dict2.ve
    ax2.set_ylabel('ve (mps)', weight='bold')
    ax2.plot(t_gps, ve_gps, '-*', label='GPS Sensor', c='g', lw=2, alpha=.5)
    ax2.plot(t_flight, ve_flight, label='On Board', c='k', lw=2, alpha=.5)
    ax2.plot(t_store1, ve_nav, label=filter1.name, c='r', lw=2, alpha=.8)
    ax2.plot(t_store2, ve_nav_mag, label=filter2.name,c='b', lw=2, alpha=.8)
    ax2.grid()

    # vd Plot
    vd_nav = data_dict1.vd
    vd_nav_mag = data_dict2.vd
    ax3.set_ylabel('vd (mps)', weight='bold')
    ax3.plot(t_gps, vd_gps, '-*', label='GPS Sensor', c='g', lw=2, alpha=.5)
    ax3.plot(t_flight, vd_flight, label='On Board', c='k', lw=2, alpha=.5)
    ax3.plot(t_store1, vd_nav, label=filter1.name, c='r', lw=2, alpha=.8)
    ax3.plot(t_store2, vd_nav_mag, label=filter2.name, c='b',lw=2, alpha=.8)
    ax3.set_xlabel('TIME (SECONDS)', weight='bold')
    ax3.grid()

# Altitude Plot
if FLAG_PLOT_ALTITUDE:
    navalt = data_dict1.alt
    nav_magalt = data_dict2.alt
    plt.figure()
    plt.title('ALTITUDE')
    plt.plot(t_gps, alt_gps, '-*', label='GPS Sensor', c='g', lw=2, alpha=.5)
    plt.plot(t_flight, navalt_flight, label='On Board', c='k', lw=2, alpha=.5)
    plt.plot(t_store1, navalt, label=filter1.name, c='r', lw=2, alpha=.8)
    plt.plot(t_store2, nav_magalt, label=filter2.name, c='b', lw=2, alpha=.8)
    plt.ylabel('ALTITUDE (METERS)', weight='bold')
    plt.legend(loc=0)
    plt.grid()

# Wind Plot
def gen_func( coeffs, min, max, steps ):
    xvals = []
    yvals = []
    step = (max - min) / steps
    func = np.poly1d(coeffs)
    for x in np.arange(min, max+step, step):
        y = func(x)
        xvals.append(x)
        yvals.append(y)
    return xvals, yvals

if FLAG_PLOT_WIND:
    fig, ax1 = plt.subplots()
    wind_deg = data_dict2.wind_deg
    wind_kt = data_dict2.wind_kt
    pitot_scale = data_dict2.pitot_scale
    ax1.set_title('Wind')
    ax1.set_ylabel('Degrees', weight='bold')
    ax1.plot(t_store1, wind_deg, label='Direction (deg)', c='r', lw=2, alpha=.8)

    ax2 = ax1.twinx()
    ax2.plot(t_store1, wind_kt, label='Speed (kt)', c='b', lw=2, alpha=.8)
    ax2.plot(t_store1, pitot_scale, label='Pitot Scale', c='k', lw=2, alpha=.8)
    ax2.set_ylabel('Knots', weight='bold')
    ax1.legend(loc=4)
    ax2.legend(loc=1)
    ax1.grid()

if 'act' in data and FLAG_PLOT_SYNTH_ASI:
    fig, ax1 = plt.subplots()
    asi = data_dict2.asi
    synth_asi = data_dict2.synth_asi
    ax1.set_title('Synthetic Airspeed')
    ax1.set_ylabel('Kts', weight='bold')
    ax1.plot(t_store1, asi, label='Measured ASI', c='r', lw=2, alpha=.8)
    ax1.plot(t_store1, synth_asi, label='Synthetic ASI', c='b', lw=2, alpha=.8)
    ax1.legend(loc=0)
    ax1.grid()
    
    # plot roll vs. yaw rate
    roll_array = []
    r_array = []
    for i in range(len(data_dict1.phi)):
        vn = data_dict1.vn[i]
        ve = data_dict1.ve[i]
        vel = math.sqrt(vn*vn + ve*ve)
        phi = data_dict1.phi[i]
        r = data_dict1.r[i]
        if vel > 8 and abs(phi) <= 0.2:
            roll_array.append(phi)
            r_array.append(r)
    roll_array = np.array(roll_array)
    r_array = np.array(r_array)
    roll_cal, res, _, _, _ = np.polyfit( roll_array, r_array, 1, full=True )
    print roll_cal
    print 'zero turn @ bank =', (-roll_cal[1] / roll_cal[0]) * 180 / math.pi, 'deg'
    xvals, yvals = gen_func(roll_cal, roll_array.min(), roll_array.max(), 100)
    fig, ax1 = plt.subplots()
    ax1.set_title('Turn Calibration')
    ax1.set_xlabel('Bank angle (rad)', weight='bold')
    ax1.set_ylabel('Turn rate (rad/sec)', weight='bold')
    ax1.plot(roll_array, r_array, '*', label='bank vs. turn', c='r', lw=2, alpha=.8)
    ax1.plot(xvals, yvals, label='fit', c='b', lw=2, alpha=.8)

# Top View (Longitude vs. Latitude) Plot
if FLAG_PLOT_GROUNDTRACK:
    navlat = data_dict1.lat
    navlon = data_dict1.lon
    nav_maglat = data_dict2.lat
    nav_maglon = data_dict2.lon
    plt.figure()
    plt.title(plotname, fontsize=10)
    plt.ylabel('LATITUDE (DEGREES)', weight='bold')
    plt.xlabel('LONGITUDE (DEGREES)', weight='bold')
    plt.plot(lon_gps, lat_gps, '*', label='GPS Sensor', c='g', lw=2, alpha=.5)
    plt.plot(r2d(navlon_flight), r2d(navlat_flight), label='On Board', c='k', lw=2, alpha=.5)
    plt.plot(r2d(navlon), r2d(navlat), label=filter1.name, c='r', lw=2, alpha=.8)
    plt.plot(r2d(nav_maglon), r2d(nav_maglat), label=filter2.name, c='b', lw=2, alpha=.8)
    plt.grid()
    plt.legend(loc=0)
    
if FLAG_PLOT_BIASES:
    bias_fig, bias_ax = plt.subplots(3,2, sharex=True)

    # Gyro Biases
    bias_ax[0,0].set_ylabel('p Bias (deg)', weight='bold')
    bias_ax[0,0].plot(t_store1, r2d(data_dict1.p_bias), label=filter1.name, c='r')
    bias_ax[0,0].plot(t_store2, r2d(data_dict2.p_bias), label=filter2.name, c='b')
    bias_ax[0,0].set_xlabel('Time (secs)', weight='bold')
    bias_ax[0,0].grid()
    
    bias_ax[1,0].set_ylabel('q Bias (deg)', weight='bold')
    bias_ax[1,0].plot(t_store1, r2d(data_dict1.q_bias), label=filter1.name, c='r')
    bias_ax[1,0].plot(t_store2, r2d(data_dict2.q_bias), label=filter2.name, c='b')
    bias_ax[1,0].set_xlabel('Time (secs)', weight='bold')
    bias_ax[1,0].grid()
    
    bias_ax[2,0].set_ylabel('r Bias (deg)', weight='bold')
    bias_ax[2,0].plot(t_store1, r2d(data_dict1.r_bias), label=filter1.name, c='r')
    bias_ax[2,0].plot(t_store2, r2d(data_dict2.r_bias), label=filter2.name, c='b')
    bias_ax[2,0].set_xlabel('Time (secs)', weight='bold')
    bias_ax[2,0].grid()
    
    # Accel Biases
    bias_ax[0,1].set_ylabel('ax Bias (m/s^2)', weight='bold')
    bias_ax[0,1].plot(t_store1, data_dict1.ax_bias, label=filter1.name, c='r')
    bias_ax[0,1].plot(t_store2, data_dict2.ax_bias, label=filter2.name, c='b')
    bias_ax[0,1].set_xlabel('Time (secs)', weight='bold')
    bias_ax[0,1].grid()
    
    bias_ax[1,1].set_ylabel('ay Bias (m/s^2)', weight='bold')
    bias_ax[1,1].plot(t_store1, data_dict1.ay_bias, label=filter1.name, c='r')
    bias_ax[1,1].plot(t_store2, data_dict2.ay_bias, label=filter2.name, c='b')
    bias_ax[1,1].set_xlabel('Time (secs)', weight='bold')
    bias_ax[1,1].grid()
    
    bias_ax[2,1].set_ylabel('az Bias (m/s^2)', weight='bold')
    bias_ax[2,1].plot(t_store1, data_dict1.az_bias, label=filter1.name, c='r')
    bias_ax[2,1].plot(t_store2, data_dict2.az_bias, label=filter2.name, c='b')
    bias_ax[2,1].set_xlabel('Time (secs)', weight='bold')
    bias_ax[2,1].grid()
    bias_ax[2,1].legend(loc=1)

plt.show()
