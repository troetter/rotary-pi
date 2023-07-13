from collections import OrderedDict
from enum import Enum
import spidev
import gpiozero
import struct


class Dir(Enum):
    R = 0
    W = 1
    RW = 2
    RWC = 3


class Register:
    def __init__(self, name, address, mode, fields):
        self.name = name
        self.address = address
        self.mode = mode
        self.fields = {f.name.upper(): f for f in fields}

    def set_fields(self, oldval, field_dict):
        newval = oldval
        for key, val in field_dict.items():
            field = self.fields[key.upper()]
            mask = (2**field.bits) - 1
            newval &= (0xFFFF_FFFF & ~(mask << field.lsb))
            newval |= (val & mask) << field.lsb
        return newval


class Field:
    def __init__(self, name, lsb, bits):
        self.name = name
        self.lsb = lsb
        self.bits = bits


class TMC5160:
    def __init__(self, spibus=0, spics=0, spibps=2000000, enapin='GPIO25'):
        self.spi = spidev.SpiDev()
        self.spi.open(spibus, spics)
        self.spi.max_speed_hz = spibps
        self.spi.mode = 3

        self.enable_pin = gpiozero.LED(enapin, active_high=False)
        self.enable_pin.off()

        self.regs = {r.name: r for r in TMC5160_REGS}
        self.vals = {r.name: 0 for r in TMC5160_REGS}
        self.regs_to_commit = OrderedDict()
        self.last_status = None

    def set_rampmode(self, mode):
        self.set_register_values({ 'RAMPMODE': { 'RAMPMODE': mode } })

    def set_target_pos(self, pos):
        self.set_register_values({ 'XTARGET': { 'XTARGET': int(pos) } })

    def set_register_values(self, reg_dict):
        for reg_name, param_dict in reg_dict.items():
            reg = self.regs[reg_name]
            oldval = self.vals[reg_name]
            newval = reg.set_fields(oldval, param_dict)
            self.regs_to_commit[reg_name] = newval
        self.commit()

    def commit(self):
        for name, val in self.regs_to_commit.items():
            reg = self.regs[name]

            mode = reg.mode
            writable = mode != Dir.R
            valid_val = val is not None

            wr_addr = reg.address | 0x80
            if writable and valid_val:
                uval = val & 0xFFFF_FFFF
                b = struct.pack('!BI', wr_addr, uval)
                print('w: ' + ' '.join(['0x{:02x}'.format(x) for x in b]))
                ret = self.spi.xfer(b)
                print('r: ' + ' '.join(['0x{:02x}'.format(x) for x in ret]))
                self.last_status = ret[0]
                self.vals[name] = val
            elif not writable:
                raise RuntimeError('attempting to write to read-only reg')
            elif not valid_val:
                raise ValueError('attempting to write bad value to reg')
        self.regs_to_commit.clear()

    def enable(self):
        self.enable_pin.on()

    def disable(self):
        self.enable_pin.off()

TMC5160_REGS = [
    # General configuration registers
    Register(name='GCONF', address=0x00, mode=Dir.RW, fields=[
        Field(name='RECALIBRATE', lsb=0, bits=1),
        Field(name='FASTSTANDSTILL', lsb=1, bits=1),
        Field(name='EN_PWM_MODE', lsb=2, bits=1),
        Field(name='MULTISTEP_FILT', lsb=3, bits=1),
        Field(name='SHAFT', lsb=4, bits=1),
        #Field(name='DIAG0_ERROR', lsb=5, bits=1),
        #Field(name='DIAG0_OTPW', lsb=6, bits=1),
        #Field(name='DIAG0_STALL', lsb=7, bits=1),
        Field(name='DIAG0_STEP', lsb=7, bits=1),
        #Field(name='DIAG1_STALL', lsb=8, bits=1),
        Field(name='DIAG1_DIR', lsb=8, bits=1),
        #Field(name='DIAG1_INDEX', lsb=9, bits=1),
        #Field(name='DIAG1_ONSTATE', lsb=10, bits=1),
        #Field(name='DIAG1_STEPS_SKIPPED', lsb=11, bits=1),
        Field(name='DIAG0_INT_PUSHPULL', lsb=12, bits=1),
        Field(name='DIAG1_POSCOMP_PUSHPULL', lsb=13, bits=1),
        Field(name='SMALL_HYSTERESIS', lsb=14, bits=1),
        Field(name='STOP_ENABLE', lsb=15, bits=1),
        Field(name='DIRECT_MODE', lsb=16, bits=1),
        Field(name='TEST_MODE', lsb=17, bits=11),
    ]),
    Register(name='GSTAT', address=0x01, mode=Dir.RWC, fields=[
        Field(name='RESET', lsb=0, bits=1),
        Field(name='DRV_ERR', lsb=1, bits=1),
        Field(name='UV_CP', lsb=2, bits=1),
    ]),
    #Register(name='IFCNT', address=0x02, mode=Dir.R, fields=[]),
    #Register(name='NODECONF', address=0x03, mode=Dir.W, fields=[]),
    Register(name='IOIN', address=0x04, mode=Dir.R, fields=[
        Field(name='REFL_STEP', lsb=0, bits=1),
        Field(name='REFR_DIR', lsb=1, bits=1),
        Field(name='ENCB_DCEN_CFG4', lsb=2, bits=1),
        Field(name='ENCA_DCIN_CFG5', lsb=3, bits=1),
        Field(name='DRV_ENN', lsb=4, bits=1),
        Field(name='ENC_N_DCO_CFG6', lsb=5, bits=1),
        Field(name='SD_MODE', lsb=6, bits=1),
        Field(name='SWCOMP_IN', lsb=7, bits=1),
        Field(name='VERSION', lsb=24, bits=8),
    ]),
    #Register(name='OUTPUT', address=0x04, mode=Dir.R, fields=[]),
    Register(name='X_COMPARE', address=0x05, mode=Dir.W, fields=[
        Field(name='X_COMPARE', lsb=0, bits=32),
    ]),
    #Register(name='OTP_PROG', address=0x06, mode=Dir.W, fields=[]),
    #Register(name='OTP_READ', address=0x07, mode=Dir.R, fields=[]),
    Register(name='FACTORY_CONF', address=0x08, mode=Dir.RW, fields=[
        Field(name='FCLKTRIM', lsb=0, bits=32),
    ]),
    Register(name='SHORT_CONF', address=0x09, mode=Dir.W, fields=[
        Field(name='S2VS_LEVEL', lsb=0, bits=4),
        Field(name='S2G_LEVEL', lsb=8, bits=4),
        Field(name='SHORTFILTER', lsb=16, bits=2),
        Field(name='shortdelay', lsb=18, bits=1),
    ]),
    Register(name='DRV_CONF', address=0x0A, mode=Dir.W, fields=[
        Field(name='BBMTIME', lsb=0, bits=5),
        Field(name='BBMCLKS', lsb=8, bits=4),
        Field(name='OTSELECT', lsb=16, bits=2),
        Field(name='DRVSTRENGTH', lsb=18, bits=2),
        Field(name='FILT_ISENSE', lsb=20, bits=2),
    ]),
    Register(name='GLOBAL_SCALER', address=0x0B, mode=Dir.W, fields=[
        Field(name='GLOBAL_SCALER', lsb=0, bits=8),
    ]),
    Register(name='OFFSET_READ', address=0x0C, mode=Dir.R, fields=[
        Field(name='PHASE_B', lsb=0, bits=8),
        Field(name='PHASE_A', lsb=8, bits=8),
    ]),

    # Velocity dependent driver feature control register set
    Register(name='IHOLD_IRUN', address=0x10, mode=Dir.W, fields=[
        Field(name='IHOLD', lsb=0, bits=5),
        Field(name='IRUN', lsb=8, bits=5),
        Field(name='IHOLDDELAY', lsb=16, bits=4),
    ]),
    Register(name='TPOWERDOWN', address=0x11, mode=Dir.W, fields=[
        Field(name='TPOWERDOWN', lsb=0, bits=8),
    ]),
    Register(name='TSTEP', address=0x12, mode=Dir.RW, fields=[
        Field(name='TSTEP', lsb=0, bits=20),
    ]),
    Register(name='TPWMTHRS', address=0x13, mode=Dir.W, fields=[
        Field(name='TPWMTHRS', lsb=0, bits=20),
    ]),
    Register(name='TCOOLTHRS', address=0x14, mode=Dir.W, fields=[
        Field(name='TCOOLTHRS', lsb=0, bits=20),
    ]),
    Register(name='THIGH', address=0x15, mode=Dir.W, fields=[
        Field(name='THIGH', lsb=0, bits=20),
    ]),

    # Ramp generator registers
    Register(name='RAMPMODE', address=0x20, mode=Dir.RW, fields=[
        Field(name='RAMPMODE', lsb=0, bits=2),
    ]),
    Register(name='XACTUAL', address=0x21, mode=Dir.RW, fields=[
        Field(name='XACTUAL', lsb=0, bits=32),
    ]),
    Register(name='VACTUAL', address=0x22, mode=Dir.R, fields=[
        Field(name='VACTUAL', lsb=0, bits=24),
    ]),
    Register(name='VSTART', address=0x23, mode=Dir.W, fields=[
        Field(name='VSTART', lsb=0, bits=18),
    ]),
    Register(name='A1', address=0x24, mode=Dir.W, fields=[
        Field(name='A1', lsb=0, bits=16),
    ]),
    Register(name='V1', address=0x25, mode=Dir.W, fields=[
        Field(name='V1', lsb=0, bits=20),
    ]),
    Register(name='AMAX', address=0x26, mode=Dir.W, fields=[
        Field(name='AMAX', lsb=0, bits=16),
    ]),
    Register(name='VMAX', address=0x27, mode=Dir.W, fields=[
        Field(name='VMAX', lsb=0, bits=23),
    ]),
    Register(name='DMAX', address=0x28, mode=Dir.W, fields=[
        Field(name='DMAX', lsb=0, bits=16),
    ]),
    Register(name='D1', address=0x2A, mode=Dir.W, fields=[
        Field(name='D1', lsb=0, bits=16),
    ]),
    Register(name='VSTOP', address=0x2B, mode=Dir.W, fields=[
        Field(name='VSTOP', lsb=0, bits=18),
    ]),
    Register(name='TZEROWAIT', address=0x2C, mode=Dir.W, fields=[
        Field(name='TZEROWAIT', lsb=0, bits=16),
    ]),
    Register(name='XTARGET', address=0x2D, mode=Dir.RW, fields=[
        Field(name='XTARGET', lsb=0, bits=32),
    ]),

    # Ramp generator driver feature control register set
    Register(name='VDCMIN', address=0x33, mode=Dir.W, fields=[
        Field(name='VDCMIN', lsb=0, bits=23),
    ]),
    Register(name='SW_MODE', address=0x34, mode=Dir.RW, fields=[
        Field(name='STOP_L_ENABLE', lsb=0, bits=1),
        Field(name='STOP_R_ENABLE', lsb=1, bits=1),
        Field(name='POL_STOP_L', lsb=2, bits=1),
        Field(name='POL_STOP_R', lsb=3, bits=1),
        Field(name='SWAP_LR', lsb=4, bits=1),
        Field(name='LATCH_L_ACTIVE', lsb=5, bits=1),
        Field(name='LATCH_L_INACTIVE', lsb=6, bits=1),
        Field(name='LATCH_R_ACTIVE', lsb=7, bits=1),
        Field(name='LATCH_R_INACTIVE', lsb=8, bits=1),
        Field(name='EN_LATCH_ENCODER', lsb=9, bits=1),
        Field(name='SG_STOP', lsb=10, bits=1),
        Field(name='EN_SOFTSTOP', lsb=11, bits=1),
    ]),
    Register(name='RAMP_STAT', address=0x35, mode=Dir.RWC, fields=[
        Field(name='STATUS_STOP_L', lsb=0, bits=1),
        Field(name='STATUS_STOP_R', lsb=1, bits=1),
        Field(name='STATUS_LATCH_L', lsb=2, bits=1),
        Field(name='STATUS_LATCH_R', lsb=3, bits=1),
        Field(name='EVENT_STOP_L', lsb=4, bits=1),
        Field(name='EVENT_STOP_R', lsb=5, bits=1),
        Field(name='EVENT_STOP_SG', lsb=6, bits=1),
        Field(name='EVENT_POS_REACHED', lsb=7, bits=1),
        Field(name='VELOCITY_REACHED', lsb=8, bits=1),
        Field(name='POSITION_REACHED', lsb=9, bits=1),
        Field(name='VZERO', lsb=10, bits=1),
        Field(name='T_ZEROWAIT_ACTIVE', lsb=11, bits=1),
        Field(name='SECOND_MOVE', lsb=12, bits=1),
        Field(name='STATUS_SG', lsb=13, bits=1),
    ]),
    Register(name='XLATCH', address=0x36, mode=Dir.R, fields=[
        Field(name='XLATCH', lsb=0, bits=32),
    ]),

    # Encoder registers
    Register(name='ENCMODE', address=0x38, mode=Dir.RW, fields=[
        Field(name='ENC_SEL_DECIMAL', lsb=0, bits=1),
        Field(name='LATCH_X_ACT', lsb=1, bits=1),
        Field(name='CLR_ENC_X', lsb=2, bits=1),
        Field(name='NEG_EDGE', lsb=3, bits=1),
        Field(name='POS_EDGE', lsb=4, bits=1),
        Field(name='CLR_ONCE', lsb=5, bits=1),
        Field(name='CLR_CONT', lsb=6, bits=1),
        Field(name='IGNORE_AB', lsb=7, bits=1),
        Field(name='POL_N', lsb=8, bits=1),
        Field(name='POL_B', lsb=9, bits=1),
        Field(name='POL_A', lsb=10, bits=1),
    ]),
    Register(name='X_ENC', address=0x39, mode=Dir.RW, fields=[
        Field(name='X_ENC', lsb=0, bits=32),
    ]),
    Register(name='ENC_CONST', address=0x3A, mode=Dir.W, fields=[
        Field(name='ENC_CONST', lsb=0, bits=32),
    ]),
    Register(name='ENC_STATUS', address=0x3B, mode=Dir.RWC, fields=[
        Field(name='n_event', lsb=0, bits=1),
        Field(name='deviation_warn', lsb=1, bits=1),
    ]),
    Register(name='ENC_LATCH', address=0x3C, mode=Dir.R, fields=[
        Field(name='ENC_LATCH', lsb=0, bits=32),
    ]),
    Register(name='ENC_DEVIATION', address=0x3D, mode=Dir.W, fields=[
        Field(name='ENC_DEVIATION', lsb=0, bits=20),
    ]),

    # Motor driver registers
    Register(name='MSLUT0', address=0x60, mode=Dir.RW, fields=[
        Field(name='LUT', lsb=0, bits=32),
    ]),
    Register(name='MSLUT1', address=0x61, mode=Dir.W, fields=[
        Field(name='LUT', lsb=0, bits=32),
    ]),
    Register(name='MSLUT2', address=0x62, mode=Dir.W, fields=[
        Field(name='LUT', lsb=0, bits=32),
    ]),
    Register(name='MSLUT3', address=0x63, mode=Dir.W, fields=[
        Field(name='LUT', lsb=0, bits=32),
    ]),
    Register(name='MSLUT4', address=0x64, mode=Dir.W, fields=[
        Field(name='LUT', lsb=0, bits=32),
    ]),
    Register(name='MSLUT5', address=0x65, mode=Dir.W, fields=[
        Field(name='LUT', lsb=0, bits=32),
    ]),
    Register(name='MSLUT6', address=0x66, mode=Dir.W, fields=[
        Field(name='LUT', lsb=0, bits=32),
    ]),
    Register(name='MSLUT7', address=0x67, mode=Dir.W, fields=[
        Field(name='LUT', lsb=0, bits=32),
    ]),
    Register(name='MSLUTSEL', address=0x68, mode=Dir.W, fields=[
        Field(name='W0', lsb=0, bits=2),
        Field(name='W1', lsb=2, bits=2),
        Field(name='W2', lsb=4, bits=2),
        Field(name='W3', lsb=6, bits=2),
        Field(name='X1', lsb=8, bits=8),
        Field(name='X2', lsb=16, bits=8),
        Field(name='X3', lsb=24, bits=8),
    ]),
    Register(name='MSLUTSTART', address=0x69, mode=Dir.W, fields=[
        Field(name='START_SIN', lsb=0, bits=8),
        Field(name='START_SIN90', lsb=16, bits=8),
    ]),
    Register(name='MSCNT', address=0x6A, mode=Dir.R, fields=[
        Field(name='MSCNT', lsb=0, bits=10),
    ]),
    Register(name='MSCURACT', address=0x6B, mode=Dir.R, fields=[
        Field(name='CUR_B', lsb=0, bits=8),
        Field(name='CUR_A', lsb=16, bits=8),
    ]),    
    Register(name='CHOPCONF', address=0x6C, mode=Dir.RW, fields=[
        Field(name='TOFF', lsb=0, bits=4),
        Field(name='HSTRT', lsb=4, bits=3),
        #Field(name='TFD20', lsb=4, bits=3),
        Field(name='HEND', lsb=7, bits=4),
        #Field(name='OFFSET', lsb=7, bits=4),
        #Field(name='TFD3', lsb=11, bits=1),
        Field(name='DISFDCC', lsb=12, bits=1),
        Field(name='CHM', lsb=14, bits=1),
        Field(name='TBL', lsb=15, bits=2),
        Field(name='VHIGHFS', lsb=18, bits=1),
        Field(name='VHIGHCHM', lsb=19, bits=1),
        Field(name='TPFD', lsb=20, bits=4),
        Field(name='MRES', lsb=24, bits=4),
        Field(name='INTPOL', lsb=28, bits=1),
        Field(name='DEDGE', lsb=29, bits=1),
        Field(name='DISS2G', lsb=30, bits=1),
        Field(name='DISS2VS', lsb=31, bits=1),
    ]),    
    Register(name='COOLCONF', address=0x6D, mode=Dir.W, fields=[
        Field(name='SEMIN', lsb=0, bits=4),
        Field(name='SEUP', lsb=5, bits=2),
        Field(name='SEMAX', lsb=8, bits=4),
        Field(name='SEDN', lsb=13, bits=2),
        Field(name='SEIMIN', lsb=15, bits=1),
        Field(name='SGT', lsb=16, bits=7),
        Field(name='SFILT', lsb=24, bits=1),
    ]),
    Register(name='DCCTRL', address=0x6E, mode=Dir.W, fields=[
        Field(name='DCCTRL', lsb=0, bits=24),
    ]),
    Register(name='DRV_STATUS', address=0x6F, mode=Dir.R, fields=[
        Field(name='SG_RESULT', lsb=0, bits=10),
        Field(name='S2VSA', lsb=12, bits=1),
        Field(name='S2VSB ', lsb=13, bits=1),
        Field(name='STEALTH', lsb=14, bits=1),
        Field(name='FSACTIVE', lsb=15, bits=1),
        Field(name='CS_ACTUAL', lsb=16, bits=5),
        Field(name='STALLGUARD', lsb=24, bits=1),
        Field(name='OT', lsb=25, bits=1),
        Field(name='OTPW', lsb=26, bits=1),
        Field(name='S2GA', lsb=27, bits=1),
        Field(name='S2GB', lsb=28, bits=1),
        Field(name='OLA', lsb=29, bits=1),
        Field(name='OLB', lsb=30, bits=1),
        Field(name='STST', lsb=31, bits=1),
    ]),
    Register(name='PWMCONF', address=0x70, mode=Dir.W, fields=[
        Field(name='PWM_OFS', lsb=0, bits=8),
        Field(name='PWM_GRAD', lsb=8, bits=8),
        Field(name='PWM_FREQ', lsb=16, bits=2),
        Field(name='PWM_AUTOSCALE', lsb=18, bits=1),
        Field(name='PWM_AUTOGRAD', lsb=19, bits=1),
        Field(name='FREEWHEEL', lsb=20, bits=2),
        Field(name='PWM_REG', lsb=24, bits=4),
        Field(name='PWM_LIM', lsb=28, bits=4),
    ]),
    Register(name='PWM_SCALE', address=0x71, mode=Dir.R, fields=[
        Field(name='PWM_SCALE_SUM', lsb=0, bits=8),
        Field(name='PWM_SCALE_AUTO', lsb=16, bits=8),
    ]),
    Register(name='PWM_AUTO', address=0x72, mode=Dir.R, fields=[
        Field(name='PWM_OFS_AUTO', lsb=0, bits=8),
        Field(name='PWM_GRAD_AUTO', lsb=16, bits=8),
    ]),
    Register(name='LOST_STEPS', address=0x73, mode=Dir.R, fields=[
        Field(name='LOST_STEPS', lsb=0, bits=20),
    ]),
]

