

# Sections 
## Frontend 

Defines the frontend equipment stuff. All of the midas code

## Pages

html code for the pages we see on the midas page 

## Utilities 

Utility code used by the frontend code. 
These scripts are all super independent and generally are just used to communicate with the equipment 

## Equipment Notes

### Buffer Names

### Equipment IDs

- LEDMidas: 16
- PicoScope: 10 
- PumpConnection: 11 
- ELLxStage: 12
- HVController: 13 


# ODB Parameters

## LED Board
### Settings
    Enabled 0/1
    ADC number
    LED number
    Rate 0/1 (slow/fast)
    Trigger 0/1 Internal/External 

### Variables
    Enabled 0/1
    ADC number
    LED number
    Rate 0/1 (slow/fast)
    Trigger 0/1 Internal/External 
    Ready Bool (matching setting/variable)

## ELLx Stage 
### Settings
    Destination float 

### Variables
    Destination float 
    Ready Bool

## WMSBenchControl 
### Settings
    Ball Valves [6x 0/1]
    Solenoid Valves [3x 0/1]
    Pumps [3x 0/1]

### Variables
    Destination float 
    Ready Bool

## HV 
### Settings
    On [2x 0/1]
    Voltage [2x float]
    Trip Thresh [2x float]

### Variables
    Status [16x bool]
    Ready Bool

# Automation

## Frontends 

### fePico - data taking and DAQ automation

Watches
    - leds enabled
    - stage location
    - led adc

Script will adjust *settings* for the stage and the board 


Stages/LED frontends will see that those have changed
Teh