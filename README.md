# EBike Battery Plug Manager

## **Important - Read this first**
*This script requires hardware to work:* 
- One or more TP-Link Smart Plug socket or Smart Strip with energy metering capability (emeter)
    - The KP115 Smart Plug and the HS300 Smart Strip are compatible.
    - The KP303 is NOT compatible as it does not have the energy metering capability.
- The associated Kasa phone app to add the TP-Link devices to the network
- A WiFi network common to both the plug monitor devices and the computer hosting the script.
- A linux or MacOS host capable of running **Python 3.10** to host the script.  (Raspberry Pi's work fine)


**If purchasing the hardware is not acceptable, GO NO FURTHER!**

## Summary
### Possible Benefits

- The script monitors charging of batteries and turns off the plug that the charger is connected to when a suitable level of charge has been attained.
- This should be equivalent to unplugging the charger from the  battery and avoiding any safety issues associated with leaving chargers and batteries plugged into power after they are charged.
- Charging can be scheduled for off peak periods since when not charging, the plug is turned off.
- Three modes are supported, **nominal**, **full charge** and **storage**:
    - The **nominal** charge mode turns off the charger slightly before full charge is attained to hopefully reduce wear on the battery and extend battery life.
    - The **full charge** mode allows the battery to charge fully to balance the cells, something that periodically needs to be done.
    - The **storage** charge mode allows keeping the battery at a lower level of charge when the battery will not be used for an extended period of time, preventing unnecessary wear on the battery.

## How it tries to do it

 The script looks at the power draw of the TP-Link plug that the charger is plugged into and based on the measured power draw, will shut off the plug once the chargers power draw drops below either nominal or full charge cutoff limits, depending on the mode the script is used in.

### How Lithium Ion chargers work
See references 4, 5 below and the ExperimentalData.md file. 
- Lithium Ion chargers work in two stages:
    - Stage 1 is the Constant Current charge and uses a constant current until an expected voltage is observed.
    - Stage 2 is the Saturation charge which occurs when the constant voltage peak is observed.  During this stage the current will steadily fall until it reaches a minimum, ~10% of the rated current.

Since we cannot see inside the charger or the battery, we observe how much current is being pulled through the SmartPlug and depend on their being a correlation between that observed current and the current drop in Stage 2 of the charger.

Three cutoff thresholds are supported.  
- A nominal cutoff threshold cuts off power to the plug/charger slightly before the battery is fully charged to hopefully extend battery life.
- A full charge cutoff threshold allows the charger to fully charge the battery enabling balancing of the individual cells.
- A storage cutoff threshold behaves identically to the nominal cutoff but allows a lower cutoff to hold the battery at a lower charge percentage which is desirable in Li Ion batteries that will be stored unused for an extended period of time.
## Disclaimer
- The owner of the script is not a electrical power engineer.
- We only observe the power draw that the chargers are pulling at the smart plug.
- We assume that power draw is related to the amount of amperage the charger is adding to the battery.
- We assume that as the battery approaches full charge, the charger draws correspondingly less power establishing a known power drawdown curve that is correlated with the actual charger as it charges the battery, allowing the script to manage the charger(s) by controlling the TP-Link smart plug(s) on/off state. 
- This was observed to be the case with Rad Power and Lectric EBike batteries and chargers.
- This is a correlational approach and results will be approximate since we do not see the actual battery charge voltage in real time.
## Compatibility
- The script is developed using Rad Power EBike battery packs and chargers.
- Lectric xpedition packs and chargers are also profiled.
- Currently only 48V systems have been profiled.
- The script provides command line control to allow moderate customization of parameters.
    - You can always directly modify the script as well.
- A configuration file is also allowed which provides more extensive customization.  See sample_ebike_battery_manager.config
## Setup
### TP Link Plugs
- Any TP-Link plug/strip that supports plug level power metering should work.  However only the KP115 and HS300 were used in development so modifications to the script may be needed for other models that support energy metering.
### Python3
- Python 3.10.6 or more recent
### Python Kasa Library
- This is mandatory, the script imports this third party library as it furnishes the API to access the TP-Link SmartDevices.
- https://github.com/python-kasa/python-kasa

#### Naming the plugs
- The script looks for all TP-Link devices prefixed with "battery_" and treats those as plugs with battery chargers attached.
- Custom battery names can be assigned via a config file.
- After you have installed the python-kasa library should create a command line interface "kasa"
- Use the kasa command without arguments to get all devices and atheir ip addresses
    - $ kasa
- Assigning a name to a plug using the kasa command line alias command
    - $ kasa --host <ip> alias <new_name>
    - For example: ```$ kasa --host 192.168.1.555 alias battery_1``` assigns a plug the name of battery_1
### Raspberry Pi
- A pi is not mandatory but it is what I use to drive the script.
- https://medium.com/geekculture/use-raspberry-pi-and-tp-link-kasa-to-automate-your-devices-9f936a6243c1## Features
## Nominal, Full Charge and Storage
- Nominal charge mode is intended for daily use to charge batteries to a point slightly less than full charge to maximize battery life.
- Full charge mode is intended for periodic use to allow battery cell balancing.
- Storage mode is intended for use if the battery will not be used for an extended period of time.
## Reports go to a logfile in the same directory the script is run in
- Whenever the script is run, it will post information to a logfile as well as to the console and optionally to email.
    - The logfile name idefault is **ebike_battery_manager.log** and can be overridden by the -l, --log_file_name command line argument
    - The logfile is overwritten with each run to prevent creating a large logfile.
### Gmail report support
- The script will support using gmail's app support to generate an email report which contains the log info.
    - This particular approach expects a Google app password: https://support.google.com/mail/answer/185833?hl=en-GB
- smtp.sendmail is the underlying mechanism so different smtp servers can be used.  Modify as needed.
## Usage
- The script handles a daily charge scenario and depends on outside support for continuous daily runs.
- Users should keep same battery in each plug/charger if possible and at a minimum need to match battery and chargers from the same manufacturer.
### Command line arguments

```
$ ./ebike_battery_manager.py -h
usage: ebike_battery_manager.py [OPTIONS]

Manage EBike battery charging with TP-Link smart socket(s)

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -e , --email          email address to send reports to
  -a , --app_key        Google app key needed to allow sending mail reports
  -f, --force_full_charge
                        forces all batteries into full charge mode
  -t, --test_mode       test mode only, verify early stage, no real plug activity
  -l , --log_file_name 
                        overrides logfile name, default is battery_plug_controller.log
  -c , --config_file    optional config file, useful to support multiple manufacturers, overrides default values
  --nominal_charge_cutoff 
                        set the default cutoff power override for nominal charge complete
  --full_charge_repeat_limit 
                        number of cycles to repeat after attaining full charge
  --max_cycles_in_fine_mode 
                        max limit of cycles to prevent forever charge
  --full_charge_cutoff 
                        set the full power override for full charge complete
  --storage_charge_cutoff 
                        set the storage power override for storage charge complete
  --storage_charge_cycle_limit 
                        max cycles to charge in storage charge mode, default is 1
  --max_hours_to_run    maximum time to run the script in hours
```

### Configuration file
- A configuration file can be used to furnish the cutoff thresholds and also to support multiple manufacturers and custom plug/battery names.
    - This file can reside in the directory the script is run from or be be specified with a full path.
- The sample config file: sample_ebike_battery_manager.config can be used as a template. -- See ./config directory
- For multiple manufacturer profiles the plugs must be dedicated to fixed chargers and only matching batteries should be charged by those chargers.
#### Configuration Sections
- The configuration files will have a section named for each manufacturer with the appropriate threshold power cutoffs.
    - Mandatory fields
        - nominal_charged_battery_power_threshold
        - fully_charged_battery_power_threshold
        - coarse_probe_threshold_margin
    - Optional field(s)
        - storage_charged_battery_power_threshold
            - if omitted, then the nominal_charged_battery_power_threshold will be used in its place
- The [Plugs] section is used to match plug_names with manufacturer section names.
- The [Storage] section is optional and when present lists plug_names that are to be in Storage mode
    - The Storage section has the highest precedence for plug charging modes.  If a plug_name is present in both this Storage section and the FullCharge section below, the plug_name will charge in Storage mode.
- The [FullCharge] section is optional and when present lists plug_names that are to be fully charged all the time, overriding any time the script is running in nominal mode.
    - This section has a lower precedence that Storage.

### Profiling a Battery and Charger pair
- Run a full charge sequence and examine the log
- Ideally you will see distinct changes in power consumption levels
    - These large changes are a clue as to where the nominal/full charge occurs.
    - If you have a multimeter, this is a good place to begin setting various nominal cutoff points and then measuring the battery voltage after the cutoff occurs and the plug shuts down.
- If you determine values for a new manufacturer, please post in ExperimentalData.md for others to use.

### Linux CRON Job Example for scheduling continuous daily running
#### Possible scenarios

##### Example Use Cases
- Use CRON to schedule daily nominal charge cycles and a full charge cycle at 12AM Saturday in anticipation of longer rides on weekends.
```
0 0  * * SUN /home/kelvin/sandbox/ebike_battery_manager.py -c /home/kelvin/sample_ebike_battery_manager.config -e <your_gmail> -a <your_gmail_app_id>
0 0  * * 1-5 /home/kelvin/sandbox/ebike_battery_manager.py -c /home/kelvin/sample_ebike_battery_manager.config -e <your_gmail> -a <your_gmail_app_id>
0 0  * * SAT /home/kelvin/sandbox/ebike_battery_manager.py -f -c /home/kelvin/sample_ebike_battery_manager.config -e <your_gmail> -a <your_gmail_app_id>
```

### Host Computer

#### Linux, including Raspberry PI
- These work as the python-kasa library that supports the script appears to be developed in linux.
- The script is set to look for bash as the command shell.  If the command shell is different, run explicitly under python by prefixing python3 to the script run line.
#### Windows
- The short answer is to run the script from a WSL linux shell.
- I have not tried this.  Also, it appears WSL supports cron but does not start the service by default.  
    - https://www.howtogeek.com/746532/how-to-launch-cron-automatically-in-wsl-on-windows-10-and-11/
- Whether or not cron runs while windows sleeps is also a matter for the interested reader to determine.
#### Mac OS
- It appears that MacOS will also work.  The default kasa install does not place the kasa script on the path so you will have to locate it.  In my MacOS install, it is at ~/Library/Python/3.9/bin/kasa and needs to be explicitly run with python.  I successfully ran it in the bin directory.
```
% cd ~/Library/Python/3.9/bin/
% python3 kasa
```
- ebike_battery_manager.py is a command line app so you have to run it in a terminal.
- Also the ebike_battery_manager.py script is set to look for bash so on the mac, which uses zsh instead, you have to explcitly run it under python by prefixing python3 to the script run lines.
- Mac OS supports cron but cron jobs will not wake a sleeping Mac OS so there will be some hoops to jump through if you want the job to run late at night, which is typical.

## References
1. https://ebikesforum.com/threads/48-volt-13s-battery-voltage-chart-li-ion-batteries.699/#:~:text=80%25%20DOD%20is%20around%2043v%20depending%20on%20cell%20chemistry
2. https://www.cnet.com/roadshow/news/how-to-keep-your-e-bike-battery-in-top-shape/
3. https://www.electrifybike.com/blogs/news/charging-and-caring-for-your-lithium-ion-ebike-battery
4. https://www.batteriesplus.com/blog/power/lithium-battery-chargers
5. https://www.electronics-notes.com/articles/electronic_components/battery-technology/li-ion-lithium-ion-charging.php

## Unit Tests
- Unit testing is furnished in ebike_battery_manager_test.py
- Run pytest in the same directory as the repository.
- Testing does not cover async functions!
```
$ cd scripts
$ python3 -m pytest ../test/
===================================================================================================== test session starts ======================================================================================================
platform linux -- Python 3.10.6, pytest-7.3.1, pluggy-1.0.0
rootdir: /home/kelvin/sandbox/projects/ebike-battery-manager
plugins: anyio-3.6.2
collected 14 items                                                                                                                                                                                                             

../test/ebike_battery_manager_test.py ..............                                                                                                                                                                     [100%]

====================================================================================================== 14 passed in 0.09s ======================================================================================================
```
## TBD
- Investigate integration of script into Home Assistant ecosystem
