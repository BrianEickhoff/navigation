These demo apps show how to setup and call the EKF.  The following
compile commands are example and will very likely need to be adjusted
for your own system.  (I am keeping things simple and avoiding
makefiles for now ...)


# 15 State Inertial Only EKF

## Compile with native compiler

g++ -O3 -I../nav_eigen ../nav_eigen/EKF_15state.cxx ../core/nav_functions.cxx ekf15_demo.cpp -o ekf15_demo -lm -lrt


## Compile with cross compiler

/opt/codesourcery/arm-2009q1/bin/arm-none-linux-gnueabi-g++ -I/home/sentera/AuraUAS -O3 EKF_15state.cxx ekfdemo.cpp ../core/nav_functions.cxx -o ekfdemo -lm -lrt


# 15 State EKF with magnetometer measurement correction

## Compile with native compiler

g++ -O3 -I../nav_eigen_mag ../nav_eigen_mag/EKF_15state_mag.cxx ../core/nav_functions.cxx ../core/coremag.c ekf15_mag_demo.cpp -o ekf15_mag_demo -lm -lrt


## Compile with cross compiler

/opt/codesourcery/arm-2009q1/bin/arm-none-linux-gnueabi-g++ -I/home/sentera/AuraUAS -O3 ../nav_eigen_mag/EKF_15state_mag.cxx ekf15_mag_demo.cpp ../core/nav_functions.cxx ../core/coremag.c -o ekf15_mag_demo -lm -lrt
