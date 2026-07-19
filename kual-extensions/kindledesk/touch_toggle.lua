local ffi = require("ffi")

ffi.cdef([[
typedef struct _XDisplay Display;
typedef unsigned long Atom;
typedef struct {
    int deviceid;
    char *name;
    int use;
    int attachment;
    int enabled;
    int num_classes;
    void **classes;
} XIDeviceInfo;
Display *XOpenDisplay(const char *display_name);
int XCloseDisplay(Display *display);
Atom XInternAtom(Display *display, const char *name, int only_if_exists);
int XSync(Display *display, int discard);
XIDeviceInfo *XIQueryDevice(Display *display, int deviceid, int *ndevices);
void XIFreeDeviceInfo(XIDeviceInfo *info);
void XIChangeProperty(Display *display, int deviceid, Atom property,
    Atom type, int format, int mode, const unsigned char *data, int count);
]])

local enabled = tonumber(arg[1])
assert(enabled == 0 or enabled == 1, "usage: touch_toggle.lua 0|1")

local x11 = ffi.load("X11")
local xi = ffi.load("Xi")
local display = assert(x11.XOpenDisplay(":0"), "cannot open X display")
local count = ffi.new("int[1]")
local devices = assert(xi.XIQueryDevice(display, 0, count), "cannot query XInput")
local device_id

for i = 0, count[0] - 1 do
    if ffi.string(devices[i].name) == "multitouch" then
        device_id = devices[i].deviceid
        break
    end
end

xi.XIFreeDeviceInfo(devices)
assert(device_id, "multitouch device not found")

local value = ffi.new("unsigned char[1]", enabled)
local property = x11.XInternAtom(display, "Device Enabled", 0)
xi.XIChangeProperty(display, device_id, property, 19, 8, 0, value, 1)
x11.XSync(display, 0)
x11.XCloseDisplay(display)
