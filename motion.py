import time
import tmc5160


driver_cfg = {
    'CHOPCONF': {
        'TOFF': 3,
        'HSTRT': 4,
        'HEND': 1,
        'TBL': 2,
    },
    'IHOLD_IRUN': {
        'IHOLD': 4,
        'IRUN': 31,
        'IHOLDDELAY': 6,
    },
    'GLOBAL_SCALER': {
        'GLOBAL_SCALER': 128,
    },
    'TPOWERDOWN': {
        'TPOWERDOWN': 10,
    },
    'GCONF': {
        'EN_PWM_MODE': 1,
    },
    'TPWMTHRS': {
        'TPWMTHRS': 500,
    },
}

ramp_cfg = {
    'A1': { 'A1': 24000 },
    'V1': { 'V1': 50000 },
    'AMAX': { 'AMAX': 20000 },
    'VMAX': { 'VMAX': 1000000 },
    'DMAX': { 'DMAX': 25000 },
    'D1': { 'D1': 35000 },
    'VSTOP': { 'VSTOP': 10 },
}

power_off = {
    'CHOPCONF': {
        'TOFF': 0
    }
}

if __name__ == '__main__':
    tmc = tmc5160.TMC5160(0, 0)
    tmc.set_register_values(driver_cfg)
    tmc.set_register_values(ramp_cfg)

    tmc.set_rampmode(0)

    tmc.enable()

    try:
        while True:
            print('move ->')
            tmc.set_target_pos(200 * 256 * 90 * 30 / 360)
            time.sleep(5)
            print('move <-')
            tmc.set_target_pos(0)
            time.sleep(5)
    except:
        pass

    tmc.set_register_values(power_off)
    tmc.disable()
    print('done')
